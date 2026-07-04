"""Retry layer for LLM completion calls — survive provider limits.

`retry_completion` wraps any zero-arg completion callable with
exponential backoff + jitter. Classification is pluggable; the default
classifier recognises rate limits (HTTP 429 / "rate_limit"), transient
server failures (5xx / overloaded / connection / timeout) as retryable,
and everything else (auth, other 4xx, unknown) as fail-fast.

A `retry-after` value is honored when it can be extracted from the
exception — the anthropic SDK exposes response headers, inspected
defensively via getattr chains so we never hard-depend on SDK internals.

Hard bounds: total sleep across all attempts never exceeds
`MAX_TOTAL_SLEEP_SECONDS` (180s). On exhaustion the layer raises
`LLMUnavailable` with the attempt count and last error, preserving the
provider-chain fallback semantics of `core.runtime.llm_provider`.

Telemetry: each retry appends a JSONL record to
`~/.arkaos/telemetry/llm-retries.jsonl` (ts, provider, attempt, delay,
reason) in the same fcntl-locked never-raises style as
`llm_cost_telemetry`.
"""

from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar

from core.runtime.llm_cost_telemetry import _locked_append


T = TypeVar("T")

MAX_TOTAL_SLEEP_SECONDS = 180.0

DEFAULT_RETRY_TELEMETRY_PATH = (
    Path.home() / ".arkaos" / "telemetry" / "llm-retries.jsonl"
)

_RATE_LIMIT_MARKERS = ("rate_limit", "rate limit", "429", "too many requests")
_OVERLOAD_MARKERS = ("overloaded", "529", "server error", "internal error")
_CONNECTION_MARKERS = (
    "connection", "timed out", "timeout", "temporarily unavailable",
)
_AUTH_MARKERS = (
    "auth", "api key", "api_key", "unauthorized", "forbidden",
    "permission", "credit balance",
)


@dataclass(frozen=True)
class RetryDecision:
    """Outcome of classifying one exception."""

    retryable: bool
    reason: str
    retry_after: float | None = None


# ─── Defensive extraction helpers ─────────────────────────────────────


def _status_code(exc: Exception) -> int | None:
    for source in (exc, getattr(exc, "response", None)):
        raw = getattr(source, "status_code", None)
        if raw is None:
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return None


def _header_retry_after(exc: Exception) -> float | None:
    """Extract a retry-after value without depending on SDK internals."""
    candidates = [getattr(exc, "retry_after", None)]
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is not None and hasattr(headers, "get"):
        try:
            candidates.append(
                headers.get("retry-after") or headers.get("Retry-After")
            )
        except Exception:  # noqa: BLE001 — header access is best-effort
            pass
    for raw in candidates:
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value >= 0:
            return value
    return None


def default_classifier(exc: Exception) -> RetryDecision:
    """Classify an exception into retryable / fail-fast.

    Order matters: rate limits win (they carry retry-after), then
    explicit 5xx status, then overload/connection heuristics. Auth and
    remaining 4xx fail fast; unknown errors fail fast (conservative).
    """
    status = _status_code(exc)
    msg = str(exc).lower()
    if status == 429 or any(m in msg for m in _RATE_LIMIT_MARKERS):
        return RetryDecision(
            retryable=True, reason="rate-limit",
            retry_after=_header_retry_after(exc),
        )
    if status is not None and status >= 500:
        return RetryDecision(retryable=True, reason="server-error")
    if status is not None and 400 <= status < 500:
        return RetryDecision(retryable=False, reason="client-error")
    if any(m in msg for m in _AUTH_MARKERS):
        return RetryDecision(retryable=False, reason="auth")
    if any(m in msg for m in _OVERLOAD_MARKERS):
        return RetryDecision(retryable=True, reason="overloaded")
    if any(m in msg for m in _CONNECTION_MARKERS):
        return RetryDecision(retryable=True, reason="connection")
    return RetryDecision(retryable=False, reason="unknown")


# ─── Backoff schedule ─────────────────────────────────────────────────


def _next_delay(
    attempt: int,
    decision: RetryDecision,
    base_delay: float,
    max_delay: float,
    jitter: float,
) -> float:
    """Delay before the retry that follows `attempt` (1-based).

    A server-provided retry-after is honored exactly (no jitter, may
    exceed max_delay — the 180s total budget still bounds it). Otherwise
    exponential backoff capped at max_delay, with symmetric jitter.
    """
    if decision.retry_after is not None:
        return decision.retry_after
    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
    if jitter > 0:
        delay *= 1 + random.uniform(-jitter, jitter)
    return max(0.0, delay)


# ─── Telemetry (never raises) ─────────────────────────────────────────


def _retry_telemetry_path() -> Path:
    override = os.environ.get("ARKA_LLM_RETRY_PATH", "").strip()
    if override:
        return Path(override)
    return DEFAULT_RETRY_TELEMETRY_PATH


def _record_retry(provider: str, attempt: int, delay: float, reason: str) -> None:
    try:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "provider": str(provider or ""),
            "attempt": int(attempt),
            "delay": round(float(delay), 3),
            "reason": str(reason or ""),
        }
        with _locked_append(_retry_telemetry_path()) as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 — telemetry must never raise
        return


# ─── Public entry point ───────────────────────────────────────────────


def retry_completion(
    fn: Callable[[], T],
    *,
    max_attempts: int = 4,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    jitter: float = 0.25,
    classify: Callable[[Exception], RetryDecision] = default_classifier,
    provider: str = "",
) -> T:
    """Call `fn` with retries on transient provider failures.

    Non-retryable exceptions re-raise unchanged (fail fast). Retryable
    exceptions back off and retry up to `max_attempts` total calls, with
    cumulative sleep capped at MAX_TOTAL_SLEEP_SECONDS. On exhaustion
    raises `LLMUnavailable` (attempt count + last error) so provider
    chains keep their existing fallback semantics.
    """
    slept = 0.0
    attempts = 0
    last_exc: Exception | None = None
    for attempt in range(1, max(1, int(max_attempts)) + 1):
        attempts = attempt
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — classifier decides
            last_exc = exc
            decision = classify(exc)
            if not decision.retryable:
                raise
            if attempt >= max_attempts:
                break
            remaining = MAX_TOTAL_SLEEP_SECONDS - slept
            if remaining <= 0:
                break
            delay = min(
                _next_delay(attempt, decision, base_delay, max_delay, jitter),
                remaining,
            )
            _record_retry(provider, attempt, delay, decision.reason)
            time.sleep(delay)
            slept += delay

    from core.runtime.llm_provider import LLMUnavailable

    raise LLMUnavailable(
        f"retries exhausted after {attempts} attempts (provider="
        f"{provider or 'unknown'}): "
        f"{last_exc.__class__.__name__}: {last_exc}"
    ) from last_exc
