"""Tests for core.cognition.retrieval (PR4 hooks-as-retrieval prototype)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.cognition import retrieval
from core.cognition.retrieval import (
    ContextCache,
    ContextHit,
    capture_context,
    extract_entities,
    format_advisory,
    read_context,
    search_vault,
)


@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "vault"
    root.mkdir()
    (root / "Projects").mkdir()
    (root / "Projects" / "ArkaOS.md").write_text(
        "# ArkaOS\nThe operating system for AI agent teams. PathResolver is documented here.",
        encoding="utf-8",
    )
    (root / "Projects" / "Fovory.md").write_text(
        "# Fovory\nLaravel 13 + Inertia v3 supplier sync project.",
        encoding="utf-8",
    )
    (root / "core_runtime_resolver.md").write_text(
        "Notes on core/runtime/path_resolver.py — the resolver module.",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def cache_dir(tmp_path):
    d = tmp_path / "context-cache"
    d.mkdir()
    return d


def test_extract_entities_picks_file_paths():
    text = "Edited core/runtime/path_resolver.py and tests/python/test_x.py"
    entities = extract_entities(text)
    assert "core/runtime/path_resolver.py" in entities
    assert "tests/python/test_x.py" in entities


def test_extract_entities_picks_camelcase_and_pascalcase():
    text = "The PathResolver class wraps the LegacyConfigLoader helper."
    entities = extract_entities(text)
    assert "PathResolver" in entities
    assert "LegacyConfigLoader" in entities


def test_extract_entities_picks_at_mentions():
    text = "Re-read @core/runtime/path_resolver.py for the resolve API."
    entities = extract_entities(text)
    assert "core/runtime/path_resolver.py" in entities


def test_extract_entities_filters_stoplist_and_digits():
    text = "The 12345 Error happened — Warning issued at None."
    entities = extract_entities(text)
    assert "The" not in entities
    assert "Error" not in entities
    assert "Warning" not in entities
    assert "None" not in entities
    assert "12345" not in entities


def test_extract_entities_dedupes_and_caps_at_20():
    parts = [
        "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf",
        "Hotel", "India", "Juliet", "Kilo", "Lima", "Mike", "November",
        "Oscar", "Papa", "Quebec", "Romeo", "Sierra", "Tango", "Uniform",
        "Victor", "Whiskey", "Xray", "Yankee", "Zulu",
    ]
    # Duplicate each word to verify dedup as well
    text = " ".join(parts + parts)
    entities = extract_entities(text)
    assert len(entities) == 20
    assert len(set(entities)) == 20


def test_extract_entities_returns_empty_for_empty_input():
    assert extract_entities("") == []
    assert extract_entities(None) == []  # type: ignore[arg-type]


def test_search_vault_returns_hits_for_known_entity(vault):
    hits = search_vault(["PathResolver"], str(vault))
    assert len(hits) >= 1
    assert all(isinstance(h, ContextHit) for h in hits)
    assert any("PathResolver" in h.snippet for h in hits)


def test_search_vault_uses_smart_case(vault):
    hits = search_vault(["pathresolver"], str(vault))
    assert len(hits) >= 1


def test_search_vault_empty_when_no_match(vault):
    assert search_vault(["NonexistentTermXYZ"], str(vault)) == []


def test_search_vault_returns_empty_for_missing_vault(tmp_path):
    assert search_vault(["x"], str(tmp_path / "does-not-exist")) == []


def test_capture_context_writes_cache_json(vault, cache_dir):
    cache = capture_context(
        "session-1",
        "Wrote core/runtime/path_resolver.py with PathResolver class.",
        str(vault),
        cache_dir,
    )
    path = cache_dir / "session-1.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["session_id"] == "session-1"
    assert "captured_at" in data
    assert len(data["hits"]) >= 1


def test_capture_context_persists_empty_hits_when_no_match(vault, cache_dir):
    cache = capture_context(
        "session-empty",
        "Nothing identifiable here just words.",
        str(vault),
        cache_dir,
    )
    assert (cache_dir / "session-empty.json").exists()
    assert cache.hits == []


def test_read_context_returns_hits_within_ttl(vault, cache_dir):
    capture_context("session-fresh", "PathResolver is the new module.", str(vault), cache_dir)
    hits = read_context("session-fresh", ttl_seconds=600, cache_dir=cache_dir)
    assert len(hits) >= 1


def test_read_context_returns_empty_when_ttl_expired(vault, cache_dir):
    # write a cache manually with a past timestamp
    expired = ContextCache(
        session_id="session-stale",
        captured_at=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        ttl_seconds=600,
        hits=[ContextHit("X", "X.md", "...")],
    )
    (cache_dir / "session-stale.json").write_text(json.dumps(expired.to_dict()))
    assert read_context("session-stale", ttl_seconds=600, cache_dir=cache_dir) == []


def test_read_context_returns_empty_when_cache_missing(cache_dir):
    assert read_context("ghost-session", cache_dir=cache_dir) == []


def test_read_context_returns_empty_on_corrupt_json(cache_dir):
    (cache_dir / "session-bad.json").write_text("{not json")
    assert read_context("session-bad", cache_dir=cache_dir) == []


def test_format_advisory_renders_compact_block():
    hits = [
        ContextHit(entity="PathResolver", vault_path="Projects/A.md", snippet="PathResolver wraps profile.json"),
        ContextHit(entity="Fovory", vault_path="Projects/B.md", snippet="Laravel 13 supplier sync"),
    ]
    out = format_advisory(hits)
    assert out.startswith("[arka:context]")
    assert "PathResolver" in out
    assert "Fovory" in out


def test_format_advisory_empty_when_no_hits():
    assert format_advisory([]) == ""


def test_format_advisory_respects_max_chars():
    long_snippet = "x" * 500
    hits = [ContextHit(entity=f"E{i}", vault_path=f"a{i}.md", snippet=long_snippet) for i in range(20)]
    out = format_advisory(hits, max_chars=600)
    assert len(out) <= 700  # header + a couple of entries plus the line that crossed the limit


def test_capture_context_idempotent_overwrites_same_session(vault, cache_dir):
    capture_context("s", "first PathResolver mention", str(vault), cache_dir)
    second = capture_context("s", "second PathResolver mention", str(vault), cache_dir)
    files = list(cache_dir.glob("s.json*"))
    assert len(files) == 1
    assert second.hits == read_context("s", cache_dir=cache_dir)
