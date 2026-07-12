"""Specialist gate clarity locks (PR-1, incident 2026-07-12).

Three defects this pins shut:
- the marker names a human (``diana``) but rules name slugs
  (``frontend-dev``), so the RIGHT specialist was blocked from her own
  files (52 of 189 measured blocks);
- the session never learned the rules before hitting them;
- the deny message called every persona "(lead)" and advertised the
  bypass beside the dispatch as an equal option.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.agents import authority_brief  # noqa: E402
from core.agents import roster_manifest as rm  # noqa: E402
from core.workflow import specialist_enforcer as se  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_alias_cache():
    se._load_aliases.cache_clear() if hasattr(
        se._load_aliases, "cache_clear") else None
    yield


# ─── Aliases ────────────────────────────────────────────────────────────

def test_alias_resolves_the_human_name_to_the_owner_slug():
    """The 28% false-block class: `-> diana` on a .vue must ALLOW."""
    decision = se.evaluate(
        tool_name="Write", transcript_path="", session_id="t", cwd="/x",
        tool_input={"file_path": "resources/js/Pages/Chat.vue"},
        messages=["[arka:routing] dev -> Paulo",
                  "[arka:dispatch] paulo -> diana"],
    )
    assert decision.allow
    assert decision.reason == "owner-match:frontend-dev"
    assert decision.persona_raw == "diana"
    assert decision.alias_resolved is True


def test_the_lead_is_still_blocked_after_alias_normalization():
    """The gate must not get more permissive — only more correct."""
    decision = se.evaluate(
        tool_name="Write", transcript_path="", session_id="t", cwd="/x",
        tool_input={"file_path": "app/Http/Controllers/AiChatController.php"},
        messages=["[arka:routing] dev -> Paulo"],
    )
    assert decision.allow is False
    assert decision.reason.startswith("lead-blocked:paulo")


def test_aliases_are_unambiguous_within_the_gate_owners():
    """Globally `diana` is ambiguous (frontend-dev AND hr-specialist);
    scoping to gate owners is what makes the alias safe. Anything still
    ambiguous must be refused, never guessed."""
    roster = json.loads(rm.ROSTER_JSON.read_text(encoding="utf-8"))
    aliases = roster["aliases"]
    owners = set(roster["gate_owners"])
    assert set(aliases.values()) <= owners
    assert len(set(aliases)) == len(aliases)
    assert roster["ambiguous_first_names"] == []
    assert aliases["diana"] == "frontend-dev"
    assert aliases["andre"] == "backend-dev"


def test_unknown_persona_passes_through_unchanged():
    slug, resolved = se._normalize_persona("someone-unknown")
    assert slug == "someone-unknown"
    assert resolved is False


# ─── Deny message ───────────────────────────────────────────────────────

def test_deny_refuses_the_false_diagnosis_and_leads_with_the_fix():
    decision = se.Decision(
        allow=False, reason="lead-blocked", current_persona="paulo",
        required_owners=["backend-dev", "senior-dev"],
        target_file="app/Http/Controllers/AiChatController.php",
    )
    message = decision.to_stderr_message()
    assert "This is NOT a bug" in message
    assert "[arka:dispatch] paulo -> backend-dev" in message
    assert 'Task(subagent_type="backend-dev"' in message
    # the bypass is present but demoted and audited
    dispatch_at = message.index("[arka:dispatch]")
    bypass_at = message.index("specialist-bypass")
    assert dispatch_at < bypass_at
    assert "visible to the operator" in message


def test_deny_never_calls_a_specialist_a_lead():
    """The old message hardcoded '(lead)' — when Diana was blocked it
    told her she was a lead, feeding the 'the gate is buggy' story."""
    message = se.Decision(
        allow=False, reason="x", current_persona="frontend-dev",
        required_owners=["backend-dev"], target_file="app/x.php",
    ).to_stderr_message()
    assert "(lead)" not in message
    assert "You are frontend-dev." in message


# ─── Bypass hardening ───────────────────────────────────────────────────

@pytest.mark.parametrize("reason", [
    "typo", "quick fix", "urgent", "trivial", "one char", "just this once",
])
def test_empty_excuses_are_rejected_as_bypass_reasons(reason):
    assert se._find_bypass([f"[arka:specialist-bypass {reason}]"]) is None


def test_short_reasons_are_rejected():
    assert se._find_bypass(["[arka:specialist-bypass too short]"]) is None


def test_substantive_structured_reason_is_accepted():
    marker = (
        "[arka:specialist-bypass owner=backend-dev reason=the specialist "
        "cannot run here, no PHP toolchain on this machine]"
    )
    assert se._find_bypass([marker])


# ─── Authority brief ────────────────────────────────────────────────────

def test_brief_names_owners_dispatchability_and_the_missing_sentence(tmp_path):
    agents = tmp_path / "agents"
    agents.mkdir()
    for slug in ("arka-frontend-dev", "arka-backend-dev"):
        (agents / f"{slug}.md").write_text("x", encoding="utf-8")
    brief = authority_brief.render(REPO_ROOT, agents_dirs=[agents])
    assert "[ARKA:AUTHORITY]" in brief
    assert "AUTHORIZATION TOKEN" in brief
    assert "frontend-dev (Diana) ok" in brief
    # the sentence whose absence caused the incident
    assert "Retrying a blocked Write never works" in brief
    # an owner with no deployed agent is called out, not hidden
    assert "MISSING" in brief
    assert "never bypass" in brief


def test_brief_survives_a_missing_roster(tmp_path, monkeypatch):
    """A hook never breaks a session: no roster -> empty brief, no raise."""
    monkeypatch.setattr(authority_brief, "ROSTER_JSON", tmp_path / "nope.json")
    assert authority_brief.render(REPO_ROOT, agents_dirs=[tmp_path]) == ""


def test_session_start_injects_the_brief():
    from core.hooks.session_start import build_message
    assert "[ARKA:AUTHORITY]" in build_message(str(REPO_ROOT))
