"""Retrieval evaluation CLI — score the KB layer, and time it honestly.

Usage:
    arka-py -m core.knowledge.retrieval_eval_cli score --gold-set <file.json>
    arka-py -m core.knowledge.retrieval_eval_cli latency
    arka-py -m core.knowledge.retrieval_eval_cli score --gold-set g.json --json

`score` runs the REAL `KBContextLayer` against a gold set. `latency` times
that same layer in a fresh subprocess, because `UserPromptSubmit` starts a
new process for every prompt and anything measured in a warm one is
measured wrong.

Neither command writes anything or changes retrieval behaviour.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from core.knowledge.retrieval_eval import (
    evaluate,
    latency_probe,
    load_gold_set,
    relative_identity,
)

DEFAULT_QUERIES = [
    "where are the configuration files kept",
    "how does the indexer decide what to skip",
    "what happens when the vault path is not set",
    "how are notes ranked before they reach the model",
    "which limits apply to the size of an injected block",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _layer(max_notes: int, min_similarity: float):
    """The production layer, constructed exactly as the hook constructs it.

    Deliberately not a test double: a ruler that measures a copy of the
    retrieval path measures something nobody runs.
    """
    from core.knowledge.vector_store import VectorStore
    from core.synapse.layers_kb import KBContextLayer

    return KBContextLayer(
        vector_store=VectorStore(str(Path.home() / ".arkaos" / "knowledge.db")),
        vault_path=os.environ.get("ARKAOS_VAULT", ""),
        max_notes=max_notes,
        min_similarity=min_similarity,
    )


def _cmd_score(args: argparse.Namespace) -> int:
    gold_set = load_gold_set(args.gold_set)
    layer = _layer(args.max_notes, args.min_similarity)

    def retrieve(query: str) -> list[str]:
        notes, _degraded = layer._retrieve(query[:2000])
        return [str(n.get("path") or "") for n in notes]

    # Gold sets are written with vault-relative paths; the layer returns
    # absolute ones. Without this the run scores every hit as a miss.
    identity = relative_identity(os.environ.get("ARKAOS_VAULT") or None)
    result = evaluate(retrieve, gold_set, identity)
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    print(f"gold set: {Path(args.gold_set).name} — {result['n_queries']} queries")
    print(f"  precision {result['precision']:.2f}")
    print(f"  recall    {result['recall']:.2f}")
    print(f"  MRR       {result['mrr']:.2f}")
    print(f"  NDCG      {result['ndcg']:.2f}")
    print(f"  returned nothing relevant: "
          f"{result['n_zero_hit']} of {result['n_queries']}")
    if result["n_zero_hit"]:
        print("\n  queries with no relevant result:")
        for row in result["per_query"]:
            if row["zero_hit"]:
                print(f"    - {row['id'] or '(unnamed)'}")
    return 0


SETUP = (
    "from pathlib import Path\n"
    "import os\n"
    "from core.knowledge.vector_store import VectorStore\n"
    "from core.synapse.layers_kb import KBContextLayer\n"
    "layer = KBContextLayer(\n"
    "    vector_store=VectorStore(str(Path.home() / '.arkaos' / 'knowledge.db')),\n"
    "    vault_path=os.environ.get('ARKAOS_VAULT', ''),\n"
    "    max_notes=5, min_similarity=0.5)\n"
)


def _cmd_latency(args: argparse.Namespace) -> int:
    queries = DEFAULT_QUERIES
    if args.queries:
        queries = [q for q in Path(args.queries).read_text(
            encoding="utf-8").splitlines() if q.strip()]
    result = latency_probe(SETUP, "layer._retrieve(query)", queries,
                           root=str(_repo_root()))
    if args.json:
        print(json.dumps(result, indent=2))
        return 0 if "error" not in result else 1
    if "error" in result:
        print(f"probe failed: {result['error']}")
        if result.get("stderr"):
            print(result["stderr"])
        return 1
    print(f"KB retrieval, {result['n']} calls in a fresh process")
    print(f"  cold  {result['cold_ms']:>6} ms   (paid once per session)")
    print(f"  p50   {result['p50_ms']:>6} ms")
    print(f"  p95   {result['p95_ms']:>6} ms")
    print(f"  max   {result['max_ms']:>6} ms")
    print("\nThis runs on every prompt, before the assistant starts. Treat"
          "\nany addition to it as a latency budget question first.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="retrieval_eval_cli")
    sub = parser.add_subparsers(dest="command", required=True)

    score = sub.add_parser("score", help="score the KB layer on a gold set")
    score.add_argument("--gold-set", required=True)
    score.add_argument("--max-notes", type=int, default=5)
    score.add_argument("--min-similarity", type=float, default=0.5)
    score.add_argument("--json", action="store_true")
    score.set_defaults(func=_cmd_score)

    latency = sub.add_parser("latency", help="time the KB layer, cold")
    latency.add_argument("--queries", help="file with one query per line")
    latency.add_argument("--json", action="store_true")
    latency.set_defaults(func=_cmd_latency)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
