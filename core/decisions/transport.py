"""OpenRouter Decisions transport (operator decision 2026-09-23: only one).

Key resolution mirrors ``core/runtime/openrouter_provider.py``:
``OPENROUTER_API_KEY`` env, then ``~/.arkaos/keys.json``. No key, no
transport — callers fall back to their heuristic.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from core.decisions.config import DecisionsConfig
from core.runtime.openrouter_provider import _APP_HEADERS

DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_MODEL = "jev-1.13"
MODEL_ALIASES: dict[str, str] = {"jev-1.13": "typesafe/jev-1.13"}
ENV_KEY = "OPENROUTER_API_KEY"
_KEYS_PATH = Path.home() / ".arkaos" / "keys.json"
# OpenRouter provider routing prefs sent with every call: no data
# collection by the upstream provider (accepted by the alpha endpoint,
# smoke test 2026-09-23 — HTTP 200).
PROVIDER_PREFS: dict[str, str] = {"data_collection": "deny"}


@dataclass(frozen=True)
class Transport:
    """Everything a decision POST needs. Key and headers stay out of repr."""

    name: str
    url: str
    key: str = field(repr=False)
    model: str
    headers: dict[str, str] = field(repr=False, default_factory=dict)
    body_extras: dict[str, object] = field(default_factory=dict)


def resolve_model(raw: str | None = None) -> str:
    """Alias → OpenRouter id; a literal id passes through unchanged."""
    name = (raw or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    return MODEL_ALIASES.get(name, name)


def _read_key_from_keys_json() -> str:
    try:
        data = json.loads(_KEYS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    value = data.get(ENV_KEY, "") if isinstance(data, dict) else ""
    return value.strip() if isinstance(value, str) else ""


def _resolve_key() -> str:
    return os.environ.get(ENV_KEY, "").strip() or _read_key_from_keys_json()


def configured_model() -> str | None:
    """``decisions.model`` from ``models.yaml`` (Model Fabric); None → default.

    One resolver for the hook and the shadow worker. Never raises: an
    unreadable or invalid ``models.yaml`` keeps :data:`DEFAULT_MODEL`.
    """
    try:
        from core.runtime.model_router import load_config

        return load_config()[0].decisions.model
    except Exception:
        return None


def resolve_transport(cfg: DecisionsConfig, model: str | None = None) -> Transport | None:
    """The OpenRouter transport, or None (unknown transport or no key)."""
    if cfg.transport != "openrouter":
        return None
    key = _resolve_key()
    if not key:
        return None
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        **_APP_HEADERS,
    }
    return Transport(
        name="openrouter", url=DECISIONS_URL, key=key,
        model=resolve_model(model), headers=headers,
        body_extras={"provider": dict(PROVIDER_PREFS)},
    )
