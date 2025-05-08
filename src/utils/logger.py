"""
Logging utilities for the pump.fun trading bot.
"""

import logging
from pathlib import Path

# Global dict to store loggers
_loggers: dict[str, logging.Logger] = {}

def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Get or create a logger with the given name.

    Args:
        name: Logger name, typically __name__
        level: Logging level

    Returns:
        Configured logger
    """
    global _loggers

    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(level)

    _loggers[name] = logger
    return logger

def setup_file_logging(
    filename: str = "pump_trading.log", level: int = logging.INFO
) -> None:
    """Set up file logging with UTF-8 encoding.

    Args:
        filename: Log file path
        level: Logging level for file handler
    """
    root_logger = logging.getLogger()

    # Check if file handler with same filename already exists
    for handler in root_logger.handlers:
        if isinstance(handler, logging.FileHandler) and handler.baseFilename == str(Path(filename).resolve()):
            return  # File handler already added

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Use UTF-8 encoding for file handler
    file_handler = logging.FileHandler(filename, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)

def log_transaction_attempt(
    logger: logging.Logger,
    action: str,
    attempt: int,
    max_attempts: int,
    success: bool,
    error: str = None,
    token_symbol: str = None,
    tx_signature: str = None
) -> None:
    """
    Log a transaction attempt with detailed information.

    Args:
        logger: Logger instance to use
        action: Type of transaction (e.g., 'buy', 'sell')
        attempt: Current attempt number (1-based)
        max_attempts: Maximum number of attempts
        success: Whether the attempt was successful
        error: Error message if the attempt failed
        token_symbol: Symbol of the token involved (optional)
        tx_signature: Transaction signature (optional)
    """
    base_message = (
        f"Transaction {action} attempt {attempt}/{max_attempts}"
        f"{f' for token {token_symbol}' if token_symbol else ''}: "
        f"{'Success' if success else 'Failed'}"
    )
    if success and tx_signature:
        base_message += f", signature: {tx_signature}"
    elif not success and error:
        base_message += f", error: {error}"

    if success:
        logger.info(base_message)
    else:
        logger.warning(base_message)