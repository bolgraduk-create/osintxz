"""
Centralized logging configuration.

Every module in the project must obtain loggers
through this module.

Example:

from app.core.logger import get_logger

logger = get_logger(__name__)
"""

from __future__ import annotations

import logging
import logging.config
from pathlib import Path

from app.core.config import LOG_DIR
from app.core.config import settings


LOG_FORMAT = (
    "%(asctime)s | "
    "%(levelname)-8s | "
    "%(name)s | "
    "%(message)s"
)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

LOG_FILE = Path(LOG_DIR) / "application.log"


LOGGING_CONFIG: dict = {

    "version": 1,

    "disable_existing_loggers": False,

    "formatters": {

        "standard": {

            "format": LOG_FORMAT,

            "datefmt": DATE_FORMAT,

        },

    },

    "handlers": {

        "console": {

            "class": "logging.StreamHandler",

            "formatter": "standard",

            "level": "DEBUG" if settings.debug else "INFO",

        },

        "file": {

            "class": "logging.handlers.RotatingFileHandler",

            "filename": str(LOG_FILE),

            "maxBytes": 10 * 1024 * 1024,

            "backupCount": 10,

            "encoding": "utf-8",

            "formatter": "standard",

            "level": "DEBUG",

        },

    },

    "root": {

        "handlers": [

            "console",

            "file",

        ],

        "level": "DEBUG" if settings.debug else "INFO",

    },

}
_configured = False


def configure_logging() -> None:
    """
    Configure logging.

    Safe to call multiple times.
    """

    global _configured

    if _configured:
        return

    logging.config.dictConfig(LOGGING_CONFIG)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Returns configured logger.
    """

    if not _configured:
        configure_logging()

    return logging.getLogger(name)


logger = get_logger("intelligence")