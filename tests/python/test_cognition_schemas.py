"""Tests for ArkaOS Cognitive Layer Pydantic schemas."""

from datetime import UTC, datetime

import pytest

from core.cognition.memory import ActionableInsight, KnowledgeEntry, RawCapture

# --- Helpers ---

def make_raw_capture(**overrides) -> RawCapture:
    defaults = {
        "session_id": "sess-abc123",
        "project_path": "/Users/dev/my-project",
        "project_name": "my-project",
        "category": "decision",
        "content": "Chose PostgreSQL over MySQL for JSONB support.",
    }
    defaults.update(overrides)
    return RawCapture(**defaults)


def make_knowledge_entry(**overrides) -> KnowledgeEntry:
    defaults = {
        "title": "Use JSONB for flexible schemas",
        "category": "pattern",
        "content": "PostgreSQL JSONB outperforms MySQL JSON for complex queries.",
        "source_project": "my-project",
    }
    defaults.update(overrides)
    return KnowledgeEntry(**defaults)


def make_actionable_insight(**overrides) -> ActionableInsight:
    defaults = {
        "project": "my-project",
        "trigger": "N+1 queries detected in OrderService",
        "category": "technical",
        "severity": "improve",
        "title": "Eager-load relationships in OrderService",
        "description": "Multiple queries fired per order item.",
        "recommendation": "Add ->with('items') to the query.",
        "context": "Detected during code review of PR #42.",
    }
    defaults.update(overrides)
    return ActionableInsight(**defaults)


# --- RawCapture Tests ---

class TestRawCapture:
    def test_valid_creation_auto_generates_id_and_timestamp(self) -> None:
        capture = make_raw_capture()
        assert capture.id  # non-empty UUID string
        assert isinstance(capture.timestamp, datetime)
        assert capture.timestamp.tzinfo is not None

    def test_valid_categories(self) -> None:
        for cat in ("decision", "solution", "pattern", "error", "config"):
            capture = make_raw_capture(category=cat)
            assert capture.category == cat

    def test_invalid_category_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid category"):
            make_raw_capture(category="unknown")

    def test_context_defaults_to_empty_dict(self) -> None:
        capture = make_raw_capture()
        assert capture.context == {}

    def test_custom_context_accepted(self) -> None:
        capture = make_raw_capture(context={"file": "main.py", "line": 42})
        assert capture.context["file"] == "main.py"

    def test_two_captures_have_different_ids(self) -> None:
        a = make_raw_capture()
        b = make_raw_capture()
        assert a.id != b.id


# --- KnowledgeEntry Tests ---

class TestKnowledgeEntry:
    def test_valid_creation_auto_generates_fields(self) -> None:
        entry = make_knowledge_entry()
        assert entry.id
        assert isinstance(entry.created_at, datetime)
        assert isinstance(entry.updated_at, datetime)
        assert entry.created_at.tzinfo is not None

    def test_valid_categories(self) -> None:
        for cat in ("pattern", "anti_pattern", "solution", "architecture",
                    "config", "lesson", "improvement"):
            entry = make_knowledge_entry(category=cat)
            assert entry.category == cat

    def test_invalid_category_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid category"):
            make_knowledge_entry(category="random")

    def test_defaults(self) -> None:
        entry = make_knowledge_entry()
        assert entry.tags == []
        assert entry.stacks == []
        assert entry.applicable_to == "any"
        assert entry.confidence == 0.5
        assert entry.times_used == 0

    def test_confidence_clamped_above_max(self) -> None:
        entry = make_knowledge_entry(confidence=1.5)
        assert entry.confidence == 1.0

    def test_confidence_clamped_below_min(self) -> None:
        entry = make_knowledge_entry(confidence=-0.3)
        assert entry.confidence == 0.0

    def test_confidence_valid_range_unchanged(self) -> None:
        entry = make_knowledge_entry(confidence=0.75)
        assert entry.confidence == 0.75

    def test_tags_and_stacks_stored(self) -> None:
        entry = make_knowledge_entry(tags=["laravel", "cache"], stacks=["PHP", "Redis"])
        assert "laravel" in entry.tags
        assert "Redis" in entry.stacks


# --- ActionableInsight Tests ---

class TestActionableInsight:
    def test_valid_creation_auto_generates_fields(self) -> None:
        insight = make_actionable_insight()
        assert insight.id
        assert isinstance(insight.date_generated, datetime)
        assert insight.date_generated.tzinfo is not None

    def test_default_status_is_pending(self) -> None:
        insight = make_actionable_insight()
        assert insight.status == "pending"

    def test_presented_at_defaults_to_none(self) -> None:
        insight = make_actionable_insight()
        assert insight.presented_at is None

    def test_valid_categories(self) -> None:
        for cat in ("business", "technical", "ux", "strategy"):
            insight = make_actionable_insight(category=cat)
            assert insight.category == cat

    def test_invalid_category_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid category"):
            make_actionable_insight(category="ops")

    def test_valid_severities(self) -> None:
        for sev in ("rethink", "improve", "consider"):
            insight = make_actionable_insight(severity=sev)
            assert insight.severity == sev

    def test_invalid_severity_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid severity"):
            make_actionable_insight(severity="critical")

    def test_valid_statuses(self) -> None:
        for status in ("pending", "presented", "accepted", "dismissed"):
            insight = make_actionable_insight(status=status)
            assert insight.status == status

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid status"):
            make_actionable_insight(status="archived")

    def test_presented_at_can_be_set(self) -> None:
        now = datetime.now(UTC)
        insight = make_actionable_insight(presented_at=now)
        assert insight.presented_at == now

    def test_two_insights_have_different_ids(self) -> None:
        a = make_actionable_insight()
        b = make_actionable_insight()
        assert a.id != b.id


class TestInstinctFields:
    """confidence / scope / evidence_count — the ECC instinct model."""

    def test_defaults(self) -> None:
        i = make_actionable_insight()
        assert i.confidence == 0.5
        assert i.scope == "project"
        assert i.evidence_count == 1

    def test_confidence_clamps_to_the_band_ceiling(self) -> None:
        assert make_actionable_insight(confidence=1.0).confidence == 0.9
        assert make_actionable_insight(confidence=5.0).confidence == 0.9

    def test_confidence_clamps_to_the_band_floor(self) -> None:
        assert make_actionable_insight(confidence=0.0).confidence == 0.3
        assert make_actionable_insight(confidence=-1.0).confidence == 0.3

    def test_confidence_within_band_is_untouched(self) -> None:
        assert make_actionable_insight(confidence=0.65).confidence == 0.65

    def test_valid_scopes(self) -> None:
        assert make_actionable_insight(scope="global").scope == "global"
        assert make_actionable_insight(scope="project").scope == "project"

    def test_invalid_scope_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid scope"):
            make_actionable_insight(scope="universe")

    def test_evidence_count_floors_at_one(self) -> None:
        assert make_actionable_insight(evidence_count=0).evidence_count == 1
        assert make_actionable_insight(evidence_count=-3).evidence_count == 1
        assert make_actionable_insight(evidence_count=7).evidence_count == 7
