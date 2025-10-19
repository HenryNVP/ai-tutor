from __future__ import annotations

import logging
from typing import Optional

import structlog


def configure_logging(level: str = "INFO", json_output: bool = False) -> None:
    """
    Initialize Python logging and structlog with consistent formatting.

    Builds a processor pipeline, swapping between console and JSON renderers, and configures
    structlog to honor the requested level so the rest of the system can use structured logging.
    """
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))
    processors = [
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def get_logger(name: Optional[str] = None):
    """Return a structlog logger that inherits the global configuration."""
    return structlog.get_logger(name)
