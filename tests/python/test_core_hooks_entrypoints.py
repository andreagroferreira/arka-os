"""Unit tests for the consolidated hook entrypoints (PR-6 v4.1.0).

Each ``core.hooks.<event>`` module is exercised end-to-end via
``python -m`` with fixture stdin JSON, a tmp HOME, and monkeypatched
state dirs — the same surface the thin bash wrappers call, minus bash.
Pure helpers get direct in-process tests.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
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
    (vault / "Laravel Service Pattern.md").write_text("# note\n")
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
            "tool_name": "Write", "tool_output": "ok", "exit_code": "0",
            "cwd": "/tmp", "session_id": "post-marker",
            "transcript_path": str(transcript),
        }, _env(hook_home))
        assert result.returncode == 0
        assert json.loads(result.stdout) == {}
        auth = Path(hook_home["ARKA_FLOW_AUTH_DIR"]) / "post-marker.json"
        assert auth.is_file()
        data = json.loads(auth.read_text(encoding="utf-8"))
        assert data["marker_type"] == "routing"

    def test_clean_output_short_circuits(self, hook_home):
        result = _run_module("core.hooks.post_tool_use", {
            "tool_name": "Bash", "tool_output": "all good", "exit_code": "0",
            "cwd": "/tmp", "session_id": "post-clean",
            "assistant_message": "",
        }, _env(hook_home))
        assert result.returncode == 0
        assert json.loads(result.stdout) == {}
        gotchas = Path(hook_home["HOME"]) / ".arkaos" / "gotchas.json"
        assert not gotchas.exists()

    def test_error_output_records_gotcha(self, hook_home):
        payload = {
            "tool_name": "Bash",
            "tool_output": "npm ERR! Error: ENOENT no such file",
            "exit_code": "1", "cwd": "/tmp/projx",
            "session_id": "post-err", "assistant_message": "",
        }
        result = _run_module("core.hooks.post_tool_use", payload, _env(hook_home))
        assert result.returncode == 0
        assert json.loads(result.stdout) == {}
        gotchas_file = Path(hook_home["HOME"]) / ".arkaos" / "gotchas.json"
        entries = json.loads(gotchas_file.read_text(encoding="utf-8"))
        assert len(entries) == 1
        assert entries[0]["count"] == 1
        assert entries[0]["category"] == "frontend"  # npm match
        assert entries[0]["projects"] == ["projx"]

        # Same error again → count increments, no duplicate entry.
        _run_module("core.hooks.post_tool_use", payload, _env(hook_home))
        entries = json.loads(gotchas_file.read_text(encoding="utf-8"))
        assert len(entries) == 1
        assert entries[0]["count"] == 2


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
        out = json.loads(result.stdout)
        assert "[ARKA:ROUTE]" in out["additionalContext"]

    def test_classifier_marks_flow_required(self, hook_home):
        result = _run_module("core.hooks.user_prompt_submit", {
            "userInput": "implement the new payment feature",
            "session_id": "ups-classify",
        }, _env(hook_home))
        out = json.loads(result.stdout)
        assert "[ARKA:WORKFLOW-REQUIRED]" in out["additionalContext"]
        marker = Path(hook_home["ARKA_WF_REQUIRED_DIR"]) / "ups-classify"
        assert marker.is_file()

    def test_slash_commands_skip_classifier(self, hook_home):
        result = _run_module("core.hooks.user_prompt_submit", {
            "userInput": "/dev implement feature",
            "session_id": "ups-slash",
        }, _env(hook_home))
        out = json.loads(result.stdout)
        assert "[ARKA:WORKFLOW-REQUIRED]" not in out["additionalContext"]
        marker = Path(hook_home["ARKA_WF_REQUIRED_DIR"]) / "ups-slash"
        assert not marker.exists()

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
        out = json.loads(result.stdout)
        assert "[arka:suggest] KB-first nudge" in out["additionalContext"]
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
            out = json.loads(result.stdout)
            assert "KB-first nudge" not in out["additionalContext"]
        finally:
            nudge_file.unlink(missing_ok=True)

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
        out = json.loads(result.stdout)
        assert "[arka:update-available] ArkaOS v9.9.9" in (
            out["additionalContext"]
        )


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
