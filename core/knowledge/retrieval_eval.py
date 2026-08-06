"""Measure the KB retrieval layer instead of arguing about it.

Retrieval is the part of this system most often changed on intuition and
least often measured. This module is the ruler: it scores what the layer
actually returns, against relevance the caller declares, using the metrics
the RAG literature settled on (context precision/recall, MRR, NDCG).

Three design decisions are load-bearing, and each one was paid for.

**It evaluates the real layer, never a copy.** `evaluate` takes a callable
that must be the production retrieval path. A reimplementation that drifts
from production measures something nobody runs.

**Latency is measured in a subprocess.** The retrieval layer runs inside
`UserPromptSubmit`, which is a fresh process on every prompt. Anything
built in memory is rebuilt every time. An in-memory BM25 index benchmarked
inside a long-lived process looked like 25 ms and was 3.8-5.4 SECONDS in a
cold process — against a layer that costs tens of milliseconds end to end.
`latency_probe` therefore refuses to measure in-process.

**Zero-hit is reported separately from recall.** Averaged recall hides the
failure users actually feel: the query that returned nothing relevant at
all. Two strategies with equal recall are not equivalent when one of them
answers half the questions with silence.

## Gold set format

    {"queries": [
       {"id": "...", "query": "...", "relevant": ["path/to/note.md", ...]},
       ...
    ]}

Paths are compared after normalisation by the `identity` callable, so the
gold set, the layer and this module all agree on what names a document.

## A warning about how gold sets are built

Pooling retrievers to decide relevance — running several retrievers and
judging their union — makes recall **optimistic**: a document no retriever
surfaced can never be judged relevant, so it never counts as a miss. That
bias also makes "does the right document appear at depth N?" circular.

`known_item_probes` exists for that reason. It starts from a document,
takes a passage, and asks for the question that passage answers. Relevance
is known by construction and no retriever votes on it.
"""
from __future__ import annotations

import json
import math
import os
import statistics
import subprocess
import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

__all__ = [
    "aggregate", "evaluate", "known_item_probes", "latency_probe",
    "load_gold_set", "relative_identity", "score_query",
]

Retriever = Callable[[str], Sequence[str]]
Identity = Callable[[str], str]


def _identity(value: str) -> str:
    return str(value).replace("\\", "/").strip().lstrip("./").lower()


def relative_identity(root: str | os.PathLike[str] | None) -> Identity:
    """Name documents by their path relative to `root`, case-folded.

    The layer returns absolute paths; a gold set is written with relative
    ones, because that is what a human can read and keep. Comparing the
    two forms directly scores every correct answer as a miss — the first
    run of this harness reported 0.00 across the board for exactly that
    reason, and the numbers looked plausible enough to believe.

    A relative input is already relative and is never resolved against the
    process working directory: that is the same bug wearing a different
    hat.
    """
    base = Path(root).resolve() if root else None

    def identity(value: str) -> str:
        raw = str(value).replace("\\", "/").strip()
        if not raw:
            return ""
        path = Path(raw)
        if not path.is_absolute():
            return raw.lstrip("./").lower()
        if base is not None:
            try:
                return path.resolve().relative_to(base).as_posix().lower()
            except (ValueError, OSError):
                pass
        return path.name.lower()

    return identity


# ── metrics ──────────────────────────────────────────────────────────────

def score_query(retrieved: Sequence[str], relevant: Iterable[str],
                identity: Identity = _identity) -> dict:
    """Metrics for one query. `retrieved` is in rank order, best first."""
    got = []
    for item in retrieved:
        norm = identity(item)
        if norm and norm not in got:
            got.append(norm)
    want = {identity(r) for r in relevant if identity(r)}
    if not want:
        return {"precision": 0.0, "recall": 0.0, "mrr": 0.0, "ndcg": 0.0,
                "n_retrieved": len(got), "n_relevant": 0, "zero_hit": True}

    hits = [i for i, item in enumerate(got, start=1) if item in want]
    precision = len(hits) / len(got) if got else 0.0
    recall = len(hits) / len(want)
    mrr = 1.0 / hits[0] if hits else 0.0
    dcg = sum(1.0 / math.log2(rank + 1) for rank in hits)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(want), len(got)) + 1))
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "mrr": round(mrr, 4),
        "ndcg": round(dcg / ideal, 4) if ideal else 0.0,
        "n_retrieved": len(got),
        "n_relevant": len(want),
        "zero_hit": not hits,
    }


def aggregate(scores: Sequence[dict]) -> dict:
    """Mean of the per-query metrics, plus the count that matters most.

    `zero_hit` is a COUNT, not a mean: it answers "how many questions did
    this answer with nothing useful", which is the failure a user notices.
    """
    if not scores:
        return {"precision": 0.0, "recall": 0.0, "mrr": 0.0, "ndcg": 0.0,
                "n_queries": 0, "n_zero_hit": 0}
    mean = lambda key: round(  # noqa: E731
        sum(s[key] for s in scores) / len(scores), 4)
    return {
        "precision": mean("precision"),
        "recall": mean("recall"),
        "mrr": mean("mrr"),
        "ndcg": mean("ndcg"),
        "n_queries": len(scores),
        "n_zero_hit": sum(1 for s in scores if s["zero_hit"]),
    }


def load_gold_set(path: str | os.PathLike[str]) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    queries = data["queries"] if isinstance(data, dict) else data
    for entry in queries:
        if "query" not in entry or "relevant" not in entry:
            raise ValueError(f"gold set entry missing query/relevant: {entry}")
    return list(queries)


def evaluate(retriever: Retriever, gold_set: Sequence[dict],
             identity: Identity = _identity) -> dict:
    """Score a retriever over a gold set. Per-query scores are kept.

    A regression that only shows in the aggregate is a regression you
    cannot debug, so the individual rows travel with the summary.
    """
    per_query = []
    for entry in gold_set:
        score = score_query(retriever(entry["query"]), entry["relevant"],
                            identity)
        score["id"] = entry.get("id", "")
        per_query.append(score)
    result = aggregate(per_query)
    result["per_query"] = per_query
    return result


# ── latency ──────────────────────────────────────────────────────────────

_PROBE = r"""
import json, sys, time
sys.path.insert(0, sys.argv[1])
setup, call = sys.argv[2], sys.argv[3]
exec(setup, globals())
timings = []
for query in json.loads(sys.argv[4]):
    started = time.perf_counter()
    try:
        eval(call, globals(), {"query": query})
    except Exception as exc:
        print("ARKA_LAT " + json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
        raise SystemExit(1)
    timings.append((time.perf_counter() - started) * 1000)
print("ARKA_LAT " + json.dumps({"timings": timings}))
"""


def latency_probe(setup: str, call: str, queries: Sequence[str],
                  root: str | os.PathLike[str] | None = None,
                  timeout: int = 300) -> dict:
    """Per-call latency in a FRESH process, which is how the hook runs.

    `setup` is executed once, `call` is evaluated per query with `query`
    bound. The first timing is reported separately as `cold_ms`: it pays
    for connections, caches and model loads that a real session also pays
    once, and averaging it in flatters or damns a design unfairly.

    Measuring this in-process is the single most expensive mistake
    available here — see the module docstring.
    """
    if not queries:
        return {"error": "no queries"}
    root = str(root or Path.cwd())
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE, root, setup, call, json.dumps(list(queries))],
        capture_output=True, text=True, timeout=timeout)
    line = next((row for row in proc.stdout.splitlines()
                 if row.startswith("ARKA_LAT ")), "")
    if not line:
        return {"error": "probe produced no result", "stderr": proc.stderr[-2000:]}
    payload = json.loads(line[len("ARKA_LAT "):])
    if "error" in payload:
        return payload
    timings = payload["timings"]
    cold, warm = timings[0], timings[1:] or timings
    ordered = sorted(warm)
    return {
        "n": len(timings),
        "cold_ms": round(cold),
        "p50_ms": round(statistics.median(ordered)),
        "p95_ms": round(ordered[min(len(ordered) - 1,
                                    round(0.95 * (len(ordered) - 1)))]),
        "max_ms": round(ordered[-1]),
    }


# ── known-item probes ────────────────────────────────────────────────────

def _passage(text: str, min_chars: int = 220) -> str:
    """A substantive paragraph from the SECOND HALF of a document.

    Questions written from a document's opening are blind to truncation
    and to summary-only indexing, which is how a chunker bug that silently
    dropped a third of this corpus stayed invisible for months. The half
    that gets lost is the half worth asking about.
    """
    body = text
    if body.startswith("---"):
        end = body.find("\n---", 3)
        if end != -1:
            body = body[end + 4:]
    paragraphs = [p.strip() for p in body.split("\n\n")]
    good = [p for p in paragraphs
            if len(p) >= min_chars
            and not p.lstrip().startswith(("#", "|", ">", "```", "- [", "!["))
            and p.count("|") < 4]
    if not good:
        return ""
    return good[len(good) // 2]


def known_item_probes(documents: Sequence[tuple[str, str]],
                      question_for: Callable[[str], str]) -> list[dict]:
    """Gold-set entries whose relevance nobody had to judge.

    `documents` is (identifier, full text). `question_for` turns a passage
    into the question it answers — inject a model for this; there is no
    default on purpose.

    A keyword-extraction stand-in is tempting and is NOT neutral: a
    question made of the passage's own rare terms is a lexical query, and
    scoring lexical and embedding retrievers against it hands the result
    to the former before the run starts.
    """
    probes = []
    for index, (identifier, text) in enumerate(documents, start=1):
        passage = _passage(text or "")
        if not passage:
            continue
        question = (question_for(passage) or "").strip()
        if not question:
            continue
        probes.append({"id": f"ki-{index:04d}", "query": question,
                       "relevant": [identifier], "passage": passage[:400]})
    return probes
