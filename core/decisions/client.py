"""Stdlib client for ``POST /api/alpha/decisions``.

:func:`post_decision` raises ONLY :class:`DecisionUnavailable`; its
``reason`` is the stable telemetry vocabulary:

``no-transport`` | ``bypassed`` | ``backoff`` | ``deadline`` |
``egress-denied:<kind>`` | ``timeout`` | ``network`` | ``http-401`` |
``http-422`` | ``http-429`` | ``http-529`` | ``http-<n>`` |
``invalid-json`` | ``invalid-shape`` | ``redirected``.

401/429/529 also trip the shared circuit breaker (``backoff.py``);
``timeout``/``network`` count towards it (3 in a row trip it for 60 s)
and a success clears the count.

Deadline: ``urlopen(timeout=)`` bounds each socket operation, not the
call — DNS is not covered and a server dripping one byte every 0.4 s
held a 1 s call for 11.4 s (QG r1 B1). The exchange runs in a daemon
thread joined against a monotonic deadline; past it the call is
``timeout`` and the thread is abandoned. The thread only fetches bytes:
parsing, cache, breaker and telemetry all happen on the caller's side,
so an abandoned thread can write nothing.

Redirects: urllib turns a 301/302/303 answer to a POST into a GET and
copies every non-content header to whatever host ``Location`` names —
the Bearer key included (reproduced against two local servers in the
2026-09-23 security review). ``Authorization`` therefore travels as an
UNREDIRECTED header (urllib never copies those), the body is dropped
by urllib itself, and a response whose final URL differs from the one
requested is refused (``redirected``) so another host cannot answer.
307/308 to a POST already surface as ``http-307``/``http-308``.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

from pydantic import ValidationError

from core.decisions import backoff
from core.decisions.models import DecisionRequest, DecisionResponse
from core.decisions.transport import Transport

BACKOFF_401_S = 3600.0
BACKOFF_429_DEFAULT_S = 60.0
BACKOFF_529_S = 120.0
MAX_RETRY_AFTER_S = 3600.0


class DecisionUnavailable(Exception):  # noqa: N818 — contract name from the ADR
    """No typed answer this time; the caller uses its heuristic."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def post_decision(
    transport: Transport, request: DecisionRequest, timeout_s: float
) -> tuple[DecisionResponse, int]:
    """POST one request; ``(response, latency_ms)`` or DecisionUnavailable."""
    try:
        payload = {**request.to_payload(), **transport.body_extras}
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise DecisionUnavailable("invalid-shape", type(exc).__name__) from exc
    req = _request(transport, body)
    start = time.monotonic()
    try:
        raw = _send_by_deadline(req, timeout_s)
    except DecisionUnavailable as exc:
        if exc.reason in ("timeout", "network"):
            backoff.record_failure(exc.reason)
        raise
    latency_ms = int((time.monotonic() - start) * 1000)
    response = _parse(raw)
    backoff.record_success()
    return response, latency_ms


def _request(transport: Transport, body: bytes) -> urllib.request.Request:
    headers = {k: v for k, v in transport.headers.items() if k.lower() != "authorization"}
    req = urllib.request.Request(transport.url, data=body, headers=headers, method="POST")
    for name, value in transport.headers.items():
        if name.lower() == "authorization":
            req.add_unredirected_header(name, value)
    return req


def _send_by_deadline(req: urllib.request.Request, timeout_s: float) -> bytes:
    """``_send`` bounded by wall clock, not per socket operation."""
    box: dict[str, object] = {}

    def worker() -> None:
        try:
            box["data"] = _send(req, timeout_s)
        except BaseException as exc:  # handed to the caller, never lost
            box["error"] = exc

    thread = threading.Thread(target=worker, name="arka-decision", daemon=True)
    thread.start()
    thread.join(max(0.0, timeout_s))
    if thread.is_alive():
        # Not closed from here: HTTPResponse.close() waits on the reader
        # lock the dripping read holds, so it would block the caller for
        # the whole drip (measured: 11.7 s). The daemon thread ends with
        # the socket or the process; it holds bytes only.
        raise DecisionUnavailable("timeout", "deadline")
    error = box.get("error")
    if isinstance(error, urllib.error.HTTPError):
        raise _map_http_error(error) from error
    if isinstance(error, BaseException):
        raise error
    data = box.get("data")
    return data if isinstance(data, bytes) else b""


def _send(req: urllib.request.Request, timeout_s: float) -> bytes:
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            final = getattr(resp, "url", None)
            if isinstance(final, str) and final != req.full_url:
                raise DecisionUnavailable("redirected")
            data: bytes = resp.read()
            return data
    except DecisionUnavailable:
        raise
    except urllib.error.HTTPError:
        raise  # mapped on the caller's side: the breaker is never tripped late
    except urllib.error.URLError as exc:
        reason = "timeout" if isinstance(exc.reason, TimeoutError) else "network"
        raise DecisionUnavailable(reason, str(exc.reason)) from exc
    except TimeoutError as exc:
        raise DecisionUnavailable("timeout") from exc
    except Exception as exc:
        raise DecisionUnavailable("network", type(exc).__name__) from exc


def _map_http_error(exc: urllib.error.HTTPError) -> DecisionUnavailable:
    code = int(exc.code)
    if code == 401:
        backoff.trip("http-401", BACKOFF_401_S)
    elif code == 429:
        backoff.trip("http-429", _retry_after(exc))
    elif code == 529:
        backoff.trip("http-529", BACKOFF_529_S)
    return DecisionUnavailable(f"http-{code}", str(exc.reason or ""))


def _retry_after(exc: urllib.error.HTTPError) -> float:
    raw = exc.headers.get("Retry-After") if exc.headers is not None else None
    try:
        seconds = float(str(raw).strip())
    except (TypeError, ValueError):
        return BACKOFF_429_DEFAULT_S
    if seconds <= 0:
        return BACKOFF_429_DEFAULT_S
    return min(seconds, MAX_RETRY_AFTER_S)


def _parse(raw: bytes) -> DecisionResponse:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise DecisionUnavailable("invalid-json", type(exc).__name__) from exc
    if not isinstance(data, dict):
        raise DecisionUnavailable("invalid-shape", "body is not an object")
    try:
        return DecisionResponse.model_validate(data)
    except ValidationError as exc:
        raise DecisionUnavailable("invalid-shape", f"{exc.error_count()} errors") from exc
