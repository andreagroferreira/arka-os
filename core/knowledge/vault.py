"""Where the operator's Obsidian vault lives, resolved from configuration.

``knowledge.vaultPath`` in ``~/.arkaos/config.json`` is the portable
source of truth (identical on macOS/Windows/Linux) and ``ARKAOS_VAULT``
covers per-session overrides.

There is deliberately NO guessed fallback. The hardcoded
``~/Documents/Personal`` this replaces was one developer's personal
layout: on every other machine it resolved to nothing, and the failure
was invisible because the caller simply carried on with a different
corpus. ``None`` is the honest answer to "not configured". Callers are
expected to say so rather than substitute another corpus — see
``scripts/knowledge-index.py``, which names the source it chose on stderr
and exits non-zero when nothing answers.

This resolver is not the only path a caller may consult: the indexer
still honours two deprecated legacy files AFTER this one, and announces
them as deprecated when they win.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_PATH = Path.home() / ".arkaos" / "config.json"


def resolve_vault_path(config_path: str | os.PathLike[str] | None = None) -> Path | None:
    """The configured vault, or ``None``. Config first, then env.

    ``config_path`` is injectable so a caller that owns its own config
    location — and the tests that pin this behaviour — need not patch
    module state to exercise it.
    """
    cfg = Path(CONFIG_PATH if config_path is None else config_path)
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
        configured = str((data.get("knowledge") or {}).get("vaultPath") or "").strip()
    except (OSError, json.JSONDecodeError, AttributeError):
        configured = ""
    if configured and Path(configured).exists():
        return Path(configured)

    env_vault = os.environ.get("ARKAOS_VAULT", "").strip()
    if env_vault and Path(env_vault).exists():
        return Path(env_vault)
    return None
