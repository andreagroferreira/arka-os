"""Tests for core.shared.decay + pattern-card decay integration (F1-C1)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from core.shared import decay
from core.shared.decay import INJECTION_FLOOR, decayed_weight, half_life_days

NOW = datetime(2026, 7, 11, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setattr(decay, "_CONFIG_PATH", tmp_path / ".arkaos" / "config.json")
    monkeypatch.delenv("ARKA_KNOWLEDGE_DECAY", raising=False)
    return tmp_path


def _iso(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat()


# ─── decayed_weight math ───────────────────────────────────────────────


def test_fresh_record_weighs_one():
    assert decayed_weight(_iso(0), now=NOW) == pytest.approx(1.0)


def test_one_half_life_halves():
    assert decayed_weight(_iso(60), now=NOW) == pytest.approx(0.5)


def test_two_half_lives_quarter():
    assert decayed_weight(_iso(120), now=NOW) == pytest.approx(0.25)


def test_unparseable_ts_dims_to_floor_never_zero():
    assert decayed_weight("not-a-date", now=NOW) == INJECTION_FLOOR
    assert decayed_weight("", now=NOW) == INJECTION_FLOOR


def test_naive_ts_normalized():
    naive = (NOW - timedelta(days=60)).replace(tzinfo=None).isoformat()
    assert decayed_weight(naive, now=NOW) == pytest.approx(0.5)


def test_future_ts_clamped_to_one():
    assert decayed_weight(_iso(-5), now=NOW) == pytest.approx(1.0)


# ─── configuration ─────────────────────────────────────────────────────


def test_env_kill_switch_disables(monkeypatch):
    monkeypatch.setenv("ARKA_KNOWLEDGE_DECAY", "0")
    assert decayed_weight(_iso(500), now=NOW) == 1.0


def test_config_disable(tmp_path):
    cfg = tmp_path / ".arkaos" / "config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"knowledge": {"decay": {"enabled": False}}}))
    assert decayed_weight(_iso(500), now=NOW) == 1.0


def test_config_half_life_override(tmp_path):
    cfg = tmp_path / ".arkaos" / "config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"knowledge": {"decay": {"halfLifeDays": 30}}}))
    assert half_life_days() == 30.0
    assert decayed_weight(_iso(30), now=NOW) == pytest.approx(0.5)


def test_invalid_half_life_falls_back(tmp_path):
    cfg = tmp_path / ".arkaos" / "config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"knowledge": {"decay": {"halfLifeDays": "junk"}}}))
    assert half_life_days() == 60.0
    cfg.write_text(json.dumps({"knowledge": {"decay": {"halfLifeDays": -3}}}))
    assert half_life_days() == 60.0


# ─── pattern-card integration ──────────────────────────────────────────


@pytest.fixture
def patterns(tmp_path, monkeypatch):
    from core.knowledge import pattern_cards

    monkeypatch.setattr(
        pattern_cards, "PATTERNS_PATH", tmp_path / "patterns" / "cards.jsonl"
    )
    return pattern_cards


def _card(patterns, cid: str, *, last_reinforced: str = "",
          last_updated: str = "") -> None:
    card = patterns.PatternCard(
        id=cid, name=f"Pattern {cid}", feature_keywords=["payment"],
        description="d", stack=["laravel"],
        created_at=_iso(300), last_updated=last_updated or _iso(300),
        last_reinforced=last_reinforced,
    )
    # record_pattern re-stamps last_updated — write directly to preserve
    # the aged fixture timestamps the decay math is being tested against.
    cards = patterns._load_all()
    cards.append(card)
    patterns._write_all(cards)


def test_faded_cards_drop_from_injection_not_disk(patterns):
    _card(patterns, "fresh", last_reinforced=_iso(1))
    _card(patterns, "ancient", last_updated=_iso(290))  # weight ~0 < floor
    results = patterns.query_patterns(keywords=["payment"])
    assert [c.id for c in results] == ["fresh"]
    assert len(patterns._load_all()) == 2  # disk untouched — fades, never deletes


def test_reinforcement_resurrects_ranking(patterns):
    _card(patterns, "old-but-used", last_updated=_iso(290))
    assert patterns.query_patterns(keywords=["payment"]) == []
    assert patterns.reinforce_pattern("old-but-used") is True
    results = patterns.query_patterns(keywords=["payment"])
    assert [c.id for c in results] == ["old-but-used"]
    assert results[0].use_count == 1
    assert results[0].last_reinforced != ""


def test_reinforce_missing_card_returns_false(patterns):
    assert patterns.reinforce_pattern("nope") is False
    assert patterns.reinforce_pattern("../evil") is False


def test_decay_disabled_restores_recency_order(patterns, monkeypatch):
    monkeypatch.setenv("ARKA_KNOWLEDGE_DECAY", "0")
    _card(patterns, "ancient", last_updated=_iso(290))
    results = patterns.query_patterns(keywords=["payment"])
    assert [c.id for c in results] == ["ancient"]  # flag off => old behaviour


def test_legacy_jsonl_lines_still_load(patterns):
    """Pre-C1 lines (no decay fields) must load with defaults."""
    patterns.PATTERNS_PATH.parent.mkdir(parents=True, exist_ok=True)
    legacy = {
        "id": "legacy", "name": "Legacy", "feature_keywords": ["payment"],
        "description": "d", "stack": [], "files": [],
        "acceptance_criteria": [], "edge_cases": [], "references": [],
        "projects_using": [], "created_at": _iso(1), "last_updated": _iso(1),
    }
    patterns.PATTERNS_PATH.write_text(json.dumps(legacy) + "\n")
    cards = patterns._load_all()
    assert cards[0].last_reinforced == ""
    assert cards[0].use_count == 0
    assert [c.id for c in patterns.query_patterns(keywords=["payment"])] == ["legacy"]


def test_query_hoists_config_reads(patterns, monkeypatch):
    """QG blocker B1: config parsed O(1) per query, never per card."""
    for i in range(50):
        _card(patterns, f"c{i}", last_reinforced=_iso(1))
    reads = {"n": 0}
    original = decay._decay_config

    def counting():
        reads["n"] += 1
        return original()

    monkeypatch.setattr(decay, "_decay_config", counting)
    patterns.query_patterns(keywords=["payment"])
    assert reads["n"] <= 3  # enabled + half-life resolution, never 2N+1


def test_floor_tie_with_null_last_updated_never_crashes(patterns):
    """QG blocker B2: two floor-tied cards, one with last_updated=None,
    must sort via the created_at fallback — master's behaviour."""
    patterns.PATTERNS_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        {"id": "a", "name": "A", "feature_keywords": ["payment"],
         "description": "d", "stack": [], "files": [],
         "acceptance_criteria": [], "edge_cases": [], "references": [],
         "projects_using": [], "created_at": _iso(1),
         "last_updated": None, "last_reinforced": "not-a-date"},
        {"id": "b", "name": "B", "feature_keywords": ["payment"],
         "description": "d", "stack": [], "files": [],
         "acceptance_criteria": [], "edge_cases": [], "references": [],
         "projects_using": [], "created_at": _iso(2),
         "last_updated": None, "last_reinforced": "also-not-a-date"},
    ]
    patterns.PATTERNS_PATH.write_text(
        "\n".join(json.dumps(entry) for entry in lines) + "\n"
    )
    results = patterns.query_patterns(keywords=["payment"])  # must not raise
    assert [c.id for c in results] == ["a", "b"]  # created_at fallback orders


# ─── post_tool_use stub reinforcement ──────────────────────────────────


def test_approved_existing_card_reinforces(patterns, monkeypatch):
    from core.hooks import post_tool_use

    _card(patterns, "checkout-flow", last_reinforced=_iso(1))
    post_tool_use._record_pattern_stub(
        "Quality Gate Verdict: APPROVED",
        "[arka:pattern-suggest checkout-flow Checkout Flow]",
    )
    card = next(c for c in patterns._load_all() if c.id == "checkout-flow")
    assert card.use_count == 1  # reinforced, not duplicated
    assert len(patterns._load_all()) == 1
