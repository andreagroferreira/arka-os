"""Unit tests for the consolidated hook entrypoints (PR-6 v4.1.0).

Each ``core.hooks.<event>`` module is exercised end-to-end via
``python -m`` with fixture stdin JSON, a tmp HOME, and monkeypatched
state dirs — the same surface the thin bash wrappers call, minus bash.
Pure helpers get direct in-process tests.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WF_REQUIRED_DIR = Path("/tmp/arkaos-wf-required")


def _run_module(
    module: str, payload: dict, env_overrides: dict[str, str]
) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update({
        "ARKAOS_ROOT": str(REPO_ROOT),
        "PYTHONPATH": str(REPO_ROOT),
    })
    env.update(env_overrides)
    for bypass in ("ARKA_BYPASS_KB_FIRST", "ARKA_BYPASS_FLOW"):
        env.pop(bypass, None)
    return subprocess.run(
        [sys.executable, "-m", module],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        check=False,
    )


@pytest.fixture
def hook_home(tmp_path):
    """Isolated HOME with an ArkaOS config enabling the KB-first gate."""
    home = tmp_path / "home"
    (home / ".arkaos").mkdir(parents=True)
    (home / ".arkaos" / "config.json").write_text(
        json.dumps({"hooks": {"kbFirst": True, "hardEnforcement": False}}),
        encoding="utf-8",
    )
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Laravel Service Pattern.md").write_text("# note\n", encoding="utf-8")
    return {
        "HOME": str(home),
        "ARKA_KB_VIOLATION_DIR": str(tmp_path / "kb-violation"),
        "ARKA_KB_QUERY_DIR": str(tmp_path / "kb-query"),
        "ARKAOS_VAULT": str(vault),
        "ARKA_MARKER_CACHE_DIR": str(tmp_path / "flow-marker"),
        "ARKA_WF_REQUIRED_DIR": str(tmp_path / "wf-required"),
        "ARKA_FLOW_AUTH_DIR": str(tmp_path / "flow-auth"),
        "_tmp": tmp_path,
    }


def _env(hook_home: dict) -> dict[str, str]:
    return {k: v for k, v in hook_home.items() if not k.startswith("_")}


def _fixture_payload(name: str) -> dict:
    """A runtime-captured hook payload from fixtures/hook_payloads/.

    session_id and cwd are replaced, prompt_id is dropped, and machine
    paths are rewritten (transcript_path emptied; the path inside
    failure_read's ``error``); every other contract field is verbatim
    from the live capture, tool_use_id included.
    """
    path = (
        Path(__file__).parent / "fixtures" / "hook_payloads" / f"{name}.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _ctx(result: subprocess.CompletedProcess) -> str:
    """additionalContext from a hook payload (Claude Code contract shape).

    The runtime only delivers context inside hookSpecificOutput with a
    hookEventName — asserting through this helper keeps every test pinned
    to the shape the runtime actually parses.
    """
    payload = json.loads(result.stdout)
    return payload["hookSpecificOutput"]["additionalContext"]


# ─── pre_tool_use ────────────────────────────────────────────────────────


class TestPreToolUse:
    def test_non_gated_tool_allows_silently(self, hook_home):
        result = _run_module("core.hooks.pre_tool_use", {
            "tool_name": "Read", "session_id": "pre-read",
            "transcript_path": "", "cwd": "/tmp", "tool_input": {},
        }, _env(hook_home))
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_kb_gate_nudges_on_first_research_call(self, hook_home):
        result = _run_module("core.hooks.pre_tool_use", {
            "tool_name": "WebSearch", "session_id": "pre-nudge",
            "transcript_path": "", "cwd": "/tmp",
            "tool_input": {"query": "laravel service pattern"},
        }, _env(hook_home))
        assert result.returncode == 0, result.stderr
        assert "[arka:kb-nudge]" in result.stderr

    def test_kb_gate_denies_on_second_research_call(self, hook_home):
        payload = {
            "tool_name": "WebSearch", "session_id": "pre-deny",
            "transcript_path": "", "cwd": "/tmp",
            "tool_input": {"query": "laravel service pattern"},
        }
        first = _run_module("core.hooks.pre_tool_use", payload, _env(hook_home))
        assert first.returncode == 0
        second = _run_module("core.hooks.pre_tool_use", payload, _env(hook_home))
        assert second.returncode == 2, second.stderr
        assert "[ARKA:KB-FIRST]" in second.stderr
        out = json.loads(second.stdout)
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_flow_gate_denies_without_marker(self, hook_home, tmp_path):
        home = Path(hook_home["HOME"])
        (home / ".arkaos" / "config.json").write_text(
            json.dumps({"hooks": {"kbFirst": False,
                                  "hardEnforcement": True}}),
            encoding="utf-8",
        )
        session_id = "pre-flow-deny-pr6"
        WF_REQUIRED_DIR.mkdir(parents=True, exist_ok=True)
        marker = WF_REQUIRED_DIR / session_id
        marker.write_text("1", encoding="utf-8")
        transcript = tmp_path / "t.jsonl"
        transcript.write_text(json.dumps(
            {"role": "assistant", "content": "plain prose, no markers"}
        ) + "\n", encoding="utf-8")
        # Exhaust the grace budget in the isolated auth dir so the hard
        # deny path fires (resilience fix graces the first turns).
        import os as _os

        from core.workflow import flow_authorization
        _prev = _os.environ.get("ARKA_FLOW_AUTH_DIR")
        _os.environ["ARKA_FLOW_AUTH_DIR"] = hook_home["ARKA_FLOW_AUTH_DIR"]
        try:
            for _ in range(flow_authorization.GRACE_CAP + 1):
                flow_authorization.register_grace(session_id)
            result = _run_module("core.hooks.pre_tool_use", {
                "tool_name": "Write", "session_id": session_id,
                "transcript_path": str(transcript), "cwd": "/tmp",
                "tool_input": {"file_path": "/tmp/x.py", "content": "x"},
            }, _env(hook_home))
        finally:
            marker.unlink(missing_ok=True)
            if _prev is None:
                _os.environ.pop("ARKA_FLOW_AUTH_DIR", None)
            else:
                _os.environ["ARKA_FLOW_AUTH_DIR"] = _prev
        assert result.returncode == 2, result.stderr
        assert "[ARKA:ENFORCEMENT]" in result.stderr
        out = json.loads(result.stdout)
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_flow_gate_allows_with_routing_marker(self, hook_home, tmp_path):
        home = Path(hook_home["HOME"])
        (home / ".arkaos" / "config.json").write_text(
            json.dumps({"hooks": {"kbFirst": False,
                                  "hardEnforcement": True}}),
            encoding="utf-8",
        )
        session_id = "pre-flow-allow-pr6"
        WF_REQUIRED_DIR.mkdir(parents=True, exist_ok=True)
        marker = WF_REQUIRED_DIR / session_id
        marker.write_text("1", encoding="utf-8")
        transcript = tmp_path / "t.jsonl"
        transcript.write_text(json.dumps(
            {"role": "assistant", "content": "[arka:routing] dev -> paulo"}
        ) + "\n", encoding="utf-8")
        try:
            result = _run_module("core.hooks.pre_tool_use", {
                "tool_name": "Write", "session_id": session_id,
                "transcript_path": str(transcript), "cwd": "/tmp",
                "tool_input": {"file_path": "/tmp/x.py", "content": "x"},
            }, _env(hook_home))
        finally:
            marker.unlink(missing_ok=True)
        assert result.returncode == 0, result.stderr


# ─── post_tool_use ───────────────────────────────────────────────────────


class TestPostToolUse:
    def test_confirms_auth_from_transcript_on_routing(self, hook_home):
        # Claude Code sends no `assistant_message`; the hook reads the
        # transcript and confirms persistent flow authorization.
        transcript = hook_home["_tmp"] / "post-t.jsonl"
        transcript.write_text("\n".join([
            json.dumps({"message": {"role": "assistant", "content": [
                {"type": "text", "text": "[arka:routing] dev -> paulo\ntask #2"}
            ]}}),
        ]), encoding="utf-8")
        result = _run_module("core.hooks.post_tool_use", {
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/x.md", "content": "ok"},
            "tool_response": {"filePath": "/tmp/x.md", "success": True},
            "cwd": "/tmp", "session_id": "post-marker",
            "transcript_path": str(transcript),
        }, _env(hook_home))
        assert result.returncode == 0
        assert json.loads(result.stdout) == {}
        auth = Path(hook_home["ARKA_FLOW_AUTH_DIR"]) / "post-marker.json"
        assert auth.is_file()
        data = json.loads(auth.read_text(encoding="utf-8"))
        assert data["marker_type"] == "routing"

    def test_benign_fixture_short_circuits(self, hook_home):
        # Runtime-captured payload (grep no-match, exit 1 interpreted as
        # benign by the runtime — PostToolUse fired, empty output).
        result = _run_module(
            "core.hooks.post_tool_use",
            _fixture_payload("post_tool_use_bash_benign"),
            _env(hook_home),
        )
        assert result.returncode == 0
        assert json.loads(result.stdout) == {}
        gotchas = Path(hook_home["HOME"]) / ".arkaos" / "gotchas.json"
        assert not gotchas.exists()

    def test_failure_event_records_gotcha(self, hook_home):
        # Runtime-captured PostToolUseFailure payload: a failed Bash call
        # (exit 7) arrives on the FAILURE event with the output inside
        # `error`, prefixed "Exit code N" — there is no tool_response.
        payload = _fixture_payload("post_tool_use_failure_bash")
        result = _run_module("core.hooks.post_tool_use", payload, _env(hook_home))
        assert result.returncode == 0
        assert json.loads(result.stdout) == {}
        gotchas_file = Path(hook_home["HOME"]) / ".arkaos" / "gotchas.json"
        entries = json.loads(gotchas_file.read_text(encoding="utf-8"))
        assert len(entries) == 1
        assert entries[0]["count"] == 1
        assert entries[0]["tool"] == "Bash"
        assert entries[0]["projects"] == ["projlive"]

        # Same failure again → count increments, no duplicate entry.
        _run_module("core.hooks.post_tool_use", payload, _env(hook_home))
        entries = json.loads(gotchas_file.read_text(encoding="utf-8"))
        assert len(entries) == 1
        assert entries[0]["count"] == 2

    def test_failure_event_read_records_gotcha(self, hook_home):
        # Runtime-captured PostToolUseFailure for a non-Bash tool: `error`
        # is a plain message with no "Exit code N" prefix.
        result = _run_module(
            "core.hooks.post_tool_use",
            _fixture_payload("post_tool_use_failure_read"),
            _env(hook_home),
        )
        assert result.returncode == 0
        gotchas_file = Path(hook_home["HOME"]) / ".arkaos" / "gotchas.json"
        entries = json.loads(gotchas_file.read_text(encoding="utf-8"))
        assert len(entries) == 1
        assert entries[0]["tool"] == "Read"

    def test_error_trigger_in_stdout_records_gotcha(self, hook_home):
        # Runtime-captured payload: exit 0 but stdout carries an error
        # trigger (real success payloads merge stderr into stdout) — the
        # dict-shaped tool_response must feed the error pipeline.
        result = _run_module(
            "core.hooks.post_tool_use",
            _fixture_payload("post_tool_use_bash_trigger"),
            _env(hook_home),
        )
        assert result.returncode == 0
        gotchas_file = Path(hook_home["HOME"]) / ".arkaos" / "gotchas.json"
        entries = json.loads(gotchas_file.read_text(encoding="utf-8"))
        assert len(entries) == 1
        assert entries[0]["category"] == "git"  # "fatal: not a git repository"
        assert entries[0]["projects"] == ["projlive"]


class TestToolResultExtraction:
    """In-process pins for the two-event 2.1.220 contract helpers.

    PostToolUse only ever delivers a structured tool_response (failures
    throw and fire PostToolUseFailure instead, proven live against the
    binary); the failure event carries the output in `error`, prefixed
    "Exit code N" for Bash, plain message for other tools.
    """

    def _mod(self):
        from core.hooks import post_tool_use
        return post_tool_use

    def test_success_dict_joins_stdout_and_stderr(self):
        mod = self._mod()
        payload = {"tool_response": {
            "stdout": "out line", "stderr": "warn line",
        }}
        assert mod._tool_text(payload) == "out line\nwarn line"
        assert mod._tool_exit_code(payload) == "0"

    def test_failure_event_strips_exit_envelope(self):
        mod = self._mod()
        payload = {
            "hook_event_name": "PostToolUseFailure",
            "error": "Exit code 7\nhello-stdout\nboom-stderr",
            "is_interrupt": False,
        }
        assert mod._tool_text(payload) == "hello-stdout\nboom-stderr"
        assert mod._tool_exit_code(payload) == "7"

    def test_failure_event_plain_error_is_code_one(self):
        mod = self._mod()
        payload = {
            "hook_event_name": "PostToolUseFailure",
            "error": "File does not exist.",
            "is_interrupt": False,
        }
        assert mod._tool_text(payload) == "File does not exist."
        assert mod._tool_exit_code(payload) == "1"

    def test_failure_envelope_only_matches_as_prefix(self):
        # Pin for the ^ anchor: an "Exit code N" line mid-error is
        # content, not envelope.
        mod = self._mod()
        payload = {
            "hook_event_name": "PostToolUseFailure",
            "error": "tests failed\nExit code 2\nmore output",
            "is_interrupt": False,
        }
        assert mod._tool_text(payload) == "tests failed\nExit code 2\nmore output"
        assert mod._tool_exit_code(payload) == "1"

    def test_interrupt_is_not_a_failure_signal(self):
        mod = self._mod()
        payload = {
            "hook_event_name": "PostToolUseFailure",
            "error": "[Request interrupted by user]",
            "is_interrupt": True,
        }
        assert mod._tool_exit_code(payload) == "0"

    def test_plain_string_response_passes_through(self):
        mod = self._mod()
        payload = {"tool_response": "just some text"}
        assert mod._tool_text(payload) == "just some text"
        assert mod._tool_exit_code(payload) == "0"

    def test_task_content_list_still_extracts(self):
        mod = self._mod()
        payload = {"tool_response": {"content": [
            {"type": "text", "text": "verdict body"},
            {"type": "image", "source": {}},
        ]}}
        assert mod._tool_text(payload) == "verdict body"
        assert mod._tool_exit_code(payload) == "0"

    def test_missing_response_is_empty_success(self):
        mod = self._mod()
        assert mod._tool_text({}) == ""
        assert mod._tool_exit_code({}) == "0"

    def test_failure_envelope_with_no_output_leaves_no_text(self):
        mod = self._mod()
        payload = {
            "hook_event_name": "PostToolUseFailure",
            "error": "Exit code 1",
            "is_interrupt": False,
        }
        assert mod._tool_text(payload) == ""
        assert mod._tool_exit_code(payload) == "1"


class TestDetectRuleViolations:
    """The stdlib rules and the forge scope-creep check must read
    tool_input.* (2.1.220), not dead keys.

    These call the helpers directly; in production sections 6-8 only
    run on turns that carry an error signal (main()'s early exit).
    """

    def _with_state(self, monkeypatch, tmp_path, phases: dict):
        home = tmp_path / "vhome"
        (home / ".arkaos").mkdir(parents=True)
        (home / ".arkaos" / "workflow-state.json").write_text(
            json.dumps({"phases": phases}), encoding="utf-8",
        )
        monkeypatch.setenv("HOME", str(home))

    def test_commit_on_master_flags_branch_isolation(
        self, monkeypatch, tmp_path
    ):
        self._with_state(monkeypatch, tmp_path, {})
        from core.hooks.post_tool_use import _detect_rule_violations
        msg, persist = _detect_rule_violations({
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m 'x'"},
            "tool_response": {
                "stdout": "[master abc1234] x", "stderr": "",
            },
        })
        assert "branch-isolation" in msg
        assert persist and persist[0][0] == "branch-isolation"

    def test_code_edit_without_spec_flags_spec_driven(
        self, monkeypatch, tmp_path
    ):
        self._with_state(
            monkeypatch, tmp_path, {"spec": {"status": "pending"}},
        )
        from core.hooks.post_tool_use import _detect_rule_violations
        msg, persist = _detect_rule_violations({
            "tool_name": "Write",
            "tool_input": {"file_path": "/app/service.py"},
            "tool_response": {"filePath": "/app/service.py"},
        })
        assert "spec-driven" in msg
        assert persist and persist[0][0] == "spec-driven"

    def test_forge_scope_creep_reads_tool_input_path(
        self, monkeypatch, tmp_path
    ):
        import yaml as yaml_mod
        home = tmp_path / "fhome"
        plans = home / ".arkaos" / "plans"
        plans.mkdir(parents=True)
        (plans / "active.yaml").write_text("forge-1", encoding="utf-8")
        (plans / "forge-1.yaml").write_text(yaml_mod.safe_dump({
            "status": "executing",
            "plan_phases": [{"deliverables": ["core/allowed.py"]}],
        }), encoding="utf-8")
        monkeypatch.setenv("HOME", str(home))
        from core.hooks.post_tool_use import _forge_violation
        msg = _forge_violation({
            "tool_name": "Edit",
            "tool_input": {"file_path": "/app/unrelated.py"},
            "tool_response": {"filePath": "/app/unrelated.py"},
        }, yaml_mod)
        assert msg, "edit outside plan deliverables must flag scope creep"
        allowed = _forge_violation({
            "tool_name": "Edit",
            "tool_input": {"file_path": "/repo/core/allowed.py"},
            "tool_response": {"filePath": "/repo/core/allowed.py"},
        }, yaml_mod)
        assert allowed == ""


def test_dead_payload_keys_never_read_again():
    """Contract lock: the 2.1.220 payload has no top-level tool_output or
    exit_code — PostToolUse carries tool_input/tool_response (proven
    against the binary; the old keys read empty forever). A reintroduced
    read would silently kill gotchas, violations and cognition capture,
    exactly the regression this PR repairs.
    """
    surfaces = [
        REPO_ROOT / "core" / "hooks" / "post_tool_use.py",
        REPO_ROOT / "config" / "hooks" / "_lib" / "fastpath" / "engine.cjs",
        REPO_ROOT / "config" / "hooks" / "post-tool-use.ps1",
    ]
    payload_exit_reads = re.compile(
        r"get_str\([^)]*[\"']exit_code[\"']\)"   # python
        r"|payload\.exit_code"                     # cjs / ps1
        r"|stdin_json\.get\([\"']exit_code[\"']\)"
    )
    for surface in surfaces:
        text = surface.read_text(encoding="utf-8")
        # The dead-key string is banned outright — comments included —
        # so the lock stays a plain substring check with no parser.
        assert "tool_output" not in text, (
            f"dead payload key string present in {surface.name}"
        )
        assert not payload_exit_reads.search(text), (
            f"top-level exit_code read in {surface.name}"
        )


# ─── stop ────────────────────────────────────────────────────────────────


def _make_transcript(path: Path, *, with_external: bool) -> None:
    recs = [
        {"role": "user", "content": "implement a Laravel OrderService"},
        {"role": "assistant", "content": "[arka:routing] dev -> paulo"},
    ]
    if with_external:
        recs.append({
            "role": "assistant",
            "content": [{"type": "tool_use", "name": "WebFetch",
                         "input": {"url": "https://laravel.com/docs"}}],
        })
    recs.append({"role": "assistant",
                 "content": "[arka:qg:approved]\n[arka:phase:13] done"})
    path.write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")


class TestStop:
    def _run(self, hook_home, tmp_path, *, session_id, with_external,
             wf_required, stop_hook_active="false"):
        transcript = tmp_path / "transcript.jsonl"
        _make_transcript(transcript, with_external=with_external)
        queue = tmp_path / "queue"
        WF_REQUIRED_DIR.mkdir(parents=True, exist_ok=True)
        marker = WF_REQUIRED_DIR / session_id
        if wf_required:
            marker.write_text("1", encoding="utf-8")
        else:
            marker.unlink(missing_ok=True)
        env = _env(hook_home)
        env["ARKA_AUTO_DOC_QUEUE"] = str(queue)
        try:
            result = _run_module("core.hooks.stop", {
                "session_id": session_id,
                "transcript_path": str(transcript),
                "stop_hook_active": stop_hook_active,
                "cwd": str(tmp_path),
            }, env)
        finally:
            marker.unlink(missing_ok=True)
        return result, queue

    def test_enqueues_auto_doc_when_all_conditions_met(
        self, hook_home, tmp_path
    ):
        result, queue = self._run(
            hook_home, tmp_path, session_id="stop-ok-pr6",
            with_external=True, wf_required=True,
        )
        assert result.returncode == 0, result.stderr
        pending = list((queue / "pending").glob("*.json"))
        assert len(pending) == 1
        payload = json.loads(pending[0].read_text(encoding="utf-8"))
        assert payload["session_id"] == "stop-ok-pr6"
        assert payload["qg_verdict"] == "APPROVED"

    def test_skips_without_external_research(self, hook_home, tmp_path):
        result, queue = self._run(
            hook_home, tmp_path, session_id="stop-noext-pr6",
            with_external=False, wf_required=True,
        )
        assert result.returncode == 0
        pending_dir = queue / "pending"
        assert not pending_dir.exists() or not any(pending_dir.glob("*.json"))

    def test_skips_when_flow_not_required(self, hook_home, tmp_path):
        result, queue = self._run(
            hook_home, tmp_path, session_id="stop-noflow-pr6",
            with_external=True, wf_required=False,
        )
        assert result.returncode == 0
        pending_dir = queue / "pending"
        assert not pending_dir.exists() or not any(pending_dir.glob("*.json"))

    def test_stop_hook_active_guards_against_loops(self, hook_home, tmp_path):
        result, queue = self._run(
            hook_home, tmp_path, session_id="stop-loop-pr6",
            with_external=True, wf_required=True, stop_hook_active="true",
        )
        assert result.returncode == 0
        pending_dir = queue / "pending"
        assert not pending_dir.exists() or not any(pending_dir.glob("*.json"))

    def test_writes_enforcement_telemetry(self, hook_home, tmp_path):
        self._run(
            hook_home, tmp_path, session_id="stop-telemetry-pr6",
            with_external=True, wf_required=True,
        )
        telemetry = (
            Path(hook_home["HOME"]) / ".arkaos" / "telemetry"
            / "enforcement.jsonl"
        )
        assert telemetry.is_file()
        rows = [
            json.loads(line)
            for line in telemetry.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        row = next(
            r for r in rows if r["session_id"] == "stop-telemetry-pr6"
        )
        assert row["event"] == "stop-hook-flow-check"
        assert row["mode"] == "warn"
        assert row["closing_marker_found"] is True  # [arka:phase:13]
        assert "meta_tag_found" in row


# ─── user_prompt_submit ──────────────────────────────────────────────────


class TestUserPromptSubmit:
    def test_outputs_route_reminder_json(self, hook_home):
        result = _run_module("core.hooks.user_prompt_submit", {
            "userInput": "hello there", "session_id": "ups-basic",
        }, _env(hook_home))
        assert result.returncode == 0
        assert "[ARKA:ROUTE]" in _ctx(result)

    def test_classifier_marks_flow_required(self, hook_home):
        result = _run_module("core.hooks.user_prompt_submit", {
            "userInput": "implement the new payment feature",
            "session_id": "ups-classify",
        }, _env(hook_home))
        assert "[ARKA:WORKFLOW-REQUIRED]" in _ctx(result)
        marker = Path(hook_home["ARKA_WF_REQUIRED_DIR"]) / "ups-classify"
        assert marker.is_file()

    def test_slash_commands_skip_classifier(self, hook_home):
        result = _run_module("core.hooks.user_prompt_submit", {
            "userInput": "/dev implement feature",
            "session_id": "ups-slash",
        }, _env(hook_home))
        assert "[ARKA:WORKFLOW-REQUIRED]" not in _ctx(result)
        marker = Path(hook_home["ARKA_WF_REQUIRED_DIR"]) / "ups-slash"
        assert not marker.exists()

    def test_vague_code_request_injects_refine_suggestion(self, hook_home):
        # Interaction Reform PR5 — vague + code-modifying → refine hint.
        result = _run_module("core.hooks.user_prompt_submit", {
            "userInput": "cria um site melhor",
            "session_id": "ups-refine",
        }, _env(hook_home))
        out = _ctx(result)
        assert "[arka:refine-suggested]" in out

    def test_specific_code_request_has_no_refine_suggestion(self, hook_home):
        result = _run_module("core.hooks.user_prompt_submit", {
            "userInput": (
                "implementa retry com backoff exponencial em "
                "core/api/client.py com no máximo 3 tentativas e testes"
            ),
            "session_id": "ups-no-refine",
        }, _env(hook_home))
        out = _ctx(result)
        assert "[arka:refine-suggested]" not in out

    def test_slash_command_never_gets_refine_suggestion(self, hook_home):
        result = _run_module("core.hooks.user_prompt_submit", {
            "userInput": "/arka refine faz um site",
            "session_id": "ups-refine-slash",
        }, _env(hook_home))
        out = _ctx(result)
        assert "[arka:refine-suggested]" not in out

    @pytest.mark.parametrize("prompt", [
        "fix the typo in README.md",       # names a file
        "add a test to AuthService",       # CamelCase identifier
        "corrige o user_repo agora",       # snake_case identifier
        "atualiza o `config.yaml`",        # backticked term
    ])
    def test_short_but_concrete_request_no_refine_suggestion(
        self, hook_home, prompt
    ):
        # QG calibration blocker (2026-07-09): a short code-modifying ask
        # that names a concrete target is specific, not vague — the +20
        # no-files scorer constant must not trip the hint.
        result = _run_module("core.hooks.user_prompt_submit", {
            "userInput": prompt, "session_id": "ups-concrete",
        }, _env(hook_home))
        out = _ctx(result)
        assert "[arka:refine-suggested]" not in out, prompt

    def test_surfaces_kb_cite_nudge_on_high_effort(self, hook_home):
        sid = "ups-nudge-high-pr6"
        cite_dir = Path("/tmp/arkaos-cite")
        cite_dir.mkdir(parents=True, exist_ok=True)
        (cite_dir / f"{sid}.json").write_text(json.dumps({
            "passed": False, "reason": "missing",
            "suggestion": "KB-first nudge",
        }), encoding="utf-8")
        result = _run_module("core.hooks.user_prompt_submit", {
            "userInput": "hi", "session_id": sid,
            "effort": {"level": "high"},
        }, _env(hook_home))
        assert "[arka:suggest] KB-first nudge" in _ctx(result)
        assert not (cite_dir / f"{sid}.json").exists()  # one-shot

    def test_suppresses_nudge_on_low_effort(self, hook_home):
        sid = "ups-nudge-low-pr6"
        cite_dir = Path("/tmp/arkaos-cite")
        cite_dir.mkdir(parents=True, exist_ok=True)
        nudge_file = cite_dir / f"{sid}.json"
        nudge_file.write_text(json.dumps({
            "passed": False, "reason": "missing",
            "suggestion": "KB-first nudge",
        }), encoding="utf-8")
        try:
            result = _run_module("core.hooks.user_prompt_submit", {
                "userInput": "hi", "session_id": sid,
                "effort": {"level": "low"},
            }, _env(hook_home))
            assert "KB-first nudge" not in _ctx(result)
        finally:
            nudge_file.unlink(missing_ok=True)

    # ─── PR-A3: deadline budget ──────────────────────────────────────

    def test_zero_budget_still_exits_clean_and_marks_the_turn(
        self, hook_home
    ):
        """End-to-end floor: at a zero budget the hook exits 0, still
        emits the assembled context, and names the skipped stages. The
        strong pins (bridge mandatory, exact skip semantics) live in
        the in-process tests below, where the tracer can see them."""
        env = _env(hook_home)
        env["ARKA_UPS_BUDGET_MS"] = "0"
        result = _run_module("core.hooks.user_prompt_submit", {
            "userInput": "hello there", "session_id": "ups-budget-0",
        }, env)
        assert result.returncode == 0
        out = _ctx(result)
        assert "[ARKA:ROUTE]" in out
        # The EXACT set, with no "nudges": this session has no one-shot
        # file pending, and a gate that recorded a skip for work with
        # nothing to do would inflate the telemetry the 6000 ms default
        # will be judged on.
        assert (
            "[arka:degraded] skipped=token-hygiene,cognitive-hits"
            " reason=budget"
        ) in out

    def test_generous_budget_carries_no_degraded_marker(self, hook_home):
        env = _env(hook_home)
        env["ARKA_UPS_BUDGET_MS"] = "60000"
        result = _run_module("core.hooks.user_prompt_submit", {
            "userInput": "hello there", "session_id": "ups-budget-big",
        }, env)
        assert "[arka:degraded]" not in _ctx(result)

    def test_zero_budget_runs_the_bridge_and_names_the_skips(
        self, hook_home, monkeypatch, capsys
    ):
        """The bridge is mandatory even at zero budget (a sentinel only
        the bridge can emit must survive), and the marker carries the
        exact skipped-stage names — a mutation that makes the bridge
        skippable, or that neuters either skip path, dies here."""
        from core.hooks import user_prompt_submit as ups

        for key, value in _env(hook_home).items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("ARKA_UPS_BUDGET_MS", "0")
        monkeypatch.setattr(
            ups, "_run_bridge", lambda *a: "[BRIDGE-SENTINEL]"
        )
        sid = "ups-budget-ip"
        cite_dir = Path("/tmp/arkaos-cite")
        cite_dir.mkdir(parents=True, exist_ok=True)
        (cite_dir / f"{sid}.json").write_text(json.dumps({
            "passed": False, "reason": "missing", "suggestion": "x",
        }), encoding="utf-8")
        try:
            assert ups.main(
                {"userInput": "hello there", "session_id": sid}, "{}"
            ) == 0
        finally:
            (cite_dir / f"{sid}.json").unlink(missing_ok=True)
        payload = json.loads(capsys.readouterr().out)
        out = payload["hookSpecificOutput"]["additionalContext"]
        assert "[BRIDGE-SENTINEL]" in out, "the bridge must never be skipped"
        assert (
            "[arka:degraded] skipped=token-hygiene,cognitive-hits,nudges"
            " reason=budget"
        ) in out

    def test_nudge_gate_refuses_a_traversal_session_id(self, tmp_path):
        """CWE-22: the id reaches the gate straight from stdin and
        becomes a path. Before the guard, "../<dir>/victim" read a file
        the hook does not own into the model context and unlinked it."""
        from core.hooks import user_prompt_submit as ups

        victim_dir = tmp_path / "victim-dir"
        victim_dir.mkdir()
        victim = victim_dir / "victim.json"
        victim.write_text(json.dumps({
            "passed": False, "reason": "missing", "suggestion": "PWNED",
        }), encoding="utf-8")
        traversal = f"../{victim_dir.name}/victim"

        def _fake_temp_dir(_subdir: str):
            return tmp_path / "arkaos-cite"

        (tmp_path / "arkaos-cite").mkdir()
        monkey = pytest.MonkeyPatch()
        monkey.setattr(ups, "arkaos_temp_dir", _fake_temp_dir)
        try:
            assert ups._nudges_pending(traversal) is False
        finally:
            monkey.undo()
        assert victim.is_file(), "a file the hook does not own must survive"

    def test_budget_run_skips_after_the_deadline_and_records_it(
        self, monkeypatch
    ):
        """Pins _Budget directly: past the deadline run() returns ""
        without calling the stage, over() answers True, and both record
        the skip that marker() then names."""
        from core.hooks import user_prompt_submit as ups

        monkeypatch.setenv("ARKA_UPS_BUDGET_MS", "0")
        budget = ups._Budget(time.monotonic())
        assert budget.run("x", lambda: "PAYLOAD") == ""
        assert budget.skipped == ["x"]
        assert budget.stage_ms == {}, "a skipped stage is never timed"
        assert budget.over("y") is True
        assert budget.skipped == ["x", "y"]
        assert budget.marker() == (
            "\n[arka:degraded] skipped=x,y reason=budget"
        )

    def test_budget_inside_the_deadline_runs_and_times(self, monkeypatch):
        from core.hooks import user_prompt_submit as ups

        monkeypatch.setenv("ARKA_UPS_BUDGET_MS", "60000")
        budget = ups._Budget(time.monotonic())
        assert budget.run("x", lambda: "PAYLOAD") == "PAYLOAD"
        assert "x" in budget.stage_ms
        assert budget.over("y") is False
        assert budget.skipped == []
        assert budget.marker() == ""

    def test_log_metrics_records_degraded_and_stage_ms(
        self, tmp_path, monkeypatch
    ):
        """PR-A3: the metrics row names what was cut and what each stage
        cost — the telemetry that decides whether the 6000 ms default is
        right."""
        from core.hooks import user_prompt_submit as ups

        monkeypatch.setattr(ups, "_CACHE_DIR", tmp_path)
        budget = ups._Budget(time.monotonic())
        budget.stage_ms["bridge"] = 12
        budget.skipped.append("token-hygiene")
        ups._log_metrics(5, "hi there", budget)
        row = json.loads(
            (tmp_path / "hook-metrics.jsonl").read_text().splitlines()[-1]
        )
        assert row["degraded"] == ["token-hygiene"]
        assert row["stage_ms"]["bridge"] == 12

    def test_sync_notice_on_version_drift(self, hook_home, tmp_path):
        fake_repo = tmp_path / "fake-repo"
        fake_repo.mkdir()
        (fake_repo / "VERSION").write_text("9.9.9\n", encoding="utf-8")
        home = Path(hook_home["HOME"])
        (home / ".arkaos" / ".repo-path").write_text(
            str(fake_repo), encoding="utf-8"
        )
        result = _run_module("core.hooks.user_prompt_submit", {
            "userInput": "hello", "session_id": "ups-sync",
        }, _env(hook_home))
        assert "[arka:update-available] ArkaOS v9.9.9" in _ctx(result)


# ─── pure helpers (in-process) ───────────────────────────────────────────


class TestHelpers:
    def test_wf_classify_matches_creation_verbs(self):
        from core.hooks.user_prompt_submit import _wf_classify
        assert _wf_classify("implement the feature") is True
        assert _wf_classify("cria o componente") is True
        assert _wf_classify("continua") is True
        assert _wf_classify("what is the weather") is False
        assert _wf_classify("/dev implement") is False
        assert _wf_classify("!ls") is False
        assert _wf_classify("") is False

    def test_wf_classify_question_guard(self):
        # X5 (Cross-Machine Lab): interrogative-led prompts ending in "?"
        # are information questions even when they contain an action verb.
        from core.hooks.user_prompt_submit import _wf_classify
        assert _wf_classify("o que e que este projeto faz?") is False
        assert _wf_classify("como fazes o deploy?") is False
        assert _wf_classify("how do I implement auth here?") is False
        assert _wf_classify("qual abordagem devo implementar?") is False
        # Polite requests keep matching — the lead word is not interrogative.
        assert _wf_classify("podes implementar a exportacao?") is True
        assert _wf_classify("can you add user auth?") is True
        # Interrogative lead without "?" stays a directive.
        assert _wf_classify("como combinado, implementa a feature") is True

    def test_wf_classify_p17_lot_decisions_preserved(self):
        # The P17 prompt lot (ubuntu-log U-007) measured 10/10 identical
        # decisions across platforms. This pins those decisions, with L04
        # flipped to False — the X5 false positive this guard fixes.
        from core.hooks.user_prompt_submit import _wf_classify
        lot = {
            "implementa uma nova feature de exportacao CSV": True,   # L01
            "le os logs": False,                                     # L02
            "corrige o bug do encoding no stop hook": True,          # L03
            "o que e que este projeto faz?": False,                  # L04 (X5)
            "melhora isto": True,                                    # L05
            "add user authentication to the API": True,              # L06
            "/arka status": False,                                   # L07
            "cria um script que faz backup da telemetria": True,     # L08
            "porque e que o roteamento parece pior no Windows?": False,  # L09
            "refactor the hook wrappers to share one resolver": True,    # L10
        }
        for prompt, expected in lot.items():
            assert _wf_classify(prompt) is expected, prompt

    def test_query_hint_priority_and_clip(self):
        from core.hooks.pre_tool_use import _query_hint
        assert _query_hint({"query": "q", "prompt": "p"}) == "q"
        assert _query_hint({"prompt": "p", "url": "u"}) == "p"
        assert _query_hint({"url": "u"}) == "u"
        assert _query_hint({}) == ""
        assert len(_query_hint({"query": "x" * 900})) == 500

    def test_normalize_pattern_masks_volatile_parts(self):
        from core.hooks.post_tool_use import _normalize_pattern
        line = (
            "2026-07-04T10:00:00Z error at abcdef1234567 line 42 in x.py:7:"
        )
        pattern = _normalize_pattern(line)
        assert "TIMESTAMP" in pattern
        assert "HASH" in pattern
        assert "line N" in pattern
        assert ":N:" in pattern

    def test_categorize_error_lines(self):
        from core.hooks.post_tool_use import _categorize
        assert _categorize("php artisan migrate failed") == "laravel"
        assert _categorize("npm ERR! broken") == "frontend"
        assert _categorize("EACCES permission denied") == "permissions"
        assert _categorize("something unknown broke") == "general"

    def test_extract_persona_dispatch_wins_over_routing(self):
        from core.hooks.stop import _extract_persona
        msg = (
            "[arka:routing] dev -> paulo\n"
            "[arka:dispatch] paulo -> backend-dev\n"
        )
        assert _extract_persona(msg) == "backend-dev"
        assert _extract_persona("[arka:routing] dev -> Paulo") == "paulo"
        assert _extract_persona("no markers") == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
