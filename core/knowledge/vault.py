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


CONFIG_SOURCE = "~/.arkaos/config.json"
ENV_SOURCE = "ARKAOS_VAULT"


def resolve_vault_with_source(
    config_path: str | os.PathLike[str] | None = None,
) -> tuple[Path | None, str]:
    """``(vault, source)`` — the path and the thing that supplied it.

    The source travels WITH the path so a caller announcing which
    configuration won cannot drift from the truth: this resolver answers
    from two places, and a caller that assumes the first will misreport
    the second. ``source`` is ``""`` when nothing answered.
    """
    cfg = Path(CONFIG_PATH if config_path is None else config_path)
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
        configured = str((data.get("knowledge") or {}).get("vaultPath") or "").strip()
    except (OSError, json.JSONDecodeError, AttributeError):
        configured = ""
    if configured and Path(configured).exists():
        return Path(configured), CONFIG_SOURCE

    env_vault = os.environ.get("ARKAOS_VAULT", "").strip()
    if env_vault and Path(env_vault).exists():
        return Path(env_vault), ENV_SOURCE
    return None, ""


def resolve_vault_path(config_path: str | os.PathLike[str] | None = None) -> Path | None:
    """The configured vault, or ``None``. Config first, then env.

    ``config_path`` is injectable so a caller that owns its own config
    location — and the tests that pin this behaviour — need not patch
    module state to exercise it. Callers that report which source won
    should use :func:`resolve_vault_with_source` instead.
    """
    return resolve_vault_with_source(config_path)[0]
