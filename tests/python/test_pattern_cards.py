"""Tests for core.knowledge.pattern_cards (PR4 Squad Intelligence).

Pattern Library — append-only JSONL store of "we have already built
this" cards. Used by the Synapse L7.5 layer to inject prior
implementations as context when the operator starts a new feature
spec. Keyword + tag match for v1 (semantic similarity via embeddings
lands in v3.75.x).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


pattern_cards = pytest.importorskip(
    "core.knowledge.pattern_cards",
    reason="pattern_cards not yet implemented (TDD red phase)",
)
PatternCard = pattern_cards.PatternCard
record_pattern = pattern_cards.record_pattern
query_patterns = pattern_cards.query_patterns


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(pattern_cards, "PATTERNS_PATH", tmp_path / "cards.jsonl")
    return tmp_path / "cards.jsonl"


def _make_card(
    *,
    id: str = "test-pattern-1",
    name: str = "Test Pattern",
    feature_keywords: list[str] | None = None,
    description: str = "A test pattern",
    stack: list[str] | None = None,
    files: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
    edge_cases: list[str] | None = None,
    references: list[str] | None = None,
    projects_using: list[str] | None = None,
    created_at: datetime | None = None,
) -> PatternCard:
    ts = (created_at or datetime.now(timezone.utc)).isoformat()
    return PatternCard(
        id=id,
        name=name,
        feature_keywords=feature_keywords if feature_keywords is not None else ["test"],
        description=description,
        stack=stack if stack is not None else ["python"],
        files=files if files is not None else [],
        acceptance_criteria=acceptance_criteria if acceptance_criteria is not None else [],
        edge_cases=edge_cases if edge_cases is not None else [],
        references=references if references is not None else [],
        projects_using=projects_using if projects_using is not None else ["arkaos"],
        created_at=ts,
        last_updated=ts,
    )


# ─── Storage roundtrip ─────────────────────────────────────────────────


def test_record_and_query_roundtrip(tmp_store):
    card = _make_card(feature_keywords=["auth", "magic-link"])
    record_pattern(card)
    results = query_patterns(keywords=["auth"])
    assert len(results) == 1
    assert results[0].id == "test-pattern-1"


def test_query_missing_keyword_returns_empty(tmp_store):
    record_pattern(_make_card(feature_keywords=["auth"]))
    assert query_patterns(keywords=["unrelated"]) == []


def test_query_returns_recent_first(tmp_store):
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    old = _make_card(id="old", feature_keywords=["match"], created_at=now - timedelta(days=2))
    new = _make_card(id="new", feature_keywords=["match"], created_at=now)
    record_pattern(old)
    record_pattern(new)
    results = query_patterns(keywords=["match"])
    assert results[0].id == "new"
    assert results[1].id == "old"


def test_record_dedup_by_id(tmp_store):
    """Re-recording the same id replaces the previous entry, not duplicates."""
    record_pattern(_make_card(id="dup", description="v1"))
    record_pattern(_make_card(id="dup", description="v2"))
    results = query_patterns(keywords=["test"])
    matches = [r for r in results if r.id == "dup"]
    assert len(matches) == 1
    assert matches[0].description == "v2"


# ─── Filters ────────────────────────────────────────────────────────────


def test_query_keywords_case_insensitive(tmp_store):
    record_pattern(_make_card(feature_keywords=["Authentication", "OAuth"]))
    assert len(query_patterns(keywords=["authentication"])) == 1
    assert len(query_patterns(keywords=["OAUTH"])) == 1


def test_query_keywords_substring_match(tmp_store):
    """Partial keyword match should also surface a card."""
    record_pattern(_make_card(feature_keywords=["magic-link-auth"]))
    assert len(query_patterns(keywords=["magic"])) == 1


def test_query_keyword_matches_name_or_description(tmp_store):
    record_pattern(
        _make_card(
            name="QG Experience Persistence",
            description="Records REJECTED verdicts to agent logs",
            feature_keywords=["unrelated"],
        )
    )
    # Should match via name
    assert len(query_patterns(keywords=["experience"])) == 1
    # Should match via description
    assert len(query_patterns(keywords=["rejected"])) == 1


def test_query_tags_filter(tmp_store):
    record_pattern(_make_card(id="a", stack=["python", "synapse"]))
    record_pattern(_make_card(id="b", stack=["javascript"]))
    record_pattern(_make_card(id="c", stack=["python", "constitution"]))
    results = query_patterns(tags=["python"])
    ids = sorted(r.id for r in results)
    assert ids == ["a", "c"]


def test_query_keywords_and_tags_intersect(tmp_store):
    record_pattern(_make_card(id="a", feature_keywords=["auth"], stack=["python"]))
    record_pattern(_make_card(id="b", feature_keywords=["auth"], stack=["javascript"]))
    record_pattern(_make_card(id="c", feature_keywords=["other"], stack=["python"]))
    results = query_patterns(keywords=["auth"], tags=["python"])
    assert len(results) == 1
    assert results[0].id == "a"


def test_query_limit(tmp_store):
    for i in range(10):
        record_pattern(_make_card(id=f"p-{i}", feature_keywords=["common"]))
    results = query_patterns(keywords=["common"], limit=3)
    assert len(results) == 3


def test_empty_query_returns_all_by_recency(tmp_store):
    record_pattern(_make_card(id="a"))
    record_pattern(_make_card(id="b"))
    results = query_patterns()
    assert len(results) == 2


# ─── Robustness ────────────────────────────────────────────────────────


def test_missing_file_returns_empty(tmp_store):
    assert query_patterns(keywords=["anything"]) == []


def test_malformed_jsonl_skipped(tmp_store):
    record_pattern(_make_card(id="valid"))
    with tmp_store.open("a", encoding="utf-8") as fh:
        fh.write("not valid json\n")
    record_pattern(_make_card(id="valid-2"))
    results = query_patterns()
    ids = sorted(r.id for r in results)
    assert "valid" in ids
    assert "valid-2" in ids


# ─── Path safety ────────────────────────────────────────────────────────


def test_record_rejects_unsafe_id(tmp_store):
    """ID with path-traversal chars should be silently rejected."""
    card = _make_card(id="../../evil")
    record_pattern(card)
    results = query_patterns(keywords=["test"])
    # No card with that id should exist
    assert not any(r.id == "../../evil" for r in results)


def test_record_rejects_empty_id(tmp_store):
    card = _make_card(id="")
    record_pattern(card)
    results = query_patterns()
    assert not any(r.id == "" for r in results)


# ─── PatternCard shape ──────────────────────────────────────────────────


def test_pattern_card_has_required_fields():
    card = _make_card()
    for field in (
        "id", "name", "feature_keywords", "description", "stack",
        "files", "acceptance_criteria", "edge_cases", "references",
        "projects_using", "created_at", "last_updated",
    ):
        assert hasattr(card, field), f"missing field: {field}"


def test_pattern_to_dict_serializes(tmp_store):
    card = _make_card(
        files=["core/governance/agent_experiences.py"],
        acceptance_criteria=["Stores REJECTED verdicts"],
    )
    d = pattern_cards.pattern_to_dict(card)
    assert d["id"] == "test-pattern-1"
    assert d["files"] == ["core/governance/agent_experiences.py"]
    assert d["acceptance_criteria"] == ["Stores REJECTED verdicts"]
