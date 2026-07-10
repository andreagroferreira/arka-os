"""Tests for core.workflow.plan_approval (Interaction Reform PR3).

State machine, reply classification, and the enforcer's WARN-phase
annotation. All state redirected to tmp via ARKA_PLAN_APPROVAL_DIR.
"""

from __future__ import annotations

import pytest

from core.workflow import plan_approval
from core.workflow.plan_approval import (
    classify_reply,
    get_state,
    is_approved,
    is_presented,
    mark_approved,
    mark_presented,
    mark_rejected,
)

SESSION = "sess-plan-approval"


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_PLAN_APPROVAL_DIR", str(tmp_path / "approval"))


class TestStateMachine:
    def test_initial_state_is_none(self):
        assert get_state(SESSION).state == "none"
        assert not is_approved(SESSION)
        assert not is_presented(SESSION)

    def test_presented_then_approved(self):
        mark_presented(SESSION)
        assert is_presented(SESSION)
        assert not is_approved(SESSION)
        mark_approved(SESSION, source="text", excerpt="força")
        assert is_approved(SESSION)
        assert get_state(SESSION).source == "text"

    def test_new_plan_invalidates_previous_approval(self):
        mark_presented(SESSION)
        mark_approved(SESSION)
        assert is_approved(SESSION)
        mark_presented(SESSION)  # plan B on the table
        assert not is_approved(SESSION), (
            "an approval must not survive a newer presented plan"
        )

    def test_approval_survives_a_stale_gate2_in_the_window(self):
        # QG 2026-07-09 (PR4 prerequisite #1 re-review): a prior turn's
        # gate:2 lingering in the 20-message window must NOT re-present
        # and invalidate a live approval. The Stop hook scopes to the
        # CURRENT turn (current_turn_assistant_texts); a marker-less
        # clarifying-question turn yields NO gate, so mark_presented is
        # never called and the approval stands.
        import json as _json
        from core.governance.phantom_action_check import (
            current_turn_assistant_texts,
        )
        from core.workflow.gate_checkpoint import extract_latest_gate

        mark_presented(SESSION)
        mark_approved(SESSION)
        assert is_approved(SESSION)

        raw = "\n".join(_json.dumps(r) for r in (
            {"role": "user", "content": "plano A"},
            {"message": {"role": "assistant", "content": [
                {"type": "text", "text": "[arka:gate:2] plano A"}]}},
            {"role": "user", "content": "aprovo"},
            {"message": {"role": "assistant", "content": [
                {"type": "text", "text": "A perguntar: A ou B?"}]}},
        ))
        turn = current_turn_assistant_texts(raw)
        # The stop hook only marks presented when the CURRENT turn hits
        # gate 2 — here it does not, so the approval must survive.
        if extract_latest_gate(turn) == 2:
            mark_presented(SESSION)
        assert is_approved(SESSION), (
            "a stale prior-turn gate:2 must not invalidate the approval"
        )

    def test_rejection_resets(self):
        mark_presented(SESSION)
        mark_rejected(SESSION)
        assert get_state(SESSION).state == "none"
        assert not is_presented(SESSION)

    def test_exit_plan_mode_source(self):
        mark_presented(SESSION)
        mark_approved(SESSION, source="exit-plan-mode")
        assert is_approved(SESSION)
        assert get_state(SESSION).source == "exit-plan-mode"

    def test_ttl_expires_approval(self, monkeypatch):
        mark_presented(SESSION)
        mark_approved(SESSION)
        monkeypatch.setattr(
            plan_approval, "DEFAULT_TTL_SECONDS", -1
        )
        assert not is_approved(SESSION)

    def test_unsafe_session_id_is_a_noop(self):
        mark_presented("../../evil")
        assert get_state("../../evil").state == "none"

    def test_corrupt_state_file_resets(self, tmp_path):
        mark_presented(SESSION)
        state_file = next((tmp_path / "approval").glob("*.json"))
        state_file.write_text("{not json", encoding="utf-8")
        assert get_state(SESSION).state == "none"

    def test_unwritable_state_dir_never_raises(self, tmp_path, monkeypatch):
        # PR4 prerequisite #3: a read-only override dir must not
        # propagate an OSError into the hook — mark/get degrade to noop.
        blocked = tmp_path / "blocked"
        blocked.mkdir()
        blocked.chmod(0o500)
        monkeypatch.setenv(
            "ARKA_PLAN_APPROVAL_DIR", str(blocked / "sub")
        )
        try:
            mark_presented(SESSION)  # must not raise
            assert get_state(SESSION).state == "none"
        finally:
            blocked.chmod(0o700)


class TestClassifyReply:
    def test_explicit_approvals_pt_and_en(self):
        for text in (
            "aprovo", "Aprovado, segue.", "força", "avança com isso",
            "go ahead", "approved", "proceed", "ship it", "LGTM",
        ):
            assert classify_reply(text) == "approve", text

    def test_short_bare_yes_counts_only_when_unambiguous(self):
        assert classify_reply("sim") == "approve"
        assert classify_reply("ok") == "approve"
        assert classify_reply("yes, do it") == "approve"

    def test_short_yes_with_question_mark_is_not_approval(self):
        assert classify_reply("sim?") == "other"

    def test_long_message_with_yes_is_not_approval(self):
        assert classify_reply(
            "sim mas primeiro quero perceber melhor como o cache funciona "
            "porque tenho dúvidas sobre o TTL"
        ) == "other"

    def test_creation_verb_neutralizes_approval_tokens(self):
        # "ok, agora implementa X" is a NEW instruction, not consent to
        # the plan on the table — the hook passes has_creation_verb=True.
        assert classify_reply(
            "ok implementa também o dark mode",
            has_creation_verb=True,
        ) == "other"

    def test_rejections(self):
        for text in ("não", "para", "espera aí", "cancela", "stop", "hold on"):
            assert classify_reply(text) == "reject", text

    def test_rejection_wins_over_embedded_approval_token(self):
        # "avança" alone is an approve token; the leading negation wins.
        assert classify_reply("não avança já") == "reject"

    def test_empty_is_other(self):
        assert classify_reply("") == "other"
        assert classify_reply("   ") == "other"


class TestEnforcerAnnotation:
    @pytest.fixture(autouse=True)
    def _flow_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ARKA_FLOW_AUTH_DIR", str(tmp_path / "auth"))
        monkeypatch.setenv(
            "ARKA_WF_REQUIRED_DIR", str(tmp_path / "wf-required")
        )

    def _decision(self, session_id: str):
        from core.workflow.flow_enforcer import Decision, _annotate_plan_approval

        return _annotate_plan_approval(
            Decision(allow=True, reason="marker-found:routing",
                     marker_found="routing"),
            session_id,
        )

    def test_no_plan_annotates_without_warning(self):
        decision = self._decision(SESSION)
        assert decision.approval_state == "no-plan"
        assert decision.warning == ""

    def test_presented_without_approval_warns(self):
        mark_presented(SESSION)
        decision = self._decision(SESSION)
        assert decision.approval_state == "missing"
        assert "no-plan-approval-warn" in decision.warning
        assert decision.allow is True, "PR3 is WARN-only, never a deny"

    def test_approved_plan_is_clean(self):
        mark_presented(SESSION)
        mark_approved(SESSION)
        decision = self._decision(SESSION)
        assert decision.approval_state == "approved"
        assert decision.warning == ""

    def test_trivial_marker_is_exempt(self):
        from core.workflow.flow_enforcer import Decision, _annotate_plan_approval

        mark_presented(SESSION)
        decision = _annotate_plan_approval(
            Decision(allow=True, reason="marker-found:trivial",
                     marker_found="trivial"),
            SESSION,
        )
        assert decision.approval_state == ""

    def test_ungated_reasons_are_exempt(self):
        from core.workflow.flow_enforcer import Decision, _annotate_plan_approval

        for reason in ("tool-not-gated", "feature-flag-off",
                       "classifier-did-not-match", "env-bypass"):
            decision = _annotate_plan_approval(
                Decision(allow=True, reason=reason), SESSION
            )
            assert decision.approval_state == "", reason
