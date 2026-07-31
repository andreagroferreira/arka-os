"""Tolerant JSON reads, atomic writes, and order-preserving merges.

The harness surfaces this package reads (``settings.json``,
``ownership.json``, ``hard-deny.json``) are operator-owned files that
can be truncated, binary, or hand-edited into invalid JSON at any time.
A loader that raises on that input takes the whole caller down with it —
the ``harness_scanner`` contract applies here too: hostile input is a
reported condition, never a traceback.

The writer is the C2 primitive: same-directory tmp file + ``os.replace``
so a crash mid-write leaves the previous content intact, and the target
file's permission bits survive the replacement.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Same ceiling as core.governance.harness_scanner: a settings file
# larger than this is itself a finding, not something to slurp.
MAX_JSON_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class LoadResult:
    """Outcome of a tolerant JSON load.

    ``data`` is the parsed top-level object on success, ``None``
    otherwise; ``error`` names the failure (``missing``, ``oversized``,
    ``unreadable``, ``invalid-json``, ``not-an-object``) or is ``None``.
    """

    data: dict[str, Any] | None
    error: str | None

    @property
    def ok(self) -> bool:
        return self.error is None


def load_json(path: Path) -> LoadResult:
    """Read ``path`` as a JSON object without ever raising."""
    try:
        if not path.is_file():
            return LoadResult(None, "missing")
        if path.stat().st_size > MAX_JSON_BYTES:
            return LoadResult(None, "oversized")
        raw = path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError):
        return LoadResult(None, "unreadable")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return LoadResult(None, "invalid-json")
    if not isinstance(data, dict):
        return LoadResult(None, "not-an-object")
    return LoadResult(data, None)


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    """Write ``data`` to ``path`` via same-dir tmp + ``os.replace``.

    Raises on failure (callers decide policy); guarantees the target is
    either the previous content or the complete new content, never a
    partial write. Existing permission bits on ``path`` are preserved.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    previous_mode = _current_mode(path)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if previous_mode is not None:
            os.chmod(tmp_name, previous_mode)
        os.replace(tmp_name, path)
    except BaseException:
        _unlink_quiet(tmp_name)
        raise


def merge_unique(*sequences: Iterable[str]) -> list[str]:
    """Order-preserving union; the FIRST occurrence of a value wins.

    Callers encode precedence by argument order — putting the
    operator's entries first keeps them ahead of shipped defaults, the
    same contract as ``mergeUnique`` in ``installer/hard-deny.js``.
    """
    seen: set[str] = set()
    merged: list[str] = []
    for sequence in sequences:
        for value in sequence:
            if value not in seen:
                seen.add(value)
                merged.append(value)
    return merged


def _current_mode(path: Path) -> int | None:
    try:
        return path.stat().st_mode & 0o7777
    except OSError:
        return None


def _unlink_quiet(name: str) -> None:
    with contextlib.suppress(OSError):
        os.unlink(name)
