"""Tests for core.runtime.mcp_telemetry — MCP usage writer + summarizer."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.runtime.mcp_telemetry import (
    parse_mcp_tool,
    record,
    summarise,
)
from core.runtime.mcp_telemetry_cli import _render, main as cli_main


def _write_lines(path: Path, entries: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write((entry if isinstance(entry, str) else json.dumps(entry)) + "\n")


def _entry(server: str, tool: str, *, days_ago: int = 0) -> dict:
    ts = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {"ts": ts.isoformat(), "server": server, "tool": tool, "session": "s1"}


class TestParseMcpTool:
    def test_plain_server(self):
        assert parse_mcp_tool("mcp__obsidian__search_notes") == ("obsidian", "search_notes")

    def test_server_with_single_underscores(self):
        assert parse_mcp_tool("mcp__claude_ai_Canva__export-design") == (
            "claude_ai_Canva", "export-design",
        )

    def test_plugin_server(self):
        assert parse_mcp_tool(
            "mcp__plugin_claude-mem_mcp-search__get_observations"
        ) == ("plugin_claude-mem_mcp-search", "get_observations")

    @pytest.mark.parametrize("name", ["Bash", "Read", "mcp__", "mcp__broken", ""])
    def test_non_mcp_names_return_none(self, name):
        assert parse_mcp_tool(name) is None


class TestRecord:
    def test_writes_one_line_for_mcp_tool(self, tmp_path: Path):
        dest = tmp_path / "mcp-usage.jsonl"
        assert record("mcp__obsidian__read_note", session_id="abc", path=dest) is True
        lines = dest.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["server"] == "obsidian"
        assert entry["tool"] == "read_note"
        assert entry["session"] == "abc"
        assert entry["ts"]

    def test_non_mcp_tool_writes_nothing(self, tmp_path: Path):
        dest = tmp_path / "mcp-usage.jsonl"
        assert record("Bash", path=dest) is False
        assert not dest.exists()

    def test_unwritable_path_returns_false_without_raising(self, tmp_path: Path):
        blocker = tmp_path / "file"
        blocker.write_text("x", encoding="utf-8")
        dest = blocker / "mcp-usage.jsonl"  # parent is a file -> OSError
        assert record("mcp__obsidian__read_note", path=dest) is False


class TestSummarise:
    def test_aggregates_servers_and_tools(self, tmp_path: Path):
        src = tmp_path / "u.jsonl"
        _write_lines(src, [
            _entry("obsidian", "read_note"),
            _entry("obsidian", "read_note"),
            _entry("obsidian", "search_notes"),
            _entry("claude-in-chrome", "navigate"),
        ])
        s = summarise("all", path=src)
        assert s.total_calls == 4
        assert s.unique_servers == 2
        assert s.top_servers[0] == ("obsidian", 3)
        assert s.top_tools[0] == ("obsidian/read_note", 2)

    def test_period_filters_old_entries(self, tmp_path: Path):
        src = tmp_path / "u.jsonl"
        _write_lines(src, [
            _entry("obsidian", "read_note"),
            _entry("obsidian", "read_note", days_ago=40),
        ])
        assert summarise("month", path=src).total_calls == 1
        assert summarise("all", path=src).total_calls == 2

    def test_corrupt_lines_counted_not_fatal(self, tmp_path: Path):
        src = tmp_path / "u.jsonl"
        _write_lines(src, [
            _entry("obsidian", "read_note"),
            "not json{{",
            json.dumps(["not", "a", "dict"]),
        ])
        s = summarise("all", path=src)
        assert s.total_calls == 1
        assert s.corrupt_line_count == 2

    def test_missing_file_yields_empty_summary(self, tmp_path: Path):
        s = summarise("all", path=tmp_path / "absent.jsonl")
        assert s.total_calls == 0
        assert s.unique_servers == 0

    def test_invalid_period_raises(self, tmp_path: Path):
        with pytest.raises(ValueError):
            summarise("year", path=tmp_path / "u.jsonl")


class TestCliRender:
    def test_render_lists_servers_and_tools(self, tmp_path: Path):
        src = tmp_path / "u.jsonl"
        _write_lines(src, [_entry("obsidian", "read_note")])
        out = _render(summarise("all", path=src))
        assert "# MCP usage — all" in out
        assert "`obsidian` — 1" in out
        assert "`obsidian/read_note` — 1" in out

    def test_render_empty_period_message(self, tmp_path: Path):
        out = _render(summarise("all", path=tmp_path / "absent.jsonl"))
        assert "No MCP calls recorded" in out

    def test_render_sanitizes_markdown_breakers(self, tmp_path: Path):
        src = tmp_path / "u.jsonl"
        _write_lines(src, [_entry("bad`server\nname", "t")])
        out = _render(summarise("all", path=src))
        assert "badserver name" in out


class TestCliMain:
    def test_valid_period_returns_zero(self, capsys):
        assert cli_main(["week"]) == 0
        assert "# MCP usage — week" in capsys.readouterr().out

    def test_invalid_period_returns_two(self, capsys):
        assert cli_main(["year"]) == 2
        assert "invalid period" in capsys.readouterr().err


class TestHookWiring:
    def test_post_tool_use_records_mcp_call_on_success_exit(
        self, tmp_path: Path, monkeypatch, capsys,
    ):
        """The hook must record MCP usage even when the tool call succeeds
        (exit 0 short-circuits every later section)."""
        from core.runtime import mcp_telemetry
        from core.hooks import post_tool_use

        dest = tmp_path / "mcp-usage.jsonl"
        monkeypatch.setattr(mcp_telemetry, "DEFAULT_PATH", dest)
        rc = post_tool_use.main({
            "tool_name": "mcp__obsidian__search_notes",
            "tool_output": "ok",
            "exit_code": "0",
            "session_id": "sess-1",
        })
        assert rc == 0
        entry = json.loads(dest.read_text(encoding="utf-8").splitlines()[0])
        assert entry["server"] == "obsidian"
        assert entry["session"] == "sess-1"
