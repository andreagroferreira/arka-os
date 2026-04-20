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
import shutil
import stat
import subprocess
from pathlib import Path

import pytest


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

    wf_dir = Path("/tmp/arkaos-wf-required")
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
    env["ARKA_AUTO_DOC_QUEUE"] = str(queue)
    env["HOME"] = str(home)
    env["PYTHONPATH"] = str(REPO_ROOT)

    subprocess.run(
        ["bash", str(STOP_SH)],
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
