"""
Main trading coordinator for pump.fun tokens.
Refactored PumpTrader to only process fresh tokens from WebSocket.
"""

import asyncio
import json
import os
from datetime import datetime
from time import monotonic

from utils.logger import get_logger

logger = get_logger(__name__)

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    logger.info("uvloop not available, using default asyncio event loop")

from solders.pubkey import Pubkey

from cleanup.modes import (
    handle_cleanup_after_failure,
    handle_cleanup_after_sell,
    handle_cleanup_post_session,
)
from core.client import SolanaClient
from core.curve import BondingCurveManager
from core.priority_fee.manager import PriorityFeeManager
from core.pubkeys import PumpAddresses
from core.wallet import Wallet
from monitoring.block_listener import BlockListener
from monitoring.geyser_listener import GeyserListener
from monitoring.logs_listener import LogsListener
from trading.base import TokenInfo, TradeResult
from trading.buyer import TokenBuyer
from trading.seller import TokenSeller

class PumpTrader:
    """Coordinates trading operations for pump.fun tokens with focus on freshness."""
    def __init__(
        self,
        rpc_endpoint: str,
        wss_endpoint: str,
        private_key: str,
        buy_amount: float,
        buy_slippage: float,
        sell_slippage: float,
        listener_type: str = "logs",
        geyser_endpoint: str | None = None,
        geyser_api_token: str | None = None,
        extreme_fast_mode: bool = False,
        extreme_fast_token_amount: int = 30,
        # Priority fee configuration
        enable_dynamic_priority_fee: bool = False,
        enable_fixed_priority_fee: bool = True,
        fixed_priority_fee: int = 200_000,
        extra_priority_fee: float = 0.0,
        hard_cap_prior_fee: int = 200_000,
        # Retry and timeout settings
        max_retries: int = 3,
        wait_time_after_creation: int = 15, # here and further - seconds
        wait_time_after_buy: int = 15,
        wait_time_before_new_token: int = 15,
        max_token_age: int | float = 0.001,
        token_wait_timeout: int = 30,
        # Cleanup settings
        cleanup_mode: str = "disabled",
        cleanup_force_close_with_burn: bool = False,
        cleanup_with_priority_fee: bool = False,
        # Trading filters
        match_string: str | None = None,
        bro_address: str | None = None,
        marry_mode: bool = False,
        yolo_mode: bool = False,
        # Sell strategy configuration
        enable_take_profit: bool = True,
        enable_fixed_time_sell: bool = True,
        take_profit_percentage: float = 0.5,
        stop_loss_percentage: float = 0.2,
        max_monitor_time: int = 300,
        # Bonding curve progress configuration
        min_progress_to_buy: float = 0.0,
        max_progress_to_buy: float = 100.0,
        enable_progress_sell: bool = False,
        progress_sell_threshold: float = 95.0,
    ):
        """Initialize the pump trader."""
        self.solana_client = SolanaClient(rpc_endpoint)
        self.wallet = Wallet(private_key)
        self.curve_manager = BondingCurveManager(self.solana_client)
        self.priority_fee_manager = PriorityFeeManager(
            client=self.solana_client,
            enable_dynamic_fee=enable_dynamic_priority_fee,
            enable_fixed_fee=enable_fixed_priority_fee,
            fixed_fee=fixed_priority_fee,
            extra_fee=extra_priority_fee,
            hard_cap=hard_cap_prior_fee,
        )
        self.buyer = TokenBuyer(
            self.solana_client,
            self.wallet,
            self.curve_manager,
            self.priority_fee_manager,
            buy_amount,
            buy_slippage,
            max_retries,
            extreme_fast_token_amount,
            extreme_fast_mode
        )
        self.seller = TokenSeller(
            self.solana_client,
            self.wallet,
            self.curve_manager,
            self.priority_fee_manager,
            sell_slippage,
            max_retries,
        )
        
        # Initialize the appropriate listener type
        listener_type = listener_type.lower()
        if listener_type == "geyser":
            if not geyser_endpoint or not geyser_api_token:
                raise ValueError("Geyser endpoint and API token are required for geyser listener")
                
            self.token_listener = GeyserListener(
                geyser_endpoint, 
                geyser_api_token, 
                PumpAddresses.PROGRAM
            )
            logger.info("Using Geyser listener for token monitoring")
        elif listener_type == "logs":
            self.token_listener = LogsListener(wss_endpoint, PumpAddresses.PROGRAM)
            logger.info("Using logsSubscribe listener for token monitoring")
        else:
            self.token_listener = BlockListener(wss_endpoint, PumpAddresses.PROGRAM)
            logger.info("Using blockSubscribe listener for token monitoring")
            
        # Trading parameters
        self.buy_amount = buy_amount
        self.buy_slippage = buy_slippage
        self.sell_slippage = sell_slippage
        self.max_retries = max_retries
        self.extreme_fast_mode = extreme_fast_mode
        self.extreme_fast_token_amount = extreme_fast_token_amount
        
        # Timing parameters
        self.wait_time_after_creation = wait_time_after_creation
        self.wait_time_after_buy = wait_time_after_buy
        self.wait_time_before_new_token = wait_time_before_new_token
        self.max_token_age = max_token_age
        self.token_wait_timeout = token_wait_timeout
        
        # Cleanup parameters
        self.cleanup_mode = cleanup_mode
        self.cleanup_force_close_with_burn = cleanup_force_close_with_burn
        self.cleanup_with_priority_fee = cleanup_with_priority_fee

        # Trading filters/modes
        self.match_string = match_string
        self.bro_address = bro_address
        self.marry_mode = marry_mode
        self.yolo_mode = yolo_mode
        
        # Sell strategy parameters
        self.enable_take_profit = enable_take_profit
        self.enable_fixed_time_sell = enable_fixed_time_sell
        self.take_profit_percentage = take_profit_percentage
        self.stop_loss_percentage = stop_loss_percentage
        self.max_monitor_time = max_monitor_time
        
        # Bonding curve progress parameters
        self.min_progress_to_buy = min_progress_to_buy
        self.max_progress_to_buy = max_progress_to_buy
        self.enable_progress_sell = enable_progress_sell
        self.progress_sell_threshold = progress_sell_threshold
        
        # Log configuration values for debugging
        logger.debug(f"Initialized PumpTrader with min_progress_to_buy: {self.min_progress_to_buy}%")
        logger.debug(f"Initialized PumpTrader with max_progress_to_buy: {self.max_progress_to_buy}%")
        
        # State tracking
        self.traded_mints: set[Pubkey] = set()
        self.token_queue: asyncio.Queue = asyncio.Queue()
        self.processing: bool = False
        self.processed_tokens: set[str] = set()
        self.token_timestamps: dict[str, float] = {}
        
        # Yolo mode limit
        self.max_tokens_per_session = 10
        self.processed_token_count = 0
        
    async def start(self) -> None:
        """Start the trading bot and listen for new tokens."""
        logger.info("Starting pump.fun trader")
        logger.info(f"Match filter: {self.match_string if self.match_string else 'None'}")
        logger.info(f"Creator filter: {self.bro_address if self.bro_address else 'None'}")
        logger.info(f"Marry mode: {self.marry_mode}")
        logger.info(f"YOLO mode: {self.yolo_mode}")
        logger.info(f"Max token age: {self.max_token_age} seconds")
        logger.info(f"Take profit enabled: {self.enable_take_profit}")
        logger.info(f"Fixed time sell enabled: {self.enable_fixed_time_sell}")
        logger.info(f"Take profit percentage: {self.take_profit_percentage * 100}%")
        logger.info(f"Stop loss percentage: {self.stop_loss_percentage * 100}%")
        logger.info(f"Max monitor time: {self.max_monitor_time} seconds")
        logger.info(f"Min progress to buy: {self.min_progress_to_buy}%")
        logger.info(f"Max progress to buy: {self.max_progress_to_buy}%")
        logger.info(f"Progress sell enabled: {self.enable_progress_sell}")
        logger.info(f"Progress sell threshold: {self.progress_sell_threshold}%")

        try:
            health_resp = await self.solana_client.get_health()
            logger.info(f"RPC warm-up successful (getHealth passed: {health_resp})")
        except Exception as e:
            logger.warning(f"RPC warm-up failed: {e!s}")

        try:
            # Choose operating mode based on yolo_mode
            if not self.yolo_mode:
                # Single token mode: process one token and exit
                logger.info("Running in single token mode - will process one token and exit")
                token_info = await self._wait_for_token()
                if token_info:
                    await self._handle_token(token_info)
                    logger.info("Finished processing single token. Exiting...")
                else:
                    logger.info(f"No suitable token found within timeout period ({self.token_wait_timeout}s). Exiting...")
            else:
                # Continuous mode: process tokens until interrupted
                logger.info("Running in continuous mode - will process tokens until interrupted")
                processor_task = asyncio.create_task(
                    self._process_token_queue()
                )

                try:
                    await self.token_listener.listen_for_tokens(
                        lambda token: self._queue_token(token),
                        self.match_string,
                        self.bro_address,
                    )
                except Exception as e:
                    logger.error(f"Token listening stopped due to error: {e!s}")
                finally:
                    processor_task.cancel()
                    try:
                        await processor_task
                    except asyncio.CancelledError:
                        pass
        
        except Exception as e:
            logger.error(f"Trading stopped due to error: {e!s}")
        
        finally:
            await self._cleanup_resources()
            logger.info("Pump trader has shut down")

    async def _wait_for_token(self) -> TokenInfo | None:
        """Wait for a single token to be detected.
        
        Returns:
            TokenInfo or None if timeout occurs
        """
        # Create a one-time event to signal when a token is found
        token_found = asyncio.Event()
        found_token = None
        
        async def token_callback(token: TokenInfo) -> None:
            nonlocal found_token
            token_key = str(token.mint)
            
            # Only process if not already processed and fresh
            if token_key not in self.processed_tokens:
                # Record when the token was discovered
                self.token_timestamps[token_key] = monotonic()
                found_token = token
                self.processed_tokens.add(token_key)
                token_found.set()
        
        listener_task = asyncio.create_task(
            self.token_listener.listen_for_tokens(
                token_callback,
                self.match_string,
                self.bro_address,
            )
        )
        
        # Wait for a token with a timeout
        try:
            logger.info(f"Waiting for a suitable token (timeout: {self.token_wait_timeout}s)...")
            await asyncio.wait_for(token_found.wait(), timeout=self.token_wait_timeout)
            logger.info(f"Found token: {found_token.symbol} ({found_token.mint})")
            return found_token
        except TimeoutError:
            logger.info(f"Timed out after waiting {self.token_wait_timeout}s for a token")
            return None
        finally:
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_resources(self) -> None:
        """Perform cleanup operations before shutting down."""
        if not self.traded_mints:
            logger.info("No traded tokens to clean up")
            await self.solana_client.close()
            return

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                logger.warning("Event loop is closed, skipping cleanup")
                return

            logger.info(f"Cleaning up {len(self.traded_mints)} traded token(s)...")
            await handle_cleanup_post_session(
                self.solana_client, 
                self.wallet, 
                list(self.traded_mints), 
                self.priority_fee_manager,
                self.cleanup_mode,
                self.cleanup_with_priority_fee,
                self.cleanup_force_close_with_burn
            )
        except Exception as e:
            logger.error(f"Error during cleanup: {e!s}")
        finally:
            await self.solana_client.close()
            logger.debug("Solana client closed")

        old_keys = {k for k in self.token_timestamps if k not in self.processed_tokens}
        for key in old_keys:
            self.token_timestamps.pop(key, None)

    async def _queue_token(
        self, token_info: TokenInfo
    ) -> None:
        """Queue a token for processing if not already processed.
        
        Args:
            token_info: Token information to queue
        """
        token_key = str(token_info.mint)

        if token_key in self.processed_tokens:
            logger.debug(f"Token {token_info.symbol} already processed. Skipping...")
            return

        # Record timestamp when token was discovered
        self.token_timestamps[token_key] = monotonic()

        await self.token_queue.put(token_info)
        logger.info(f"Queued new token: {token_info.symbol} ({token_info.mint})")

    async def _process_token_queue(self) -> None:
        """Continuously process tokens from the queue, only if they're fresh."""
        while self.processed_token_count < self.max_tokens_per_session:
            try:
                token_info = await self.token_queue.get()
                token_key = str(token_info.mint)

                # Check if token is still "fresh"
                current_time = monotonic()
                token_age = current_time - self.token_timestamps.get(
                    token_key, current_time
                )

                if token_age > self.max_token_age:
                    logger.info(
                        f"Skipping token {token_info.symbol} - too old ({token_age:.1f}s > {self.max_token_age}s)"
                    )
                    self.token_queue.task_done()
                    continue

                self.processed_tokens.add(token_key)
                self.processed_token_count += 1
                logger.info(
                    f"Processing fresh token: {token_info.symbol} (age: {token_age:.1f}s)"
                )
                try:
                    await self._handle_token(token_info)
                finally:
                    self.token_queue.task_done()

            except asyncio.CancelledError:
                # Handle cancellation gracefully
                logger.info("Token queue processor was cancelled")
                break
            except Exception as e:
                logger.error(f"Error in token queue processor: {e!s}")

    async def _handle_token(
        self, token_info: TokenInfo
    ) -> None:
        """Handle a new token creation event.

        Args:
            token_info: Token information
        """
        try:
            # Wait for bonding curve to stabilize (unless in extreme fast mode)
            if not self.extreme_fast_mode:
                logger.info(
                    f"Waiting for {self.wait_time_after_creation} seconds for the bonding curve to stabilize..."
                )
                await asyncio.sleep(self.wait_time_after_creation)

            # Check bonding curve progress before buying
            if not self.extreme_fast_mode:
                try:
                    curve_state = await self.curve_manager.get_curve_state(token_info.bonding_curve)
                    progress = curve_state.get_progress()
                    if progress < self.min_progress_to_buy or progress > self.max_progress_to_buy:
                        logger.info(
                            f"Skipping token {token_info.symbol}: progress {progress:.2f}% "
                            f"outside range [{self.min_progress_to_buy}, {self.max_progress_to_buy}]"
                        )
                        return
                    logger.info(f"Token {token_info.symbol} progress: {progress:.2f}%")
                except Exception as e:
                    logger.error(f"Failed to check bonding curve progress for {token_info.symbol}: {str(e)}")
                    return

            # Buy token
            logger.info(
                f"Buying {self.buy_amount:.6f} SOL worth of {token_info.symbol}..."
            )
            buy_result: TradeResult = await self.buyer.execute(token_info)

            if buy_result.success:
                await self._handle_successful_buy(token_info, buy_result)
            else:
                await self._handle_failed_buy(token_info, buy_result)

            # Only wait for next token in yolo mode
            if self.yolo_mode:
                logger.info(
                    f"YOLO mode enabled. Waiting {self.wait_time_before_new_token} seconds before looking for next token..."
                )
                await asyncio.sleep(self.wait_time_before_new_token)

        except Exception as e:
            logger.error(f"Error handling token {token_info.symbol}: {e!s}")

    async def _handle_successful_buy(
        self, token_info: TokenInfo, buy_result: TradeResult
    ) -> None:
        """Handle successful token purchase.
        
        Args:
            token_info: Token information
            buy_result: The result of the buy operation
        """
        logger.info(f"Successfully bought {token_info.symbol}")
        self._log_trade(
            "buy",
            token_info,
            buy_result.price,
            buy_result.amount,
            buy_result.tx_signature,
        )
        self.traded_mints.add(token_info.mint)
        
        if not self.marry_mode and (self.enable_take_profit or self.enable_fixed_time_sell or self.enable_progress_sell):
            sold = False
            start_time = monotonic()
            initial_price = buy_result.price
            
            # Log bonding curve state
            try:
                curve_state = await self.curve_manager.get_curve_state(token_info.bonding_curve)
                logger.debug(f"Bonding curve state for {token_info.symbol}: complete={curve_state.complete}, virtual_token_reserves={curve_state.virtual_token_reserves}, virtual_sol_reserves={curve_state.virtual_sol_reserves}")
            except Exception as e:
                logger.error(f"Failed to get bonding curve state for {token_info.symbol}: {str(e)}")
            
            if self.enable_take_profit:
                target_profit = 1.0 + self.take_profit_percentage  # e.g., 1.5 for 50% profit
                stop_loss = 1.0 - self.stop_loss_percentage       # e.g., 0.8 for 20% loss
                logger.info(f"Monitoring price for {token_info.symbol} (Take Profit: {self.take_profit_percentage * 100}%, Stop Loss: {self.stop_loss_percentage * 100}%)")
            
            # Monitor price, fixed time sell, and progress concurrently
            while monotonic() - start_time < max(self.max_monitor_time, self.wait_time_after_buy):
                elapsed_time = monotonic() - start_time
                
                # Check for fixed time sell
                if self.enable_fixed_time_sell and not sold and elapsed_time >= self.wait_time_after_buy:
                    logger.info(f"Fixed time sell triggered for {token_info.symbol} after {self.wait_time_after_buy} seconds")
                    self._log_trade(
                        "sell_trigger",
                        token_info,
                        0.0,
                        buy_result.amount,
                        None,
                        reason="fixed_time"
                    )
                    sold = True
                    break
                
                # Check price for take profit/stop loss and progress
                if (self.enable_take_profit or self.enable_progress_sell) and not sold and elapsed_time < self.max_monitor_time:
                    try:
                        curve_state = await self.curve_manager.get_curve_state(token_info.bonding_curve)
                        current_price = curve_state.calculate_price()
                        price_change = current_price / initial_price
                        logger.debug(f"Current price for {token_info.symbol}: {current_price:.9f} SOL, Change: {price_change:.2f}x")
                        
                        if self.enable_take_profit:
                            if price_change >= target_profit:
                                logger.info(f"Take profit triggered: {price_change:.2f}x")
                                self._log_trade(
                                    "sell_trigger",
                                    token_info,
                                    current_price,
                                    buy_result.amount,
                                    None,
                                    reason="take_profit"
                                )
                                sold = True
                                break
                            elif price_change <= stop_loss:
                                logger.info(f"Stop loss triggered: {price_change:.2f}x")
                                self._log_trade(
                                    "sell_trigger",
                                    token_info,
                                    current_price,
                                    buy_result.amount,
                                    None,
                                    reason="stop_loss"
                                )
                                sold = True
                                break
                        
                        if self.enable_progress_sell:
                            progress = curve_state.get_progress()
                            if progress >= self.progress_sell_threshold:
                                logger.info(f"Progress sell triggered: {progress:.2f}%")
                                self._log_trade(
                                    "sell_trigger",
                                    token_info,
                                    current_price,
                                    buy_result.amount,
                                    None,
                                    reason="progress_threshold"
                                )
                                sold = True
                                break
                            
                    except Exception as e:
                        logger.error(f"Error monitoring price or progress for {token_info.symbol}: {e}")
                        break
                
                await asyncio.sleep(5)  # Check every 5 seconds
            
            if sold:
                logger.info(f"Selling {token_info.symbol}...")
                sell_result = await self.seller.execute(token_info)
                if sell_result.success:
                    logger.info(f"Successfully sold {token_info.symbol}")
                    self._log_trade(
                        "sell",
                        token_info,
                        sell_result.price,
                        sell_result.amount,
                        sell_result.tx_signature,
                    )
                    await handle_cleanup_after_sell(
                        self.solana_client, 
                        self.wallet, 
                        token_info.mint, 
                        self.priority_fee_manager,
                        self.cleanup_mode,
                        self.cleanup_with_priority_fee,
                        self.cleanup_force_close_with_burn
                    )
                else:
                    logger.error(f"Failed to sell {token_info.symbol}: {sell_result.error_message}")
                    self._log_trade(
                        "sell_failed",
                        token_info,
                        0.0,
                        buy_result.amount,
                        None,
                        reason=sell_result.error_message
                    )
                    # Trigger cleanup even if sell fails
                    await handle_cleanup_after_sell(
                        self.solana_client, 
                        self.wallet, 
                        token_info.mint, 
                        self.priority_fee_manager,
                        self.cleanup_mode,
                        self.cleanup_with_priority_fee,
                        self.cleanup_force_close_with_burn
                    )
        else:
            logger.info("Marry mode enabled or no sell strategies active. Skipping sell operation.")

    async def _handle_failed_buy(
        self, token_info: TokenInfo, buy_result: TradeResult
    ) -> None:
        """Handle failed token purchase.
        
        Args:
            token_info: Token information
            buy_result: The result of the buy operation
        """
        logger.error(
            f"Failed to buy {token_info.symbol}: {buy_result.error_message}"
        )
        # Close ATA if enabled
        await handle_cleanup_after_failure(
            self.solana_client, 
            self.wallet, 
            token_info.mint, 
            self.priority_fee_manager,
            self.cleanup_mode,
            self.cleanup_with_priority_fee,
            self.cleanup_force_close_with_burn
        )

    async def _save_token_info(
        self, token_info: TokenInfo
    ) -> None:
        """Save token information to a file.

        Args:
            token_info: Token information
        """
        try:
            os.makedirs("trades", exist_ok=True)
            file_name = os.path.join("trades", f"{token_info.mint}.txt")

            with open(file_name, "w") as file:
                file.write(json.dumps(token_info.to_dict(), indent=2))

            logger.info(f"Token information saved to {file_name}")
        except Exception as e:
            logger.error(f"Failed to save token information: {e!s}")

    def _log_trade(
        self,
        action: str,
        token_info: TokenInfo,
        price: float,
        amount: float,
        tx_hash: str | None,
        reason: str | None = None
    ) -> None:
        """Log trade information.

        Args:
            action: Trade action (buy/sell/sell_trigger/sell_failed)
            token_info: Token information
            price: Token price in SOL
            amount: Trade amount in tokens
            tx_hash: Transaction hash
            reason: Reason for sell trigger or failure
        """
        try:
            os.makedirs("trades", exist_ok=True)

            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "action": action,
                "token_address": str(token_info.mint),
                "symbol": token_info.symbol,
                "price": price,
                "amount": amount,
                "tx_hash": str(tx_hash) if tx_hash else None,
            }
            if reason:
                log_entry["reason"] = reason

            with open("trades/trades.log", "a") as log_file:
                log_file.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to log trade information: {e!s}")