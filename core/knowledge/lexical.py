"""Lexical retrieval over the knowledge base, as an on-disk FTS5 index.

WHY THIS EXISTS
The active embedding model is English-only (`BAAI/bge-small-en-v1.5`) and
roughly a fifth of the indexed corpus is Portuguese. Measured on a
known-item probe set — questions generated from a note, so relevance is
known by construction and no retriever votes on it — the gap is not
subtle:

    Portuguese notes   embedding MRR 0.46   lexical MRR 0.70
    English notes      embedding MRR 0.71   lexical MRR 0.60

The two signals fail on opposite halves of the corpus, which is exactly
the condition under which fusing them beats either. Adding the lexical
signal raised recall by 24% on a 33-question set and 51% on a held-out
15-question set, at the cost of some precision.

WHY FTS5 AND NOT AN IN-MEMORY BM25
The retrieval layer runs inside `UserPromptSubmit`, a fresh process on
every prompt. An in-memory postings index is rebuilt every time: measured
at 3.8-5.4 SECONDS against a layer that currently costs 32 ms. FTS5 keeps
the index on disk, so a cold process opens and queries it in about 42 ms.
The algorithm is not what makes this shippable; where the index lives is.

PORTABILITY
FTS5 is compiled into most SQLite builds but is not guaranteed — some
Linux distributions ship without it. Every entry point here degrades to
returning nothing rather than raising, so a build without FTS5 loses the
lexical signal and keeps the layer working exactly as it did before.
"""
from __future__ import annotations

import logging
import os
import re
import sqlite3
import unicodedata
from pathlib import Path

logger = logging.getLogger(__name__)

# Portuguese and English function words. FTS5's unicode61 tokenizer has no
# stopword list, and BM25 alone does not neutralise them in short queries:
# 'como', 'para' and 'the' appear in nearly every chunk and only add rank
# noise on an OR match. Dropping them moved held-out zero-hit from 9 to 8.
# Kept as prose and split at import: sixty quoted strings would be no
# clearer and much easier to typo.
_STOP_WORDS = """
a o as os um uma uns umas de do da dos das em no na nos nas por para com sem
que se e ou mas como qual quais quando onde porque entao ja nao sim ao aos
pelo pela ser esta este estas estes isso isto nosso nossa muito mais
the an of to in on for with without and or but that which when where how
is are was were be been being this these those it its as at by from we our
"""
_STOP = frozenset(_STOP_WORDS.split())

_MIN_TERM_LEN = 3
_ROW_LIMIT = 120


def _ro_uri(path: Path) -> str:
    """Read-only SQLite URI with the path properly percent-encoded.

    `f"file:{path}?mode=ro"` looks equivalent and is not: a directory
    containing '%' makes SQLite decode an escape that was never there, and
    on POSIX a '?' in a name is legal and truncates the URI. Both are
    plausible in a personal vault, and neither reproduces on a path that
    happens to be plain ASCII.
    """
    return path.resolve().as_uri() + "?mode=ro"


def index_path(db_path: str | os.PathLike[str]) -> Path:
    """Sidecar next to the knowledge db, never inside it.

    Keeping it separate means a failed or half-written lexical build can
    be deleted without putting the vector index at risk.
    """
    return Path(db_path).with_suffix(".lexical.db")


def fts5_available() -> bool:
    try:
        con = sqlite3.connect(":memory:")
        con.execute("create virtual table t using fts5(x)")
        con.close()
        return True
    except Exception:
        return False


def fold(text: str) -> str:
    """Lowercase and strip diacritics.

    Applied identically at index and query time. The corpus writes
    'memoria' and 'memória' interchangeably and unicode61 would otherwise
    treat them as unrelated terms.
    """
    folded = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in folded if not unicodedata.combining(c))


def terms(query: str) -> list[str]:
    return [w for w in re.split(r"[^a-z0-9]+", fold(query))
            if len(w) >= _MIN_TERM_LEN and w not in _STOP]


def build(db_path: str | os.PathLike[str]) -> tuple[bool, str]:
    """(built, message). Never raises: a corpus without a lexical index
    retrieves exactly as it did before this module existed."""
    if not fts5_available():
        return False, "FTS5 não disponível nesta compilação do SQLite"
    src_path = Path(db_path)
    if not src_path.is_file():
        return False, f"base de dados de conhecimento inexistente: {src_path}"

    target = index_path(src_path)
    tmp = target.with_suffix(".tmp")
    try:
        src = sqlite3.connect(_ro_uri(src_path), uri=True)
        rows = src.execute("select source, text from chunks").fetchall()
        src.close()

        if tmp.exists():
            tmp.unlink()
        out = sqlite3.connect(tmp)
        out.execute("create virtual table fts using fts5("
                    "source unindexed, body, tokenize='unicode61')")
        out.executemany("insert into fts(source, body) values (?, ?)",
                        [(s, fold(t)) for s, t in rows])
        out.commit()
        out.close()
        # Swap only once the new index is complete, so a crash mid-build
        # leaves the previous index serving instead of a truncated one.
        os.replace(tmp, target)
        return True, f"{len(rows)} chunks indexados em {target.name}"
    except Exception as exc:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        return False, f"falha a construir o índice: {type(exc).__name__}: {exc}"


def is_stale(db_path: str | os.PathLike[str]) -> bool:
    """True when the knowledge db has moved on since the lexical build.

    A stale index is worse than none: it silently serves notes that were
    reindexed or deleted, which is the failure mode orphaned chunks
    already caused once in this system.
    """
    src, idx = Path(db_path), index_path(db_path)
    if not idx.is_file():
        return True
    try:
        return src.stat().st_mtime > idx.stat().st_mtime
    except OSError:
        return True


def search(db_path: str | os.PathLike[str], query: str,
           top_k: int = 20) -> list[str]:
    """Source paths in BM25 order, best first. [] on any failure.

    Returns raw `source` values so the caller decides identity; this
    module has no opinion about how a chunk maps to a note.
    """
    idx = index_path(db_path)
    if not idx.is_file():
        logger.debug("lexical index absent (%s) — vector-only retrieval", idx)
        return []
    if is_stale(db_path):
        # Refusing a stale index is correct, but doing it silently means a
        # corpus quietly loses half its retrieval signal and nothing says
        # so. Run the indexer to rebuild.
        logger.warning(
            "lexical index %s is stale (knowledge db is newer) — lexical "
            "signal disabled until reindex", idx,
        )
        return []
    query_terms = terms(query)
    if not query_terms:
        return []
    # OR, not AND: a half-remembered question rarely shares every term
    # with the note it is looking for, and AND returns nothing for most
    # real prompts.
    match = " OR ".join(query_terms)
    try:
        con = sqlite3.connect(_ro_uri(idx), uri=True)
        rows = con.execute(
            "select source, bm25(fts) as k from fts where fts match ? "
            "order by k limit ?", (match, _ROW_LIMIT)).fetchall()
        con.close()
    except Exception:
        return []
    out: list[str] = []
    for source, _ in rows:
        if source and source not in out:
            out.append(source)
        if len(out) >= top_k:
            break
    return out


def rrf(rankings: list[list[str]], top_k: int = 5, k: int = 60) -> list[str]:
    """Reciprocal Rank Fusion, Cormack et al. 2009.

    An item ranked mediocre by two independent retrievers beats one
    ranked first by a single retriever and unseen by the other. That is
    the property being bought here: agreement across signals is evidence,
    and the two signals fail on opposite halves of this corpus.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return [i for i, _ in sorted(scores.items(),
                                 key=lambda x: x[1], reverse=True)[:top_k]]
