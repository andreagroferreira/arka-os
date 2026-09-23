"""Circuit breaker shared by every process: one JSON file under the cache.

``trip`` records ``{"reason", "until"}``; ``blocked`` answers the reason
while ``now < until``. A longer existing block is never shortened.
Neither function raises — a broken breaker means "not blocked".

Transport failures (``timeout`` / ``network``) trip it too, but only
after :data:`FAILURE_TRIP_COUNT` in a row (``failures.json``, shared by
every hook process): one slow turn is noise, three are an outage the
next turns must not each pay for (QG r1 B2). A success clears the count;
a count older than :data:`FAILURE_WINDOW_S` starts over.

Directories this module creates are 0700 and its files 0600 (QG r1 m3).
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import time
from pathlib import Path

from core.decisions.paths import cache_root

# No caller trips for longer (client.py caps Retry-After at an hour); a
# deadline further out is a corrupt or planted file, not a real trip,
# and must neither block forever nor stop a real trip from landing.
MAX_BLOCK_S = 3600.0
FAILURE_TRIP_COUNT = 3
FAILURE_BACKOFF_S = 60.0
FAILURE_WINDOW_S = 600.0


def _state_path() -> Path:
    return cache_root() / "backoff.json"


def _failures_path() -> Path:
    return cache_root() / "failures.json"


def ensure_private_dir(path: Path) -> None:
    """``mkdir -p`` where every directory CREATED here is 0700."""
    missing: list[Path] = []
    probe = path
    while not probe.exists() and probe != probe.parent:
        missing.append(probe)
        probe = probe.parent
    for directory in reversed(missing):
        with contextlib.suppress(FileExistsError):
            directory.mkdir(mode=0o700)
        os.chmod(directory, 0o700)  # mkdir's mode is masked by the umask


def record_failure(reason: str, now: float | None = None) -> int:
    """Count one transport failure; trip at the threshold. Never raises."""
    ref = time.time() if now is None else now
    try:
        state = json.loads(_failures_path().read_text(encoding="utf-8"))
        count = int(state["count"]) if ref - float(state["last"]) <= FAILURE_WINDOW_S else 0
    except (OSError, ValueError, KeyError, TypeError):
        count = 0
    count += 1
    if count >= FAILURE_TRIP_COUNT:
        trip(reason, FAILURE_BACKOFF_S, now=ref)
        record_success()
        return count
    with contextlib.suppress(OSError, ValueError):
        _atomic_write(_failures_path(), {"count": count, "last": ref})
    return count


def record_success() -> None:
    """A call went through: consecutive failures start from zero."""
    with contextlib.suppress(OSError):
        _failures_path().unlink(missing_ok=True)


def _read() -> dict[str, object]:
    try:
        data = json.loads(_state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def blocked(now: float | None = None) -> str | None:
    """The trip reason while the breaker is open, else None."""
    state = _read()
    until = state.get("until")
    if not isinstance(until, int | float):
        return None
    ref = time.time() if now is None else now
    if ref >= until or until - ref > MAX_BLOCK_S:
        return None
    return str(state.get("reason") or "backoff")


def trip(reason: str, seconds: float, now: float | None = None) -> None:
    """Open the breaker for ``seconds``; keeps any later existing deadline."""
    ref = time.time() if now is None else now
    until = ref + min(max(0.0, float(seconds)), MAX_BLOCK_S)
    current = _read().get("until")
    if isinstance(current, int | float) and until < current <= ref + MAX_BLOCK_S:
        return
    with contextlib.suppress(OSError, ValueError):
        _atomic_write(_state_path(), {"reason": reason, "until": until})


def _atomic_write(path: Path, payload: dict[str, object]) -> None:
    ensure_private_dir(path.parent)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".backoff-", suffix=".tmp")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
