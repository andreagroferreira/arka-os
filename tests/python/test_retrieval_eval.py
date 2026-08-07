"""Tests for the retrieval evaluation harness.

The metrics are arithmetic and easy to get subtly wrong in ways that
flatter whatever is being measured, so each one is pinned against a case
worked out by hand rather than against the implementation's own output.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.knowledge.retrieval_eval import (
    aggregate,
    evaluate,
    known_item_probes,
    latency_probe,
    load_gold_set,
    relative_identity,
    score_query,
)

# ── per-query metrics ────────────────────────────────────────────────────

def test_perfect_retrieval():
    s = score_query(["a.md", "b.md"], ["a.md", "b.md"])
    assert s["precision"] == 1.0
    assert s["recall"] == 1.0
    assert s["mrr"] == 1.0
    assert s["zero_hit"] is False


def test_nothing_relevant_is_flagged_not_just_scored_zero():
    s = score_query(["x.md", "y.md"], ["a.md"])
    assert s["recall"] == 0.0
    assert s["zero_hit"] is True, (
        "a query that returned nothing useful must be countable, not just "
        "averaged into a recall number"
    )


def test_mrr_uses_the_first_hit_only():
    assert score_query(["x.md", "a.md", "b.md"], ["a.md", "b.md"])["mrr"] == 0.5


def test_recall_is_over_relevant_not_over_retrieved():
    s = score_query(["a.md"], ["a.md", "b.md", "c.md", "d.md"])
    assert s["recall"] == 0.25
    assert s["precision"] == 1.0


def test_identity_normalises_separators_and_case():
    s = score_query([r"Notes\Deep Work.md"], ["notes/deep work.md"])
    assert s["recall"] == 1.0, "a backslash must not read as a miss"


def test_absolute_layer_paths_match_a_relative_gold_set(tmp_path):
    """The defect that made the first real run report 0.00 across the board.

    The layer returns absolute paths, a gold set is written with relative
    ones, and comparing them directly turns every hit into a miss while
    producing numbers that look entirely believable.
    """
    vault = tmp_path / "Vault"
    (vault / "Notes").mkdir(parents=True)
    note = vault / "Notes" / "Deep Work.md"
    note.write_text("x", encoding="utf-8")
    identity = relative_identity(vault)
    s = score_query([str(note)], ["notes/deep work.md"], identity)
    assert s["recall"] == 1.0
    assert s["zero_hit"] is False


def test_relative_input_is_not_resolved_against_the_cwd(tmp_path):
    identity = relative_identity(tmp_path)
    assert identity("notes/a.md") == "notes/a.md"


def test_path_outside_the_root_degrades_to_its_name(tmp_path):
    identity = relative_identity(tmp_path / "Vault")
    assert identity(str(tmp_path / "elsewhere" / "Other.md")) == "other.md"


def test_identity_without_a_root_still_normalises():
    identity = relative_identity(None)
    assert identity(r"Notes\A.md") == "notes/a.md"


def test_duplicate_results_do_not_inflate_precision():
    s = score_query(["a.md", "a.md", "a.md"], ["a.md"])
    assert s["precision"] == 1.0
    assert s["n_retrieved"] == 1


def test_empty_relevant_set_scores_zero_without_raising():
    s = score_query(["a.md"], [])
    assert s["zero_hit"] is True
    assert s["recall"] == 0.0


def test_empty_retrieval_is_a_zero_hit():
    assert score_query([], ["a.md"])["zero_hit"] is True


def test_ndcg_rewards_ranking_the_hit_higher():
    early = score_query(["a.md", "x.md", "y.md"], ["a.md"])
    late = score_query(["x.md", "y.md", "a.md"], ["a.md"])
    assert early["ndcg"] > late["ndcg"]
    assert early["recall"] == late["recall"], (
        "recall cannot tell these apart, which is why NDCG is reported"
    )


# ── aggregation ──────────────────────────────────────────────────────────

def test_zero_hit_is_counted_not_averaged():
    scores = [score_query(["a.md"], ["a.md"]), score_query(["x.md"], ["a.md"])]
    agg = aggregate(scores)
    assert agg["n_zero_hit"] == 1
    assert agg["n_queries"] == 2


def test_aggregate_of_nothing_is_not_an_error():
    assert aggregate([])["n_queries"] == 0


# ── gold set ─────────────────────────────────────────────────────────────

def test_load_accepts_both_shapes(tmp_path):
    entry = [{"id": "q1", "query": "x", "relevant": ["a.md"]}]
    wrapped = tmp_path / "w.json"
    wrapped.write_text(json.dumps({"queries": entry}), encoding="utf-8")
    bare = tmp_path / "b.json"
    bare.write_text(json.dumps(entry), encoding="utf-8")
    assert load_gold_set(wrapped) == load_gold_set(bare)


def test_malformed_gold_set_fails_loudly(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"queries": [{"query": "x"}]}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_gold_set(bad)


def test_evaluate_keeps_per_query_rows():
    gold = [{"id": "q1", "query": "one", "relevant": ["a.md"]},
            {"id": "q2", "query": "two", "relevant": ["b.md"]}]
    result = evaluate(lambda q: ["a.md"], gold)
    assert result["n_queries"] == 2
    assert result["n_zero_hit"] == 1
    assert [r["id"] for r in result["per_query"]] == ["q1", "q2"]


# ── latency ──────────────────────────────────────────────────────────────

def test_latency_is_measured_in_a_separate_process():
    """A warm in-process timing is the mistake this exists to prevent."""
    result = latency_probe(
        "import os\nPID = os.getpid()\n", "PID", ["a", "b", "c"])
    assert "error" not in result
    assert result["n"] == 3
    assert result["p50_ms"] >= 0


def test_latency_reports_the_first_call_separately():
    result = latency_probe("import time\ntime.sleep(0.05)\n", "1 + 1",
                           ["a", "b", "c"])
    assert "cold_ms" in result and "p50_ms" in result


def test_latency_surfaces_a_failing_call():
    result = latency_probe("", "1 / 0", ["a"])
    assert "error" in result and "ZeroDivisionError" in result["error"]


def test_latency_without_queries_is_an_error_not_a_crash():
    assert "error" in latency_probe("", "1", [])


# ── known-item probes ────────────────────────────────────────────────────

_DOC = (
    "---\ntitle: Example\n---\n\n"
    "# Heading\n\n"
    + "Opening paragraph that a naive probe would ask about, written long "
      "enough here to clear the minimum length threshold on its own merits, "
      "because a document whose only substantial prose sits at the top is "
      "exactly the case this selection is meant to walk past.\n\n"
    + "| a | b |\n| - | - |\n\n"
    + "The second half of the note carries the claim worth remembering, and "
      "is written long enough to be selected as the passage rather than "
      "skipped for being too short to matter, which is the behaviour under "
      "test and the reason the fixture is this verbose.\n"
)


def test_probe_takes_a_passage_from_the_second_half():
    probes = known_item_probes([("note.md", _DOC)], lambda p: "q?")
    assert probes and "second half" in probes[0]["passage"]


def test_probe_skips_structure_and_frontmatter():
    probes = known_item_probes([("note.md", _DOC)], lambda p: "q?")
    passage = probes[0]["passage"]
    assert not passage.startswith(("#", "|", "---"))


def test_document_without_a_usable_passage_is_skipped():
    assert known_item_probes([("tiny.md", "# Title\n\nshort.\n")],
                             lambda p: "q?") == []


def test_probe_relevance_needs_no_judgement():
    probes = known_item_probes([("note.md", _DOC)], lambda p: "q?")
    assert probes[0]["relevant"] == ["note.md"], (
        "the point of a known-item probe is that no retriever votes on "
        "what counts as relevant"
    )


def test_empty_generated_question_is_dropped():
    assert known_item_probes([("note.md", _DOC)], lambda p: "  ") == []
