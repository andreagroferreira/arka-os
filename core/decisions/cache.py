"""Response cache keyed by sha256(model + prepared state + questions).

Stores RESPONSES only — never the state. One file per key under
``<cache_root>/<key[:2]>/<key>.json``, written tmp+rename with mode
0600. Corrupt, expired or foreign files are a miss; nothing raises.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path

from pydantic import ValidationError

from core.decisions.backoff import ensure_private_dir
from core.decisions.models import DecisionResponse, Question, State
from core.decisions.paths import cache_root

_KEY_RE = re.compile(r"[0-9a-f]{64}")


def cache_key(model: str, state: State, questions: dict[str, Question]) -> str:
    """Deterministic sha256 over the canonical JSON of the request."""
    canonical = json.dumps(
        {
            "model": model,
            "state": state,
            "questions": {k: q.to_payload() for k, q in questions.items()},
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8", errors="surrogatepass")).hexdigest()


def _entry_path(key: str) -> Path | None:
    if not _KEY_RE.fullmatch(key):
        return None
    return cache_root() / key[:2] / f"{key}.json"


def get(key: str, ttl_s: float, now: float | None = None) -> DecisionResponse | None:
    """The cached response while younger than ``ttl_s``, else None."""
    path = _entry_path(key)
    if path is None:
        return None
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
        stored_at = float(entry["stored_at"])
        response = DecisionResponse.model_validate(entry["response"])
    except (OSError, ValueError, KeyError, TypeError, ValidationError):
        return None
    ref = time.time() if now is None else now
    if ttl_s <= 0 or ref - stored_at > ttl_s:
        return None
    return response


def put(key: str, response: DecisionResponse, now: float | None = None) -> bool:
    """Store one response atomically; False when it could not."""
    path = _entry_path(key)
    if path is None:
        return False
    stored_at = time.time() if now is None else now
    payload = {"stored_at": stored_at, "response": response.model_dump(mode="json")}
    try:
        _atomic_write(path, payload)
    except (OSError, ValueError, TypeError):
        return False
    return True


def _atomic_write(path: Path, payload: dict[str, object]) -> None:
    # Every directory created on the way is 0700, not the umask default.
    ensure_private_dir(path.parent)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".entry-", suffix=".tmp")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
