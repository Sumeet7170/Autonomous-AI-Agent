"""
Retry and resilience utilities using tenacity.
Wraps LLM calls and external API calls with exponential backoff.

Why exponential backoff?
  - LLM providers rate-limit under load
  - Linear retries hammer the API; exponential spreads them out
  - Jitter prevents the "thundering herd" problem in production
"""
import asyncio
import logging
from functools import wraps
from typing import Callable

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    RetryError,
)

from .config import settings
from .logger import get_logger

logger = get_logger(__name__)
_stdlib_logger = logging.getLogger(__name__)


def llm_retry(func: Callable) -> Callable:
    """
    Universal retry decorator for LLM + embedding API calls.
    Works on both sync and async functions.

    Retries up to MAX_RETRIES times with exponential backoff.
    Logs a warning before each retry so you can see what's happening.
    Re-raises the original exception after all retries are exhausted.
    """
    retry_decorator = retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(
            multiplier=settings.RETRY_WAIT_SECONDS,
            min=1,
            max=30,
        ),
        retry=retry_if_exception_type(Exception),
        before_sleep=before_sleep_log(_stdlib_logger, logging.WARNING),
        reraise=True,
    )

    if asyncio.iscoroutinefunction(func):
        @retry_decorator
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return async_wrapper
    else:
        @retry_decorator
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return sync_wrapper


__all__ = ["llm_retry", "RetryError"]
