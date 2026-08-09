"""Canonical resolver for ArkaOS user-local data paths.

User-mutable data lives under ~/.arkaos/. The installed skill bundle at
~/.claude/skills/arka/ is read-only and installer-managed. Two historical
paths still receive user writes in some installs:

    ~/.claude/skills/arka/projects/*.md
    ~/.claude/skills/arka/knowledge/ecosystems.json

This module returns the canonical new path when present, falls back to the
legacy path with a one-shot deprecation warning, and returns None when
neither exists. Callers treat None as empty. See ADR
docs/adr/2026-04-17-user-data-separation.md.

``ARKA_PROJECTS_DIR`` overrides the projects directory ahead of that whole
chain, for both reads and writes. Legacy fallback sunsets in v2.21.0.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_LEGACY_SKILLS_ROOT = Path.home() / ".claude" / "skills" / "arka"
_USER_DATA_ROOT = Path.home() / ".arkaos"

#: Operator/test override for the projects directory. Read at call time,
#: never cached, so a test can set it per-case.
PROJECTS_DIR_ENV = "ARKA_PROJECTS_DIR"

_warned: set[str] = set()


def _projects_dir_override() -> Path | None:
    """The ``ARKA_PROJECTS_DIR`` override, or None when unset.

    UNCONDITIONAL when set: it never falls through to ~/.arkaos or the
    legacy path, and it is returned whether or not it exists yet. Both
    properties are the point rather than side effects — the override
    exists so a caller can guarantee it is NOT touching the operator's
    real descriptors (#497/#510: an unstubbed run_sync resolved the real
    ~/.arkaos/projects and handed every registered project directory to
    five writers). A fallback on a missing directory would put those
    writes straight back where they were.

    Applied to ``projects_dir()`` AND ``projects_dir_for_write()``: an
    override that redirects reads while writes still land in the real
    home is worse than no override at all, because it reads as isolation.
    """
    raw = os.environ.get(PROJECTS_DIR_ENV, "").strip()
    return Path(raw).expanduser() if raw else None


def user_data_root() -> Path:
    """Root directory for ArkaOS user-local state."""
    return _USER_DATA_ROOT


def projects_dir() -> Path | None:
    """Resolve the user projects directory.

    Returns the ``ARKA_PROJECTS_DIR`` override when set, else the new path
    when it exists, else the legacy path with a one-shot deprecation
    warning, else None.
    """
    override = _projects_dir_override()
    if override is not None:
        return override
    new = _USER_DATA_ROOT / "projects"
    legacy = _LEGACY_SKILLS_ROOT / "projects"
    return _resolve_with_fallback("projects_dir", new, legacy)


def ecosystems_file() -> Path | None:
    """Resolve the ecosystems registry file.

    Returns the new path when it exists, else the legacy path with a
    one-shot deprecation warning, else None.
    """
    new = _USER_DATA_ROOT / "ecosystems.json"
    legacy = _LEGACY_SKILLS_ROOT / "knowledge" / "ecosystems.json"
    return _resolve_with_fallback("ecosystems_file", new, legacy)


def projects_dir_for_write() -> Path:
    """Return the write target for user project descriptors.

    The ``ARKA_PROJECTS_DIR`` override wins; otherwise writers always
    target the new path. The directory is created if absent.
    """
    target = _projects_dir_override() or (_USER_DATA_ROOT / "projects")
    target.mkdir(parents=True, exist_ok=True)
    return target


def ecosystems_file_for_write() -> Path:
    """Return the write target for the ecosystems registry.

    Writers always target the new path. Parent directory is created if absent.
    """
    new = _USER_DATA_ROOT / "ecosystems.json"
    new.parent.mkdir(parents=True, exist_ok=True)
    return new


def legacy_projects_dir() -> Path:
    """Legacy projects directory (for migration tooling only)."""
    return _LEGACY_SKILLS_ROOT / "projects"


def legacy_ecosystems_file() -> Path:
    """Legacy ecosystems file (for migration tooling only)."""
    return _LEGACY_SKILLS_ROOT / "knowledge" / "ecosystems.json"


def reset_warnings() -> None:
    """Clear the per-process deprecation warning cache.

    Intended for tests. Real runtime should emit each warning exactly once.
    """
    _warned.clear()


def _resolve_with_fallback(kind: str, new: Path, legacy: Path) -> Path | None:
    if new.exists():
        return new
    if legacy.exists():
        _warn_once(kind, legacy)
        return legacy
    return None


def _warn_once(kind: str, legacy: Path) -> None:
    if kind in _warned:
        return
    _warned.add(kind)
    logger.warning(
        "ArkaOS: reading %s from legacy location %s. "
        "This path is deprecated and will be removed in v2.21.0. "
        "Run `npx arkaos@latest migrate-user-data` or `/arka update` to "
        "move your data to ~/.arkaos/.",
        kind,
        legacy,
    )
