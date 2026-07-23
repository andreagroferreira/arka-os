"""Frontend gate ↔ design_authorization — the deadlock fix.

Regression class: in hard mode, a denied Write never persisted its
turn's [arka:design] text to the transcript, and tool-heavy sequences
rolled the marker out of the 20-message window — so every retry denied
again, forever. Persist-on-observe + consult-before-deny breaks the
loop; a session with no evidence at all must still deny.
"""

from __future__ import annotations

import json

import pytest

from core.workflow import design_authorization as da
from core.workflow import frontend_gate

STRUCTURED = (
    "[arka:design] benchmark=Vercel skills=frontend-design,ui-ux-pro-max "
    "tokens=app/main.css"
)
TOOL_ONLY_WINDOW = [f"<tool_use:Bash>{i}" for i in range(20)]


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_DESIGN_AUTH_DIR", str(tmp_path / "design-auth"))
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"hooks": {"frontendGate": "hard"}}), encoding="utf-8")
    monkeypatch.setattr(frontend_gate, "CONFIG_PATH", config)


def _evaluate(session: str, messages: list[str]) -> frontend_gate.Decision:
    return frontend_gate.evaluate(
        tool_name="Write",
        transcript_path="",
        session_id=session,
        cwd="/tmp",
        tool_input={"file_path": "app/components/Thing.vue", "content": "x"},
        messages=messages,
    )


def test_structured_marker_allows_and_persists() -> None:
    decision = _evaluate("sess-p1", [f"intro\n{STRUCTURED}\n"])
    assert decision.allow
    assert decision.reason == "design-evidence"
    assert da.confirmed_marker("sess-p1") == STRUCTURED.strip()


def test_persisted_auth_survives_window_rolling() -> None:
    _evaluate("sess-p2", [STRUCTURED])
    rolled = _evaluate("sess-p2", TOOL_ONLY_WINDOW)
    assert rolled.allow
    assert rolled.reason == "design-evidence-persisted"
    assert rolled.marker_kind == "persisted"


def test_other_session_still_denies_in_hard_mode() -> None:
    _evaluate("sess-p3", [STRUCTURED])
    other = _evaluate("sess-unrelated", TOOL_ONLY_WINDOW)
    assert not other.allow
    assert other.reason == "no-design-marker"


def test_no_evidence_at_all_still_denies() -> None:
    decision = _evaluate("sess-p4", TOOL_ONLY_WINDOW)
    assert not decision.allow


def test_trivial_marker_allows_but_does_not_persist() -> None:
    decision = _evaluate("sess-p5", ["[arka:trivial] one-line color tweak"])
    assert decision.allow
    assert decision.marker_kind == "trivial"
    assert not da.is_confirmed("sess-p5")


def test_warn_mode_still_warns_not_denies(tmp_path, monkeypatch) -> None:
    config = tmp_path / "warn-config.json"
    config.write_text(json.dumps({"hooks": {"frontendGate": "warn"}}), encoding="utf-8")
    monkeypatch.setattr(frontend_gate, "CONFIG_PATH", config)
    decision = _evaluate("sess-p6", TOOL_ONLY_WINDOW)
    assert decision.allow
    assert decision.reason == "no-design-marker"


def test_persisted_auth_expires_with_ttl(monkeypatch) -> None:
    import time as _time

    _evaluate("sess-p7", [STRUCTURED])
    real = _time.time()
    monkeypatch.setattr(_time, "time", lambda: real + da.DEFAULT_TTL_SECONDS + 1)
    decision = _evaluate("sess-p7", TOOL_ONLY_WINDOW)
    assert not decision.allow
