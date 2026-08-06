"""Deep recall on demand — the slow lane of a two-speed retrieval design.

The per-prompt KB layer has a hard latency budget (it runs inside
`UserPromptSubmit`, measured at ~40 ms end to end), which caps it at a
handful of notes. Plenty of relevant notes sit just below that cut: on a
measured corpus, about a quarter of the relevant documents ranked between
position 6 and 50 — found by the index, buried by the cutoff.

This CLI is the explicit second look. The user pays ~100 ms when they ask,
and nothing when they do not:

    arka-py -m core.knowledge.recall_cli "how did we fix the deploy race"
    arka-py -m core.knowledge.recall_cli "..." --top 20 --json

It fuses the embedding ranking with the lexical (FTS5) ranking when that
index is available, and degrades to embedding-only when it is not — so it
works, slightly diminished, on installs without the lexical module or on
SQLite builds without FTS5. Each result says which signals surfaced it;
`both` is the strongest evidence of relevance the fusion can offer.

Read-only by construction: nothing here writes, so the worst possible
outcome of any failure is an empty list.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

DEPTH = 50  # how deep each signal searches before fusing


def _fuse(rankings: list[list[str]], top_k: int) -> list[str]:
    """Reciprocal Rank Fusion, delegated to its single implementation.

    ``lexical.rrf`` owns the algorithm and its k constant; this module
    must nonetheless stay importable on an install without the lexical
    layer. That costs nothing, because on such an install
    ``_lexical_ranking`` can only return ``[]`` and there is never a
    second ranking to fuse — and RRF over one ranking is a monotone
    transform of its rank, so it preserves that ranking's order exactly.
    The fallback is therefore the degenerate case of the fusion, not a
    second copy of it: with one signal, all that remains is the cut.
    """
    if not rankings:
        return []
    try:
        from core.knowledge import lexical
    except ImportError:
        return rankings[0][:top_k]
    return lexical.rrf(rankings, top_k=top_k)


def _dedupe_to_notes(hits: list[dict]) -> list[str]:
    """Chunk hits collapse to their note, keeping the best rank."""
    out: list[str] = []
    for hit in hits:
        source = str(hit.get("source") or "")
        if source and source not in out:
            out.append(source)
    return out


def _store_db_path(store: Any) -> str:
    """The store's db path, through the one shared helper.

    Third consumer of the same lookup; the other two already resolve it
    via ``get_stats()``. Returns "" when the lexical package is absent —
    the only thing this path feeds is the lexical ranking, which cannot
    run in that case either.
    """
    try:
        from core.knowledge.lexical_fusion import store_db_path

        return store_db_path(store)
    except ImportError:
        return ""


def _lexical_ranking(db_path: str, query: str) -> list[str]:
    """The lexical signal, or [] wherever it cannot serve.

    Optional on purpose: this CLI must work on an install that has no
    lexical module and on a SQLite build without FTS5.
    """
    try:
        from core.knowledge import lexical
        return lexical.search(db_path, query, top_k=DEPTH)
    except Exception:
        return []


def deep_recall(store, query: str, top_k: int = 15) -> list[dict]:
    """Fused deep ranking: [{source, signals}], best first.

    `signals` names which retriever surfaced each note — a note both
    signals agree on is the strongest relevance evidence fusion offers,
    and showing that lets the reader calibrate their own trust.
    """
    vector = _dedupe_to_notes(store.search(query, top_k=DEPTH))
    lexical_rank = _lexical_ranking(_store_db_path(store), query)

    rankings = [ranking for ranking in (vector, lexical_rank) if ranking]
    if not rankings:
        return []
    fused = _fuse(rankings, top_k)

    vector_set, lexical_set = set(vector), set(lexical_rank)
    results = []
    for source in fused:
        signals = [name for name, members in
                   (("vector", vector_set), ("lexical", lexical_set))
                   if source in members]
        results.append({"source": source, "signals": signals})
    return results


def _display_path(source: str) -> str:
    vault = os.environ.get("ARKAOS_VAULT", "")
    if vault:
        try:
            return Path(source).resolve().relative_to(
                Path(vault).resolve()).as_posix()
        except (ValueError, OSError):
            pass
    return source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="recall_cli", description="deep on-demand KB recall")
    parser.add_argument("query")
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    from core.knowledge.vector_store import VectorStore
    store = VectorStore(str(Path.home() / ".arkaos" / "knowledge.db"))
    results = deep_recall(store, args.query, top_k=args.top)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=1))
        return 0
    if not results:
        print("nothing found — is the knowledge base indexed?")
        return 1
    both = sum(1 for r in results if len(r["signals"]) == 2)
    print(f"{len(results)} notes (depth {DEPTH} per signal, "
          f"{both} found by both signals)\n")
    for rank, r in enumerate(results, start=1):
        marker = "=" if len(r["signals"]) == 2 else r["signals"][0][0]
        print(f" {rank:>2} [{marker}] {_display_path(r['source'])}")
    print("\n[=] both signals   [v] vector only   [l] lexical only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
