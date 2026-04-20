"""v2 tests — turn-scoped marker cache and widened fallback window.

Complements tests/python/test_flow_enforcer.py which covers the stateless
v1 gate. These tests pin down:

- The `marker_cache` module API (write / read / invalidate / turn-validity).
- Security: path-traversal guard on session_id.
- Robustness: corrupt cache file degrades to "no marker" (never to deny-sole-basis).
- `evaluate()` takes the cache-hit fast path only for ALLOW — the transcript
  remains authoritative for any deny decision (ADR-compliant).
- Hook parity: bash + PowerShell scripts wire the cache correctly.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from core.workflow import flow_enforcer, marker_cache
from core.workflow.flow_enforcer import Decision, evaluate, mark_flow_required


REPO_ROOT = Path(__file__).resolve().parents[2]


# ─── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    """Redirect marker_cache storage to a tmp dir."""
    cache_dir = tmp_path / "marker-cache"
    monkeypatch.setattr(marker_cache, "MARKER_CACHE_DIR", cache_dir)
    return cache_dir


@pytest.fixture
def enforcement_env(tmp_path, monkeypatch, isolated_cache):
    """Full isolation: config, telemetry, flow-required, marker cache."""
    home = tmp_path / "home"
    home.mkdir()
    flow_required = tmp_path / "wf-required"
    monkeypatch.setattr(flow_enforcer, "CONFIG_PATH", home / "config.json")
    monkeypatch.setattr(flow_enforcer, "BYPASS_AUDIT_PATH", home / "audit" / "bypass.log")
    monkeypatch.setattr(flow_enforcer, "TELEMETRY_PATH", home / "telemetry" / "enforcement.jsonl")
    monkeypatch.setattr(flow_enforcer, "FLOW_REQUIRED_DIR", flow_required)
    (home / "config.json").write_text(
        json.dumps({"hooks": {"hardEnforcement": True}}),
        encoding="utf-8",
    )
    return home


def _write_transcript(path: Path, assistant_messages: list[str]) -> Path:
    records = [{"role": "user", "content": "implement a feature"}]
    for m in assistant_messages:
        records.append({"role": "assistant", "content": m})
    path.write_text(
        "\n".join(json.dumps(r) for r in records),
        encoding="utf-8",
    )
    return path


# ─── marker_cache: core API ─────────────────────────────────────────────


def test_marker_cache_write_read_roundtrip(isolated_cache):
    marker_cache.write_marker("session-a", "routing", "dev", "paulo")
    got = marker_cache.read_marker("session-a")
    assert got is not None
    assert got["marker_type"] == "routing"
    assert got["dept"] == "dev"
    assert got["lead"] == "paulo"
    assert got["turn_start_ts"] > 0


def test_marker_cache_invalidate(isolated_cache):
    marker_cache.write_marker("session-b", "trivial")
    assert marker_cache.read_marker("session-b") is not None
    marker_cache.invalidate_marker("session-b")
    assert marker_cache.read_marker("session-b") is None


def test_marker_cache_invalidate_missing_is_noop(isolated_cache):
    marker_cache.invalidate_marker("never-existed")


def test_marker_cache_rejects_invalid_marker_type(isolated_cache):
    marker_cache.write_marker("session-c", "not-a-real-type")
    assert marker_cache.read_marker("session-c") is None


@pytest.mark.parametrize(
    "hostile_id",
    [
        "../etc/passwd",
        "../../home/victim/.ssh/keys",
        "foo/bar",
        "foo\\bar",
        "with space",
        "with\nnewline",
        "x" * 129,
        "",
    ],
)
def test_marker_cache_safe_session_id_rejects_traversal(
    isolated_cache, hostile_id
):
    """Any session_id outside the allowlist must be a silent no-op."""
    marker_cache.write_marker(hostile_id, "routing", "dev", "paulo")
    if isolated_cache.exists():
        assert list(isolated_cache.iterdir()) == []
    assert marker_cache.read_marker(hostile_id) is None


def test_marker_cache_atomic_write_concurrent(isolated_cache):
    """Concurrent writers must never leave a half-written file on disk."""

    def _writer(i: int) -> None:
        marker_cache.write_marker("session-concurrent", "routing", "dev", f"lead{i}")

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(_writer, range(200)))

    got = marker_cache.read_marker("session-concurrent")
    assert got is not None
    assert got["marker_type"] == "routing"
    assert got["lead"].startswith("lead")


def test_marker_cache_corrupt_file_returns_none(isolated_cache):
    isolated_cache.mkdir(parents=True, exist_ok=True)
    (isolated_cache / "session-corrupt.json").write_text(
        "this is not valid json{",
        encoding="utf-8",
    )
    assert marker_cache.read_marker("session-corrupt") is None


def test_marker_cache_non_dict_payload_returns_none(isolated_cache):
    isolated_cache.mkdir(parents=True, exist_ok=True)
    (isolated_cache / "session-arr.json").write_text(
        json.dumps(["not", "a", "dict"]),
        encoding="utf-8",
    )
    assert marker_cache.read_marker("session-arr") is None


def test_is_valid_for_current_turn_true_when_written_after_prompt(isolated_cache):
    before = time.time()
    marker_cache.write_marker("session-t", "routing", "dev", "paulo")
    assert marker_cache.is_valid_for_current_turn("session-t", before) is True


def test_is_valid_for_current_turn_false_when_prompt_is_newer(isolated_cache):
    marker_cache.write_marker("session-t2", "routing", "dev", "paulo")
    future = time.time() + 60
    assert marker_cache.is_valid_for_current_turn("session-t2", future) is False


def test_is_valid_for_current_turn_false_when_missing(isolated_cache):
    assert marker_cache.is_valid_for_current_turn("no-such-session", 0.0) is False


# ─── evaluate(): cache integration ─────────────────────────────────────


def test_evaluate_allows_with_cache_hit_routing(enforcement_env, tmp_path):
    mark_flow_required("session-hit-r")
    marker_cache.write_marker("session-hit-r", "routing", "dev", "paulo")
    transcript = _write_transcript(tmp_path / "t.jsonl", ["no marker in transcript"])
    d = evaluate("Write", str(transcript), "session-hit-r", "/tmp")
    assert d.allow is True
    assert d.reason == "marker-cache-hit:routing"
    assert d.marker_found == "routing"


def test_evaluate_allows_with_cache_hit_trivial(enforcement_env, tmp_path):
    mark_flow_required("session-hit-t")
    marker_cache.write_marker("session-hit-t", "trivial")
    transcript = _write_transcript(tmp_path / "t.jsonl", ["no marker"])
    d = evaluate("Write", str(transcript), "session-hit-t", "/tmp")
    assert d.allow is True
    assert d.reason == "marker-cache-hit:trivial"
    assert d.marker_found == "trivial"


def test_evaluate_cache_miss_falls_back_to_transcript_scan(enforcement_env, tmp_path):
    mark_flow_required("session-miss-ok")
    transcript = _write_transcript(
        tmp_path / "t.jsonl",
        ["[arka:routing] dev -> paulo\nkicking off"],
    )
    d = evaluate("Write", str(transcript), "session-miss-ok", "/tmp")
    assert d.allow is True
    assert d.marker_found == "routing"
    assert not d.reason.startswith("marker-cache-hit")


def test_evaluate_cache_miss_widened_window_6(enforcement_env, tmp_path):
    """Marker at N-5 still found under the widened 6-message window."""
    mark_flow_required("session-wide")
    transcript = _write_transcript(
        tmp_path / "t.jsonl",
        [
            "[arka:routing] dev -> paulo",
            "Step 2",
            "Step 3",
            "Step 4",
            "Step 5",
            "Step 6",
        ],
    )
    d = evaluate("Write", str(transcript), "session-wide", "/tmp")
    assert d.allow is True
    assert d.marker_found == "routing"


def test_evaluate_cache_never_sole_basis_for_deny(enforcement_env, tmp_path):
    """ADR constraint: cache absence alone must never deny — transcript decides."""
    mark_flow_required("session-sole")
    # No cache entry, transcript has a valid marker.
    assert marker_cache.read_marker("session-sole") is None
    transcript = _write_transcript(
        tmp_path / "t.jsonl",
        ["[arka:phase:11] running per-todo loop"],
    )
    d = evaluate("Write", str(transcript), "session-sole", "/tmp")
    assert d.allow is True
    assert d.marker_found == "phase"


def test_evaluate_cross_turn_subagent_scenario(enforcement_env, tmp_path):
    """Reproduces the reported bug:
    routing was emitted early, subagent calls + long tool outputs then pushed
    it past the window. v1 (window=3) denied. v2 either finds it via cache
    (turn-scoped) or via the widened window-6 scan.
    """
    mark_flow_required("session-subagent")
    # v2 fix path A: cache hit, regardless of transcript distance.
    marker_cache.write_marker("session-subagent", "routing", "dev", "paulo")

    # Simulate 10 assistant messages after the one with the marker —
    # far beyond the v1 window-of-3.
    transcript = _write_transcript(
        tmp_path / "t.jsonl",
        [
            "[arka:routing] dev -> paulo",
            *[f"subagent step {i}" for i in range(10)],
        ],
    )
    d = evaluate("Write", str(transcript), "session-subagent", "/tmp")
    assert d.allow is True
    assert d.reason.startswith("marker-cache-hit")


def test_evaluate_ignores_stale_marker_from_previous_turn(
    enforcement_env, tmp_path, monkeypatch
):
    """When invalidate_marker fires on new user prompt, evaluate must fall
    back to the transcript scan. If the transcript also lacks a marker, deny.
    """
    mark_flow_required("session-stale")
    marker_cache.write_marker("session-stale", "routing", "dev", "paulo")
    marker_cache.invalidate_marker("session-stale")
    transcript = _write_transcript(tmp_path / "t.jsonl", ["no fresh marker"])
    d = evaluate("Write", str(transcript), "session-stale", "/tmp")
    assert d.allow is False
    assert "no-flow-marker" in d.reason


# ─── Hook parity: bash + PowerShell ────────────────────────────────────


def test_post_tool_use_sh_writes_marker_on_routing_detected():
    """post-tool-use.sh greps assistant_message for markers and writes cache."""
    script = REPO_ROOT / "config" / "hooks" / "post-tool-use.sh"
    assert script.exists(), f"missing hook: {script}"
    text = script.read_text(encoding="utf-8")
    assert "marker_cache" in text, "bash hook does not reference marker_cache"
    assert "write_marker" in text, "bash hook does not call write_marker"
    assert "arka:routing" in text, "bash hook does not detect [arka:routing]"


def test_post_tool_use_sh_detects_trivial_marker():
    script = REPO_ROOT / "config" / "hooks" / "post-tool-use.sh"
    text = script.read_text(encoding="utf-8")
    assert "arka:trivial" in text, "bash hook does not detect [arka:trivial]"


def test_user_prompt_submit_sh_invalidates_marker():
    script = REPO_ROOT / "config" / "hooks" / "user-prompt-submit.sh"
    text = script.read_text(encoding="utf-8")
    assert "invalidate_marker" in text, "user-prompt-submit.sh does not invalidate cache"


def test_windows_parity_ps1_exists_with_same_logic():
    pus = REPO_ROOT / "config" / "hooks" / "post-tool-use.ps1"
    ups = REPO_ROOT / "config" / "hooks" / "user-prompt-submit.ps1"
    assert pus.exists() and ups.exists(), "Windows hooks missing"
    pus_text = pus.read_text(encoding="utf-8")
    ups_text = ups.read_text(encoding="utf-8")
    assert "marker_cache" in pus_text, "PS1 post-tool-use lacks marker_cache ref"
    assert "write_marker" in pus_text, "PS1 post-tool-use lacks write_marker call"
    assert "invalidate_marker" in ups_text, "PS1 user-prompt-submit lacks invalidate_marker"


# ─── Live hook smoke test (bash only — mirrors production wiring) ──────


def test_post_tool_use_sh_no_marker_when_absent(tmp_path, monkeypatch):
    """When the assistant message lacks any marker, no cache file is written."""
    cache_dir = tmp_path / "flow-marker"
    monkeypatch.setenv("ARKA_MARKER_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))
    script = REPO_ROOT / "config" / "hooks" / "post-tool-use.sh"

    payload = json.dumps({
        "tool_name": "Write",
        "tool_output": "ok",
        "exit_code": "0",
        "cwd": str(tmp_path),
        "session_id": "session-nomarker",
        "assistant_message": "plain prose, no flow marker at all",
    })
    subprocess.run(
        ["bash", str(script)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if cache_dir.exists():
        assert list(cache_dir.iterdir()) == []


def test_post_tool_use_sh_writes_marker_live(tmp_path, monkeypatch):
    """End-to-end: pipe a payload containing [arka:routing] into the bash
    hook and confirm a cache file is written for the session.
    """
    cache_dir = tmp_path / "flow-marker"
    monkeypatch.setenv("ARKA_MARKER_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))
    monkeypatch.setenv("ARKAOS_ROOT", str(REPO_ROOT))
    script = REPO_ROOT / "config" / "hooks" / "post-tool-use.sh"

    payload = json.dumps({
        "tool_name": "Write",
        "tool_output": "ok",
        "exit_code": "0",
        "cwd": str(tmp_path),
        "session_id": "session-livemarker",
        "assistant_message": "[arka:routing] dev -> paulo\nkicking off task #2",
    })
    subprocess.run(
        ["bash", str(script)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert cache_dir.exists(), "hook did not create cache dir"
    entries = list(cache_dir.iterdir())
    assert any(e.name == "session-livemarker.json" for e in entries), (
        f"expected session-livemarker.json, got {[e.name for e in entries]}"
    )
    data = json.loads((cache_dir / "session-livemarker.json").read_text())
    assert data["marker_type"] == "routing"
    assert data["dept"] == "dev"
    assert data["lead"] == "paulo"
