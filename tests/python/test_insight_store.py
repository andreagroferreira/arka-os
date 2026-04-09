"""Tests for InsightStore — SQLite CRUD store for actionable insights."""

import pytest
from datetime import datetime, timezone
from pathlib import Path

from core.cognition.insights import InsightStore
from core.cognition.memory.schemas import ActionableInsight


# --- Helpers ---

def make_insight(**overrides) -> ActionableInsight:
    defaults = {
        "project": "my-project",
        "trigger": "session_end",
        "category": "technical",
        "severity": "improve",
        "title": "Consider connection pooling",
        "description": "Database connections are not pooled.",
        "recommendation": "Use pgBouncer or SQLAlchemy pooling.",
        "context": "Observed repeated short-lived connections in logs.",
    }
    defaults.update(overrides)
    return ActionableInsight(**defaults)


# --- Fixtures ---

@pytest.fixture()
def store(tmp_path: Path) -> InsightStore:
    return InsightStore(db_path=str(tmp_path / "insights.db"))


# --- Tests ---

class TestInsightStoreSaveAndRetrieve:
    def test_save_and_get_pending_by_project(self, store: InsightStore) -> None:
        insight = make_insight()
        store.save(insight)
        results = store.get_pending("my-project")
        assert len(results) == 1
        assert results[0].id == insight.id
        assert results[0].title == insight.title

    def test_save_preserves_all_fields(self, store: InsightStore) -> None:
        insight = make_insight(
            trigger="daily_review",
            category="business",
            severity="rethink",
            title="Rethink pricing model",
            description="Freemium is causing churn.",
            recommendation="Move to usage-based pricing.",
            context="Q3 churn data shows 40% drop-off.",
        )
        store.save(insight)
        results = store.get_pending("my-project")
        r = results[0]
        assert r.trigger == "daily_review"
        assert r.category == "business"
        assert r.severity == "rethink"
        assert r.title == "Rethink pricing model"
        assert r.recommendation == "Move to usage-based pricing."

    def test_save_replace_overwrites_existing(self, store: InsightStore) -> None:
        insight = make_insight()
        store.save(insight)
        updated = ActionableInsight(
            id=insight.id,
            project=insight.project,
            trigger=insight.trigger,
            date_generated=insight.date_generated,
            category=insight.category,
            severity=insight.severity,
            title="Updated title",
            description=insight.description,
            recommendation=insight.recommendation,
            context=insight.context,
        )
        store.save(updated)
        results = store.get_pending("my-project")
        assert len(results) == 1
        assert results[0].title == "Updated title"

    def test_date_generated_is_timezone_aware(self, store: InsightStore) -> None:
        insight = make_insight()
        store.save(insight)
        results = store.get_pending("my-project")
        assert results[0].date_generated.tzinfo is not None


class TestGetPendingByProject:
    def test_filters_by_project(self, store: InsightStore) -> None:
        a = make_insight(project="project-a", title="A insight")
        b = make_insight(project="project-b", title="B insight")
        store.save(a)
        store.save(b)

        results = store.get_pending("project-a")
        assert len(results) == 1
        assert results[0].title == "A insight"

    def test_excludes_non_pending_statuses(self, store: InsightStore) -> None:
        pending = make_insight(title="pending one")
        presented = make_insight(title="presented one")
        accepted = make_insight(title="accepted one")
        dismissed = make_insight(title="dismissed one")

        store.save(pending)
        store.save(presented)
        store.save(accepted)
        store.save(dismissed)

        store.update_status(presented.id, "presented")
        store.update_status(accepted.id, "accepted")
        store.update_status(dismissed.id, "dismissed")

        results = store.get_pending("my-project")
        assert len(results) == 1
        assert results[0].title == "pending one"

    def test_returns_empty_for_unknown_project(self, store: InsightStore) -> None:
        results = store.get_pending("nonexistent")
        assert results == []

    def test_returns_multiple_pending_for_project(self, store: InsightStore) -> None:
        for i in range(3):
            store.save(make_insight(title=f"insight-{i}"))
        results = store.get_pending("my-project")
        assert len(results) == 3


class TestGetAllPending:
    def test_returns_pending_across_all_projects(self, store: InsightStore) -> None:
        store.save(make_insight(project="alpha", title="A"))
        store.save(make_insight(project="beta", title="B"))
        store.save(make_insight(project="gamma", title="C"))

        results = store.get_all_pending()
        assert len(results) == 3

    def test_excludes_non_pending_across_projects(self, store: InsightStore) -> None:
        pending = make_insight(project="alpha", title="keep")
        dismissed = make_insight(project="beta", title="skip")
        store.save(pending)
        store.save(dismissed)
        store.update_status(dismissed.id, "dismissed")

        results = store.get_all_pending()
        assert len(results) == 1
        assert results[0].title == "keep"

    def test_returns_empty_when_no_pending(self, store: InsightStore) -> None:
        insight = make_insight()
        store.save(insight)
        store.update_status(insight.id, "accepted")

        results = store.get_all_pending()
        assert results == []


class TestGetByProject:
    def test_returns_all_statuses_for_project(self, store: InsightStore) -> None:
        a = make_insight(title="pending")
        b = make_insight(title="dismissed")
        c = make_insight(title="accepted")
        store.save(a)
        store.save(b)
        store.save(c)
        store.update_status(b.id, "dismissed")
        store.update_status(c.id, "accepted")

        results = store.get_by_project("my-project")
        assert len(results) == 3

    def test_excludes_other_projects(self, store: InsightStore) -> None:
        store.save(make_insight(project="mine"))
        store.save(make_insight(project="theirs"))

        results = store.get_by_project("mine")
        assert len(results) == 1
        assert results[0].project == "mine"

    def test_returns_empty_for_unknown_project(self, store: InsightStore) -> None:
        results = store.get_by_project("ghost")
        assert results == []


class TestUpdateStatus:
    def test_update_status_changes_value(self, store: InsightStore) -> None:
        insight = make_insight()
        store.save(insight)
        store.update_status(insight.id, "accepted")

        results = store.get_by_project("my-project")
        assert results[0].status == "accepted"

    def test_update_status_removes_from_pending(self, store: InsightStore) -> None:
        insight = make_insight()
        store.save(insight)
        store.update_status(insight.id, "dismissed")

        assert store.get_pending("my-project") == []

    def test_update_status_nonexistent_id_is_safe(self, store: InsightStore) -> None:
        store.update_status("does-not-exist", "accepted")  # should not raise


class TestMarkPresented:
    def test_mark_presented_sets_status(self, store: InsightStore) -> None:
        insight = make_insight()
        store.save(insight)
        store.mark_presented([insight.id])

        results = store.get_by_project("my-project")
        assert results[0].status == "presented"

    def test_mark_presented_sets_presented_at_timestamp(self, store: InsightStore) -> None:
        insight = make_insight()
        store.save(insight)

        before = datetime.now(timezone.utc)
        store.mark_presented([insight.id])
        after = datetime.now(timezone.utc)

        results = store.get_by_project("my-project")
        assert results[0].presented_at is not None
        assert before <= results[0].presented_at <= after

    def test_mark_presented_multiple_ids(self, store: InsightStore) -> None:
        a = make_insight(title="A")
        b = make_insight(title="B")
        c = make_insight(title="C")
        store.save(a)
        store.save(b)
        store.save(c)

        store.mark_presented([a.id, b.id])

        pending = store.get_pending("my-project")
        assert len(pending) == 1
        assert pending[0].title == "C"

    def test_mark_presented_empty_list_is_safe(self, store: InsightStore) -> None:
        insight = make_insight()
        store.save(insight)
        store.mark_presented([])  # should not raise or change anything

        results = store.get_pending("my-project")
        assert len(results) == 1

    def test_presented_at_is_none_before_mark(self, store: InsightStore) -> None:
        insight = make_insight()
        store.save(insight)
        results = store.get_by_project("my-project")
        assert results[0].presented_at is None


class TestDismissedCounts:
    def test_counts_by_category(self, store: InsightStore) -> None:
        for _ in range(3):
            i = make_insight(category="technical")
            store.save(i)
            store.update_status(i.id, "dismissed")
        for _ in range(2):
            i = make_insight(category="business")
            store.save(i)
            store.update_status(i.id, "dismissed")
        i = make_insight(category="ux")
        store.save(i)
        store.update_status(i.id, "dismissed")

        counts = store.dismissed_counts("my-project")
        assert counts["technical"] == 3
        assert counts["business"] == 2
        assert counts["ux"] == 1

    def test_excludes_non_dismissed_statuses(self, store: InsightStore) -> None:
        pending = make_insight(category="technical")
        dismissed = make_insight(category="technical")
        store.save(pending)
        store.save(dismissed)
        store.update_status(dismissed.id, "dismissed")

        counts = store.dismissed_counts("my-project")
        assert counts.get("technical", 0) == 1

    def test_excludes_other_projects(self, store: InsightStore) -> None:
        mine = make_insight(project="mine", category="ux")
        theirs = make_insight(project="theirs", category="ux")
        store.save(mine)
        store.save(theirs)
        store.update_status(mine.id, "dismissed")
        store.update_status(theirs.id, "dismissed")

        counts = store.dismissed_counts("mine")
        assert counts.get("ux", 0) == 1

    def test_returns_empty_dict_when_no_dismissed(self, store: InsightStore) -> None:
        store.save(make_insight())
        counts = store.dismissed_counts("my-project")
        assert counts == {}

    def test_returns_empty_dict_for_unknown_project(self, store: InsightStore) -> None:
        counts = store.dismissed_counts("ghost")
        assert counts == {}


class TestClose:
    def test_close_is_noop(self, store: InsightStore) -> None:
        store.close()  # should not raise
