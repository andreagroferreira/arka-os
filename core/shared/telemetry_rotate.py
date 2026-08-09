"""Size-capped rotation for append-only telemetry JSONL (Gate Economy PR-10).

The enforcement writers append on every gated tool call and never
trimmed: ``enforcement.jsonl`` reached 39MB, ``kb_first.jsonl`` 33MB and
``specialist-dispatch.jsonl`` 16MB on the operator's machine. One
generation is kept (``<name>.1``) so a rotation never destroys the
recent record an investigation would want.

Deliberately NOT applied to the eval corpora (``qg-verdicts.jsonl``,
``judge-verdicts.jsonl``) or the cost ledger — those are datasets, not
logs, and their writers do not call this helper.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

#: Default cap per file. Override with ARKA_TELEMETRY_MAX_BYTES; a value
#: of 0 or a non-integer disables rotation entirely.
DEFAULT_MAX_BYTES = 10 * 1024 * 1024


def _max_bytes() -> int:
    raw = os.environ.get("ARKA_TELEMETRY_MAX_BYTES", "").strip()
    if not raw:
        return DEFAULT_MAX_BYTES
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_MAX_BYTES


def rotate_if_oversized(path: Path, max_bytes: int | None = None) -> bool:
    """Rotate ``path`` to ``<name>.1`` when it exceeds the cap.

    Returns True when a rotation happened. Never raises — telemetry
    plumbing must not break a hook. On POSIX, concurrent ROTATORS are
    serialized on a dedicated ``<name>.rotlock`` flock and the size is
    re-checked under the lock, so a losing rotator sees the fresh
    (small) file and stands down instead of replacing again and
    destroying the one kept generation. Where ``fcntl`` is unavailable
    (Windows) the flock helpers no-op, rotation is best-effort, and a
    rare concurrent double-rotation can still drop the kept generation;
    the loss is confined to telemetry logs. A concurrent APPENDER holding a
    handle to the renamed inode keeps writing into ``<name>.1`` — data
    lands in the kept generation, never lost.
    """
    cap = _max_bytes() if max_bytes is None else max_bytes
    if cap <= 0:
        return False
    try:
        if not path.is_file() or path.stat().st_size <= cap:
            return False
    except OSError:
        return False
    try:
        with open(
            path.with_name(path.name + ".rotlock"), "a", encoding="utf-8"
        ) as lock_fh:
            _flock(lock_fh)
            try:
                # Re-check under the lock: a winner may just have rotated.
                if not path.is_file() or path.stat().st_size <= cap:
                    return False
                os.replace(path, path.with_name(path.name + ".1"))
                return True
            finally:
                _funlock(lock_fh)
    except OSError:
        return False


def _flock(fh: object) -> None:
    with contextlib.suppress(ImportError, OSError):
        import fcntl

        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)  # type: ignore[attr-defined]


def _funlock(fh: object) -> None:
    with contextlib.suppress(ImportError, OSError):
        import fcntl

        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)  # type: ignore[attr-defined]
