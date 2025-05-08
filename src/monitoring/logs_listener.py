"""
WebSocket monitoring for pump.fun tokens using logsSubscribe.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable

import websockets
from solders.pubkey import Pubkey
from websockets.exceptions import ConnectionClosed

from core.pubkeys import PumpAddresses
from monitoring.logs_event_processor import LogsEventProcessor
from trading.base import TokenInfo
from utils.logger import get_logger

logger = get_logger(__name__)

class LogsListener:
    """WebSocket listener for pump.fun token creation events using logsSubscribe."""
    
    def __init__(self, wss_endpoint: str, pump_program: Pubkey):
        """Initialize token listener.

        Args:
            wss_endpoint: WebSocket endpoint URL
            pump_program: Pump.fun program address
        """
        self.wss_endpoint = wss_endpoint
        self.pump_program = pump_program
        self.event_processor = LogsEventProcessor(pump_program)
        self.ping_interval = 10  # Seconds
        self._is_running = True
        self._websocket = None
        self._ping_task = None
        
    async def stop(self):
        """Stop the listener and close any active WebSocket connections."""
        logger.info("Stopping LogsListener...")
        self._is_running = False
        if self._ping_task is not None:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                logger.debug("Ping task cancelled successfully")
            self._ping_task = None
        if self._websocket is not None:
            try:
                await self._websocket.close()
                logger.info("WebSocket closed during stop")
            except Exception as e:
                logger.warning(f"Error closing WebSocket during stop: {str(e)}")
            self._websocket = None
        
    async def listen_for_tokens(
        self,
        token_callback: Callable[[TokenInfo], Awaitable[None]],
        match_string: str | None = None,
        creator_address: str | None = None,
    ) -> None:
        """Listen for new token creations using logsSubscribe.

        Args:
            token_callback: Callback function for new tokens
            match_string: Optional string to match in token name/symbol
            creator_address: Optional creator address to filter by
        """
        while self._is_running:
            try:
                async with websockets.connect(self.wss_endpoint) as websocket:
                    self._websocket = websocket
                    await self._subscribe_to_logs(websocket)
                    self._ping_task = asyncio.create_task(self._ping_loop(websocket))

                    try:
                        while self._is_running:
                            token_info = await self._wait_for_token_creation(websocket)
                            if not token_info:
                                continue

                            logger.info(
                                f"New token detected: {token_info.name} ({token_info.symbol})"
                            )

                            if match_string and not (
                                match_string.lower() in token_info.name.lower()
                                or match_string.lower() in token_info.symbol.lower()
                            ):
                                logger.info(
                                    f"Token does not match filter '{match_string}'. Skipping..."
                                )
                                continue

                            if (
                                creator_address
                                and str(token_info.user) != creator_address
                            ):
                                logger.info(
                                    f"Token not created by {creator_address}. Skipping..."
                                )
                                continue

                            await token_callback(token_info)

                    except ConnectionClosed:
                        logger.warning("WebSocket connection closed. Reconnecting...")
                        if self._ping_task is not None:
                            self._ping_task.cancel()
                            self._ping_task = None
                    except asyncio.CancelledError:
                        logger.info("Logs listener cancelled")
                        if self._ping_task is not None:
                            self._ping_task.cancel()
                            self._ping_task = None
                        self._is_running = False
                        await websocket.close()
                        self._websocket = None
                        return
                    except Exception as e:
                        logger.error(f"Error in logs listener: {str(e)}")
                        if self._ping_task is not None:
                            self._ping_task.cancel()
                            self._ping_task = None
                        await websocket.close()
                        self._websocket = None

            except asyncio.CancelledError:
                logger.info("Logs listener cancelled during connection attempt")
                self._is_running = False
                return
            except Exception as e:
                logger.error(f"WebSocket connection error: {str(e)}")
                logger.info("Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

    async def _subscribe_to_logs(self, websocket) -> None:
        """Subscribe to logs mentioning the pump.fun program.

        Args:
            websocket: Active WebSocket connection
        """
        subscription_message = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "logsSubscribe",
                "params": [
                    {"mentions": [str(self.pump_program)]},
                    {"commitment": "processed"},
                ],
            }
        )

        await websocket.send(subscription_message)
        logger.info(f"Subscribed to logs mentioning program: {self.pump_program}")

        # Wait for subscription confirmation
        try:
            response = await websocket.recv()
            response_data = json.loads(response)
            if "result" in response_data:
                logger.info(f"Subscription confirmed with ID: {response_data['result']}")
            else:
                logger.warning(f"Unexpected subscription response: {response}")
        except ConnectionClosed:
            logger.warning("Connection closed during subscription")
            raise

    async def _ping_loop(self, websocket) -> None:
        """Keep connection alive with pings.

        Args:
            websocket: Active WebSocket connection
        """
        try:
            elapsed = 0
            while self._is_running:
                if not self._is_running:
                    logger.debug("Ping loop stopped due to _is_running=False")
                    break
                await asyncio.sleep(0.1)  # Fast sleep for immediate cancellation
                elapsed += 0.1
                if elapsed >= self.ping_interval and self._is_running:
                    try:
                        pong_waiter = await websocket.ping()
                        await asyncio.wait_for(pong_waiter, timeout=1)  # Reduced timeout
                        logger.debug("Ping successful")
                        elapsed = 0  # Reset after successful ping
                    except asyncio.TimeoutError:
                        logger.warning("Ping timeout - server not responding")
                        await websocket.close()
                        self._websocket = None
                        return
                    except ConnectionClosed:
                        logger.warning("Connection closed during ping")
                        self._websocket = None
                        return
        except asyncio.CancelledError:
            logger.info("Ping loop cancelled")
            if self._websocket is not None:
                try:
                    await websocket.close()
                    logger.debug("WebSocket closed in ping loop cancellation")
                except Exception as e:
                    logger.warning(f"Error closing WebSocket in ping loop: {str(e)}")
                self._websocket = None
            raise
        except Exception as e:
            logger.error(f"Ping error: {str(e)}")
            if self._websocket is not None:
                try:
                    await websocket.close()
                    logger.debug("WebSocket closed due to ping error")
                except Exception as e:
                    logger.warning(f"Error closing WebSocket in ping loop: {str(e)}")
                self._websocket = None
        finally:
            logger.debug("Ping loop exiting")

    async def _wait_for_token_creation(self, websocket) -> TokenInfo | None:
        """Wait for a token creation event.

        Args:
            websocket: Active WebSocket connection
            
        Returns:
            TokenInfo if a valid token creation is detected, None otherwise
        """
        if not self._is_running:
            logger.info("Listener stopped, skipping token creation wait")
            return None

        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=30)
            data = json.loads(response)

            if "method" not in data or data["method"] != "logsNotification":
                return None

            log_data = data["params"]["result"]["value"]
            logs = log_data.get("logs", [])
            signature = log_data.get("signature", "unknown")

            # Use the processor to extract token info
            return self.event_processor.process_program_logs(logs, signature)

        except asyncio.TimeoutError:
            logger.debug("No data received for 30 seconds")
        except ConnectionClosed:
            logger.warning("WebSocket connection closed")
            raise
        except asyncio.CancelledError:
            logger.info("WebSocket listener cancelled")
            self._is_running = False
            self._websocket = None
            return None
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {str(e)}")
            return None