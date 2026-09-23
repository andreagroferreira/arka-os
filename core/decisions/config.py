"""Decisions config — the ``decisions`` block of ``~/.arkaos/config.json``.

Shape (every key optional; the seed lives in ``installer/config-seed.js``)::

    "decisions": {"enabled": true, "transport": "openrouter",
      "redactClients": true, "hookTimeoutMs": 1500,
      "cacheTtlSeconds": 86400,
      "thresholds": {"read": 0.6, "write": 0.75, "destructive": 0.9},
      "sites": {"topic-drift": "act",
                "route": {"mode": "act", "minConfidence": 0.7}}}

Loading never raises: a missing, oversized, corrupt or invalid file
yields the defaults. ``ARKA_BYPASS_DECISIONS=1`` turns every site off.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

if TYPE_CHECKING:
    from core.decisions.site import Site

Mode = Literal["off", "shadow", "act"]
MODES: frozenset[str] = frozenset({"off", "shadow", "act"})

# Default action thresholds by site risk. Read at decision time (never
# copied into a config instance) so a config override and this table
# stay the only two sources — pinned by test_write_threshold_is_load_bearing.
THRESHOLDS: dict[str, float] = {"read": 0.60, "write": 0.75, "destructive": 0.90}

CONFIG_PATH: Path = Path.home() / ".arkaos" / "config.json"
MAX_CONFIG_BYTES = 1_000_000
BYPASS_ENV = "ARKA_BYPASS_DECISIONS"


class SiteConfig(BaseModel):
    """Per-site override: mode, action threshold, call ceiling."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    mode: Mode = "act"
    min_confidence: float | None = Field(default=None, alias="minConfidence", ge=0.0, le=1.0)
    timeout_ms: int | None = Field(default=None, alias="timeoutMs", gt=0)

    @field_validator("mode", mode="before")
    @classmethod
    def _unknown_mode_is_off(cls, value: object) -> object:
        return value if isinstance(value, str) and value in MODES else "off"


class DecisionsConfig(BaseModel):
    """The whole ``decisions`` block with safe defaults."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    enabled: bool = True
    transport: str = "openrouter"
    redact_clients: bool = Field(default=True, alias="redactClients")
    hook_timeout_ms: int = Field(default=1500, alias="hookTimeoutMs", gt=0)
    cache_ttl_seconds: int = Field(default=86400, alias="cacheTtlSeconds", ge=0)
    thresholds: dict[str, float] = Field(default_factory=dict)
    sites: dict[str, SiteConfig] = Field(default_factory=dict)

    @field_validator("sites", mode="before")
    @classmethod
    def _coerce_sites(cls, value: object) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        out: dict[str, Any] = {}
        for name, raw in value.items():
            if isinstance(raw, str):
                out[str(name)] = {"mode": raw}
            elif isinstance(raw, dict):
                out[str(name)] = raw
            else:
                out[str(name)] = {"mode": "off"}
        return out


def load_decisions_config(path: Path | None = None) -> DecisionsConfig:
    """Read the ``decisions`` block; any failure returns the defaults."""
    target = path or CONFIG_PATH
    try:
        if target.stat().st_size > MAX_CONFIG_BYTES:
            return DecisionsConfig()
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return DecisionsConfig()
    block = data.get("decisions") if isinstance(data, dict) else None
    if not isinstance(block, dict):
        return DecisionsConfig()
    try:
        return DecisionsConfig.model_validate(block)
    except ValidationError:
        return DecisionsConfig()


def bypassed() -> bool:
    """Global kill-switch for diagnosis: ``ARKA_BYPASS_DECISIONS=1``."""
    return os.environ.get(BYPASS_ENV, "").strip() == "1"


def site_mode(cfg: DecisionsConfig, site: Site) -> Mode:
    """Effective mode: bypass/disabled → off, else config, else site default."""
    if bypassed() or not cfg.enabled:
        return "off"
    override = cfg.sites.get(site.name)
    return override.mode if override is not None else site.default_mode


def threshold_for(cfg: DecisionsConfig, site: Site) -> float:
    """Site ``minConfidence``, else config threshold, else ``THRESHOLDS[risk]``."""
    override = cfg.sites.get(site.name)
    if override is not None and override.min_confidence is not None:
        return override.min_confidence
    if site.risk in cfg.thresholds:
        return cfg.thresholds[site.risk]
    return THRESHOLDS[site.risk]


def site_timeout_ms(cfg: DecisionsConfig, site: Site) -> int:
    """Site ``timeoutMs`` override, else the site's own ceiling."""
    override = cfg.sites.get(site.name)
    if override is not None and override.timeout_ms is not None:
        return override.timeout_ms
    return site.timeout_ms
