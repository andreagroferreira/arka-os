"""core.decisions.promotion — the D2 mode rule (pure, table-driven).

Mutants the spec names, each killed by at least one case below:
2 runs → 1 (``test_one_pass_is_not_enough``), same-digest check removed
(``test_digest_change_restarts_the_count``), 2-of-3 → 1-of-3
(``test_one_fail_in_three_is_watch``), prescreen margin 20 % → 25 %
(``test_prescreen_needs_the_margin``), off touched (``test_off_is_never_touched``),
not-measured counted (``test_not_measured_is_skipped``).
"""

from __future__ import annotations

import pytest

from core.decisions.config import Mode
from core.decisions.promotion import (
    PRESCREEN_MAX_ABSTAIN,
    RunGate,
    RunVerdict,
    current_window,
    propose_mode,
)

A, B = "a" * 64, "b" * 64


def runs(*spec: str, digest: str = A, abstain: float | None = 0.10) -> list[RunVerdict]:
    """``"pass"``/``"fail"``/``"nm"`` → verdicts on one digest."""
    names: dict[str, RunGate] = {"pass": "pass", "fail": "fail", "nm": "not-measured"}
    return [RunVerdict(names[s], abstain, digest, f"t{i}") for i, s in enumerate(spec)]


def action(site: str, current: Mode, history: list[RunVerdict]) -> tuple[str, str]:
    p = propose_mode(site, current, history)
    return p.action, p.proposed


def test_two_passes_promote_shadow_to_act():
    p = propose_mode("refine", "shadow", runs("pass", "pass"))
    assert (p.action, p.proposed, p.runs_considered, p.corpus_sha256) == ("promote", "act", 2, A)


@pytest.mark.parametrize("history", [runs("pass"), runs("fail", "pass"), runs("pass", "fail")])
def test_one_pass_is_not_enough(history):
    assert action("refine", "shadow", history) == ("keep", "shadow")


def test_digest_change_restarts_the_count():
    history = runs("pass", digest=A) + runs("pass", digest=B)
    assert action("refine", "shadow", history) == ("keep", "shadow")
    history += runs("pass", digest=B)
    assert action("refine", "shadow", history) == ("promote", "act")


def test_digest_change_restarts_demotion_too():
    history = runs("fail", digest=A) + runs("fail", digest=B)
    assert action("route", "act", history) == ("watch", "act")


def test_not_measured_is_skipped():
    assert action("refine", "shadow", runs("pass", "nm", "pass")) == ("promote", "act")
    assert action("refine", "shadow", runs("pass", "nm")) == ("keep", "shadow")
    assert action("route", "act", runs("fail", "nm", "fail")) == ("demote", "shadow")
    assert action("route", "act", runs("nm", "nm", "nm")) == ("keep", "act")


@pytest.mark.parametrize(("spec", "want"), [
    (("fail", "fail", "pass"), ("demote", "shadow")),
    (("fail", "pass", "fail"), ("demote", "shadow")),
    (("fail", "fail"), ("demote", "shadow")),
    (("fail", "pass", "pass"), ("watch", "act")),
    (("pass", "pass", "pass"), ("keep", "act")),
    (("fail", "fail", "pass", "pass"), ("watch", "act")),  # only the last three count
])
def test_act_demotion_table(spec, want):
    assert action("route", "act", runs(*spec)) == want


def test_one_fail_in_three_is_watch():
    assert action("route", "act", runs("pass", "pass", "fail")) == ("watch", "act")


@pytest.mark.parametrize("history", [runs("pass", "pass"), runs("fail", "fail", "fail")])
def test_off_is_never_touched(history):
    p = propose_mode("route", "off", history)
    assert (p.action, p.proposed, p.current) == ("keep", "off", "off")


def test_prescreen_needs_the_margin():
    history = [RunVerdict("pass", 0.10, A), RunVerdict("pass", 0.21, A)]
    assert action("qg-prescreen", "shadow", history) == ("keep", "shadow")
    at_margin = runs("pass", "pass", abstain=PRESCREEN_MAX_ABSTAIN)
    assert action("qg-prescreen", "shadow", at_margin) == ("promote", "act")
    unknown = runs("pass", "pass", abstain=None)
    assert action("qg-prescreen", "shadow", unknown) == ("keep", "shadow")


def test_margin_is_prescreen_only():
    assert action("refine", "shadow", runs("pass", "pass", abstain=0.24)) == ("promote", "act")


def test_current_window_is_the_trailing_same_digest_stretch():
    history = runs("pass", digest=A) + runs("fail", "nm", digest=B) + runs("pass", digest=B)
    window = current_window(history)
    assert [r.gate for r in window] == ["fail", "pass"] and {r.corpus_sha256 for r in window} == {B}
    assert current_window(runs("nm", "nm")) == []
