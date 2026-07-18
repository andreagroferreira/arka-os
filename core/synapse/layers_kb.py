"""L2.5 KB Context layer (Obsidian) — extracted from layers.py.

Semantic + keyword retrieval over the operator's Obsidian vault with a
grounding policy that quarantines inferred (Dreaming-written) notes.
All names are re-exported by core.synapse.layers for backward
compatibility — import from there unless you need the module itself.
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

from core.synapse.layers_base import Layer, LayerResult, PromptContext

_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]")
_FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
_KB_CONFIG_PATH = Path.home() / ".arkaos" / "config.json"
# Cap fallback-note scanning to avoid O(vault size) blow-ups on large
# Obsidian vaults. The cap is above any realistic top-N retrieval need
# (Jaccard ranks the top few notes; scanning 2000 sorted-by-name first
# is plenty — see `_load_fallback_notes`) while still bounding worst-case latency.
_MAX_FALLBACK_NOTES = 2000
_KB_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "by", "from", "as", "is", "was", "are", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "should", "could",
    "may", "might", "must", "can", "this", "that", "these", "those", "it", "its",
    "about", "into", "over", "under", "up", "down", "out", "than", "then", "so",
    "if", "because", "while", "where", "when", "what", "which", "who", "whom",
    "how", "why", "all", "some", "any", "no", "not", "very", "just", "also",
})


def _l25_feature_flag_on() -> bool:
    if os.environ.get("ARKA_BYPASS_L25", "").strip() == "1":
        return False
    if not _KB_CONFIG_PATH.exists():
        return True
    try:
        data = json.loads(_KB_CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return True
    synapse_cfg = data.get("synapse") or {}
    return bool(synapse_cfg.get("l25KbContext", True))


def _tokenize_for_jaccard(text: str) -> set[str]:
    if not text:
        return set()
    words = re.findall(r"[a-zA-Z0-9]{3,}", text.lower())
    return {w for w in words if w not in _KB_STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _extract_note_body(raw: str) -> str:
    return _FRONTMATTER_RE.sub("", raw, count=1).lstrip()


def _extract_title(raw: str, fallback: str) -> str:
    body = _extract_note_body(raw)
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
        if stripped:
            return fallback
    return fallback


def _extract_excerpt(raw: str, max_lines: int = 2) -> str:
    body = _extract_note_body(raw)
    lines: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
        if len(lines) >= max_lines:
            break
    return " ".join(lines)[:240]


def _extract_wikilinks(raw: str, limit: int = 3) -> list[str]:
    body = _extract_note_body(raw)
    seen: list[str] = []
    for match in _WIKILINK_RE.finditer(body):
        target = match.group(1).strip()
        if target and target not in seen:
            seen.append(target)
        if len(seen) >= limit:
            break
    return seen


def _format_kb_block(notes: list[dict], degraded: bool = False) -> str:
    lines: list[str] = [
        f"[arka:kb-context] O teu cérebro (Obsidian) tem {len(notes)} "
        f"nota{'s' if len(notes) != 1 else ''} relevante{'s' if len(notes) != 1 else ''} "
        f"para este pedido:",
        "",
    ]
    if degraded:
        lines.insert(1, "")
        lines.insert(
            1,
            "Atenção: correspondência por palavras-chave (pesquisa semântica "
            "indisponível) — NÃO é similaridade semântica.",
        )
    for note in notes:
        title = note.get("title", "")
        path = note.get("path", "")
        excerpt = note.get("excerpt", "")
        relates = note.get("relates", []) or []
        suffix = " (inferred — not authoritative)" if note.get("inferred") else ""
        lines.append(f"- [[{title}]]{suffix} (path: `{path}`)")
        if excerpt:
            lines.append(f"  Excerto: {excerpt}")
        if relates:
            rel = ", ".join(f"[[{r}]]" for r in relates)
            lines.append(f"  Relacionada: {rel}")
        lines.append("")
    lines.append(
        "Consulta-as antes de ir a Context7/Web. Se preencherem o pedido, "
        "usa-as e cita. Se tiverem lacuna, investiga externamente e "
        "documenta de volta."
    )
    return "\n".join(lines).strip()


def _vector_search(store: Any, prompt: str, top_k: int) -> list[dict]:
    if store is None:
        return []
    try:
        return list(store.search(prompt, top_k=top_k)) or []
    except Exception:
        return []


def _jaccard_fallback(
    prompt: str, notes: list[dict], top_k: int, threshold: float
) -> list[dict]:
    prompt_tokens = _tokenize_for_jaccard(prompt)
    scored: list[tuple[float, dict]] = []
    for note in notes:
        title_tokens = _tokenize_for_jaccard(note.get("title", ""))
        score = _jaccard(prompt_tokens, title_tokens)
        if score >= threshold:
            scored.append((score, note))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [n for _, n in scored[:top_k]]


def _load_fallback_notes(vault_path: Optional[Path]) -> list[dict]:
    if vault_path is None or not vault_path.exists() or not vault_path.is_dir():
        return []
    notes: list[dict] = []
    for md in sorted(vault_path.rglob("*.md")):
        if len(notes) >= _MAX_FALLBACK_NOTES:
            break
        try:
            raw = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        notes.append(
            {
                "title": _extract_title(raw, md.stem),
                "path": str(md),
                "raw": raw,
            }
        )
    return notes


_GROUNDING_INFERRED_RE = re.compile(r"^grounding:\s*inferred\s*$", re.MULTILINE)


def _frontmatter_marks_inferred(raw: str) -> bool:
    """Cheap check: does the YAML frontmatter carry `grounding: inferred`?

    Parses ONLY the frontmatter block (the note content is already in
    hand) — no YAML library, no full-document scan. Dreaming-written
    notes carry this marker (see core/cognition/dreaming.py, PR-3 v4.1).
    """
    match = _FRONTMATTER_RE.match(raw or "")
    if not match:
        return False
    return bool(_GROUNDING_INFERRED_RE.search(match.group(0)))


def _hit_is_inferred(hit: dict) -> bool:
    """Inferred check for a vector-store hit.

    Chunk text has frontmatter stripped by the chunker, so check the hit
    metadata first, then read just the head of the source file (cheap:
    frontmatter lives in the first bytes).
    """
    metadata = hit.get("metadata") or {}
    if isinstance(metadata, dict) and metadata.get("grounding") == "inferred":
        return True
    source = hit.get("source", "") or ""
    if not source:
        return False
    try:
        with open(source, "r", encoding="utf-8", errors="ignore") as fh:
            head = fh.read(2048)
    except OSError:
        return False
    return _frontmatter_marks_inferred(head)


def _build_note_entry(
    raw: str, title: str, path: str, score: float, inferred: bool = False
) -> dict:
    return {
        "title": title,
        "path": path,
        "excerpt": _extract_excerpt(raw),
        "relates": _extract_wikilinks(raw),
        "score": float(score),
        "inferred": inferred,
    }


def _note_from_vector_hit(hit: dict) -> dict:
    source = hit.get("source", "") or ""
    raw = hit.get("text", "") or ""
    title = hit.get("heading") or Path(source).stem or "note"
    score_val = hit.get("score", 0.0) or 0.0
    return _build_note_entry(
        raw, str(title), str(source), float(score_val),
        inferred=_hit_is_inferred(hit),
    )


def _apply_grounding_policy(notes: list[dict], max_notes: int) -> list[dict]:
    """Quarantine inferred notes (Dreaming output) from grounded context.

    Policy (PR-3 v4.1): inferred notes are EXCLUDED by default; they are
    only included — explicitly suffixed `(inferred — not authoritative)`
    by the formatter — when fewer than 2 grounded notes matched.
    """
    grounded = [n for n in notes if not n.get("inferred")]
    if len(grounded) >= 2:
        return grounded[:max_notes]
    inferred = [n for n in notes if n.get("inferred")]
    return (grounded + inferred)[:max_notes]


class KBContextLayer(Layer):
    """L2.5: Obsidian KB context injection before the model thinks.

    Design (see plan ``2026-04-20-intelligence-v2.md``):
      1. Semantic search the user prompt against the vector store.
      2. If store empty or embedder unavailable, fall back to Jaccard
         keyword similarity against cached note titles.
      3. Keep notes with similarity ≥ ``min_similarity`` (default 0.5),
         up to ``max_notes``.
      4. Format as ``[arka:kb-context]`` block with title, path, 2-line
         excerpt, and top 3 wikilinks per note.
      5. Call ``record_obsidian_query`` so research_gate (Task #6) can
         verify KB-first was respected this turn.

    Feature flag: ``synapse.l25KbContext`` in ``~/.arkaos/config.json``
    (default ``true``). ``ARKA_BYPASS_L25=1`` env disables for debugging.
    """

    def __init__(
        self,
        vector_store: Any = None,
        vault_path: Optional[str] = None,
        max_notes: int = 5,
        min_similarity: float = 0.5,
    ) -> None:
        self._store = vector_store
        self._vault_path = Path(vault_path) if vault_path else None
        self._max_notes = max_notes
        self._min_similarity = min_similarity

    @property
    def id(self) -> str:
        return "L2.5"

    @property
    def name(self) -> str:
        return "KBContext"

    @property
    def input_sensitive(self) -> bool:
        return True

    @property
    def cache_ttl(self) -> int:
        return 0

    @property
    def priority(self) -> int:
        return 25

    def _empty(self, start: float) -> LayerResult:
        ms = int((time.time() - start) * 1000)
        return LayerResult(
            layer_id=self.id, tag="", content="", tokens_est=0, compute_ms=ms, cached=False
        )

    def _session_id(self, ctx: PromptContext) -> str:
        return ctx.extra.get("session_id", "") if ctx.extra else ""

    def _record(self, ctx: PromptContext, hit_count: int) -> None:
        session_id = self._session_id(ctx)
        if not session_id:
            return
        try:
            from core.synapse.kb_cache import record_obsidian_query

            record_obsidian_query(session_id, ctx.user_input, hit_count)
        except Exception:
            pass

    def _retrieve(self, prompt: str) -> tuple[list[dict], bool]:
        """Return (notes, degraded). Degraded = keyword-only retrieval.

        Degraded hits carry no similarity score, so the min_similarity
        threshold does not apply to them — they are included but labeled
        (never presented as semantic matches).
        """
        hits = _vector_search(self._store, prompt, top_k=self._max_notes * 2)
        degraded = any(h.get("retrieval") == "keyword-degraded" for h in hits)
        notes: list[dict] = []
        for h in hits:
            if not degraded:
                score = float(h.get("score", 0.0) or 0.0)
                if score < self._min_similarity:
                    continue
            notes.append(_note_from_vector_hit(h))
        notes = _apply_grounding_policy(notes, self._max_notes)
        if notes:
            return notes, degraded
        candidates = _load_fallback_notes(self._vault_path)
        if not candidates:
            return [], False
        picked = _jaccard_fallback(
            prompt, candidates, self._max_notes * 2, self._min_similarity
        )
        fallback_notes = [
            _build_note_entry(
                n["raw"], n["title"], n["path"], 0.0,
                inferred=_frontmatter_marks_inferred(n["raw"]),
            )
            for n in picked
        ]
        return _apply_grounding_policy(fallback_notes, self._max_notes), False

    def build(self, prompt: str) -> Optional[str]:
        """Public entrypoint — returns the formatted block or None."""
        if not prompt or not _l25_feature_flag_on():
            return None
        notes, degraded = self._retrieve(prompt[:2000])
        if not notes:
            return None
        return _format_kb_block(notes[: self._max_notes], degraded=degraded)

    def compute(self, ctx: PromptContext) -> LayerResult:
        start = time.time()
        if not ctx.user_input or not _l25_feature_flag_on():
            return self._empty(start)
        try:
            notes, degraded = self._retrieve(ctx.user_input[:2000])
        except Exception:
            return self._empty(start)
        self._record(ctx, len(notes))
        if not notes:
            return self._empty(start)
        block = _format_kb_block(notes[: self._max_notes], degraded=degraded)
        ms = int((time.time() - start) * 1000)
        tag = f"[kb-context:{len(notes)}]"
        if degraded:
            tag = f"[kb-context:{len(notes)} degraded=keyword]"
        return LayerResult(
            layer_id=self.id,
            tag=tag,
            content=block,
            tokens_est=len(block.split()),
            compute_ms=ms,
            cached=False,
        )
