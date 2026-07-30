"""Doctrine classification and second-pass retrieval for the knowledge base.

Why this exists
---------------
Semantic retrieval over a mixed vault has a structural blind spot: prompts
framed in PROJECT terms ("validate the acme-tests suite structure") always
rank project notes above reference material, because project chunks share
the prompt's entities and doctrine chunks do not. Measured on a live vault
(2026-07-29, 5.5k chunks, 36% book/reference content): the project-framed
prompt returned ZERO doctrine chunks even in the top 60, in both English
and Portuguese, while a conceptual query over the same topics returned
10/10. The operator's ingested books, video distillations and frameworks
are invisible exactly when they should inform the work.

The fix has two halves, both here:

1. **Classification at index time** (``resolve_knowledge_class``): every
   note gets a ``knowledge_class`` in its chunk metadata, resolved by a
   ladder — explicit frontmatter first, unambiguous type/tag conventions
   second, a PARA folder fallback last. Location- and medium-agnostic: a
   video distillation under ``Projects/`` tagged ``doctrine`` classifies
   the same as a book chapter under ``Resources/``.

2. **Derived-query retrieval at prompt time** (``doctrine_block``): the
   raw prompt cannot reach doctrine (proven above), so a conceptual query
   is REBUILT from the prompt's overlap with the domain vocabulary that
   indexing harvested from doctrine frontmatter, and its results are
   filtered to ``knowledge_class == "doctrine"`` and rendered as a
   separate ``[arka:doctrine]`` block.

Matching is by shared morphological stem, never by loose prefix — prefix
matching was tried and produced real damage in live replay (pt "projeto"
prefix-matched the domain "projections"; a single weak match dragged
neighbor-book co-occurrences into an unrelated prompt).
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any

DEFAULT_VOCAB_PATH = Path.home() / ".arkaos" / "doctrine-domains.json"

# Types/tags that are doctrine EVERYWHERE. Deliberately narrow: an audit of
# a real vault showed `framework`, `reference`, `guide`, `source` and
# `concept` are also used on project-scoped notes, which must stay
# operational (the normal retrieval pass already finds them). Rule 1
# (explicit frontmatter) is the escape hatch for doctrine outside these.
DOCTRINE_TYPES = frozenset({
    "book-moc", "book-chapter", "video-distillation", "distilled",
})
DOCTRINE_TAGS = frozenset({"book", "distilled", "doctrine"})
_GENERIC_TAGS = frozenset({"book", "moc", "distilled", "doctrine", "note", "source"})
PARA_CLASS = {"Resources": "doctrine", "Archive": "archive"}

VALID_CLASSES = frozenset({"doctrine", "operational", "excluded", "archive"})

# Bounded PT->EN alias table for tech vocabulary. Linguistic glue only —
# domains themselves always come from vault frontmatter.
_PT_ALIASES: dict[str, str] = {
    "teste": "testing", "testes": "testing", "testar": "testing",
    "valida": "validation", "validar": "validation", "validacao": "validation",
    "estrutura": "structure", "estruturas": "structure",
    "qualidade": "quality", "arquitetura": "architecture",
    "arquitectura": "architecture", "integracao": "integration",
    "integracoes": "integration", "seguranca": "security",
    "desempenho": "performance", "dados": "data", "modelacao": "modeling",
    "dominio": "domain", "escrita": "writing", "conteudo": "content",
    # "marca" -> "brand" was tried and removed: the verb sense ("marca a
    # reuniao" = schedule the meeting) false-positived StoryBrand into a
    # scheduling prompt (validation matrix, 2026-07-30).
    "preco": "pricing", "precos": "pricing",
    "entrevista": "interviews", "entrevistas": "interviews",
    "particionar": "partitioning", "particionamento": "partitioning",
    "replicar": "replication", "replicacao": "replication",
    "escalar": "scalability", "escalabilidade": "scalability",
    "consistencia": "consistency",
    "vies": "biases", "vieses": "biases", "enviesar": "biases",
    "decisao": "decision-making", "decisoes": "decision-making",
    "decidir": "decision-making", "julgamento": "judgment",
    "heuristica": "heuristics", "heuristicas": "heuristics",
    "notas": "notes", "conhecimento": "knowledge",
    "fiabilidade": "reliability", "resiliencia": "resilience",
    "eventos": "events", "mensagens": "messaging",
    "api": "api", "apis": "api", "microservicos": "microservices",
    "refatoracao": "refactoring", "refactorizacao": "refactoring",
    "complexidade": "complexity", "design": "design",
    "padroes": "patterns", "padrao": "patterns",
    "estrategia": "strategy", "produto": "product",
    "cliente": "customers", "clientes": "customers", "vendas": "sales",
}

_MAX_QUERY_TERMS = 8
_DOCTRINE_TOP_K = 40
_MAX_DOCTRINE_NOTES = 3
_MIN_SCORE = 0.50
_QUERY_SUFFIX = "best practices patterns principles"

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)

_VOCAB_CACHE: dict[str, Any] = {"mtime": None, "vocab": {}}


# ─── frontmatter + classification (index time) ───────────────────────────


def parse_frontmatter(content: str) -> dict:
    """YAML frontmatter as a dict, or {}. Never raises."""
    match = _FRONTMATTER_RE.match(content or "")
    if not match:
        return {}
    try:
        import yaml
        data = yaml.safe_load(match.group(1))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _as_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return []


def resolve_knowledge_class(frontmatter: dict, relative_path: Path | PurePosixPath) -> str:
    """Resolve a note's knowledge class. First rule that answers wins."""
    explicit = str(frontmatter.get("knowledge_class", "")).strip().lower()
    if explicit in VALID_CLASSES:
        return explicit
    if frontmatter.get("doctrine") is True:
        return "doctrine"
    if frontmatter.get("doctrine") is False:
        return "operational"
    note_type = str(frontmatter.get("type", "")).strip().lower()
    if note_type in DOCTRINE_TYPES:
        return "doctrine"
    tags = {t.strip().lower() for t in _as_list(frontmatter.get("tags"))}
    if tags & DOCTRINE_TAGS:
        return "doctrine"
    top = relative_path.parts[0] if relative_path.parts else ""
    return PARA_CLASS.get(top, "operational")


def note_domains(frontmatter: dict) -> list[str]:
    """Declared domains: ``domain:`` first, else non-generic tags."""
    domains = [d.strip().lower() for d in _as_list(frontmatter.get("domain"))]
    if domains:
        return domains
    return [
        t.strip().lower() for t in _as_list(frontmatter.get("tags"))
        if t.strip().lower() not in _GENERIC_TAGS
    ]


def update_vocabulary(vocab: dict, domains: list[str], note_title: str) -> None:
    """Fold one doctrine note's domains into the vocabulary (in place)."""
    for domain in domains:
        entry = vocab.setdefault(domain, {"count": 0, "notes": []})
        entry["count"] += 1
        if len(entry["notes"]) < 12:
            entry["notes"].append(note_title)
        for other in domains:
            if other != domain:
                cooccurs = entry.setdefault("cooccurs", {})
                cooccurs[other] = cooccurs.get(other, 0) + 1


def rebuild_vocabulary_from_sources(source_metadata) -> dict:
    """Full vocabulary from (source, metadata) pairs of the WHOLE index.

    The vocabulary must always describe the complete doctrine corpus.
    Building it from the files touched by one indexing run breaks
    incremental indexing: a run that ingests three new notes would
    overwrite the sidecar with a three-note vocabulary and blind the
    doctrine pass to everything else. The chunk metadata already in the
    store is the always-complete source of truth, so the sidecar is
    rebuilt from it after every run.
    """
    vocab: dict = {}
    for source, metadata in source_metadata:
        if not isinstance(metadata, dict):
            continue
        if metadata.get("knowledge_class") != "doctrine":
            continue
        domains = [d for d in (metadata.get("domains") or []) if d]
        update_vocabulary(vocab, domains, Path(source).stem)
    return vocab


def save_vocabulary(vocab: dict, path: Path | None = None) -> Path:
    """Persist the domain vocabulary sidecar. Returns the written path."""
    target = path or DEFAULT_VOCAB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(vocab, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return target


# ─── derived query (prompt time) ─────────────────────────────────────────


def _load_vocab(path: Path | None = None) -> dict:
    target = path or DEFAULT_VOCAB_PATH
    try:
        mtime = target.stat().st_mtime
    except OSError:
        return {}
    if _VOCAB_CACHE["mtime"] == (str(target), mtime):
        return _VOCAB_CACHE["vocab"]
    try:
        vocab = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(vocab, dict):
        return {}
    _VOCAB_CACHE.update(mtime=(str(target), mtime), vocab=vocab)
    return vocab


def _normalize(token: str) -> str:
    token = unicodedata.normalize("NFKD", token.lower())
    return "".join(c for c in token if not unicodedata.combining(c))


def _variants(word: str) -> set[str]:
    """Morphological variants for matching: shared stems, never prefixes."""
    out = {word}
    for suffix in ("ing", "tion", "sion", "ments",
                   "ment",  # codespell:ignore ment
                   "ies", "ers", "er", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            stem = word[: -len(suffix)]
            out.add(stem)
            if suffix == "ies":
                out.add(stem + "y")
    return out


def _prompt_tokens(prompt: str) -> set[str]:
    raw = re.findall(
        r"[A-Za-zÀ-ÿ0-9]{3,}",
        prompt.lower().replace("-", " ").replace("_", " "),
    )
    tokens: set[str] = set()
    for token in raw:
        norm = _normalize(token)
        alias = _PT_ALIASES.get(norm)
        if alias:
            norm = alias
        tokens |= _variants(norm)
    return tokens


def _domain_matches(domain: str, tokens: set[str]) -> bool:
    return bool(_variants(_normalize(domain)) & tokens)


def derive_doctrine_query(prompt: str, vocab_path: Path | None = None) -> str:
    """Conceptual query from prompt-domain overlap; '' when nothing matches."""
    vocab = _load_vocab(vocab_path)
    if not vocab or not prompt:
        return ""
    tokens = _prompt_tokens(prompt)
    matched = [d for d in vocab if _domain_matches(d, tokens)]
    if not matched:
        return ""
    matched.sort(key=lambda d: -int(vocab[d].get("count", 0)))
    terms: list[str] = list(dict.fromkeys(matched))[:_MAX_QUERY_TERMS]
    # Co-occurring domains only FILL a thin match, and only from the
    # STRONGEST matched domain — filling from every match let a broad
    # 1-count domain ("organization") drag unrelated-book noise into a
    # zettelkasten prompt (validation matrix, 2026-07-30).
    if len(terms) < 3 and terms:
        cooccurs = vocab[terms[0]].get("cooccurs") or {}
        for other, _n in sorted(cooccurs.items(), key=lambda kv: -kv[1])[:2]:
            if other not in terms and len(terms) < _MAX_QUERY_TERMS:
                terms.append(other)
    return " ".join(terms[:_MAX_QUERY_TERMS]) + " " + _QUERY_SUFFIX


# ─── retrieval + rendering (consumed by Synapse L2.5) ────────────────────


def _is_doctrine_hit(hit: dict) -> bool:
    metadata = hit.get("metadata")
    return isinstance(metadata, dict) and metadata.get("knowledge_class") == "doctrine"


def doctrine_notes(
    store: Any, prompt: str, exclude_sources: set[str],
    vocab_path: Path | None = None,
) -> list[dict]:
    """Top doctrine chunks for the derived query. Fail-open: [] on any error."""
    query = derive_doctrine_query(prompt, vocab_path)
    if not query or store is None:
        return []
    try:
        hits = list(store.search(query, top_k=_DOCTRINE_TOP_K)) or []
    except Exception:
        return []
    # Aggregate by SOURCE before picking: on a nearly-flat score band a
    # source with several chunks in the deep top-K is topically stronger
    # than a single stray chunk from another collection (validation
    # matrix 2026-07-30: the right book had 3 chunks at 0.575 and lost
    # every slot to lone 0.577 chunks). Rank = best score + a small
    # per-extra-chunk bonus — never enough to beat a genuinely better match.
    by_source: dict[str, dict] = {}
    for hit in hits:
        if hit.get("retrieval") == "keyword-degraded":
            # No similarity exists — never present keyword noise as doctrine.
            return []
        if float(hit.get("score") or 0.0) < _MIN_SCORE:
            continue
        if not _is_doctrine_hit(hit):
            continue
        source = hit.get("source", "") or ""
        if not source or source in exclude_sources:
            continue
        entry = by_source.get(source)
        if entry is None:
            by_source[source] = {"hit": hit, "n": 1}
        else:
            entry["n"] += 1
            if float(hit.get("score") or 0.0) > float(entry["hit"].get("score") or 0.0):
                entry["hit"] = hit
    ranked = sorted(
        by_source.values(),
        key=lambda e: float(e["hit"].get("score") or 0.0) + 0.005 * (e["n"] - 1),
        reverse=True,
    )
    return [e["hit"] for e in ranked[:_MAX_DOCTRINE_NOTES]]


def format_doctrine_block(hits: list[dict]) -> str:
    if not hits:
        return ""
    lines = [
        "[arka:doctrine] Doutrina relevante no teu cérebro (livros/vídeos/"
        "frameworks ingeridos) para a tarefa em curso — consulta ANTES de "
        "desenhar ou avaliar:",
        "",
    ]
    for hit in hits:
        source = hit.get("source", "") or ""
        title = hit.get("heading") or Path(source).stem or "nota"
        excerpt = " ".join((hit.get("text") or "").split())[:220]
        lines.append(f"- [[{Path(source).stem}]] — {title} (path: `{source}`)")
        if excerpt:
            lines.append(f"  Excerto: {excerpt}")
        lines.append("")
    lines.append(
        "Estas notas são doutrina (referência), não estado do projeto. "
        "Cita as que usares; se contradisserem a prática do projeto, di-lo."
    )
    return "\n".join(lines).strip()


def doctrine_block(
    store: Any, prompt: str, exclude_sources: set[str] | None = None,
) -> str:
    """Public entrypoint for L2.5. Never raises; '' when nothing qualifies."""
    try:
        hits = doctrine_notes(store, prompt, exclude_sources or set())
        return format_doctrine_block(hits)
    except Exception:
        return ""
