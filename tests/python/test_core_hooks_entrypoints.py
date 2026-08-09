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

from core.shared.temp_paths import arkaos_temp_dir

REPO_ROOT = Path(__file__).resolve().parents[2]


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
        # Path.home() consults USERPROFILE on Windows and HOME on POSIX, and
        # _run_module inherits os.environ — so setting HOME alone left the
        # real profile in play and every hook read the developer's own
        # ~/.arkaos/config.json instead of the fixture's. Same pairing as
        # tests/python/watch/conftest.py and tests/python/diagram/conftest.py.
        "USERPROFILE": str(home),
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
        wf_dir = Path(hook_home["ARKA_WF_REQUIRED_DIR"])
        wf_dir.mkdir(parents=True, exist_ok=True)
        marker = wf_dir / session_id
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
        wf_dir = Path(hook_home["ARKA_WF_REQUIRED_DIR"])
        wf_dir.mkdir(parents=True, exist_ok=True)
        marker = wf_dir / session_id
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
        # QG round 1 (B1): arm the state where the TRACKER puts it —
        # the per-project .arka/workflow-state.json — so these tests
        # exercise the production reader, not a legacy path.
        home = tmp_path / "vhome"
        (home / ".arkaos").mkdir(parents=True)
        monkeypatch.setenv("HOME", str(home))
        project = tmp_path / "proj"
        (project / ".arka").mkdir(parents=True)
        (project / ".arka" / "workflow-state.json").write_text(
            json.dumps({"phases": phases}), encoding="utf-8",
        )
        monkeypatch.chdir(project)
        from core.workflow import state as _st

        _st.reset_root_cache()

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
        wf_dir = Path(hook_home["ARKA_WF_REQUIRED_DIR"])
        wf_dir.mkdir(parents=True, exist_ok=True)
        marker = wf_dir / session_id
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
        cite_dir = arkaos_temp_dir("arkaos-cite")
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
        cite_dir = arkaos_temp_dir("arkaos-cite")
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

    def test_v1_migration_notice_ignores_orphan_dir(self, tmp_path, monkeypatch):
        # Cross-Machine Lab U1: a leftover v1 dir holding one bookkeeping
        # file re-armed the notice forever, and the early-return in main()
        # killed the whole per-prompt chain on both platforms.
        from core.hooks.user_prompt_submit import _v1_migration_notice
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        v1 = tmp_path / ".claude" / "skills" / "arkaos"
        v1.mkdir(parents=True)
        (v1 / ".arkaos-root").write_text("x", encoding="utf-8")
        assert _v1_migration_notice() is None

    def test_v1_migration_notice_fires_on_real_v1(self, tmp_path, monkeypatch):
        from core.hooks.user_prompt_submit import _v1_migration_notice
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        v1 = tmp_path / ".claude" / "skills" / "arkaos"
        v1.mkdir(parents=True)
        (v1 / "SKILL.md").write_text("# v1\n", encoding="utf-8")
        notice = _v1_migration_notice()
        assert notice is not None and "[MIGRATION]" in notice

    def test_v1_migration_notice_trusts_v2_manifest(self, tmp_path, monkeypatch):
        # install-manifest.json is the canonical v2 signal; a functional
        # v2 install is never nagged even when a real v1 dir remains.
        from core.hooks.user_prompt_submit import _v1_migration_notice
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        v1 = tmp_path / ".claude" / "skills" / "arkaos"
        v1.mkdir(parents=True)
        (v1 / "SKILL.md").write_text("# v1\n", encoding="utf-8")
        arkaos = tmp_path / ".arkaos"
        arkaos.mkdir()
        (arkaos / "install-manifest.json").write_text("{}", encoding="utf-8")
        assert _v1_migration_notice() is None

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


# ─── degraded-run telemetry (#502) ───────────────────────────────────────
#
# A gate that allows because it could not run is indistinguishable, from
# the outside, from a gate that ran and found nothing: exit 0, no stdout,
# no stderr. record_degraded() is what makes the two distinguishable, so
# the tests below are the only thing standing between a working record and
# a mechanism that silently records nothing — the exact failure it exists
# to expose. Two halves: the writer's own contract, then every call site.


@pytest.fixture
def degraded_home(tmp_path, monkeypatch):
    """Isolated home for the in-process writer tests.

    Both variables, deliberately: Path.home() consults HOME on POSIX and
    USERPROFILE on Windows, and record_degraded ships on both. Setting one
    leaves the developer's real ~/.arkaos in play on the other platform.
    """
    home = tmp_path / "degraded-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


def _degraded_path(home: Path) -> Path:
    return home / ".arkaos" / "telemetry" / "hook-degraded.jsonl"


def _degraded_lines(home: Path) -> list[dict]:
    """Parsed JSONL records, or [] when nothing was ever written.

    Parses rather than greps: a record that is not valid JSON is not a
    record, and the whole point is that a reader can consume the file.
    """
    path = _degraded_path(home)
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class TestRecordDegraded:
    """The writer: schema, append semantics, and the never-raises promise."""

    def test_writes_one_line_with_the_declared_schema(self, degraded_home):
        from core.hooks._shared import record_degraded
        record_degraded("pre-tool-use", "kb-gate-import-failed", "no pydantic")
        lines = _degraded_lines(degraded_home)
        assert len(lines) == 1
        assert set(lines[0]) == {"ts", "hook", "reason", "detail"}
        assert lines[0]["hook"] == "pre-tool-use"
        assert lines[0]["reason"] == "kb-gate-import-failed"
        assert lines[0]["detail"] == "no pydantic"
        assert re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", lines[0]["ts"]
        ), f"ts is not the UTC second-precision form: {lines[0]['ts']!r}"

    def test_events_append_one_line_each(self, degraded_home):
        from core.hooks._shared import record_degraded
        record_degraded("pre-tool-use", "first")
        record_degraded("pre-tool-use", "second")
        raw = _degraded_path(degraded_home).read_text(encoding="utf-8")
        assert raw.count("\n") == 2, "JSONL: exactly one newline per record"
        assert [r["reason"] for r in _degraded_lines(degraded_home)] == [
            "first", "second"
        ]

    def test_detail_defaults_to_the_live_exception(self, degraded_home):
        # Every current call site sits inside an `except` block and passes
        # no detail — the exception in flight IS the diagnosis, and a record
        # that dropped it would name the gate but never the cause.
        from core.hooks._shared import record_degraded
        try:
            raise ModuleNotFoundError("No module named 'pydantic'")
        except ModuleNotFoundError:
            record_degraded("pre-tool-use", "kb-gate-import-failed")
        assert _degraded_lines(degraded_home)[0]["detail"] == (
            "ModuleNotFoundError: No module named 'pydantic'"
        )

    def test_detail_is_clipped(self, degraded_home):
        from core.hooks._shared import record_degraded
        record_degraded("pre-tool-use", "verbose", "x" * 4000)
        assert len(_degraded_lines(degraded_home)[0]["detail"]) == 400

    def test_control_characters_survive_as_valid_json(self, degraded_home):
        # json.dumps escapes them rather than emitting raw bytes; the shell
        # twin has to strip them by hand, so pin the Python side too.
        from core.hooks._shared import record_degraded
        record_degraded("pre-tool-use", "raw", 'tab\there\nnl \x01 "quote" \\')
        record = _degraded_lines(degraded_home)[0]
        assert record["detail"] == 'tab\there\nnl \x01 "quote" \\'

    def test_writes_nothing_to_stdout_or_stderr(self, degraded_home, capsys):
        # NON-NEGOTIABLE for this writer: Claude Code surfaces hook stderr
        # to the user as an error, so a diagnostic there would trade a silent
        # degradation for visible noise on every single event.
        from core.hooks._shared import record_degraded
        record_degraded("pre-tool-use", "silent-by-contract")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_never_raises_when_home_cannot_be_resolved(self, monkeypatch):
        # Exactly what Path.home() does when neither the env nor the passwd
        # database yields a directory. Patched rather than env-deleted: on
        # POSIX, unsetting HOME makes expanduser fall back to the real
        # account and this test would write into the developer's own vault.
        from core.hooks._shared import record_degraded

        def unresolvable():
            raise RuntimeError("Could not determine home directory")

        monkeypatch.setattr(Path, "home", staticmethod(unresolvable))
        record_degraded("pre-tool-use", "no-home")  # must not raise

    def test_never_raises_when_the_telemetry_dir_is_a_file(self, degraded_home):
        arkaos = degraded_home / ".arkaos"
        arkaos.mkdir()
        (arkaos / "telemetry").write_text("occupied", encoding="utf-8")
        from core.hooks._shared import record_degraded
        record_degraded("pre-tool-use", "dir-is-a-file")  # must not raise
        assert (arkaos / "telemetry").read_text(encoding="utf-8") == "occupied"

    @pytest.mark.skipif(
        sys.platform == "win32" or getattr(os, "geteuid", lambda: 1)() == 0,
        reason="directory permissions do not restrict root or Windows",
    )
    def test_never_raises_when_home_is_read_only(self, degraded_home):
        from core.hooks._shared import record_degraded
        os.chmod(degraded_home, 0o500)
        try:
            record_degraded("pre-tool-use", "read-only-home")  # must not raise
        finally:
            os.chmod(degraded_home, 0o700)
        assert _degraded_lines(degraded_home) == []

    def test_rotates_once_past_the_cap(self, degraded_home):
        # The runaway this cap exists for: the degradations recorded here
        # fire on EVERY tool call, so an uncapped log on a broken machine
        # grows without bound (264MB measured in the PR review's probe).
        from core.hooks._shared import DEGRADED_LOG_MAX_BYTES, record_degraded
        path = _degraded_path(degraded_home)
        path.parent.mkdir(parents=True)
        path.write_bytes(b"x" * DEGRADED_LOG_MAX_BYTES)

        record_degraded("pre-tool-use", "after-rotation")

        rotated = path.parent / (path.name + ".1")
        assert rotated.is_file(), "the oversized log must be kept, not deleted"
        assert rotated.stat().st_size == DEGRADED_LOG_MAX_BYTES
        assert [r["reason"] for r in _degraded_lines(degraded_home)] == [
            "after-rotation"
        ]

    def test_does_not_rotate_below_the_cap(self, degraded_home):
        from core.hooks._shared import DEGRADED_LOG_MAX_BYTES, record_degraded
        path = _degraded_path(degraded_home)
        path.parent.mkdir(parents=True)
        path.write_bytes(b"x" * (DEGRADED_LOG_MAX_BYTES - 1))
        record_degraded("pre-tool-use", "still-appending")
        assert not (path.parent / (path.name + ".1")).exists()
        assert path.stat().st_size > DEGRADED_LOG_MAX_BYTES


class TestPreToolUseDegradedCallSites:
    """Every fail-open in core/hooks/pre_tool_use.py leaves a record.

    Each gate turns an unimportable module into "allow" — the right posture
    for governance code, since a broken dependency must never block the
    user's work — and each was previously indistinguishable from a gate that
    ran. The break is applied the way a real one arrives: the module becomes
    unimportable and the gate's own ``except Exception`` is what catches it.
    Nothing here asserts on the handler's source, so deleting a
    record_degraded() call fails these tests rather than passing vacuously.
    """

    @staticmethod
    def _break_import(monkeypatch, module: str) -> None:
        # ``sys.modules[name] = None`` makes ``from name import x`` raise
        # ImportError from inside the import machinery — the same shape a
        # missing transitive dependency produces, without needing one.
        monkeypatch.setitem(sys.modules, module, None)

    def test_kb_gate_records_and_still_allows(self, degraded_home, monkeypatch):
        from core.hooks import pre_tool_use
        self._break_import(monkeypatch, "core.workflow.research_gate")

        verdict = pre_tool_use._kb_gate(str(REPO_ROOT), "WebSearch", "sid", "q")

        assert verdict is None, "fail-open contract: a broken gate allows"
        lines = _degraded_lines(degraded_home)
        assert [(r["hook"], r["reason"]) for r in lines] == [
            ("pre-tool-use", "kb-gate-import-failed")
        ]
        # The auto-captured detail names the module that could not load —
        # without it the record says which gate degraded but never why.
        assert "core.workflow.research_gate" in lines[0]["detail"]

    def test_specialist_gate_records_and_still_allows(
        self, degraded_home, monkeypatch
    ):
        from core.hooks import pre_tool_use
        self._break_import(monkeypatch, "core.workflow.specialist_enforcer")

        verdict = pre_tool_use._specialist_gate(
            str(REPO_ROOT), "Write", "", "sid", "/tmp",
            {"file_path": "/tmp/x.py"}, pre_tool_use._MessagesOnce(""),
        )

        assert verdict is None
        assert [r["reason"] for r in _degraded_lines(degraded_home)] == [
            "specialist-import-failed"
        ]

    def test_frontend_gate_records_and_still_allows(
        self, degraded_home, monkeypatch
    ):
        from core.hooks import pre_tool_use
        self._break_import(monkeypatch, "core.workflow.frontend_gate")

        verdict = pre_tool_use._frontend_gate(
            str(REPO_ROOT), "Write", "", "sid", "/tmp",
            {"file_path": "/tmp/App.vue"}, pre_tool_use._MessagesOnce(""),
        )

        assert verdict is None
        assert [r["reason"] for r in _degraded_lines(degraded_home)] == [
            "frontend-gate-import-failed"
        ]

    def test_config_gate_records_and_still_allows(
        self, degraded_home, monkeypatch
    ):
        from core.hooks import pre_tool_use
        self._break_import(monkeypatch, "core.workflow.config_guard")

        verdict = pre_tool_use._config_gate(
            str(REPO_ROOT), "Write", "", {"file_path": "/tmp/.ruff.toml"}
        )

        assert verdict is None
        assert [r["reason"] for r in _degraded_lines(degraded_home)] == [
            "config-guard-import-failed"
        ]

    def test_flow_gate_records_and_still_allows(self, degraded_home, monkeypatch):
        from core.hooks import pre_tool_use
        self._break_import(monkeypatch, "core.workflow.flow_enforcer")

        verdict = pre_tool_use._flow_gate(
            str(REPO_ROOT), "Write", "", "sid", "/tmp",
            {"file_path": "/tmp/x.py"}, pre_tool_use._MessagesOnce(""),
        )

        assert verdict == 0, "fail-open contract: a broken enforcer allows"
        assert [r["reason"] for r in _degraded_lines(degraded_home)] == [
            "enforcer-import-failed"
        ]

    def test_unhandled_failure_records_and_still_exits_zero(
        self, degraded_home, monkeypatch, capsys
    ):
        """The module's own last resort, executed as ``__main__``.

        runpy re-executes the shipped source under run_name="__main__", so
        the guard under test is the real one rather than a copy of it. The
        failure is injected at main()'s first call — read_stdin_json, bound
        from the cached core.hooks._shared — because a handler that exists
        for "whatever nothing else caught" has no in-band trigger.
        """
        import runpy
        import warnings

        def boom():
            raise RuntimeError("interpreter cannot import the gate modules")

        monkeypatch.setattr("core.hooks._shared.read_stdin_json", boom)

        with warnings.catch_warnings():
            # runpy warns that the module is already in sys.modules — true,
            # expected, and irrelevant here: alter_sys defaults to False, so
            # the fresh execution never replaces the cached entry.
            warnings.simplefilter("ignore", RuntimeWarning)
            with pytest.raises(SystemExit) as exc:
                runpy.run_module("core.hooks.pre_tool_use", run_name="__main__")

        assert exc.value.code == 0, "fail-open contract: still allows"
        captured = capsys.readouterr()
        assert captured.out == "", "an allow emits no stdout, degraded or not"
        lines = _degraded_lines(degraded_home)
        assert [r["reason"] for r in lines] == ["unhandled-fail-open"]
        assert lines[0]["detail"] == (
            "RuntimeError: interpreter cannot import the gate modules"
        )


class TestDecisionsAreNeverRecordedAsDegradation:
    """The other half of the contract, at process level.

    Telemetry that fires on healthy runs is worse than none: it would bury
    the real signal under a line per tool call and teach every reader to
    ignore the file. A gate that ran — whether it allowed or denied — must
    leave this log untouched.
    """

    def test_a_clean_allow_writes_no_degraded_line(self, hook_home):
        result = _run_module("core.hooks.pre_tool_use", {
            "tool_name": "Read", "session_id": "degraded-allow",
            "transcript_path": "", "cwd": "/tmp", "tool_input": {},
        }, _env(hook_home))
        assert result.returncode == 0
        assert _degraded_lines(Path(hook_home["HOME"])) == []

    def test_a_real_deny_writes_no_degraded_line(self, hook_home):
        # exit 2 is a gate doing its job — the documented block code, never
        # a degradation.
        payload = {
            "tool_name": "WebSearch", "session_id": "degraded-deny",
            "transcript_path": "", "cwd": "/tmp",
            "tool_input": {"query": "laravel service pattern"},
        }
        assert _run_module(
            "core.hooks.pre_tool_use", payload, _env(hook_home)
        ).returncode == 0
        second = _run_module("core.hooks.pre_tool_use", payload, _env(hook_home))
        assert second.returncode == 2, second.stderr
        assert _degraded_lines(Path(hook_home["HOME"])) == []


class TestIsWithinProject:
    """The scope predicate itself (#507)."""

    def test_file_inside_the_root_is_governed(self, tmp_path):
        from core.hooks._shared import is_within_project
        root = tmp_path / "project"
        (root / "core").mkdir(parents=True)
        assert is_within_project(str(root / "core" / "svc.py"), str(root))

    def test_the_root_itself_is_governed(self, tmp_path):
        from core.hooks._shared import is_within_project
        assert is_within_project(str(tmp_path), str(tmp_path))

    def test_sibling_with_the_root_as_a_string_prefix_is_not_governed(
        self, tmp_path
    ):
        """`/x/repo-backup` must not read as inside `/x/repo`."""
        from core.hooks._shared import is_within_project
        root = tmp_path / "repo"
        sibling = tmp_path / "repo-backup"
        root.mkdir()
        sibling.mkdir()
        assert not is_within_project(str(sibling / "svc.py"), str(root))

    def test_relative_paths_resolve_against_the_root(self, tmp_path):
        from core.hooks._shared import is_within_project
        assert is_within_project("core/svc.py", str(tmp_path))
        assert not is_within_project("../outside/svc.py", str(tmp_path))

    def test_symlinked_root_compares_equal(self, tmp_path):
        """/tmp -> /private/tmp (macOS) must not make every path foreign."""
        from core.hooks._shared import is_within_project
        real = tmp_path / "real"
        (real / "core").mkdir(parents=True)
        link = tmp_path / "link"
        link.symlink_to(real)
        assert is_within_project(str(link / "core" / "svc.py"), str(real))
        assert is_within_project(str(real / "core" / "svc.py"), str(link))

    def test_missing_evidence_fails_closed(self, tmp_path):
        """No root (or no path) leaves the gate exactly as wide as today."""
        from core.hooks._shared import is_within_project
        assert is_within_project("/anywhere/svc.py", "")
        assert is_within_project("", str(tmp_path))

    def test_unresolvable_path_falls_back_instead_of_raising(self, tmp_path):
        """A hook that raises eats the whole PostToolUse payload, so
        _realpath swallows OSError/ValueError and returns the path
        untouched. A NUL byte is the reachable trigger.

        The predicate then degrades to a lexical prefix test, which keeps
        the fail-closed posture: an unresolvable path INSIDE the root
        stays governed, one outside stays out.
        """
        from core.hooks._shared import _realpath, is_within_project
        poisoned_inside = f"{tmp_path}/pro\x00ject/svc.py"
        assert _realpath(poisoned_inside) == poisoned_inside
        assert is_within_project(poisoned_inside, str(tmp_path)) is True
        assert is_within_project(
            f"{tmp_path}-elsewhere/pro\x00ject/svc.py", str(tmp_path)
        ) is False


class TestPostToolUseGateScope:
    """#507 — the PostToolUse gates judge deliverables, not the scratchpad.

    The reported symptom: spec-driven fired on
    ``/private/tmp/claude-*/**/scratchpad/calib*.py``, a throwaway
    measurement script no spec can or should cover. Each test pairs the
    out-of-root case with the in-root case, so a scope guard that simply
    switched the gate off would fail here.
    """

    def _project_and_scratchpad(self, tmp_path):
        root = tmp_path / "project"
        (root / "core").mkdir(parents=True)
        scratch = tmp_path / "claude-501" / "sess-1" / "scratchpad"
        scratch.mkdir(parents=True)
        return root, scratch

    def _with_state(self, monkeypatch, tmp_path, phases: dict):
        # QG round 1 (B1): the state lives at the project root the
        # payload's cwd declares — written where the tracker writes it.
        home = tmp_path / "shome"
        (home / ".arkaos").mkdir(parents=True)
        monkeypatch.setenv("HOME", str(home))
        root = tmp_path / "project"
        (root / ".arka").mkdir(parents=True, exist_ok=True)
        (root / ".arka" / "workflow-state.json").write_text(
            json.dumps({"phases": phases}), encoding="utf-8",
        )
        monkeypatch.chdir(root)
        from core.workflow import state as _st

        _st.reset_root_cache()

    def _write_payload(self, root, file_path: Path) -> dict:
        return {
            "tool_name": "Write",
            "cwd": str(root),
            "tool_input": {"file_path": str(file_path)},
            "tool_response": {"filePath": str(file_path)},
        }

    # ─── Section 6: spec-driven / sequential-validation ────────────────

    def test_scratchpad_edit_raises_no_violation(self, monkeypatch, tmp_path):
        self._with_state(
            monkeypatch, tmp_path, {"spec": {"status": "pending"}},
        )
        from core.hooks.post_tool_use import _detect_rule_violations
        root, scratch = self._project_and_scratchpad(tmp_path)
        msg, persist = _detect_rule_violations(
            self._write_payload(root, scratch / "calib.py")
        )
        assert msg == "", "scratchpad script is not a governed deliverable"
        assert persist == []

    def test_in_root_edit_still_flags_spec_driven(self, monkeypatch, tmp_path):
        self._with_state(
            monkeypatch, tmp_path, {"spec": {"status": "pending"}},
        )
        from core.hooks.post_tool_use import _detect_rule_violations
        root, _ = self._project_and_scratchpad(tmp_path)
        msg, persist = _detect_rule_violations(
            self._write_payload(root, root / "core" / "svc.py")
        )
        assert "spec-driven" in msg
        assert persist and persist[0][0] == "spec-driven"

    def test_scratchpad_edit_raises_no_sequential_validation(
        self, monkeypatch, tmp_path
    ):
        self._with_state(monkeypatch, tmp_path, {
            "spec": {"status": "completed"},
            "implementation": {"status": "pending"},
        })
        from core.hooks.post_tool_use import _detect_rule_violations
        root, scratch = self._project_and_scratchpad(tmp_path)
        msg, persist = _detect_rule_violations(
            self._write_payload(root, scratch / "calib.py")
        )
        assert msg == ""
        assert persist == []

    def test_in_root_edit_still_flags_sequential_validation(
        self, monkeypatch, tmp_path
    ):
        self._with_state(monkeypatch, tmp_path, {
            "spec": {"status": "completed"},
            "implementation": {"status": "pending"},
        })
        from core.hooks.post_tool_use import _detect_rule_violations
        root, _ = self._project_and_scratchpad(tmp_path)
        msg, persist = _detect_rule_violations(
            self._write_payload(root, root / "core" / "svc.py")
        )
        assert "sequential-validation" in msg
        assert persist and persist[0][0] == "sequential-validation"

    # ─── Section 7: enforcement engine (rules_registry spec-driven) ────

    def _enforcer_msg(self, payload) -> str:
        from core.hooks.post_tool_use import _enforcer_messages
        from core.workflow.enforcer import enforce_tool
        return _enforcer_messages(
            payload, enforce_tool, lambda *a, **k: None, "",
        )

    def test_enforcer_ignores_scratchpad_edit(self, monkeypatch, tmp_path):
        root, scratch = self._project_and_scratchpad(tmp_path)
        # No .arkaos/specs anywhere: the rule would fire on any path it
        # considers in scope.
        monkeypatch.chdir(root)
        assert self._enforcer_msg(
            self._write_payload(root, scratch / "calib.py")
        ) == ""

    def test_enforcer_still_flags_in_root_edit(self, monkeypatch, tmp_path):
        root, _ = self._project_and_scratchpad(tmp_path)
        monkeypatch.chdir(root)
        assert "spec-driven" in self._enforcer_msg(
            self._write_payload(root, root / "core" / "svc.py")
        )

    # ─── Section 8: forge scope-creep ──────────────────────────────────

    def _with_forge_plan(self, monkeypatch, tmp_path, deliverables):
        import yaml as yaml_mod
        home = tmp_path / "fghome"
        plans = home / ".arkaos" / "plans"
        plans.mkdir(parents=True)
        (plans / "active.yaml").write_text("forge-1", encoding="utf-8")
        (plans / "forge-1.yaml").write_text(yaml_mod.safe_dump({
            "status": "executing",
            "plan_phases": [{"deliverables": deliverables}],
        }), encoding="utf-8")
        monkeypatch.setenv("HOME", str(home))
        return yaml_mod

    def test_forge_ignores_scratchpad_edit(self, monkeypatch, tmp_path):
        yaml_mod = self._with_forge_plan(
            monkeypatch, tmp_path, ["core/allowed.py"],
        )
        from core.hooks.post_tool_use import _forge_violation
        root, scratch = self._project_and_scratchpad(tmp_path)
        assert _forge_violation(
            self._write_payload(root, scratch / "calib.py"), yaml_mod,
        ) == ""

    def test_forge_still_flags_in_root_edit_outside_deliverables(
        self, monkeypatch, tmp_path
    ):
        yaml_mod = self._with_forge_plan(
            monkeypatch, tmp_path, ["core/allowed.py"],
        )
        from core.hooks.post_tool_use import _forge_violation
        root, _ = self._project_and_scratchpad(tmp_path)
        assert _forge_violation(
            self._write_payload(root, root / "core" / "svc.py"), yaml_mod,
        ), "an in-root edit outside the plan is still scope creep"


def test_every_posttooluse_file_gate_reads_the_scoped_predicate():
    """Lock the single-point fix (#507).

    Three gates judge ``tool_input.file_path``; the defect was that each
    read it raw. A fourth gate added later must go through
    ``_governed_file_path`` too, so the raw read is allowed exactly once —
    inside that helper.
    """
    source = (
        REPO_ROOT / "core" / "hooks" / "post_tool_use.py"
    ).read_text(encoding="utf-8")
    raw_reads = re.findall(
        r'get_str\(\s*input_data,\s*"tool_input",\s*"file_path"\s*\)', source
    )
    assert len(raw_reads) == 1, (
        "unscoped tool_input.file_path read outside _governed_file_path — "
        f"found {len(raw_reads)}"
    )
    assert source.count("_governed_file_path(input_data)") == 3, (
        "each of the three file-judging gates must call the scope predicate"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
