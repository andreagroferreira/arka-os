"""Knowledge decay — "the graph that forgets" (F1-C1, ruflo teardown).

Read-time exponential decay for knowledge stores (pattern cards,
recipes, agent experiences): records are NEVER deleted by decay — they
fade out of context injection unless reinforcement re-touches them.
Verified semantics from the claude-flow v3 teardown: rows carry a
last-reinforced timestamp; weight halves every ``half_life_days``;
consumers drop records below a floor from injection only.

Config (``~/.arkaos/config.json``):
    knowledge.decay.enabled       default True
    knowledge.decay.halfLifeDays  default 60
Env kill-switch: ``ARKA_KNOWLEDGE_DECAY=0``.
"""

from __future__ import annotations

import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_HALF_LIFE_DAYS = 60.0
INJECTION_FLOOR = 0.15  # below this weight a record fades from injection
_CONFIG_PATH = Path.home() / ".arkaos" / "config.json"


def _decay_config() -> dict:
    try:
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    knowledge = data.get("knowledge")
    if not isinstance(knowledge, dict):
        return {}
    section = knowledge.get("decay")
    return section if isinstance(section, dict) else {}


def decay_enabled() -> bool:
    if os.environ.get("ARKA_KNOWLEDGE_DECAY", "").strip() == "0":
        return False
    return bool(_decay_config().get("enabled", True))


def half_life_days() -> float:
    value = _decay_config().get("halfLifeDays", DEFAULT_HALF_LIFE_DAYS)
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return DEFAULT_HALF_LIFE_DAYS
    return parsed if parsed > 0 else DEFAULT_HALF_LIFE_DAYS


def _parse_ts(ts: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def decayed_weight(
    last_reinforced_iso: str,
    half_life: float | None = None,
    now: datetime | None = None,
) -> float:
    """Weight in (0, 1]: 1.0 fresh, 0.5 after one half-life, and so on.

    An unparseable/empty timestamp returns the floor (not 0.0): a record
    with unknown age is dimmed, never silently erased from ranking.
    When decay is disabled every record weighs 1.0.
    """
    if not decay_enabled():
        return 1.0
    parsed = _parse_ts(last_reinforced_iso or "")
    if parsed is None:
        return INJECTION_FLOOR
    current = now or datetime.now(UTC)
    age_days = max(0.0, (current - parsed).total_seconds() / 86400.0)
    return math.pow(0.5, age_days / (half_life or half_life_days()))
