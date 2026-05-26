"""Per-process bearer token for WebSocket terminal handshake.

PR99a v3.67.0 — a random url-safe 32-byte token generated once at
process startup. The frontend fetches it from `/api/terminal/token`
(CORS-restricted to localhost) and includes it as a query parameter
on the WebSocket upgrade. Token rotates whenever the API restarts.

Rationale: CORS already blocks cross-origin XHR, but a malicious page
on `http://localhost:9999` could open a WebSocket without a preflight,
so we add a second authentication factor that only the dashboard
(running on localhost too) can read.
"""

from __future__ import annotations

import hmac
import secrets

_TOKEN: str = secrets.token_urlsafe(32)


def current_token() -> str:
    """Return the per-process terminal bearer token."""
    return _TOKEN


def verify(candidate: str) -> bool:
    """Constant-time compare a candidate against the current token."""
    if not isinstance(candidate, str) or not candidate:
        return False
    return hmac.compare_digest(candidate, _TOKEN)


def rotate() -> str:
    """Rotate the token (used by tests; never called in production)."""
    global _TOKEN
    _TOKEN = secrets.token_urlsafe(32)
    return _TOKEN
