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
    plumbing must not break a hook. Concurrent rotations are benign:
    ``os.replace`` is atomic and the losing writer simply appends to
    the fresh file.
    """
    cap = _max_bytes() if max_bytes is None else max_bytes
    if cap <= 0:
        return False
    try:
        if not path.is_file() or path.stat().st_size <= cap:
            return False
    except OSError:
        return False
    with contextlib.suppress(OSError):
        os.replace(path, path.with_name(path.name + ".1"))
        return True
    return False
