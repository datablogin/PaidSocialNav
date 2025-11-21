"""Centralized logging configuration for PaidSocialNav.

Configures structured JSON logging for production environments
and human-readable logging for development/CLI usage.
"""

import logging
import logging.config
from typing import Any


# Default logging configuration
LOGGING_CONFIG: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S%z",
        },
        "console": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "console",
            "stream": "ext://sys.stderr",
        },
        "json_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "json",
            "filename": "logs/paidsocialnav.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
        },
    },
    "loggers": {
        "paid_social_nav": {
            "level": "DEBUG",
            "handlers": ["console", "json_file"],
            "propagate": False,
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
}


def setup_logging(json_output: bool = False, log_level: str = "INFO") -> None:
    """Configure logging for the application.

    Args:
        json_output: If True, use JSON formatter for console output (for production)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    import os

    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)

    config = LOGGING_CONFIG.copy()

    # Override console formatter if JSON output requested
    if json_output:
        config["handlers"]["console"]["formatter"] = "json"

    # Override log level if specified
    if log_level:
        config["handlers"]["console"]["level"] = log_level
        config["loggers"]["paid_social_nav"]["level"] = log_level

    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Configured logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Starting sync", extra={"account_id": "act_123", "level": "ad"})
    """
    return logging.getLogger(name)
