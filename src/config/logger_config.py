import logging
import sys
import os
from logging.handlers import TimedRotatingFileHandler
from src.config.settings import settings


def setup_logging():
    log_level = logging.DEBUG if settings.debug_mode else logging.INFO
    log_file_path = "logs/bot_activity.log"

    # Create log directory if it doesn't exist
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    # Create logger
    logger = logging.getLogger("token_tracker_bot")
    logger.setLevel(log_level)

    # Clear existing handlers to prevent duplicate output
    if logger.hasHandlers():
        logger.handlers.clear()

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File Handler (for more persistent logs with daily rotation)
    file_handler = TimedRotatingFileHandler(
        log_file_path, when='midnight', interval=1, backupCount=7, encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Optionally add a specific handler for errors to stderr
    error_handler = logging.StreamHandler(sys.stderr)
    error_handler.setLevel(logging.ERROR)
    error_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    error_handler.setFormatter(error_formatter)
    logger.addHandler(error_handler)

    logger.info(f"Logging initialized. Level: {logging.getLevelName(log_level)}")
    if settings.debug_mode:
        logger.warning("Debug mode is active. Sensitive info might be logged.")

    return logger


# Create a global logger instance
logger = setup_logging()
