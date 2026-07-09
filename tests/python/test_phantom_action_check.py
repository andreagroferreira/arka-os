"""Tests for core.governance.phantom_action_check (prompt-surface P0)."""

from __future__ import annotations

import json

import pytest

from core.governance.phantom_action_check import (
    check_phantom_actions,
    count_turn_tool_uses,
    find_action_claims,
)


def _jsonl(*records: dict) -> str:
    return "\n".join(json.dumps(r) for r in records)


def _user(text: str) -> dict:
    return {"role": "user", "content": text}


def _assistant_text(text: str) -> dict:
    return {"message": {"role": "assistant", "content": [
        {"type": "text", "text": text},
    ]}}


def _assistant_with_tool(text: str) -> dict:
    return {"message": {"role": "assistant", "content": [
        {"type": "text", "text": text},
        {"type": "tool_use", "id": "t1", "name": "Bash", "input": {}},
    ]}}


def _tool_result() -> dict:
    return {"message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": "ok"},
    ]}}


class TestFindActionClaims:
    def test_bound_portuguese_effect_claims_flagged(self):
        assert find_action_claims("Criei o ficheiro de config e corri os testes.")
        assert find_action_claims("Atualizei o módulo de sync.")
        assert find_action_claims("Adicionei a classe `PhantomCheck`.")

    def test_standalone_git_claims_flagged(self):
        assert find_action_claims("Fiz commit das alterações.")
        assert find_action_claims("Publiquei a versão nova.")

    def test_english_effect_claims_flagged(self):
        assert find_action_claims("I pushed the fix upstream.")
        assert find_action_claims("I've created the PR for review.")
        assert find_action_claims("I ran the tests locally.")

    def test_passive_effect_nouns_flagged(self):
        assert find_action_claims("Commit feito e PR criado.")

    def test_negation_not_flagged(self):
        assert find_action_claims("Ainda não criei o ficheiro.") == []
        assert find_action_claims("Não fiz commit de nada.") == []

    def test_future_intent_not_flagged(self):
        assert find_action_claims("Vou criar o módulo e depois corro os testes.") == []

    # B2 regression pack — Marta's reproduced false positives must stay clean.
    def test_ambiguous_verbs_without_effect_object_not_flagged(self):
        assert find_action_claims("I ran through the codebase to understand the flow.") == []
        assert find_action_claims("Escrevi um resumo das alterações abaixo.") == []
        assert find_action_claims("Atualizei o meu entendimento sobre o problema.") == []
        assert find_action_claims("I wrote a summary of the findings below.") == []
        assert find_action_claims("Adicionei alguns pontos que faltavam.") == []

    # Residual pack (QG condition on #255 before enforcement promotion):
    # the proximity heuristic must not cross analytic nouns or idioms.
    def test_analytic_noun_between_verb_and_object_not_flagged(self):
        assert find_action_claims("I ran into a problem with the commit.") == []
        assert find_action_claims("I updated my understanding of the file.") == []
        assert find_action_claims("Adicionei contexto sobre os testes.") == []
        assert find_action_claims("Escrevi notas sobre o módulo de sync.") == []
        assert find_action_claims("I added a summary of the test results.") == []

    def test_true_positives_survive_the_residual_fix(self):
        assert find_action_claims("I updated the config file.")
        assert find_action_claims("Adicionei os testes ao módulo.")
        assert find_action_claims("I ran the test suite.")

    # QG second-sweep pack (#followups review): the analytic-noun CLASS,
    # not just the 3 named residuals — Marta's 6 reproduced leaks.
    def test_analytic_class_extension_not_flagged(self):
        for text in (
            "I updated my thoughts on the module.",
            "I updated my takeaways from the tests.",
            "I updated my mental model of the file.",
            "Criei uma imagem mental do módulo.",
            "Atualizei a minha noção do ficheiro.",
            "Atualizei a minha perspetiva sobre o módulo.",
        ):
            assert find_action_claims(text) == [], text

    # QG M2/M3 residuals closed 2026-07-09 (ADR phantom-check-stays-
    # warn-only listed M3 as the hard prerequisite of any promotion).
    def test_m2_closed_second_ran_in_coordinated_clause(self):
        assert find_action_claims(
            "I ran through the plan, then ran the test suite."
        )

    def test_m2_coordination_never_crosses_the_sentence(self):
        # The coordinated-verb allowance is sentence-bounded: a new
        # sentence with a non-assistant subject must not inherit the I.
        assert find_action_claims(
            "I read the plan. The migration ran and created the table."
        ) == []

    def test_m2_coordination_never_bridges_embedded_third_party_clause(self):
        # QG re-review blocker (2026-07-09): a cognition verb introducing
        # a third-party clause must NOT let the I anchor reach that
        # clause's effect verb — the chunk only opens with the I-clause's
        # own ran-idiom.
        for text in (
            "I confirmed the hook ran and created the state file.",
            "I believe the deploy ran and updated the release tag.",
            "I verified the migration ran and updated the schema file.",
            "I saw the script ran and wrote the output file.",
            "I saw that the script, when run, created the file.",
        ):
            assert find_action_claims(text) == [], text

    def test_m3_closed_analytic_synonym_tail(self):
        for text in (
            "I updated my read on the file.",
            "I updated my reading of the tests.",
            "I updated my take on the module.",
            "I added an interpretation of the tests.",
            "I updated my assessment of the module.",
            "Atualizei a minha leitura do ficheiro.",
            "Atualizei a minha interpretação dos testes.",
            # Plural forms (QG re-review blocker, 2026-07-09).
            "I updated my reads on the failing tests.",
            "I updated my takes on the failing tests.",
            "I updated my readings of the modules.",
            "Atualizei as minhas leituras dos ficheiros.",
            "Atualizei as minhas interpretações dos testes.",
        ):
            assert find_action_claims(text) == [], text

    def test_m3_verb_read_still_binds_as_effect_prose(self):
        # 'read' guarded as a noun only before on/of — verb uses keep
        # their prior behavior (not an effect verb, never flagged).
        assert find_action_claims("I updated the read-only file flag.")

    def test_analysis_prose_not_flagged(self):
        assert find_action_claims("Analisei o código e o plano parece sólido.") == []


class TestCountTurnToolUses:
    def test_counts_tool_uses_after_last_real_user_message(self):
        raw = _jsonl(
            _user("faz o commit"),
            _assistant_with_tool("A correr."),
            _tool_result(),
            _assistant_text("Feito."),
        )
        assert count_turn_tool_uses(raw) == 1

    def test_zero_when_turn_is_prose_only(self):
        raw = _jsonl(
            _user("primeira"),
            _assistant_with_tool("ok"),
            _tool_result(),
            _user("e agora?"),
            _assistant_text("Criei o ficheiro X."),
        )
        # Tool use belongs to the PREVIOUS turn — current turn has none.
        assert count_turn_tool_uses(raw) == 0

    def test_unparseable_returns_none(self):
        assert count_turn_tool_uses("not json at all") is None
        assert count_turn_tool_uses(None) is None
        assert count_turn_tool_uses("") is None

    def test_no_real_user_message_returns_none(self):
        # Fail-open instead of summing the whole transcript (QG note).
        raw = _jsonl(_assistant_with_tool("solo"), _tool_result())
        assert count_turn_tool_uses(raw) is None

    # B1 regression — malformed records must not raise (fail-open contract).
    def test_malformed_message_value_does_not_raise(self):
        raw = _jsonl(
            {"message": "truncated-string-not-dict"},
            {"role": "user", "content": "cria"},
            {"message": 42},
            _assistant_text("Criei o ficheiro X."),
        )
        assert count_turn_tool_uses(raw) == 0


class TestCheckPhantomActions:
    def test_phantom_claim_without_tools_fails(self):
        raw = _jsonl(_user("cria o módulo"), _assistant_text("Criei o módulo X."))
        result = check_phantom_actions("Criei o módulo X.", raw)
        assert result.passed is False
        assert result.reason == "phantom-action"
        assert result.claims
        assert result.suggestion

    def test_claim_with_tool_call_passes(self):
        raw = _jsonl(
            _user("cria o módulo"),
            _assistant_with_tool("A criar."),
            _tool_result(),
            _assistant_text("Criei o módulo X."),
        )
        result = check_phantom_actions("Criei o módulo X.", raw)
        assert result.passed is True
        assert result.reason == "tools-present"

    def test_no_claims_passes_without_parsing(self):
        result = check_phantom_actions("O plano tem 3 fases.", None)
        assert result.passed is True
        assert result.reason == "no-claims"

    def test_unparseable_transcript_fails_open(self):
        result = check_phantom_actions("Fiz commit da correção.", "garbage")
        assert result.passed is True
        assert result.reason == "transcript-unparseable"

    # B1 regression — the public entrypoint never raises on malformed input.
    def test_malformed_records_fail_open_not_raise(self):
        raw = _jsonl({"message": "not-a-dict"}, {"role": "user", "content": []})
        result = check_phantom_actions("Fiz commit da correção.", raw)
        assert result.passed is True
        assert result.reason in ("transcript-unparseable", "check-error")
