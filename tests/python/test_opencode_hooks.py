"""Tests for core.runtime.opencode_hooks — the OpenCode plugin bridge."""

from __future__ import annotations

import json

from core.runtime import opencode_hooks as oh


class TestToolNameMapping:
    def test_builtin_map(self):
        assert oh._map_tool_name("edit") == "Edit"
        assert oh._map_tool_name("webfetch") == "WebFetch"

    def test_mcp_server_prefix(self):
        assert (
            oh._map_tool_name("context7_query-docs")
            == "mcp__context7__query-docs"
        )

    def test_already_claude_style(self):
        assert oh._map_tool_name("mcp__x__y") == "mcp__x__y"

    def test_unknown_passthrough(self):
        assert oh._map_tool_name("somethingcustom") == "somethingcustom"


class TestArgMapping:
    def test_opencode_keys_become_claude_keys(self):
        out = oh._map_args({"filePath": "/a.vue", "newString": "x", "other": 1})
        assert out == {"file_path": "/a.vue", "new_string": "x", "other": 1}


class TestPromptAction:
    def test_vague_reference_suggestion(self):
        out = oh._action_prompt(
            {"prompt": "fix the bug", "session_id": "pytest-vague"}
        )
        assert any("vaga" in s or "vague" in s.lower() for s in out["suggestions"])

    def test_large_paste_with_fence(self):
        out = oh._action_prompt(
            {"prompt": "x" * 2100 + "\n```\ncode\n```", "session_id": "pytest-paste"}
        )
        assert any("Paste grande" in s for s in out["suggestions"])

    def test_clean_prompt_no_suggestions(self):
        out = oh._action_prompt(
            {"prompt": "@src/main.py explica esta função", "session_id": "pytest-clean"}
        )
        assert out["suggestions"] == []


class TestPreToolAction:
    def test_research_gate_nudge_on_first_external_call(self):
        import uuid

        out = oh._action_pre_tool(
            {
                "tool": "webfetch",
                "args": {"url": "https://x"},
                "session_id": f"pytest-rg-{uuid.uuid4().hex[:12]}",
            }
        )
        assert out["allow"] is True
        assert out["reason"] in ("first-violation-nudge", "ok")

    def test_non_research_tool_passes(self):
        out = oh._action_pre_tool(
            {"tool": "read", "args": {"filePath": "/a"}, "session_id": "pytest-rg2"}
        )
        assert out["allow"] is True

    def test_frontend_gate_warns_on_ui_edit(self):
        out = oh._action_pre_tool(
            {
                "tool": "edit",
                "args": {"filePath": "/tmp/x.vue", "newString": "<template/>"},
                "session_id": "pytest-fe1",
            }
        )
        assert out["reason"] in ("no-design-marker", "ok", "not-ui-scope")


class TestMain:
    def test_unknown_action_never_raises(self, capsys, monkeypatch):
        monkeypatch.setattr("sys.stdin", type("S", (), {"read": lambda s: '{"action":"nope"}'})())
        assert oh.main() == 0
        out = json.loads(capsys.readouterr().out)
        assert "error" in out

    def test_corrupt_stdin_never_raises(self, capsys, monkeypatch):
        monkeypatch.setattr("sys.stdin", type("S", (), {"read": lambda s: "not json"})())
        assert oh.main() == 0
