"""Tests for the knowledge source registry and video detection."""
from __future__ import annotations

import time

import pytest

from core.knowledge.ingest import IngestEngine
from core.knowledge.sources import SourceRegistry, source_id


@pytest.fixture
def registry(tmp_path):
    """An isolated SourceRegistry backed by a temp database."""
    reg = SourceRegistry(db_path=str(tmp_path / "knowledge.db"))
    yield reg
    reg.close()


def test_source_id_is_deterministic_and_stable():
    """source_id returns a stable, prefixed id for the same input."""
    sid = source_id("https://youtu.be/abc")
    assert sid == source_id("https://youtu.be/abc")
    assert sid.startswith("src-")
    assert len(sid) == len("src-") + 12
    assert sid != source_id("https://youtu.be/xyz")


def test_upsert_returns_stable_id(registry):
    """upsert returns the deterministic id for the source."""
    sid = registry.upsert("vid-1", title="One")
    assert sid == source_id("vid-1")


def test_get_round_trips_all_fields(registry):
    """get returns every stored field with the right values."""
    sid = registry.upsert(
        "vid-2", type="video", title="Two", duration=120,
        language="en", thumbnail_path="/t.jpg", media_path="/m.mp4",
        transcript="hello world", chunk_count=3, status="ready",
    )
    row = registry.get(sid)
    assert row is not None
    assert row["source"] == "vid-2"
    assert row["type"] == "video"
    assert row["title"] == "Two"
    assert row["duration"] == 120
    assert row["language"] == "en"
    assert row["thumbnail_path"] == "/t.jpg"
    assert row["media_path"] == "/m.mp4"
    assert row["transcript"] == "hello world"
    assert row["chunk_count"] == 3
    assert row["status"] == "ready"


def test_get_by_source(registry):
    """get_by_source resolves a row from the raw source string."""
    registry.upsert("vid-3", title="Three")
    row = registry.get_by_source("vid-3")
    assert row is not None and row["title"] == "Three"


def test_get_missing_returns_none(registry):
    """get returns None for an unknown id."""
    assert registry.get("src-doesnotexist") is None


def test_update_preserves_created_at_changes_updated_at(registry):
    """Re-upserting keeps created_at and advances updated_at."""
    sid = registry.upsert("vid-4", title="v1")
    first = registry.get(sid)
    time.sleep(1.1)
    registry.upsert("vid-4", title="v2")
    second = registry.get(sid)
    assert second["title"] == "v2"
    assert second["created_at"] == first["created_at"]
    assert second["updated_at"] >= first["updated_at"]


def test_list_orders_by_updated_at_desc(registry):
    """list returns rows newest-updated first."""
    registry.upsert("a")
    time.sleep(1.1)
    registry.upsert("b")
    rows = registry.list()
    assert [r["source"] for r in rows[:2]] == ["b", "a"]


def test_delete(registry):
    """delete removes a row and reports success."""
    sid = registry.upsert("vid-5")
    assert registry.delete(sid) is True
    assert registry.get(sid) is None
    assert registry.delete(sid) is False


def test_detect_source_type_video_url():
    """An .mp4 URL is detected as a video source."""
    assert IngestEngine.detect_source_type(
        "https://cdn.example.com/clip.mp4"
    ) == "video"


def test_detect_source_type_video_file():
    """A .mov file path is detected as a video source."""
    assert IngestEngine.detect_source_type("/tmp/movie.MOV") == "video"
