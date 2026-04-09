"""Tests for CaptureStore — SQLite CRUD store for raw session captures."""

import pytest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from core.cognition.capture import CaptureStore
from core.cognition.memory.schemas import RawCapture


# --- Helpers ---

def make_capture(**overrides) -> RawCapture:
    defaults = {
        "session_id": "sess-test-001",
        "project_path": "/Users/dev/my-project",
        "project_name": "my-project",
        "category": "decision",
        "content": "Chose PostgreSQL over MySQL for JSONB support.",
        "context": {"file": "main.py", "line": 42},
    }
    defaults.update(overrides)
    return RawCapture(**defaults)


def make_capture_at(dt: datetime, **overrides) -> RawCapture:
    return make_capture(timestamp=dt, **overrides)


TODAY = date.today()
TODAY_NOON = datetime(TODAY.year, TODAY.month, TODAY.day, 12, 0, 0, tzinfo=timezone.utc)
YESTERDAY = TODAY - timedelta(days=1)
YESTERDAY_NOON = datetime(YESTERDAY.year, YESTERDAY.month, YESTERDAY.day, 12, 0, 0, tzinfo=timezone.utc)


# --- Fixtures ---

@pytest.fixture()
def store(tmp_path: Path) -> CaptureStore:
    return CaptureStore(db_path=str(tmp_path / "captures.db"))


# --- Tests ---

class TestCaptureStoreSaveAndRetrieve:
    def test_save_and_get_by_date_returns_capture(self, store: CaptureStore) -> None:
        capture = make_capture_at(TODAY_NOON)
        store.save(capture)
        results = store.get_by_date(TODAY)
        assert len(results) == 1
        assert results[0].id == capture.id
        assert results[0].content == capture.content

    def test_context_dict_is_preserved(self, store: CaptureStore) -> None:
        capture = make_capture_at(TODAY_NOON, context={"key": "value", "num": 99})
        store.save(capture)
        results = store.get_by_date(TODAY)
        assert results[0].context == {"key": "value", "num": 99}

    def test_empty_context_is_preserved(self, store: CaptureStore) -> None:
        capture = make_capture_at(TODAY_NOON, context={})
        store.save(capture)
        results = store.get_by_date(TODAY)
        assert results[0].context == {}

    def test_save_replace_overwrites_existing(self, store: CaptureStore) -> None:
        capture = make_capture_at(TODAY_NOON)
        store.save(capture)
        updated = RawCapture(
            id=capture.id,
            timestamp=capture.timestamp,
            session_id=capture.session_id,
            project_path=capture.project_path,
            project_name=capture.project_name,
            category=capture.category,
            content="Updated content",
        )
        store.save(updated)
        results = store.get_by_date(TODAY)
        assert len(results) == 1
        assert results[0].content == "Updated content"

    def test_timestamp_is_timezone_aware(self, store: CaptureStore) -> None:
        capture = make_capture_at(TODAY_NOON)
        store.save(capture)
        results = store.get_by_date(TODAY)
        assert results[0].timestamp.tzinfo is not None


class TestGetByDate:
    def test_filters_today_excludes_yesterday(self, store: CaptureStore) -> None:
        today_capture = make_capture_at(TODAY_NOON, content="today")
        yesterday_capture = make_capture_at(YESTERDAY_NOON, content="yesterday")
        store.save(today_capture)
        store.save(yesterday_capture)

        results = store.get_by_date(TODAY)
        assert len(results) == 1
        assert results[0].content == "today"

    def test_filters_yesterday_excludes_today(self, store: CaptureStore) -> None:
        today_capture = make_capture_at(TODAY_NOON, content="today")
        yesterday_capture = make_capture_at(YESTERDAY_NOON, content="yesterday")
        store.save(today_capture)
        store.save(yesterday_capture)

        results = store.get_by_date(YESTERDAY)
        assert len(results) == 1
        assert results[0].content == "yesterday"

    def test_returns_empty_for_date_with_no_captures(self, store: CaptureStore) -> None:
        results = store.get_by_date(TODAY)
        assert results == []

    def test_excludes_archived_captures(self, store: CaptureStore) -> None:
        capture = make_capture_at(TODAY_NOON)
        store.save(capture)
        store.mark_processed([capture.id])
        store.archive_processed()

        results = store.get_by_date(TODAY)
        assert results == []

    def test_includes_multiple_captures_same_day(self, store: CaptureStore) -> None:
        c1 = make_capture_at(TODAY_NOON, content="first")
        c2 = make_capture_at(
            TODAY_NOON.replace(hour=14), content="second"
        )
        store.save(c1)
        store.save(c2)

        results = store.get_by_date(TODAY)
        assert len(results) == 2


class TestGetByProject:
    def test_returns_captures_for_project(self, store: CaptureStore) -> None:
        c1 = make_capture_at(TODAY_NOON, project_name="project-a")
        c2 = make_capture_at(TODAY_NOON, project_name="project-b")
        store.save(c1)
        store.save(c2)

        results = store.get_by_project("project-a")
        assert len(results) == 1
        assert results[0].project_name == "project-a"

    def test_returns_empty_for_unknown_project(self, store: CaptureStore) -> None:
        results = store.get_by_project("nonexistent")
        assert results == []

    def test_returns_multiple_captures_for_project(self, store: CaptureStore) -> None:
        for i in range(3):
            store.save(make_capture_at(TODAY_NOON, content=f"cap-{i}", project_name="my-project"))

        results = store.get_by_project("my-project")
        assert len(results) == 3


class TestGetUnprocessedAndMarkProcessed:
    def test_all_new_captures_are_unprocessed(self, store: CaptureStore) -> None:
        store.save(make_capture_at(TODAY_NOON, content="a"))
        store.save(make_capture_at(TODAY_NOON, content="b"))

        results = store.get_unprocessed()
        assert len(results) == 2

    def test_mark_processed_removes_from_unprocessed(self, store: CaptureStore) -> None:
        c1 = make_capture_at(TODAY_NOON, content="process me")
        c2 = make_capture_at(TODAY_NOON, content="keep me")
        store.save(c1)
        store.save(c2)

        store.mark_processed([c1.id])

        unprocessed = store.get_unprocessed()
        assert len(unprocessed) == 1
        assert unprocessed[0].id == c2.id

    def test_mark_processed_with_empty_list_is_safe(self, store: CaptureStore) -> None:
        store.save(make_capture_at(TODAY_NOON))
        store.mark_processed([])
        assert len(store.get_unprocessed()) == 1

    def test_mark_processed_multiple_ids(self, store: CaptureStore) -> None:
        captures = [make_capture_at(TODAY_NOON, content=f"c{i}") for i in range(5)]
        for c in captures:
            store.save(c)

        ids_to_process = [c.id for c in captures[:3]]
        store.mark_processed(ids_to_process)

        assert len(store.get_unprocessed()) == 2


class TestArchiveProcessed:
    def test_archive_processed_returns_count(self, store: CaptureStore) -> None:
        c1 = make_capture_at(TODAY_NOON, content="a")
        c2 = make_capture_at(TODAY_NOON, content="b")
        store.save(c1)
        store.save(c2)
        store.mark_processed([c1.id, c2.id])

        count = store.archive_processed()
        assert count == 2

    def test_archive_excludes_unprocessed(self, store: CaptureStore) -> None:
        c1 = make_capture_at(TODAY_NOON, content="processed")
        c2 = make_capture_at(TODAY_NOON, content="not processed")
        store.save(c1)
        store.save(c2)
        store.mark_processed([c1.id])

        count = store.archive_processed()
        assert count == 1

    def test_archived_captures_not_returned_by_get_unprocessed(self, store: CaptureStore) -> None:
        capture = make_capture_at(TODAY_NOON)
        store.save(capture)
        store.mark_processed([capture.id])
        store.archive_processed()

        assert store.get_unprocessed() == []

    def test_double_archive_returns_zero(self, store: CaptureStore) -> None:
        capture = make_capture_at(TODAY_NOON)
        store.save(capture)
        store.mark_processed([capture.id])
        store.archive_processed()

        count = store.archive_processed()
        assert count == 0


class TestStats:
    def test_empty_store_stats(self, store: CaptureStore) -> None:
        s = store.stats()
        assert s["total"] == 0
        assert s["unprocessed"] == 0
        assert s["by_category"] == {}

    def test_stats_total_and_unprocessed(self, store: CaptureStore) -> None:
        c1 = make_capture_at(TODAY_NOON, category="decision")
        c2 = make_capture_at(TODAY_NOON, category="error")
        c3 = make_capture_at(TODAY_NOON, category="decision")
        store.save(c1)
        store.save(c2)
        store.save(c3)
        store.mark_processed([c1.id])

        s = store.stats()
        assert s["total"] == 3
        assert s["unprocessed"] == 2

    def test_stats_by_category(self, store: CaptureStore) -> None:
        for _ in range(3):
            store.save(make_capture_at(TODAY_NOON, category="decision"))
        for _ in range(2):
            store.save(make_capture_at(TODAY_NOON, category="error"))
        store.save(make_capture_at(TODAY_NOON, category="pattern"))

        s = store.stats()
        assert s["by_category"]["decision"] == 3
        assert s["by_category"]["error"] == 2
        assert s["by_category"]["pattern"] == 1
