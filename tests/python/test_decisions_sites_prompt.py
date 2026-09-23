"""core.decisions.sites.prompt — the four UPS sites and their questions."""

from __future__ import annotations

import pytest

from core.decisions.engine import build_request
from core.decisions.models import Answer
from core.decisions.registry import SITES
from core.decisions.site import LANGUAGE_PREAMBLE, SiteCall
from core.decisions.sites import prompt as prompt_sites
from core.decisions.sites.prompt import (
    CREATION_INTENT,
    DEPARTMENT_DESCRIPTIONS,
    REFINE,
    ROUTE,
    TOPIC_DRIFT,
    prompt_state,
    route_options,
)
from core.synapse.layers import DEPARTMENT_PATTERNS


def test_route_keys_are_departments_plus_none():
    assert set(route_options()) == set(DEPARTMENT_PATTERNS) | {"none"}
    assert set(ROUTE.questions()["department"].criteria) == set(DEPARTMENT_PATTERNS) | {"none"}


def test_every_department_has_a_written_description():
    assert set(DEPARTMENT_DESCRIPTIONS) == set(DEPARTMENT_PATTERNS)


def test_new_department_is_never_forgotten(monkeypatch):
    monkeypatch.setitem(DEPARTMENT_PATTERNS, "legal", r"\b(contract)\b")
    assert route_options()["legal"] == "The 'legal' department."


def test_registry_holds_the_ten_sites():
    assert set(SITES) == {
        "topic-drift", "refine", "creation-intent", "route", "bash-effect",
        "forge-departments", "forge-complexity", "dispatch-role",
        "subagent-discipline", "skill-hints",
    }


def test_site_names_never_collide_on_the_wire():
    # question_key maps "-" to "_" and splits on "__": two names equal after
    # the mapping, or one holding "__", would mix their answers.
    wire = [name.replace("-", "_") for name in SITES]
    assert len(set(wire)) == len(wire) == 10
    assert not any("__" in w for w in wire)
    assert all(site.name == name for name, site in SITES.items())


@pytest.mark.parametrize("site", [TOPIC_DRIFT, REFINE, CREATION_INTENT, ROUTE])
def test_questions_carry_the_language_preamble(site):
    for question in site.questions().values():
        assert question.instructions.startswith(LANGUAGE_PREAMBLE)
    assert LANGUAGE_PREAMBLE == (
        "Messages may be in Portuguese (pt-PT) or English; judge meaning, not language."
    )


def test_all_questions_fit_in_one_request():
    calls = [SiteCall(s, None) for s in prompt_sites.PROMPT_SITES]
    request = build_request(calls, prompt_state("olá"), "typesafe/jev-1.13")
    assert set(request.questions) == {
        "topic_drift__topic_shift", "refine__vague", "refine__missing",
        "creation_intent__creation_intent", "route__department",
    }


def test_site_policies():
    assert (TOPIC_DRIFT.risk, REFINE.risk, CREATION_INTENT.risk, ROUTE.risk) == (
        "read", "read", "write", "write")
    assert CREATION_INTENT.direction == "escalate_only"
    esc = CREATION_INTENT.is_escalation
    assert esc is not None
    assert esc(True, False) is True
    assert esc(False, True) is False and esc(True, True) is False


def test_prompt_state_shapes():
    assert prompt_state("a", "b") == {"prompt": "a", "recent_user_messages": ["b"]}
    assert prompt_state("a", ["b", " ", ""]) == {"prompt": "a", "recent_user_messages": ["b"]}
    assert prompt_state("a") == {"prompt": "a", "recent_user_messages": []}


def test_topic_drift_and_creation_interpret():
    assert TOPIC_DRIFT.interpret({"topic_shift": Answer(noul=0.96)}, 0.6) is True
    assert CREATION_INTENT.interpret({"creation_intent": Answer(noul=0.37)}, 0.75) is None
    assert CREATION_INTENT.interpret({}, 0.75) is None


def test_refine_uses_vague_then_missing_gap():
    assert REFINE.interpret({"vague": Answer(noul=0.95)}, 0.6) is True
    coin = Answer(noul=0.5)
    gap = {"vague": coin, "missing": Answer(choice="target", confidence=0.9)}
    assert REFINE.interpret(gap, 0.6) is True
    none = {"vague": coin, "missing": Answer(choice="none", confidence=0.9)}
    assert REFINE.interpret(none, 0.6) is False
    assert REFINE.interpret({"vague": coin}, 0.6) is None
    assert set(prompt_sites.REFINE_GAPS) == {"target", "scope", "acceptance", "none"}


def test_route_interpret():
    assert ROUTE.interpret({"department": Answer(choice="dev", confidence=1.0)}, 0.7) == "dev"
    assert ROUTE.interpret({"department": Answer(choice="none", confidence=0.79)}, 0.7) == ""
    assert ROUTE.interpret({"department": Answer(choice="dev", confidence=0.5)}, 0.7) is None


def test_refine_clauses_are_exact_complements():
    # Eduardo (QG PR1 carry): a prompt with target + scope but no success
    # criterion must fall into ONE clause — YES — never into both.
    text = REFINE.questions()["vague"].instructions
    assert "Answer YES when at least one of the three items is missing" in text
    assert "answer NO only when all three are present" in text
    for item in ("concrete target", "bounded scope", "success criterion"):
        assert item in text
    assert "competent engineer" not in text and "intended result, even briefly" not in text
    assert prompt_sites.REFINE_CHECKLIST in text
