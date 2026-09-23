"""Filesystem roots of the decisions layer, each with an env override.

Resolved at call time (never cached at import) so tests and sandboxes
redirect them with an environment variable.
"""

from __future__ import annotations

import os
from pathlib import Path

CACHE_ENV = "ARKA_DECISIONS_CACHE_DIR"
TELEMETRY_ENV = "ARKA_DECISIONS_TELEMETRY_PATH"


def cache_root() -> Path:
    """``~/.arkaos/cache/decisions`` unless ``ARKA_DECISIONS_CACHE_DIR`` is set."""
    override = os.environ.get(CACHE_ENV, "").strip()
    if override:
        return Path(override)
    return Path.home() / ".arkaos" / "cache" / "decisions"


def spool_dir() -> Path:
    """Where shadow calls wait for their detached worker."""
    return cache_root() / "spool"


def telemetry_path() -> Path:
    """``~/.arkaos/telemetry/decisions.jsonl`` unless overridden."""
    override = os.environ.get(TELEMETRY_ENV, "").strip()
    if override:
        return Path(override)
    return Path.home() / ".arkaos" / "telemetry" / "decisions.jsonl"


def repo_root() -> Path:
    """The checkout this package runs from (PYTHONPATH for workers)."""
    return Path(__file__).resolve().parents[2]
