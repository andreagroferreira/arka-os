"""Tests for the Stop hook auto-documentor wiring (Task #7).

These tests execute the actual `config/hooks/stop.sh` / `stop.ps1`
scripts in a sandboxed environment and assert that the auto-doc job
queue is populated when the preconditions are met (flow-required,
QG APPROVED, external research present), and left alone otherwise.

Windows test is skipped unless pwsh is available.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
from pathlib import Path

import pytest
from hook_shell import BASH

REPO_ROOT = Path(__file__).resolve().parents[2]
STOP_SH = REPO_ROOT / "config" / "hooks" / "stop.sh"
STOP_PS1 = REPO_ROOT / "config" / "hooks" / "stop.ps1"


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
    # QG approval must land in the *last* assistant message for the hook
    # to detect it via `_load_last_assistant_messages(n=1)`.
    recs.append({"role": "assistant", "content": (
        "[arka:qg:approved]\n[arka:phase:13] done"
    )})
    path.write_text(
        "\n".join(json.dumps(r) for r in recs), encoding="utf-8"
    )


def _run_stop_sh(
    *,
    tmp_path: Path,
    session_id: str,
    transcript_path: Path,
    wf_required: bool,
) -> Path:
    """Invoke stop.sh in a sandbox and return the queue root."""
    queue = tmp_path / "queue"
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)

    # Scoped through ARKA_WF_REQUIRED_DIR (set in `env` below) — the
    # override core.shared.temp_paths.wf_required_dir reads, which stop.sh
    # inherits via `-m core.hooks.stop`. The literal /tmp/arkaos-wf-required
    # this replaced is the directory LIVE sessions coordinate through: the
    # test planted a marker in it and then unlinked one, i.e. a unit test
    # reading and deleting production state. Nothing in the chain needs the
    # shared path, and exercising the override here is also the end-to-end
    # proof that writer and reader now resolve the same directory.
    wf_dir = tmp_path / "arkaos-wf-required"
    wf_dir.mkdir(parents=True, exist_ok=True)
    marker = wf_dir / session_id
    if wf_required:
        marker.write_text("1", encoding="utf-8")
    else:
        marker.unlink(missing_ok=True)

    payload = {
        "session_id": session_id,
        "transcript_path": str(transcript_path),
        "stop_hook_active": "false",
        "cwd": str(tmp_path),
    }
    env = os.environ.copy()
    env["ARKAOS_ROOT"] = str(REPO_ROOT)
    env["ARKA_WF_REQUIRED_DIR"] = str(wf_dir)
    env["ARKA_AUTO_DOC_QUEUE"] = str(queue)
    env["HOME"] = str(home)
    env["PYTHONPATH"] = str(REPO_ROOT)
    # No detached stop-lint workers from the harness (they would race
    # pytest's tmp_path cleanup; the enqueue has its own unit tests).
    env["ARKA_STOP_LINT"] = "0"

    subprocess.run(
        [BASH, str(STOP_SH)],
        input=json.dumps(payload).encode("utf-8"),
        env=env,
        timeout=15,
        check=False,
        capture_output=True,
    )
    # Cleanup the belt-and-braces marker so subsequent tests start clean.
    marker.unlink(missing_ok=True)
    return queue


@pytest.mark.skipif(platform.system() == "Windows", reason="bash hook")
def test_stop_hook_enqueues_job_when_all_conditions_met(tmp_path):
    session_id = "sess-stop-ok"
    transcript = tmp_path / "transcript.jsonl"
    _make_transcript(transcript, with_external=True)
    queue = _run_stop_sh(
        tmp_path=tmp_path,
        session_id=session_id,
        transcript_path=transcript,
        wf_required=True,
    )
    pending = list((queue / "pending").glob("*.json")) if (queue / "pending").exists() else []
    assert len(pending) == 1
    payload = json.loads(pending[0].read_text(encoding="utf-8"))
    assert payload["session_id"] == session_id
    assert payload["qg_verdict"] == "APPROVED"


@pytest.mark.skipif(platform.system() == "Windows", reason="bash hook")
def test_stop_hook_skips_when_no_external_research(tmp_path):
    session_id = "sess-stop-no-ext"
    transcript = tmp_path / "transcript.jsonl"
    _make_transcript(transcript, with_external=False)
    queue = _run_stop_sh(
        tmp_path=tmp_path,
        session_id=session_id,
        transcript_path=transcript,
        wf_required=True,
    )
    pending_dir = queue / "pending"
    assert not pending_dir.exists() or not any(pending_dir.glob("*.json"))


@pytest.mark.skipif(platform.system() == "Windows", reason="bash hook")
def test_stop_hook_skips_when_flow_not_required(tmp_path):
    session_id = "sess-stop-no-flow"
    transcript = tmp_path / "transcript.jsonl"
    _make_transcript(transcript, with_external=True)
    queue = _run_stop_sh(
        tmp_path=tmp_path,
        session_id=session_id,
        transcript_path=transcript,
        wf_required=False,
    )
    pending_dir = queue / "pending"
    assert not pending_dir.exists() or not any(pending_dir.glob("*.json"))


# ─── F1-A2: turn-capture enqueue (unit-level, no bash) ─────────────────


class _FakeProc:
    stdin = None


def test_enqueue_turn_capture_spawns_detached_worker(monkeypatch, tmp_path):
    from core.hooks import stop

    calls = []
    monkeypatch.setattr(
        "subprocess.Popen", lambda *a, **k: calls.append((a, k)) or _FakeProc()
    )
    monkeypatch.setattr(stop, "repo_path", lambda: str(REPO_ROOT))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ARKA_SESSION_MEMORY", raising=False)
    stop._enqueue_turn_capture("sess-x", "/tmp/t.jsonl", "/repo/proj")
    assert len(calls) == 1
    argv = calls[0][0][0]
    assert argv[1:5] == ["-m", "core.memory.turn_capture", "sess-x", "/tmp/t.jsonl"]
    assert argv[5] == "/repo/proj"
    assert calls[0][1]["start_new_session"] is True


def test_enqueue_turn_capture_env_kill_switch(monkeypatch, tmp_path):
    from core.hooks import stop

    called = []
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: called.append(1))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ARKA_SESSION_MEMORY", "0")
    stop._enqueue_turn_capture("sess-x", "/tmp/t.jsonl", "")
    assert not called


def test_enqueue_turn_capture_config_flag_off(monkeypatch, tmp_path):
    from core.hooks import stop

    cfg_dir = tmp_path / ".arkaos"
    cfg_dir.mkdir()
    (cfg_dir / "config.json").write_text(
        json.dumps({"memory": {"sessionMemory": False}}), encoding="utf-8"
    )
    called = []
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: called.append(1))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ARKA_SESSION_MEMORY", raising=False)
    stop._enqueue_turn_capture("sess-x", "/tmp/t.jsonl", "")
    assert not called


def test_main_enqueues_capture_before_wf_marker_gate(monkeypatch, tmp_path):
    """Capture runs for EVERY turn — even when no workflow marker exists."""
    from core.hooks import stop

    calls = []
    monkeypatch.setattr(
        "subprocess.Popen", lambda *a, **k: calls.append((a, k)) or _FakeProc()
    )
    monkeypatch.setattr(stop, "repo_path", lambda: str(REPO_ROOT))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ARKA_SESSION_MEMORY", raising=False)
    transcript = tmp_path / "t.jsonl"
    transcript.write_text('{"role":"assistant","content":"done"}\n', encoding="utf-8")
    rc = stop.main({
        "session_id": "sess-main-nc",
        "transcript_path": str(transcript),
        "stop_hook_active": "false",
        "cwd": str(tmp_path),
    })
    assert rc == 0
    capture_calls = [
        c for c in calls if "core.memory.turn_capture" in c[0][0]
    ]
    assert len(capture_calls) == 1


def test_stop_delivers_queued_reviewer_verdicts(tmp_path, monkeypatch, capsys):
    """The orchestrator learns of a reviewer verdict HERE: Stop's
    additionalContext is 'delivered to the model', SubagentStop's is
    'delivered to the subagent' (2.1.220 contract)."""
    import json as _json

    monkeypatch.setenv("HOME", str(tmp_path))
    from core.governance import reviewer_ledger
    from core.hooks import stop as stop_hook

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    reviewer_ledger.queue_notice(
        "stop-notice", None, "[arka:subagent-qa] francisca-tech needs gating"
    )
    stop_hook._emit_subagent_notices("stop-notice")
    payload = _json.loads(capsys.readouterr().out.strip())
    assert payload["hookSpecificOutput"]["hookEventName"] == "Stop"
    assert "[arka:subagent-qa]" in payload["hookSpecificOutput"]["additionalContext"]


def test_stop_is_silent_without_notices(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    from core.hooks import stop as stop_hook

    stop_hook._emit_subagent_notices("stop-empty")
    assert capsys.readouterr().out.strip() == ""


def test_notices_survive_a_failed_emit(tmp_path, monkeypatch):
    """Clearing before emitting loses the verdict permanently — the exact
    relay failure this surface exists to prevent. A failed delivery must
    leave the queue intact for the next turn, and must not abort the hook."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    from core.governance import reviewer_ledger
    from core.hooks import stop as stop_hook

    reviewer_ledger.queue_notice("stop-fail", None, "[arka:subagent-qa] pending")

    def _boom(_event, _context):
        raise OSError("stdout closed")

    monkeypatch.setattr(stop_hook, "emit_additional_context", _boom)
    stop_hook._emit_subagent_notices("stop-fail")  # must not raise

    assert "[arka:subagent-qa] pending" in reviewer_ledger.notices_context(
        "stop-fail"
    ), "a failed emit must not consume the queue"


def test_stop_main_delivers_notices_end_to_end(tmp_path, monkeypatch, capsys):
    """The feature's LAST hop: the only path by which the operator ever
    learns a verdict exists. Deleting _emit_subagent_notices from main()
    left the whole suite green — the same gap closed for post_tool_use
    and session_end, left open on the one that matters most."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    from core.governance import reviewer_ledger
    from core.hooks import stop as stop_hook

    reviewer_ledger.queue_notice(
        "stop-e2e", None, "[arka:subagent-qa] francisca-tech needs gating"
    )
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("", encoding="utf-8")
    assert stop_hook.main({
        "session_id": "stop-e2e",
        "transcript_path": str(transcript),
        "cwd": "/tmp",
    }) == 0
    out = capsys.readouterr().out
    assert "[arka:subagent-qa]" in out, "main() must deliver queued notices"
    payload = json.loads(out.strip().splitlines()[0])
    assert payload["hookSpecificOutput"]["hookEventName"] == "Stop"
    assert reviewer_ledger.notices_context("stop-e2e") == "", (
        "a delivered notice must be cleared"
    )


# ─── PR-B5: in-process coverage of the full main() path ─────────────────
#
# The module's real-world entry is `bash stop.sh`, and a bash parent
# severs the coverage trace (verified with coverage 7.15 patch =
# subprocess — the .pth hook the child would need is not installed), so
# the e2e tests above execute main()/_flow_checks without measuring
# them. main() takes an injected payload precisely so the same path can
# run in-process; these tests close the module's measured-coverage debt
# without duplicating the e2e assertions.


class TestMainInProcess:
    def _env(self, monkeypatch, tmp_path):
        from core.hooks import stop as stop_hook

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        monkeypatch.setenv("ARKAOS_ROOT", str(REPO_ROOT))
        monkeypatch.setenv("ARKA_STOP_LINT", "0")
        monkeypatch.setenv("ARKA_SESSION_MEMORY", "0")
        monkeypatch.setenv("ARKA_AUTO_DOC_QUEUE", str(tmp_path / "queue"))
        # No detached workers from a unit test — same rule as the
        # enqueue tests above.
        monkeypatch.setattr(
            "subprocess.Popen", lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("no detached spawns from in-process tests")
            )
        )
        # Keep the shared /tmp marker dir out of unit tests entirely.
        monkeypatch.setattr(
            stop_hook, "arkaos_temp_dir", lambda name: tmp_path / name
        )
        return stop_hook

    def test_stop_hook_active_short_circuits(self, monkeypatch, tmp_path):
        stop_hook = self._env(monkeypatch, tmp_path)
        assert stop_hook.main(
            {"stop_hook_active": "true", "session_id": "sess-ip0"}
        ) == 0

    def test_full_path_without_wf_marker(self, monkeypatch, tmp_path, capsys):
        """No workflow marker: main() still runs dna-fidelity, native
        usage, notice delivery and the enqueue guards, then returns 0."""
        stop_hook = self._env(monkeypatch, tmp_path)
        transcript = tmp_path / "t.jsonl"
        _make_transcript(transcript, with_external=True)
        rc = stop_hook.main({
            "session_id": "sess-ip1",
            "transcript_path": str(transcript),
            "cwd": str(tmp_path),
            "assistant_message": "[arka:qg:approved] done",
        })
        assert rc == 0
        capsys.readouterr()

    def test_full_path_with_wf_marker_runs_flow_checks(
        self, monkeypatch, tmp_path, capsys
    ):
        """The flagged-session path: marker present, flow checks and the
        auto-doc sweep run in-process, the marker is consumed."""
        stop_hook = self._env(monkeypatch, tmp_path)
        transcript = tmp_path / "t.jsonl"
        _make_transcript(transcript, with_external=True)
        marker_dir = tmp_path / "arkaos-wf-required"
        marker_dir.mkdir(parents=True)
        (marker_dir / "sess-ip2").write_text("1", encoding="utf-8")
        rc = stop_hook.main({
            "session_id": "sess-ip2",
            "transcript_path": str(transcript),
            "cwd": str(tmp_path),
        })
        assert rc == 0
        assert not (marker_dir / "sess-ip2").exists(), (
            "the workflow marker must be consumed"
        )
        queue = tmp_path / "queue" / "pending"
        pending = list(queue.glob("*.json")) if queue.exists() else []
        assert len(pending) == 1, (
            "QG-approved + external research must enqueue the auto-doc job"
        )
        capsys.readouterr()
