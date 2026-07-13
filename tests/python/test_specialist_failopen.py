"""Specialist gate fail-open locks (P0.2, incident 2026-07-12).

The defect pinned shut here: the persona marker rolling out of the
20-message window returned ALLOW (``no-routing-tag``) — 4,093 of 5,683
telemetry records (72%). Routing once and hammering the gate with 20
messages of noise was a winning strategy. Two scope leaks rode along:
interleaved subagent records accelerated the eviction, and the fix
(persisted personas) could have blocked dispatched specialists if it
leaked across transcripts.

Every test runs against sandboxed HOME + auth dirs (the B6 lesson from
QG redo 1: no test may write real machine state, and a persona confirmed
by one test must never restore into the next).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.workflow import specialist_authorization as sa  # noqa: E402
from core.workflow import specialist_enforcer as se  # noqa: E402
from core.workflow import transcript_scope  # noqa: E402

_OWNERSHIP = """
version: 1
c_suite: [marta]
ownership:
  - pattern: "**/*.vue"
    owners: [frontend-dev]
  - pattern: "**/app/Http/Controllers/**"
    owners: [senior-dev, backend-dev]
lead_allowed: []
"""


@pytest.fixture(autouse=True)
def _isolated_specialist_auth(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "ARKA_SPECIALIST_AUTH_DIR", str(tmp_path / "specialist-auth")
    )


@pytest.fixture
def gate_on(tmp_path, monkeypatch):
    """Enforcement ON in a sandboxed HOME — never inherit the operator's."""
    home = tmp_path / "home"
    (home / "telemetry").mkdir(parents=True)
    (home / "config.json").write_text(
        json.dumps({"hooks": {"specialistEnforcement": True}}),
        encoding="utf-8",
    )
    ownership = tmp_path / "agent-ownership.yaml"
    ownership.write_text(_OWNERSHIP, encoding="utf-8")
    monkeypatch.setattr(se, "CONFIG_PATH", home / "config.json")
    monkeypatch.setattr(
        se, "TELEMETRY_PATH", home / "telemetry" / "specialist.jsonl")
    monkeypatch.setattr(se, "OWNERSHIP_YAML_PATH", ownership)
    se._load_ownership.cache_clear()
    yield tmp_path
    se._load_ownership.cache_clear()


def _write_transcript(path: Path, records: list[tuple[str, bool]]) -> Path:
    """records: (assistant text, isSidechain)."""
    lines = [json.dumps({"role": "user", "content": "go"})]
    for text, side in records:
        lines.append(json.dumps({
            "type": "assistant",
            "isSidechain": side,
            "message": {"role": "assistant", "content": text},
        }))
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _main(*texts: str) -> list[tuple[str, bool]]:
    return [(t, False) for t in texts]


_NOISE = "reading files and reporting progress"


# ─── The fail-open itself ───────────────────────────────────────────────

def test_a_block_survives_marker_eviction(gate_on, tmp_path):
    """The winning strategy dies: routing + 25 messages of noise used to
    return ALLOW no-routing-tag. The persisted persona now decides
    exactly as if the marker were visible — including deciding BLOCK."""
    tx = _write_transcript(
        tmp_path / "tx.jsonl",
        _main("[arka:routing] dev -> Paulo", *[_NOISE] * 25),
    )
    # the seed happened on an earlier call that still saw the marker
    sa.confirm("s1", str(tx), persona="paulo", marker="routing")
    d = se.evaluate(
        tool_name="Write", transcript_path=str(tx), session_id="s1",
        tool_input={"file_path": "app/Http/Controllers/X.php"},
    )
    assert d.allow is False
    assert d.reason.startswith("lead-blocked:paulo")
    assert d.persona_source == "persisted"


def test_evaluate_itself_persists_on_observe(gate_on, tmp_path):
    """No separate seeding step: seeing the marker IS the confirmation."""
    tx = _write_transcript(
        tmp_path / "tx.jsonl",
        _main("[arka:routing] dev -> Paulo", _NOISE),
    )
    se.evaluate(
        tool_name="Write", transcript_path=str(tx), session_id="s1",
        tool_input={"file_path": "app/Http/Controllers/X.php"},
    )
    restored = sa.confirmed("s1", str(tx))
    assert restored is not None
    assert restored["persona"] == "paulo"


def test_a_dispatched_owner_survives_eviction_too(gate_on, tmp_path):
    """Restoration is symmetric: the specialist stays allowed, the lead
    stays blocked. The gate got more correct, not more permissive."""
    marker_tx = _write_transcript(
        tmp_path / "tx.jsonl",
        _main("[arka:dispatch] paulo -> diana", _NOISE),
    )
    se.evaluate(
        tool_name="Write", transcript_path=str(marker_tx), session_id="s1",
        tool_input={"file_path": "resources/js/App.vue"},
    )
    _write_transcript(
        tmp_path / "tx.jsonl", _main(*[_NOISE] * 25))
    d = se.evaluate(
        tool_name="Write", transcript_path=str(marker_tx), session_id="s1",
        tool_input={"file_path": "resources/js/App.vue"},
    )
    assert d.allow is True
    assert d.reason == "owner-match:frontend-dev"
    assert d.persona_source == "persisted"


def test_window_resolution_still_wins_when_marker_visible(gate_on, tmp_path):
    tx = _write_transcript(
        tmp_path / "tx.jsonl",
        _main("[arka:routing] dev -> Paulo", *[_NOISE] * 5),
    )
    d = se.evaluate(
        tool_name="Write", transcript_path=str(tx), session_id="s1",
        tool_input={"file_path": "app/Http/Controllers/X.php"},
    )
    assert d.allow is False
    assert d.persona_source == "window"
    assert d.msgs_since_marker == 5


def test_the_persona_follows_the_last_marker_not_the_first(gate_on, tmp_path):
    """Re-routing re-persists: an operator who moved on to a new dispatch
    is judged by the CURRENT persona after eviction, never a stale one."""
    tx = _write_transcript(
        tmp_path / "tx.jsonl",
        _main("[arka:routing] dev -> Paulo",
              "[arka:dispatch] paulo -> diana", _NOISE),
    )
    se.evaluate(
        tool_name="Write", transcript_path=str(tx), session_id="s1",
        tool_input={"file_path": "resources/js/App.vue"},
    )
    restored = sa.confirmed("s1", str(tx))
    assert restored["persona"] == "frontend-dev"
    assert restored["persona_raw"] == "diana"
    assert restored["alias_resolved"] is True


def test_never_routed_session_keeps_todays_allow(gate_on, tmp_path):
    """This PR closes the EVICTION hole only. Hardening never-routed
    sessions is a separate, telemetry-gated decision."""
    tx = _write_transcript(tmp_path / "tx.jsonl", _main(*[_NOISE] * 3))
    d = se.evaluate(
        tool_name="Write", transcript_path=str(tx), session_id="s1",
        tool_input={"file_path": "resources/js/App.vue"},
    )
    assert d.allow is True
    assert d.reason == "never-routed"


def test_an_expired_persona_never_restores(gate_on, tmp_path):
    tx = _write_transcript(tmp_path / "tx.jsonl", _main(*[_NOISE] * 3))
    sa.confirm("s1", str(tx), persona="paulo", marker="routing")
    auth_file = Path(os.environ["ARKA_SPECIALIST_AUTH_DIR"]) / "s1.json"
    stale = json.loads(auth_file.read_text(encoding="utf-8"))
    stale["confirmed_ts"] = time.time() - 13 * 3600
    auth_file.write_text(json.dumps(stale), encoding="utf-8")
    d = se.evaluate(
        tool_name="Write", transcript_path=str(tx), session_id="s1",
        tool_input={"file_path": "app/Http/Controllers/X.php"},
    )
    assert d.allow is True
    assert d.reason == "never-routed"


def test_bypass_is_orthogonal_to_eviction(gate_on, tmp_path):
    """A substantive bypass in the LAST message keeps working when the
    persona arrives via restoration — the two mechanisms never tangle."""
    tx = _write_transcript(
        tmp_path / "tx.jsonl",
        _main(*[_NOISE] * 25,
              "[arka:specialist-bypass owner=frontend-dev reason=the vue "
              "toolchain is absent on this machine]"),
    )
    sa.confirm("s1", str(tx), persona="paulo", marker="routing")
    d = se.evaluate(
        tool_name="Write", transcript_path=str(tx), session_id="s1",
        tool_input={"file_path": "resources/js/App.vue"},
    )
    assert d.allow is True
    assert d.reason == "bypass-with-reason"
    assert d.persona_source == "persisted"


# ─── The sidechain guard ────────────────────────────────────────────────

def test_subagent_noise_cannot_evict_the_marker(gate_on, tmp_path):
    """The eviction accelerator dies: 30 sidechain records after the
    dispatch leave the main-scope window — and the marker — intact."""
    records = _main("[arka:dispatch] paulo -> diana")
    records += [(_NOISE, True)] * 30
    tx = _write_transcript(tmp_path / "tx.jsonl", records)
    d = se.evaluate(
        tool_name="Write", transcript_path=str(tx), session_id="s1",
        tool_input={"file_path": "resources/js/App.vue"},
    )
    assert d.allow is True
    assert d.reason == "owner-match:frontend-dev"
    assert d.persona_source == "window"
    assert d.is_sidechain is True  # active scope: the subagent is acting


def test_a_sidechain_with_no_marker_reads_subagent_scope(gate_on, tmp_path):
    records = [(_NOISE, True)] * 3
    tx = _write_transcript(tmp_path / "tx.jsonl", records)
    d = se.evaluate(
        tool_name="Write", transcript_path=str(tx), session_id="s1",
        tool_input={"file_path": "resources/js/App.vue"},
    )
    assert d.allow is True
    assert d.reason == "subagent-scope"
    assert d.is_sidechain is True


def test_a_sidechain_never_consults_the_parents_persistence(gate_on, tmp_path):
    """The risk the design flagged: a dispatched specialist evaluated
    under the PARENT's persisted persona would be blocked from the very
    files it was dispatched to write. Sidechain scope never restores."""
    tx = _write_transcript(tmp_path / "tx.jsonl", [(_NOISE, True)] * 3)
    sa.confirm("s1", str(tx), persona="paulo", marker="routing")
    d = se.evaluate(
        tool_name="Write", transcript_path=str(tx), session_id="s1",
        tool_input={"file_path": "resources/js/App.vue"},
    )
    assert d.allow is True
    assert d.reason == "subagent-scope"


def test_a_different_transcript_never_inherits_the_persona(gate_on, tmp_path):
    """Subagents run on their own transcript file (ADR 2026-05-28), so
    the record is keyed by transcript name too — same session, other
    file, no restore. Defense in depth under the isSidechain guard."""
    parent = _write_transcript(
        tmp_path / "parent.jsonl", _main(*[_NOISE] * 3))
    sub = _write_transcript(tmp_path / "sub.jsonl", _main(*[_NOISE] * 3))
    sa.confirm("s1", str(parent), persona="paulo", marker="routing")
    d = se.evaluate(
        tool_name="Write", transcript_path=str(sub), session_id="s1",
        tool_input={"file_path": "resources/js/App.vue"},
    )
    assert d.allow is True
    assert d.reason == "never-routed"


def test_the_hook_contract_threads_the_scope(gate_on, tmp_path):
    """The consolidated hook passes pre-parsed messages + is_sidechain
    (parse-once, PR-6); the enforcer must honor the flag it cannot
    self-detect on that path."""
    tx = _write_transcript(tmp_path / "tx.jsonl", _main(_NOISE))
    d = se.evaluate(
        tool_name="Write", transcript_path=str(tx), session_id="s1",
        tool_input={"file_path": "resources/js/App.vue"},
        messages=[_NOISE], is_sidechain=True,
    )
    assert d.reason == "subagent-scope"
    d = se.evaluate(
        tool_name="Write", transcript_path=str(tx), session_id="s1",
        tool_input={"file_path": "resources/js/App.vue"},
        messages=[_NOISE], is_sidechain=False,
    )
    assert d.reason == "never-routed"


# ─── Units: scope split + authorization store ───────────────────────────

def test_split_by_scope_separates_and_flags_the_active_scope():
    raw = "\n".join([
        json.dumps({"role": "assistant", "content": "main one"}),
        json.dumps({
            "isSidechain": True,
            "message": {"role": "assistant", "content": "side one"},
        }),
        json.dumps({"role": "user", "content": "ignored"}),
        json.dumps({
            "isSidechain": False,
            "message": {"role": "assistant", "content": "main two"},
        }),
    ])
    split = transcript_scope.split_by_scope(raw)
    assert split.main == ["main one", "main two"]
    assert split.sidechain == ["side one"]
    assert split.active_sidechain is False  # last assistant record is main


def test_records_without_the_field_are_main_scope():
    """A transcript that predates isSidechain behaves exactly as before."""
    raw = json.dumps({"role": "assistant", "content": "old style"})
    split = transcript_scope.split_by_scope(raw)
    assert split.main == ["old style"]
    assert split.active_sidechain is False


def test_authorization_store_roundtrip_and_refusals(tmp_path):
    sa.confirm("s1", str(tmp_path / "tx.jsonl"), persona="paulo",
               marker="routing", persona_raw="paulo")
    assert sa.confirmed("s1", str(tmp_path / "tx.jsonl"))["persona"] == "paulo"
    # other transcript, empty persona, empty path, bad session: all None
    assert sa.confirmed("s1", str(tmp_path / "other.jsonl")) is None
    assert sa.confirmed("s1", "") is None
    sa.confirm("s2", str(tmp_path / "tx.jsonl"), persona="", marker="routing")
    assert sa.confirmed("s2", str(tmp_path / "tx.jsonl")) is None
    sa.confirm("../evil", str(tmp_path / "tx.jsonl"), persona="x", marker="m")
    assert sa.confirmed("../evil", str(tmp_path / "tx.jsonl")) is None
    sa.clear("s1")
    assert sa.confirmed("s1", str(tmp_path / "tx.jsonl")) is None
