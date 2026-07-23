"""Tests for core.hooks.session_start — consolidated entrypoint (F2-2)."""

from __future__ import annotations

import json

import pytest

from core.hooks import session_start
from core.hooks.session_start import (
    build_context,
    build_message,
    build_recap,
    build_visible,
    main,
)
from core.memory.semantic_store import SessionMemoryStore, TurnRecord


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ARKA_SESSION_MEMORY_DB", str(tmp_path / "sm.db"))
    monkeypatch.delenv("ARKA_HOOK_CWD", raising=False)
    # No repo => background spawns (reorganizer/dashboard) are inert and
    # version falls back cleanly; individual tests override as needed.
    monkeypatch.setattr(session_start, "repo_path", lambda: "")
    return tmp_path


def _seed(project: str, n: int = 3) -> None:
    store = SessionMemoryStore()
    for i in range(n):
        store.save(TurnRecord(
            id=f"t{i}", ts=f"2026-07-0{i + 1}T00:00:00+00:00",
            session_id=f"s{i}", project_name=project,
            summary=f"turn {i}: shipped feature {i}",
            importance=0.5 + i * 0.1,
            embedding_backend="fastembed" if i else "none",
        ))


# ─── build_message: golden sections ────────────────────────────────────


def test_message_carries_banner_contracts_and_version(tmp_path):
    msg = build_message("/repo/proj")
    assert "A R K A   O S" in msg
    assert "Olá, founder" in msg
    assert "WizardingCode" in msg
    assert "[ARKA:EVIDENCE-FLOW] NON-NEGOTIABLE" in msg
    assert "G2 PLAN (short plan -> EXPLICIT user approval" in msg
    assert "[ARKA:META-TAG]" in msg
    assert "[arka:meta] kb=N research=X persona=Y gap=Z critic=W" in msg
    assert "A R K A   O S — v" in msg


def test_visible_is_compact_and_contracts_live_in_context(tmp_path):
    """Foundation PR-2: the user-facing greeting carries NO contract
    wall — the contracts ship to the model via additionalContext."""
    _seed("proj")
    visible = build_visible("/repo/proj")
    context = build_context("/repo/proj")
    for marker in (
        "[ARKA:EVIDENCE-FLOW]",
        "[ARKA:META-TAG]",
        "[ARKA:AUTHORITY]",
        "[SESSION-MEMORY]",
        "[SESSION]",
    ):
        assert marker not in visible, f"{marker} leaked into the visible greeting"
    assert "[ARKA:EVIDENCE-FLOW] NON-NEGOTIABLE" in context
    assert "[ARKA:META-TAG]" in context
    assert "[SESSION-MEMORY] Prior turns" in context
    assert not context.startswith("\n")


def test_message_shows_profile(tmp_path):
    cfg = tmp_path / ".arkaos"
    cfg.mkdir(exist_ok=True)
    (cfg / "profile.json").write_text(
        json.dumps({"name": "Andre", "company": "WizardingCode"}), encoding="utf-8"
    )
    msg = build_visible("/repo/proj")
    assert "Olá, Andre" in msg
    assert "WizardingCode" in msg


def test_message_drift_never_synced(tmp_path):
    msg = build_message("/repo/proj")
    assert "[arka:update-available] Never synced" in msg


def test_message_drift_on_version_mismatch(tmp_path):
    arka = tmp_path / ".arkaos"
    (arka / "lib").mkdir(parents=True, exist_ok=True)
    (arka / "lib" / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    (arka / "sync-state.json").write_text(json.dumps({"version": "9.9.8"}), encoding="utf-8")
    msg = build_message("/repo/proj")
    assert "Core v9.9.9 != synced v9.9.8" in msg


def test_message_no_drift_when_synced(tmp_path):
    arka = tmp_path / ".arkaos"
    (arka / "lib").mkdir(parents=True, exist_ok=True)
    (arka / "lib" / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    (arka / "sync-state.json").write_text(json.dumps({"version": "9.9.9"}), encoding="utf-8")
    msg = build_message("/repo/proj")
    assert "[arka:update-available]" not in msg


def test_message_workflow_line(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "core.workflow.state.get_state",
        lambda: {
            "workflow": "dev-feature",
            "branch": "feat/x",
            "violations": ["v1"],
            "phases": {
                "spec": {"status": "completed"},
                "build": {"status": "in_progress"},
            },
        },
    )
    msg = build_message("/repo/proj")
    assert "Workflow: dev-feature (1/2) branch:feat/x VIOLATIONS:1" in msg


def test_message_includes_memory_recap(tmp_path):
    _seed("proj")
    msg = build_message("/repo/proj")
    assert "[SESSION-MEMORY] Prior turns" in msg
    assert "shown: 3 turns (proj)" in msg


# ─── background side effects: gated and inert without a repo ───────────


def test_no_spawns_without_repo(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(session_start, "_spawn_detached",
                        lambda *a, **k: calls.append(a))
    build_message("/repo/proj")
    assert calls == []  # no repo => reorganizer and dashboard both inert


def test_reorganizer_config_gate(monkeypatch, tmp_path):
    """The F2-1 QG follow-up gate: cognition.reorganize_on_session=false."""
    monkeypatch.setattr(session_start, "repo_path", lambda: str(tmp_path / "repo"))
    (tmp_path / "repo" / "core").mkdir(parents=True)
    cfg = tmp_path / ".arkaos"
    cfg.mkdir(exist_ok=True)
    (cfg / "config.json").write_text(json.dumps({
        "cognition": {"reorganize_on_session": False},
        "dashboard": {"ensure_on_session": False},
    }), encoding="utf-8")
    calls = []
    monkeypatch.setattr(session_start, "_spawn_detached",
                        lambda *a, **k: calls.append(a))
    build_message("/repo/proj")
    assert calls == []


def test_reorganizer_satisfied_by_todays_proposal(monkeypatch, tmp_path):
    from datetime import UTC, datetime

    monkeypatch.setattr(session_start, "repo_path", lambda: str(tmp_path / "repo"))
    (tmp_path / "repo").mkdir(exist_ok=True)
    proposals = tmp_path / ".arkaos" / "reorganize-proposals"
    proposals.mkdir(parents=True)
    (proposals / f"{datetime.now(UTC).strftime('%Y-%m-%d')}.md").touch()
    (tmp_path / ".arkaos" / "config.json").write_text(
        json.dumps({"dashboard": {"ensure_on_session": False}}), encoding="utf-8"
    )
    calls = []
    monkeypatch.setattr(session_start, "_spawn_detached",
                        lambda *a, **k: calls.append(a))
    build_message("/repo/proj")
    assert calls == []  # today's UTC proposal exists — nothing to do


# ─── build_recap (F1-A3 semantics preserved) ───────────────────────────


def test_recap_ranks_and_scopes(tmp_path):
    _seed("proj")
    recap = build_recap("/repo/proj")
    assert recap.startswith("[SESSION-MEMORY] Prior turns")
    assert "turn 2" in recap.splitlines()[1]  # highest importance first
    assert "backends=fastembed,none" in recap
    assert build_recap("") == ""  # scope-or-skip: never a global read
    assert build_recap("/repo/other") == ""


def test_recap_shows_cross_runtime_handoff(tmp_path):
    """Newest turn in the project came from opencode -> the claude
    SessionStart recap opens with the [arka:handoff] line."""
    from datetime import UTC, datetime

    _seed("proj")
    SessionMemoryStore().save(TurnRecord(
        id="oc-latest", ts=datetime.now(UTC).isoformat(),
        session_id="oc-sess", runtime="opencode", project_name="proj",
        summary="finished the opencode refactor",
    ))
    recap = build_recap("/repo/proj")
    lines = recap.splitlines()
    assert lines[1].startswith("[arka:handoff] última sessão em opencode")
    assert "finished the opencode refactor" in lines[1]
    assert "shown: 3 turns (proj)" in recap  # handoff not counted as turn


def test_recap_no_handoff_without_cross_runtime(tmp_path):
    _seed("proj")  # all runtime="" — nothing to hand off from
    assert "[arka:handoff]" not in build_recap("/repo/proj")


# ─── main(): the hook contract ─────────────────────────────────────────


def test_main_emits_split_payload(tmp_path, capsys):
    """systemMessage stays compact; contracts + recap ride
    hookSpecificOutput.additionalContext (Foundation PR-2)."""
    _seed("proj")
    assert main({"cwd": "/repo/proj"}) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "A R K A   O S" in payload["systemMessage"]
    assert "[SESSION-MEMORY]" not in payload["systemMessage"]
    assert "[ARKA:EVIDENCE-FLOW]" not in payload["systemMessage"]
    hso = payload["hookSpecificOutput"]
    assert hso["hookEventName"] == "SessionStart"
    assert "[ARKA:EVIDENCE-FLOW] NON-NEGOTIABLE" in hso["additionalContext"]
    assert "[SESSION-MEMORY]" in hso["additionalContext"]


def test_main_cwd_falls_back_to_env(tmp_path, capsys, monkeypatch):
    _seed("proj")
    monkeypatch.setenv("ARKA_HOOK_CWD", "/repo/proj")
    assert main({}) == 0
    payload = json.loads(capsys.readouterr().out)
    context = payload["hookSpecificOutput"]["additionalContext"]
    assert "shown: 3 turns (proj)" in context


def test_main_fail_open_on_internal_error(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(
        session_start, "build_visible",
        lambda cwd: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert main({"cwd": "/x"}) == 0  # never raises
    payload = json.loads(capsys.readouterr().out)
    assert "A R K A   O S" in payload["systemMessage"]  # static banner


def test_reorganizer_fires_on_happy_path(monkeypatch, tmp_path):
    """QG blocker: the gate's PURPOSE — repo present, gate default-on,
    no proposal for today => the reorganizer IS spawned. An inverted
    guard silencing it entirely must fail here."""
    monkeypatch.setattr(session_start, "repo_path", lambda: str(tmp_path / "repo"))
    (tmp_path / "repo").mkdir(exist_ok=True)
    (tmp_path / ".arkaos").mkdir(exist_ok=True)
    (tmp_path / ".arkaos" / "config.json").write_text(
        json.dumps({"dashboard": {"ensure_on_session": False}}), encoding="utf-8"
    )
    calls = []
    monkeypatch.setattr(session_start, "_spawn_detached",
                        lambda cmd, repo, **k: calls.append(cmd))
    build_message("/repo/proj")
    assert len(calls) == 1
    assert calls[0][1:] == ["-m", "core.cognition.reorganizer_cli"]
