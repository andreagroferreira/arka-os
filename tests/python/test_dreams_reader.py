"""Tests for core.cognition.dreams_reader (PR9 v2.31.0)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.cognition.dreams_reader import (
    StoredInsight,
    _extract_body,
    _extract_h1,
    _parse_frontmatter,
    _parse_list,
    list_insights,
    parse_insight,
)


def _write_insight(
    dreams_dir: Path,
    *,
    date: str,
    title: str,
    confidence: str = "high",
    sources: list[str] | None = None,
) -> Path:
    sources = sources or ["[[Projects/Test.md]]"]
    body = f"""---
type: arkaos-insight
date: {date}
status: surfaced
confidence: {confidence}
sources:
{chr(10).join(f"  - {s}" for s in sources)}
tags:
  - arkaos-dream
  - test
plugin_compat_version: 1.0
---

# {title}

## What I noticed
{title} — some body text describing the pattern observed.

## Sources
- [[Projects/Test.md]]
"""
    path = dreams_dir / f"{date}-{title.lower().replace(' ', '-')}.md"
    path.write_text(body, encoding="utf-8")
    return path


@pytest.fixture
def dreams_dir(tmp_path):
    d = tmp_path / "Dreams"
    d.mkdir()
    return d


def test_list_insights_returns_empty_when_dir_missing(tmp_path):
    assert list_insights(tmp_path / "ghost") == []


def test_list_insights_returns_today(dreams_dir):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _write_insight(dreams_dir, date=today, title="Today insight")
    result = list_insights(dreams_dir, since_days=1)
    assert len(result) == 1
    assert result[0].title == "Today insight"


def test_list_insights_filters_old_by_since_days(dreams_dir):
    today = datetime.now(timezone.utc).date()
    _write_insight(dreams_dir, date=today.strftime("%Y-%m-%d"), title="Today")
    five_days_ago = (today - timedelta(days=5)).strftime("%Y-%m-%d")
    _write_insight(dreams_dir, date=five_days_ago, title="Five days ago")
    # since_days=2 keeps today (and yesterday) but cuts 5 days ago
    result = list_insights(dreams_dir, since_days=2)
    titles = [i.title for i in result]
    assert "Today" in titles
    assert "Five days ago" not in titles


def test_list_insights_includes_within_window(dreams_dir):
    today = datetime.now(timezone.utc).date()
    _write_insight(dreams_dir, date=today.strftime("%Y-%m-%d"), title="Today")
    three_days_ago = (today - timedelta(days=3)).strftime("%Y-%m-%d")
    _write_insight(dreams_dir, date=three_days_ago, title="Three days ago")
    result = list_insights(dreams_dir, since_days=7)
    titles = [i.title for i in result]
    assert "Today" in titles
    assert "Three days ago" in titles


def test_list_insights_skips_non_insight_files(dreams_dir):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (dreams_dir / "random.md").write_text("not an insight\n", encoding="utf-8")
    _write_insight(dreams_dir, date=today, title="Real insight")
    result = list_insights(dreams_dir)
    assert len(result) == 1
    assert result[0].title == "Real insight"


def test_parse_insight_extracts_metadata(tmp_path):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dreams = tmp_path / "Dreams"
    dreams.mkdir()
    path = _write_insight(dreams, date=today, title="Pest pagination", confidence="high")
    text = path.read_text(encoding="utf-8")
    insight = parse_insight(path, text)
    assert insight is not None
    assert insight.title == "Pest pagination"
    assert insight.confidence == "high"
    assert insight.date == today
    assert "[[Projects/Test.md]]" in insight.sources
    assert "arkaos-dream" in insight.tags


def test_parse_insight_returns_none_for_missing_frontmatter(tmp_path):
    path = tmp_path / "x.md"
    path.write_text("# No frontmatter here\nbody", encoding="utf-8")
    assert parse_insight(path, path.read_text(encoding="utf-8")) is None


def test_parse_insight_returns_none_for_wrong_type(tmp_path):
    path = tmp_path / "x.md"
    path.write_text(
        "---\ntype: not-an-insight\ndate: 2026-05-13\n---\n# X\nbody",
        encoding="utf-8",
    )
    assert parse_insight(path, path.read_text(encoding="utf-8")) is None


def test_parse_frontmatter_extracts_list_values():
    block = """type: arkaos-insight
date: 2026-05-13
sources:
  - "[[a.md]]"
  - "[[b.md]]"
confidence: high"""
    out = _parse_frontmatter(block)
    assert out["type"] == "arkaos-insight"
    assert out["date"] == "2026-05-13"
    assert out["sources"] == ['"[[a.md]]"', '"[[b.md]]"']
    assert out["confidence"] == "high"


def test_parse_list_handles_str_and_list():
    assert _parse_list(["a", "b"]) == ["a", "b"]
    assert _parse_list("solo") == ["solo"]
    assert _parse_list("") == []
    assert _parse_list(None) == []


def test_extract_h1_finds_first_h1():
    body = "## sub\nfoo\n# Real Title\nmore\n# Second"
    assert _extract_h1(body) == "Real Title"


def test_extract_h1_returns_none_when_absent():
    body = "no headings here\njust prose"
    assert _extract_h1(body) is None


def test_extract_body_returns_what_i_noticed_section():
    body = """# Title

## What I noticed
This is the insight body text that should be extracted.

## Sources
- [[x.md]]
"""
    result = _extract_body(body)
    assert "insight body text" in result
    assert "Sources" not in result
