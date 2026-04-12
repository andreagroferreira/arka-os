"""Retry wrapper for sync engine phases.

Wraps phase callables with exponential backoff. Errors are surfaced as
RetryExhausted after max attempts so the orchestrator can convert them
into structured SyncError entries on the report.
"""

from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


class RetryExhausted(RuntimeError):
    def __init__(self, message: str, last_exception: BaseException | None = None):
        super().__init__(message)
        self.last_exception = last_exception


def run_with_retry(
    fn: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 0.1,
    backoff: float = 2.0,
) -> T:
    """Call fn with exponential backoff; raise RetryExhausted after max_retries.

    max_retries=0 means a single attempt (no retries).
    """
    attempt = 0
    last_exc: BaseException | None = None
    while attempt <= max_retries:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt == max_retries:
                break
            time.sleep(base_delay * (backoff ** attempt))
            attempt += 1

    raise RetryExhausted(
        f"exhausted {max_retries} retries: {last_exc}",
        last_exception=last_exc,
    )
