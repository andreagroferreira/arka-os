"""Canonical harness paths, resolved at call time.

Every path here takes an explicit override — ``home`` for the
user-tree paths (defaulting to ``Path.home()``), ``root`` for
``hooks_dir`` — resolved at CALL time, so tests and the C2 manager can
operate on an alternate tree without monkeypatching. Nothing here is a
module-level constant: paths captured at import bind to whatever root
the importing process started with, which is exactly the split-root
failure mode PR-A2 closed (``ARKAOS_ROOT`` in the shell pointing one
way, ``.repo-path`` another).
"""

from __future__ import annotations

from pathlib import Path

from core.hooks._shared import resolve_arkaos_root


def claude_home(home: Path | None = None) -> Path:
    """``~/.claude`` — the Claude Code configuration tree."""
    return (home or Path.home()) / ".claude"


def claude_settings_path(home: Path | None = None) -> Path:
    """``~/.claude/settings.json`` — the executed harness surface."""
    return claude_home(home) / "settings.json"


def claude_global_md_path(home: Path | None = None) -> Path:
    """``~/.claude/CLAUDE.md`` — global instructions (C5 managed block)."""
    return claude_home(home) / "CLAUDE.md"


def arkaos_home(home: Path | None = None) -> Path:
    """``~/.arkaos`` — ArkaOS user-mutable data."""
    return (home or Path.home()) / ".arkaos"


def ownership_manifest_path(home: Path | None = None) -> Path:
    """``~/.arkaos/ownership.json`` — the C2 ownership manifest."""
    return arkaos_home(home) / "ownership.json"


def audit_dir(home: Path | None = None) -> Path:
    """``~/.arkaos/audit`` — mutation audit trails."""
    return arkaos_home(home) / "audit"


def harness_audit_log_path(home: Path | None = None) -> Path:
    """``~/.arkaos/audit/harness-mutations.jsonl`` (written by C2)."""
    return audit_dir(home) / "harness-mutations.jsonl"


def hard_deny_extension_path(home: Path | None = None) -> Path:
    """``~/.arkaos/hard-deny.json`` — operator hard-deny extensions."""
    return arkaos_home(home) / "hard-deny.json"


def arkaos_config_path(home: Path | None = None) -> Path:
    """``~/.arkaos/config.json`` — feature flags (hardEnforcement, ...)."""
    return arkaos_home(home) / "config.json"


def hooks_dir(root: str | None = None) -> Path:
    """``<arkaos-root>/config/hooks`` — the deployed hook scripts.

    The root goes through the PR-A2 validated chain
    (``core.hooks._shared.resolve_arkaos_root``) at call time; passing
    ``root`` overrides it for tests.
    """
    return Path(root or resolve_arkaos_root()) / "config" / "hooks"
