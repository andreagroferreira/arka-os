"""Tests for core.runtime.opencode_hooks — the OpenCode plugin bridge."""

from __future__ import annotations

import json

import pytest

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


class TestIdleCapture:
    @pytest.fixture
    def captured(self, monkeypatch):
        calls = []

        class _FakeStdin:
            def __init__(self):
                self.data = b""

            def write(self, chunk):
                self.data += chunk

            def close(self):
                pass

        class _FakeProc:
            def __init__(self):
                self.stdin = _FakeStdin()

        def _fake_popen(argv, **kwargs):
            proc = _FakeProc()
            calls.append({"argv": argv, "kwargs": kwargs, "proc": proc})
            return proc

        monkeypatch.setattr(oh.subprocess, "Popen", _fake_popen)
        return calls

    def test_idle_enqueues_detached_capture(self, captured):
        oh._action_idle(
            {
                "response_text": "trabalho feito no opencode",
                "session_id": "sess-oc-1",
                "cwd": "/repo/myproj",
            }
        )
        assert len(captured) == 1
        argv = captured[0]["argv"]
        assert argv[1:3] == ["-m", "core.memory.turn_capture"]
        assert argv[3:] == ["capture-text", "sess-oc-1", "/repo/myproj", "opencode"]
        assert captured[0]["kwargs"]["start_new_session"] is True
        assert b"trabalho feito no opencode" in captured[0]["proc"].stdin.data

    def test_idle_skips_capture_without_text(self, captured):
        oh._action_idle({"response_text": "  ", "session_id": "s", "cwd": "/r"})
        assert captured == []

    def test_capture_failure_never_raises(self, monkeypatch):
        def _boom(*a, **k):
            raise OSError("no spawn")

        monkeypatch.setattr(oh.subprocess, "Popen", _boom)
        out = oh._action_idle(
            {"response_text": "texto", "session_id": "s", "cwd": "/r"}
        )
        assert "nudges" in out  # fail-open, compliance still returned


class TestMemoryAction:
    @pytest.fixture
    def seeded(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("ARKA_SESSION_MEMORY_DB", str(tmp_path / "sm.db"))
        monkeypatch.setattr(oh, "_PROMPT_CACHE_DIR", tmp_path / "cache")
        from datetime import UTC, datetime

        from core.memory.semantic_store import SessionMemoryStore, TurnRecord

        store = SessionMemoryStore()
        store.save(
            TurnRecord(
                id="cl-turn",
                ts=datetime.now(UTC).isoformat(),
                session_id="claude-sess",
                runtime="claude",
                project_name="myproj",
                summary="designed the payment retry queue",
            )
        )
        return store

    def test_keyword_hit_from_other_runtime_surfaces(self, seeded):
        out = oh._action_memory(
            {"prompt": "payment queue design", "session_id": "oc-sess",
             "cwd": "/repo/myproj"}
        )
        assert any("payment retry queue" in line for line in out["context"])
        assert any("keyword" in line for line in out["context"])

    def test_handoff_once_per_session(self, seeded):
        payload = {"prompt": "", "session_id": "oc-sess-2", "cwd": "/repo/myproj"}
        first = oh._action_memory(payload)
        handoffs = [l for l in first["context"] if l.startswith("[arka:handoff]")]
        assert len(handoffs) == 1
        assert "claude" in handoffs[0]
        second = oh._action_memory(payload)
        assert not any(
            l.startswith("[arka:handoff]") for l in second["context"]
        )

    def test_no_handoff_when_latest_is_same_runtime(self, seeded):
        from datetime import UTC, datetime, timedelta

        from core.memory.semantic_store import TurnRecord

        seeded.save(
            TurnRecord(
                id="oc-turn",
                ts=(datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
                session_id="other-oc",
                runtime="opencode",
                project_name="myproj",
                summary="opencode turn",
            )
        )
        out = oh._action_memory(
            {"prompt": "", "session_id": "oc-sess-3", "cwd": "/repo/myproj"}
        )
        assert not any(
            l.startswith("[arka:handoff]") for l in out["context"]
        )

    def test_memory_failure_returns_empty_context(self, monkeypatch):
        import core.synapse.session_memory_layer as sml

        monkeypatch.setattr(
            sml, "_l95_feature_flag_on",
            lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        out = oh._action_memory(
            {"prompt": "x", "session_id": "s", "cwd": "/repo/p"}
        )
        assert out == {"context": []}


class TestRoutingBlock:
    """UserPromptSubmit routing parity — makes /arka optional in opencode."""

    def test_route_reminder_always_present(self):
        out = oh._action_prompt({"prompt": "olá", "session_id": "rt-1"})
        assert any("[ARKA:ROUTE]" in line for line in out["routing"])

    def test_dept_detection_dev(self):
        out = oh._action_prompt(
            {"prompt": "implementa a feature de login com tests",
             "session_id": "rt-2", "cwd": "/repo/p"}
        )
        assert any("[dept:dev]" in line for line in out["routing"])

    def test_dept_detection_marketing(self):
        out = oh._action_prompt(
            {"prompt": "plan a seo campaign for the launch",
             "session_id": "rt-3", "cwd": "/repo/p"}
        )
        assert any("[dept:marketing]" in line for line in out["routing"])

    def test_explicit_prefix_wins(self):
        out = oh._action_prompt(
            {"prompt": "/dev audit the security", "session_id": "rt-4",
             "cwd": "/repo/p"}
        )
        assert any("[dept:dev]" in line for line in out["routing"])

    def test_command_hints_emitted(self):
        out = oh._action_prompt(
            {"prompt": "faz review deste código", "session_id": "rt-5",
             "cwd": "/repo/p"}
        )
        assert any("[hint:" in line for line in out["routing"])

    def test_workflow_directive_on_creation_verb(self):
        out = oh._action_prompt(
            {"prompt": "implementa a feature de login", "session_id": "rt-6",
             "cwd": "/repo/p"}
        )
        assert any("[ARKA:WORKFLOW-REQUIRED]" in line for line in out["routing"])

    def test_no_workflow_directive_on_command(self):
        out = oh._action_prompt(
            {"prompt": "/dev implement login", "session_id": "rt-7",
             "cwd": "/repo/p"}
        )
        assert not any(
            "[ARKA:WORKFLOW-REQUIRED]" in line for line in out["routing"]
        )

    def test_no_workflow_directive_on_question(self):
        out = oh._action_prompt(
            {"prompt": "o que é o quality gate?", "session_id": "rt-8",
             "cwd": "/repo/p"}
        )
        assert not any(
            "[ARKA:WORKFLOW-REQUIRED]" in line for line in out["routing"]
        )

    def test_empty_prompt_still_routes(self):
        out = oh._action_prompt({"prompt": "", "session_id": "rt-9"})
        assert out["routing"]  # reminder only, never a crash

    def test_missing_registry_still_routes(self, monkeypatch):
        monkeypatch.setattr(oh, "_load_commands_registry", lambda: [])
        out = oh._action_prompt(
            {"prompt": "implementa a api", "session_id": "rt-10",
             "cwd": "/repo/p"}
        )
        assert any("[dept:dev]" in line for line in out["routing"])


class TestMain:
    def test_unknown_action_never_raises(self, capsys, monkeypatch):
        monkeypatch.setattr("sys.stdin", type("S", (), {"read": lambda s: '{"action":"nope"}'})())
        assert oh.main() == 0
        out = json.loads(capsys.readouterr().out)
        assert "error" in out

    def test_corrupt_stdin_never_raises(self, capsys, monkeypatch):
        monkeypatch.setattr("sys.stdin", type("S", (), {"read": lambda s: "not json"})())
        assert oh.main() == 0
