"""PR5 lane D — relabelled corpora, held-out sets, D6 window reading, refine gap."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch

import pytest
from _decisions_helpers import fake_ok, isolate_decisions
from pydantic import ValidationError

from core.decisions import replay as rp
from core.decisions.config import DecisionsConfig
from core.decisions.replay import ReplayCase, load_corpus, main, replay
from core.decisions.sites.forge import DIMENSIONS
from core.decisions.transport import resolve_transport
from core.egress.credentials import egress_secret_labels

URLOPEN = "core.decisions.client.urllib.request.urlopen"
ARBITRATED_GAPS = {"rf-pt-01": "target", "rf-pt-03": "target", "rf-en-02": "target",
                   "rf-en-06": "target"}


def _corpus_merge() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / "tools" / "corpus_merge.py"
    spec = importlib.util.spec_from_file_location("corpus_merge_relabel", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve their module by name
    spec.loader.exec_module(module)
    return module


CM = _corpus_merge()


@pytest.fixture
def transport(monkeypatch, tmp_path):
    isolate_decisions(monkeypatch, tmp_path, clients=["zz-no-such-client"])
    t = resolve_transport(DecisionsConfig())
    assert t is not None
    return t


def _keyed(cases: list[ReplayCase], answer: Any) -> Any:
    by_prompt = {c.prompt: c for c in cases}

    def respond(request: Any, timeout: float) -> Any:
        state = json.loads(request.data.decode("utf-8"))["state"]
        return fake_ok(answer(by_prompt[state["prompt"]]))

    return respond


# --- the case model ------------------------------------------------------------


def test_case_defaults_to_seed_without_gap_and_still_forbids_extras():
    case = ReplayCase(id="x", lang="pt", prompt="p", expected=True)
    assert (case.source, case.gap) == ("seed", None)
    with pytest.raises(ValueError):
        ReplayCase.model_validate({"id": "x", "lang": "pt", "prompt": "p", "expected": True,
                                   "rationale": "labeller notes stay out of the corpus"})


@pytest.mark.parametrize(("site", "row", "error"), [
    ("refine", {"expected": True, "gap": "colour"}, "is not one of"),
    ("refine", {"expected": True, "gap": "none"}, "contradicts"),
    ("refine", {"expected": False, "gap": "target"}, "contradicts"),
    ("topic-drift", {"expected": True, "gap": "target"}, "refine field"),
])
def test_a_bad_gap_names_its_line(tmp_path: Path, site: str, row: dict[str, Any], error: str):
    path = tmp_path / "c.jsonl"
    path.write_text(json.dumps({"id": "x", "lang": "pt", "prompt": "p", **row}) + "\n",
                    encoding="utf-8")
    with pytest.raises(ValueError, match=error) as info:
        load_corpus(site, path)
    assert f"{path}:1:" in str(info.value)


# --- the shipped corpora -------------------------------------------------------


def test_refine_is_relabelled_with_gaps_and_the_arbitration():
    cases = {c.id: c for c in load_corpus("refine")}
    assert all(c.gap is not None for c in cases.values())
    assert {i: cases[i].gap for i in ARBITRATED_GAPS} == ARBITRATED_GAPS
    # Consensus replaced the seed label: both labellers call these vague.
    assert all(cases[i].expected is True for i in ("rf-pt-13", "rf-pt-14", "rf-en-09"))


def test_forge_complexity_takes_the_labellers_tier():
    cases = {c.id: c for c in load_corpus("forge-complexity")}
    assert cases["forge-complexity-29"].expected == "STANDARD"  # operator arbitration
    seed = [c for c in cases.values() if c.source == "seed"]
    assert sum(c.expected == "STANDARD" for c in seed) == 4  # was 12 before the relabel
    assert cases["forge-complexity-09"].expected == "SHALLOW"


@pytest.mark.parametrize("site", ["refine", "forge-complexity"])
def test_relabelled_corpora_meet_the_merge_floors(site: str):
    cases = load_corpus(site)
    new = [c for c in cases if c.source != "seed"]
    assert len(new) / len(cases) >= 0.5
    assert sum(c.lang == "pt" for c in cases) / len(cases) >= 0.55
    assert {c.source for c in new} == {"handwritten-2026-09-25-A", "handwritten-2026-09-25-B"}


@pytest.mark.parametrize("site", rp.HELDOUT_SITES)
def test_heldout_sets_load_and_never_mix_into_the_corpus(site: str):
    held = load_corpus(site, rp.heldout_corpus_path(site))
    train = load_corpus(site)
    assert len(held) >= rp.MIN_HELDOUT_CASES
    assert not {c.id for c in held} & {c.id for c in train}
    assert not {c.prompt for c in held} & {c.prompt for c in train}
    # Spec D7: not even a near-duplicate (the merge's own Jaccard threshold).
    near = [(h.id, t.id) for h in held for t in train
            if CM.jaccard(h.prompt, t.prompt) >= CM.DUP_JACCARD]
    assert near == [], f"held-out cases near-duplicating training: {near}"
    assert all(c.source != "seed" for c in held)
    assert not [c.id for c in held if egress_secret_labels(c.prompt)]


@pytest.mark.parametrize("source", ["seed", "handwritten-2026-09-25-A", "handwritten-B"])
def test_case_source_accepts_seed_and_handwritten_batches(source: str):
    assert ReplayCase(id="x", lang="pt", prompt="p", expected=True, source=source).source == source


@pytest.mark.parametrize("source", ["", "Seed", "seed ", "seed\n", "handwritten", "handwritten-",
                                    "handwriten-A", "manual", "handwritten-A/../x"])
def test_case_source_rejects_anything_else(source: str):
    with pytest.raises(ValidationError):
        ReplayCase(id="x", lang="pt", prompt="p", expected=True, source=source)


def test_every_shipped_source_is_valid():
    """The validator accepts every source the shipped corpora carry."""
    paths = [rp.default_corpus_path(n) for n in rp.HEURISTICS]
    paths += [rp.heldout_corpus_path(n) for n in rp.HELDOUT_SITES]
    sources = {c.source for path in paths for c in load_corpus(path.stem, path)}
    assert sources == {"seed", "handwritten-2026-09-25-A", "handwritten-2026-09-25-B"}


def test_heldout_floor_is_its_own():
    held = load_corpus("learning-signal", rp.heldout_corpus_path("learning-signal"))
    assert len(held) < rp.MIN_CASES
    as_heldout = replay("learning-signal", held, transport=None, offline=True, corpus="heldout")
    assert as_heldout.failures == [] and as_heldout.corpus == "heldout"
    as_corpus = replay("learning-signal", held, transport=None, offline=True)
    assert any("< 30" in f for f in as_corpus.failures)


def test_cli_heldout_flag_reads_the_heldout_file(capsys: pytest.CaptureFixture[str]):
    assert main(["--site", "slop-score", "--heldout", "--offline", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["corpus"] == "heldout"
    assert report["cases"] == len(load_corpus("slop-score", rp.heldout_corpus_path("slop-score")))
    assert main(["--site", "route", "--heldout", "--offline"]) == 2  # no held-out set


# --- D6: the window reading on the corpus replay --------------------------------

# Spread over three neighbours (top cell 0.4, window 0.9) with a calibrated
# confidence under the read threshold: the shape the live probe returned.
LEVEL_FOR_TIER = {"SHALLOW": 1, "STANDARD": 4, "DEEP": 8}


def _spread(level: int) -> dict[str, Any]:
    probs = [0.1 / 7] * 10
    probs[level - 1], probs[level], probs[level + 1] = 0.25, 0.4, 0.25
    return {"score": level, "confidence": 0.45, "probabilities": probs}


def test_window_reading_answers_where_the_single_cell_abstains(transport):
    # Kills D6's mutant: without the window forge-complexity abstains on
    # every case of the relabelled corpus (single-cell top 0.4 < 0.60).
    cases = load_corpus("forge-complexity")

    def answer(case: ReplayCase) -> dict[str, Any]:
        level = LEVEL_FOR_TIER[str(case.expected)]
        return {f"forge_complexity__{d}": _spread(level) for d in DIMENSIONS}

    with patch(URLOPEN, side_effect=_keyed(cases, answer)):
        report = replay("forge-complexity", cases, transport=transport)
    assert report.abstain_rate == 0.0
    assert report.single_cell_abstain_rate == 1.0
    assert "single-cell reading (pre-D6): 100.0%" in rp._render(report)


# --- refine's missing-piece choice ---------------------------------------------


def test_refine_gap_accuracy_compares_the_missing_choice(transport):
    cases = load_corpus("refine")
    wrong = {cases[0].id}

    def answer(case: ReplayCase) -> dict[str, Any]:
        gap = "scope" if case.id in wrong else case.gap
        p = 0.95 if case.expected else 0.05
        return {"refine__vague": {"noul": p},
                "refine__missing": {"choice": gap, "confidence": 0.9}}

    with patch(URLOPEN, side_effect=_keyed(cases, answer)):
        report = replay("refine", cases, transport=transport)
    assert report.jev_accuracy == 1.0
    assert report.gap_accuracy == round((len(cases) - 1) / len(cases), 4)
    assert report.single_cell_abstain_rate is None
    assert "missing-piece choice vs gap label" in rp._render(report)


def test_gap_accuracy_is_none_without_labelled_gaps():
    case = ReplayCase(id="x", lang="pt", prompt="p", expected=True)
    assert rp._gap_accuracy([(case, True, None)]) is None
