import asyncio
import logging
import multiprocessing
from datetime import datetime
from pathlib import Path
import time
import traceback

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    import asyncio
    logging.info("uvloop not available, using default asyncio event loop")

from config_loader import load_bot_config, print_config_summary
from trading.trader import PumpTrader
from utils.logger import setup_file_logging

def setup_logging(bot_name: str):
    """
    Set up logging to file for a specific bot instance.
    
    Args:
        bot_name: Name of the bot for the log file
    """
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = log_dir / f"{bot_name}_{timestamp}.log"
    
    setup_file_logging(str(log_filename))

async def start_bot(config_path: str):
    """
    Start a trading bot with the configuration from the specified path.
    
    Args:
        config_path: Path to the YAML configuration file
    """
    cfg = load_bot_config(config_path)
    setup_logging(cfg["name"])
    print_config_summary(cfg)
    
    # Log progress parameters for debugging
    logging.debug(f"Config min_progress_to_buy: {cfg['trade']['min_progress_to_buy']}%")
    logging.debug(f"Config max_progress_to_buy: {cfg['trade']['max_progress_to_buy']}%")
    
    trader = PumpTrader(
        # Connection settings
        rpc_endpoint=cfg["rpc_endpoint"],
        wss_endpoint=cfg["wss_endpoint"],
        private_key=cfg["private_key"],
        
        # Trade parameters
        buy_amount=cfg["trade"]["buy_amount"],
        buy_slippage=cfg["trade"]["buy_slippage"],
        sell_slippage=cfg["trade"]["sell_slippage"],
        
        # Extreme fast mode settings
        extreme_fast_mode=cfg["trade"].get("extreme_fast_mode", False),
        extreme_fast_token_amount=cfg["trade"].get("extreme_fast_token_amount", 30),
        
        # Listener configuration
        listener_type=cfg["filters"]["listener_type"],
        
        # Geyser configuration (if applicable)
        geyser_endpoint=cfg.get("geyser", {}).get("endpoint"),
        geyser_api_token=cfg.get("geyser", {}).get("api_token"),
        
        # Priority fee configuration
        enable_dynamic_priority_fee=cfg.get("priority_fees", {}).get("enable_dynamic", False),
        enable_fixed_priority_fee=cfg.get("priority_fees", {}).get("enable_fixed", True),
        fixed_priority_fee=cfg.get("priority_fees", {}).get("fixed_amount", 500000),
        extra_priority_fee=cfg.get("priority_fees", {}).get("extra_percentage", 0.0),
        hard_cap_prior_fee=cfg.get("priority_fees", {}).get("hard_cap", 500000),
        
        # Retry and timeout settings
        max_retries=cfg.get("retries", {}).get("max_attempts", 10),
        wait_time_after_creation=cfg.get("retries", {}).get("wait_after_creation", 15),
        wait_time_after_buy=cfg.get("retries", {}).get("wait_after_buy", 15),
        wait_time_before_new_token=cfg.get("retries", {}).get("wait_before_new_token", 15),
        max_token_age=cfg.get("filters", {}).get("max_token_age", 0.001),
        token_wait_timeout=cfg.get("timing", {}).get("token_wait_timeout", 30),
        
        # Cleanup settings
        cleanup_mode=cfg.get("cleanup", {}).get("mode", "disabled"),
        cleanup_force_close_with_burn=cfg.get("cleanup", {}).get("force_close_with_burn", False),
        cleanup_with_priority_fee=cfg.get("cleanup", {}).get("with_priority_fee", False),

        # Trading filters
        match_string=cfg["filters"].get("match_string"),
        bro_address=cfg["filters"].get("bro_address"),
        marry_mode=cfg["filters"].get("marry_mode", False),
        yolo_mode=cfg["filters"].get("yolo_mode", False),
        
        # Sell strategy configuration
        enable_take_profit=cfg["trade"].get("enable_take_profit", True),
        enable_fixed_time_sell=cfg["trade"].get("enable_fixed_time_sell", True),
        take_profit_percentage=cfg["trade"].get("take_profit_percentage", 0.5),
        stop_loss_percentage=cfg["trade"].get("stop_loss_percentage", 0.2),
        max_monitor_time=cfg["trade"].get("max_monitor_time", 300),
        
        # Bonding curve progress configuration
        min_progress_to_buy=cfg["trade"]["min_progress_to_buy"],
        max_progress_to_buy=cfg["trade"]["max_progress_to_buy"],
        enable_progress_sell=cfg["trade"].get("enable_progress_sell", False),
        progress_sell_threshold=cfg["trade"].get("progress_sell_threshold", 95.0),
    )
    
    try:
        await trader.start()
    except asyncio.CancelledError:
        logging.info("Bot cancelled, shutting down gracefully")
        await trader._cleanup_resources()
    except Exception as e:
        logging.error(f"Bot stopped due to error: {str(e)}")
        await trader._cleanup_resources()
    finally:
        loop = asyncio.get_event_loop()
        if not loop.is_closed():
            pending = asyncio.all_tasks(loop)
            for task in pending:
                if task is not asyncio.current_task(loop):
                    loop.call_soon_threadsafe(task.cancel)
            try:
                time.sleep(10.0)  # Reduced initial delay
                start_time = time.time()
                pending = asyncio.all_tasks(loop)
                pending_tasks = [task for task in pending if task is not asyncio.current_task(loop) and not task.done()]
                if pending_tasks:
                    logging.warning(f"{len(pending_tasks)} tasks still pending after cancellation delay")
                    for task in pending_tasks:
                        try:
                            coro_name = task.get_coro().__qualname__
                            stack = ''.join(traceback.format_stack(task.get_stack()))
                            logging.warning(f"Pending task: {coro_name}\nStack: {stack}\nCancellation attempt: 1 at {datetime.now()}, elapsed: {time.time() - start_time:.2f}s")
                        except AttributeError:
                            logging.warning(f"Pending task: Unknown coroutine\nCancellation attempt: 1 at {datetime.now()}, elapsed: {time.time() - start_time:.2f}s")
                        loop.call_soon_threadsafe(task.cancel)  # Retry cancellation
                    time.sleep(1.0)  # Reduced delay
                    pending = asyncio.all_tasks(loop)
                    pending_tasks = [task for task in pending if task is not asyncio.current_task(loop) and not task.done()]
                    if pending_tasks:
                        logging.warning(f"{len(pending_tasks)} tasks still pending after second cancellation attempt")
                        for task in pending_tasks:
                            try:
                                coro_name = task.get_coro().__qualname__
                                stack = ''.join(traceback.format_stack(task.get_stack()))
                                logging.warning(f"Pending task: {coro_name}\nCancellation attempt: 2 at {datetime.now()}, elapsed: {time.time() - start_time:.2f}s")
                            except AttributeError:
                                logging.warning(f"Pending task: Unknown coroutine\nCancellation attempt: 2 at {datetime.now()}, elapsed: {time.time() - start_time:.2f}s")
                            loop.call_soon_threadsafe(task.cancel)  # Second cancellation attempt
                    time.sleep(1.0)  # Reduced delay
                    pending = asyncio.all_tasks(loop)
                    pending_tasks = [task for task in pending if task is not asyncio.current_task(loop) and not task.done()]
                    if pending_tasks:
                        logging.warning(f"{len(pending_tasks)} tasks still pending after third cancellation attempt")
                        for task in pending_tasks:
                            try:
                                coro_name = task.get_coro().__qualname__
                                stack = ''.join(traceback.format_stack(task.get_stack()))
                                logging.warning(f"Pending task: {coro_name}\nCancellation attempt: 3 at {datetime.now()}, elapsed: {time.time() - start_time:.2f}s")
                            except AttributeError:
                                logging.warning(f"Pending task: Unknown coroutine\nCancellation attempt: 3 at {datetime.now()}, elapsed: {time.time() - start_time:.2f}s")
                            loop.call_soon_threadsafe(task.cancel)  # Third cancellation attempt
                else:
                    logging.info("No pending tasks detected after cancellation delay")
            except Exception as e:
                logging.warning(f"Error during shutdown delay: {str(e)}")
            finally:
                try:
                    if loop.is_running():
                        start_time = time.time()
                        timeout = 30.0  # Increased timeout for VM
                        stop_attempts = 0
                        while loop.is_running() and (time.time() - start_time) < timeout:
                            pending = asyncio.all_tasks(loop)
                            pending_tasks = [task for task in pending if task is not asyncio.current_task(loop) and not task.done()]
                            if not pending_tasks:
                                logging.info("No pending tasks detected, exiting stop loop")
                                break
                            loop.stop()
                            logging.debug(f"loop.stop() attempt {stop_attempts + 1} at {datetime.now()}")
                            time.sleep(0.05)  # Reduced delay for faster shutdown
                            stop_attempts += 1
                            if stop_attempts >= 100:  # Limit to 100 stop attempts
                                break
                        logging.info(f"Completed {stop_attempts} loop.stop() attempts")
                    if not loop.is_running() and not loop.is_closed():
                        loop.close()
                except RuntimeError as e:
                    logging.warning(f"Error closing loop: {str(e)}")

def run_bot_in_process(config_path: str):
    """
    Helper function to run a bot in a separate process with its own event loop.
    
    Args:
        config_path: Path to the YAML configuration file
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(start_bot(config_path))
    finally:
        if not loop.is_closed():
            try:
                loop.stop()
                loop.close()
            except RuntimeError as e:
                logging.warning(f"Error closing loop in process: {str(e)}")

def run_all_bots():
    """
    Run all bots defined in YAML files in the 'bots' directory.
    Only runs bots that have enabled=True (or where enabled is not specified).
    Bots can be run in separate processes based on their configuration.
    """
    bot_dir = Path("bots")
    if not bot_dir.exists():
        logging.error(f"Bot directory '{bot_dir}' not found")
        return
    
    bot_files = list(bot_dir.glob("*.yaml"))
    if not bot_files:
        logging.error(f"No bot configuration files found in '{bot_dir}'")
        return
    
    logging.info(f"Found {len(bot_files)} bot configuration files")
    
    processes = []
    skipped_bots = 0
    
    for file in bot_files:
        try:
            cfg = load_bot_config(str(file))
            bot_name = cfg.get("name", file.stem)
            
            # Skip bots with enabled=False
            if not cfg.get("enabled", True):
                logging.info(f"Skipping disabled bot '{bot_name}'")
                skipped_bots += 1
                continue

            if cfg.get("separate_process", False):
                logging.info(f"Starting bot '{bot_name}' in separate process")
                p = multiprocessing.Process(
                    target=run_bot_in_process,
                    args=(str(file),),
                    name=f"bot-{bot_name}"
                )
                p.start()
                processes.append(p)
            else:
                logging.info(f"Starting bot '{bot_name}' in main process")
                try:
                    asyncio.run(start_bot(str(file)))
                except RuntimeError as e:
                    logging.error(f"Failed to run bot {bot_name}: {str(e)}")
        except Exception as e:
            logging.exception(f"Failed to start bot from {file}: {e}")
    
    logging.info(f"Started {len(bot_files) - skipped_bots} bots, skipped {skipped_bots} disabled bots")
    
    for p in processes:
        p.join()
        logging.info(f"Process {p.name} completed")

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        run_all_bots()
    except KeyboardInterrupt:
        logging.info("Received KeyboardInterrupt, shutting down gracefully...")
        if not loop.is_closed():
            pending = asyncio.all_tasks(loop)
            for task in pending:
                if task is not asyncio.current_task(loop):
                    loop.call_soon_threadsafe(task.cancel)
            try:
                time.sleep(10.0)  # Reduced initial delay
                start_time = time.time()
                pending = asyncio.all_tasks(loop)
                pending_tasks = [task for task in pending if task is not asyncio.current_task(loop) and not task.done()]
                if pending_tasks:
                    logging.warning(f"{len(pending_tasks)} tasks still pending after cancellation delay")
                    for task in pending_tasks:
                        try:
                            coro_name = task.get_coro().__qualname__
                            stack = ''.join(traceback.format_stack(task.get_stack()))
                            logging.warning(f"Pending task: {coro_name}\nStack: {stack}\nCancellation attempt: 1 at {datetime.now()}, elapsed: {time.time() - start_time:.2f}s")
                        except AttributeError:
                            logging.warning(f"Pending task: Unknown coroutine\nCancellation attempt: 1 at {datetime.now()}, elapsed: {time.time() - start_time:.2f}s")
                        loop.call_soon_threadsafe(task.cancel)  # Retry cancellation
                    time.sleep(1.0)  # Reduced delay
                    pending = asyncio.all_tasks(loop)
                    pending_tasks = [task for task in pending if task is not asyncio.current_task(loop) and not task.done()]
                    if pending_tasks:
                        logging.warning(f"{len(pending_tasks)} tasks still pending after second cancellation attempt")
                        for task in pending_tasks:
                            try:
                                coro_name = task.get_coro().__qualname__
                                stack = ''.join(traceback.format_stack(task.get_stack()))
                                logging.warning(f"Pending task: {coro_name}\nCancellation attempt: 2 at {datetime.now()}, elapsed: {time.time() - start_time:.2f}s")
                            except AttributeError:
                                logging.warning(f"Pending task: Unknown coroutine\nCancellation attempt: 2 at {datetime.now()}, elapsed: {time.time() - start_time:.2f}s")
                            loop.call_soon_threadsafe(task.cancel)  # Second cancellation attempt
                    time.sleep(1.0)  # Reduced delay
                    pending = asyncio.all_tasks(loop)
                    pending_tasks = [task for task in pending if task is not asyncio.current_task(loop) and not task.done()]
                    if pending_tasks:
                        logging.warning(f"{len(pending_tasks)} tasks still pending after third cancellation attempt")
                        for task in pending_tasks:
                            try:
                                coro_name = task.get_coro().__qualname__
                                stack = ''.join(traceback.format_stack(task.get_stack()))
                                logging.warning(f"Pending task: {coro_name}\nCancellation attempt: 3 at {datetime.now()}, elapsed: {time.time() - start_time:.2f}s")
                            except AttributeError:
                                logging.warning(f"Pending task: Unknown coroutine\nCancellation attempt: 3 at {datetime.now()}, elapsed: {time.time() - start_time:.2f}s")
                            loop.call_soon_threadsafe(task.cancel)  # Third cancellation attempt
                else:
                    logging.info("No pending tasks detected after cancellation delay")
            except Exception as e:
                logging.warning(f"Error during shutdown delay: {str(e)}")
            finally:
                try:
                    if loop.is_running():
                        start_time = time.time()
                        timeout = 30.0  # Increased timeout for VM
                        stop_attempts = 0
                        while loop.is_running() and (time.time() - start_time) < timeout:
                            pending = asyncio.all_tasks(loop)
                            pending_tasks = [task for task in pending if task is not asyncio.current_task(loop) and not task.done()]
                            if not pending_tasks:
                                logging.info("No pending tasks detected, exiting stop loop")
                                break
                            loop.stop()
                            logging.debug(f"loop.stop() attempt {stop_attempts + 1} at {datetime.now()}")
                            time.sleep(0.05)  # Reduced delay for faster shutdown
                            stop_attempts += 1
                            if stop_attempts >= 100:  # Limit to 100 stop attempts
                                break
                        logging.info(f"Completed {stop_attempts} loop.stop() attempts")
                    if not loop.is_running() and not loop.is_closed():
                        loop.close()
                except RuntimeError as e:
                    logging.warning(f"Error closing loop: {str(e)}")
    except Exception as e:
        logging.error(f"Main loop error: {str(e)}")
    finally:
        if not loop.is_closed():
            try:
                loop.stop()
                loop.close()
            except RuntimeError as e:
                logging.warning(f"Error closing loop: {str(e)}")

if __name__ == "__main__":
    main()