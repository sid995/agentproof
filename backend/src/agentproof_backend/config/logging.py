"""Structured logging configuration"""

import logging
import sys
from typing import Any, cast

import structlog


def build_logging_config(
    *,
    level: str,
    json_logs: bool,
) -> dict[str, Any]:
    """Configure a structlog and return a Django logging configuration."""

    timestamp_processor = structlog.processors.TimeStamper(
        fmt="iso",
        utc=True,
    )

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        timestamp_processor,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    renderer: Any = structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structured": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": renderer,
                "foreign_pre_chain": shared_processors,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "structured",
                "stream": sys.stdout,
            },
        },
        "root": {
            "handlers": ["console"],
            "level": level,
        },
        "loggers": {
            "django": {
                "handlers": ["console"],
                "level": level,
                "propagate": False,
            },
            "django.server": {
                "handlers": ["console"],
                "level": level,
                "propagate": False,
            },
            "agentproof": {
                "handlers": ["console"],
                "level": level,
                "propagate": False,
            },
        },
    }


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structured logger."""
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))


logging.captureWarnings(True)
