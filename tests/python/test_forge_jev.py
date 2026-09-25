"""Forge step 3 x the JEV sites (JEV Decisions Layer PR2, decision 3).

Network mocked at ``urlopen``; the budget uses an injected clock so the
deadline arithmetic is exact.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from _decisions_helpers import fake_ok, isolate_decisions, sent_payload

from core.forge import jev_sites
from core.forge.budget import FORGE_CALL_MS, FORGE_TOTAL_MS, ForgeBudget
from core.forge.complexity import analyze_complexity, score_dimensions
from core.forge.orchestrator import ForgeOrchestrator
from core.forge.schema import ForgeContext, ForgeTier

URLOPEN = "core.decisions.client.urllib.request.urlopen"
PROMPT = "lança a campanha do produto novo com landing page e emails"


class Clock:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def jev(monkeypatch, tmp_path):
    # forge-departments ships in act (replay jev-pr5-final), forge-complexity
    # in shadow; these tests exercise both act paths, so they pin both
    # explicitly, exactly as an operator would.
    from _decisions_helpers import write_config

    home = isolate_decisions(monkeypatch, tmp_path)
    write_config(home, {"sites": {"forge-complexity": "act", "forge-departments": "act"}})
    return home


def _depts(probs: dict[str, float]) -> dict[str, Any]:
    top = max(probs, key=probs.__getitem__)
    return {"forge_departments__departments": {
        "type": "choice", "choice": top, "probabilities": probs}}


def _levels(level: int) -> dict[str, Any]:
    return {f"forge_complexity__{dim}": {"type": "score", "score": level, "confidence": 0.9}
            for dim in ("scope", "dependencies", "ambiguity", "risk", "novelty")}


def _orchestrator(prompt: str = PROMPT) -> ForgeOrchestrator:
    orch = ForgeOrchestrator()
    orch._forge_context = ForgeContext(repo="r", branch="b", commit_at_forge="c",
                                       arkaos_version="5", prompt=prompt)
    orch._similar_plans, orch._reused_patterns = [], []
    return orch


# --- budget ---------------------------------------------------------------------

class TestForgeBudget:
    def test_defaults_are_the_spec(self):
        assert (FORGE_TOTAL_MS, FORGE_CALL_MS) == (5000, 3000)

    def test_caps_each_call_and_the_total(self):
        clock = Clock()
        budget = ForgeBudget(clock=clock)
        assert budget.remaining_ms() == 3000
        clock.t += 4.0
        assert budget.remaining_ms() == 1000
        clock.t += 2.0
        assert budget.remaining_ms() == 0

    def test_explicit_cap(self):
        assert ForgeBudget(total_ms=5000, clock=Clock()).remaining_ms(1200) == 1200


# --- no call without a deadline -------------------------------------------------------

def test_every_call_carries_the_remaining_budget(jev, monkeypatch):
    """Kills: dropping ``timeout_ms`` (the engine default is 1500) or not
    sharing one deadline between the two calls."""
    from core.decisions import engine

    clock, seen = Clock(), []

    def spy(calls, state, **kw):
        seen.append(kw["timeout_ms"])
        clock.t += 4.0  # the first call eats 4 s of the 5 s
        return engine._heuristics(calls, {}, "off")

    monkeypatch.setattr(engine, "decide", spy)
    budget = ForgeBudget(clock=clock)
    departments = jev_sites.decide_departments(PROMPT, [], ["marketing"], budget)
    jev_sites.decide_dimensions(PROMPT, [], departments, ([], []), budget)
    assert seen == [3000, 1000]


def test_the_wire_timeout_is_three_seconds(jev):
    with patch(URLOPEN, return_value=fake_ok({})) as net:
        jev_sites.decide_departments(PROMPT, [], ["dev"], ForgeBudget())
    assert net.call_args.kwargs["timeout"] == pytest.approx(3.0, abs=0.05)


def test_exhausted_budget_makes_no_call(jev):
    clock = Clock()
    budget = ForgeBudget(clock=clock)
    clock.t += 10.0
    with patch(URLOPEN) as net:
        assert jev_sites.decide_departments(PROMPT, [], ["dev"], budget) == ["dev"]
    net.assert_not_called()


# --- departments ---------------------------------------------------------------------

def test_jev_departments_replace_the_keyword_estimate(jev):
    answer = _depts({"marketing": 0.5, "landing": 0.3, "dev": 0.1, "none": 0.1})
    with patch(URLOPEN, return_value=fake_ok(answer)) as net:
        out = jev_sites.decide_departments(PROMPT, [], ["dev"], ForgeBudget())
    assert out == ["marketing", "landing"]
    assert sent_payload(net)["state"]["departments"] == ["dev"]


def test_unsure_or_unavailable_keeps_the_estimate(jev):
    with patch(URLOPEN, return_value=fake_ok(_depts({"none": 0.9, "dev": 0.1}))):
        assert jev_sites.decide_departments(PROMPT, [], ["dev"], ForgeBudget()) == ["dev"]
    with patch(URLOPEN, side_effect=OSError("down")):
        assert jev_sites.decide_departments(PROMPT, [], ["dev"], ForgeBudget()) == ["dev"]


# --- complexity ----------------------------------------------------------------------

def test_jev_dimensions_drive_the_tier(jev):
    with patch(URLOPEN, return_value=fake_ok(_levels(9))):
        dims = jev_sites.decide_dimensions(PROMPT, [], ["dev"], ([], []), ForgeBudget())
    assert dims.model_dump() == dict.fromkeys(dims.model_dump(), 100)
    assert analyze_complexity(PROMPT, [], ["dev"], [], [], dimensions=dims).tier is ForgeTier.DEEP


def test_partial_scores_keep_the_heuristic(jev):
    partial = _levels(9)
    partial.pop("forge_complexity__risk")
    with patch(URLOPEN, return_value=fake_ok(partial)):
        dims = jev_sites.decide_dimensions(PROMPT, [], ["dev"], ([], []), ForgeBudget())
    assert dims == score_dimensions(PROMPT, [], ["dev"], [], [])


def test_analyze_complexity_without_dimensions_is_unchanged():
    base = analyze_complexity(PROMPT, ["core/a.py"], ["dev"], [], [])
    same = analyze_complexity(PROMPT, ["core/a.py"], ["dev"], [], [], dimensions=None)
    assert base == same


# --- step 3 end to end ---------------------------------------------------------------

def test_step3_uses_both_sites_in_order(jev):
    responses = [fake_ok(_depts({"marketing": 0.6, "landing": 0.3, "none": 0.1})),
                 fake_ok(_levels(1))]
    with patch(URLOPEN, side_effect=responses) as net:
        orch = _orchestrator()
        orch._step3_complexity()
    assert net.call_count == 2
    # The complexity call saw the departments the first call settled on.
    assert sent_payload(net)["state"]["departments"] == ["marketing", "landing"]
    assert orch._complexity.tier is ForgeTier.SHALLOW
    assert orch._complexity.dimensions.scope == 11


def test_step3_without_a_key_is_the_heuristic(monkeypatch, tmp_path):
    isolate_decisions(monkeypatch, tmp_path, key=None)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    orch = _orchestrator()
    with patch(URLOPEN) as net:
        orch._step3_complexity()
    net.assert_not_called()
    expected = analyze_complexity(PROMPT, orch._estimate_affected_files(PROMPT),
                                  orch._estimate_departments(PROMPT), [], [])
    assert orch._complexity == expected


def test_shipped_default_departments_act_complexity_shadow(monkeypatch, tmp_path):
    """No operator override: forge-departments acts (Jev's set replaces the
    keyword estimate) and forge-complexity stays shadow (heuristic
    dimensions, detached worker, no synchronous call)."""
    isolate_decisions(monkeypatch, tmp_path)
    answer = _depts({"marketing": 0.3, "landing": 0.25, "dev": 0.22,
                     "content": 0.21, "brand": 0.02})
    with patch(URLOPEN, return_value=fake_ok(answer)) as net:
        out = jev_sites.decide_departments(PROMPT, [], ["ops"], ForgeBudget())
    assert net.call_count == 1
    assert out == ["marketing", "landing", "dev", "content"]
    with patch(URLOPEN) as net, patch("core.decisions.shadow.subprocess.Popen") as pop:
        dims = jev_sites.decide_dimensions(PROMPT, [], ["dev"], ([], []), ForgeBudget())
    net.assert_not_called()
    assert pop.call_count == 1
    assert dims == score_dimensions(PROMPT, [], ["dev"], [], [])


def test_departments_shadow_override_keeps_the_estimate(monkeypatch, tmp_path):
    """Operator override back to shadow: the keyword estimate acts and no
    synchronous call leaves (the shadow worker is detached)."""
    from _decisions_helpers import write_config

    home = isolate_decisions(monkeypatch, tmp_path)
    write_config(home, {"sites": {"forge-departments": "shadow"}})
    with patch(URLOPEN) as net, patch("core.decisions.shadow.subprocess.Popen") as pop:
        out = jev_sites.decide_departments(PROMPT, [], ["dev"], ForgeBudget())
    assert out == ["dev"]
    net.assert_not_called()
    assert pop.call_count == 1
