"""
Structured logging setup using structlog.
- Development: pretty colorized console output
- Production: JSON lines (compatible with Datadog, Grafana Loki, CloudWatch)
"""
import logging
import sys
import structlog
from .config import settings


def setup_logging() -> None:
    """Configure structlog for the application. Call once at startup."""
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    # Configure Python's standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Processors applied to every log event
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.DEBUG:
        # Human-readable output for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # Machine-readable JSON for production log aggregators
        processors = shared_processors + [
            structlog.processors.ExceptionRenderer(),
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__):
    """
    Get a bound structlog logger.

    Usage:
        logger = get_logger(__name__)
        logger.info("task started", task_id="abc", agent="Planner")
    """
    return structlog.get_logger(name)
