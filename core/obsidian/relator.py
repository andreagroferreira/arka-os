"""Relator — discovers related notes and wires bidirectional wikilinks.

After the Cataloger writes a new note, the Relator:
1. Finds semantically similar notes in the vault (embedder + vector store,
   with Jaccard keyword fallback when unavailable).
2. Generates a "## Related" markdown block for the new note.
3. Back-references the new note in each related note (idempotent: appends
   to existing Related block if present, otherwise creates it).
4. Updates MOC files with a new bullet under a configurable section.
5. Deduplicates tag lists against the vault-wide tag index.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class RelatedNote:
    path: Path
    title: str
    score: float
    excerpt: str = ""


_RELATED_HEADING = "## Related"
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
    "with", "at", "by", "from", "is", "are", "was", "were", "be", "been",
    "this", "that", "these", "those", "it", "its", "as", "if", "then",
})


def find_related(
    content: str,
    vault: Path,
    top_n: int = 5,
    min_similarity: float = 0.5,
    exclude: Optional[Path] = None,
) -> list[RelatedNote]:
    if not vault.exists():
        return []
    candidates = _collect_notes(vault, exclude)
    if not candidates:
        return []
    scored = _score_candidates(content, candidates)
    filtered = [r for r in scored if r.score >= min_similarity]
    filtered.sort(key=lambda r: r.score, reverse=True)
    return filtered[:top_n]


def _collect_notes(vault: Path, exclude: Optional[Path]) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    exclude_abs = exclude.resolve() if exclude else None
    for md in vault.rglob("*.md"):
        try:
            if exclude_abs and md.resolve() == exclude_abs:
                continue
            text = md.read_text(encoding="utf-8")
            out.append((md, _strip_frontmatter(text)))
        except (OSError, UnicodeDecodeError):
            continue
    return out


def _score_candidates(
    content: str, candidates: list[tuple[Path, str]]
) -> list[RelatedNote]:
    try:
        return _semantic_score(content, candidates)
    except Exception:
        return _keyword_score(content, candidates)


def _semantic_score(
    content: str, candidates: list[tuple[Path, str]]
) -> list[RelatedNote]:
    from core.knowledge.embedder import embed, is_available
    if not is_available():
        return _keyword_score(content, candidates)
    query_emb = embed(content)
    if query_emb is None:
        return _keyword_score(content, candidates)
    results = []
    for path, text in candidates:
        note_emb = embed(text[:2000])
        if note_emb is None:
            continue
        score = _cosine(query_emb, note_emb)
        results.append(RelatedNote(
            path=path, title=_title_from_path(path),
            score=score, excerpt=text[:160],
        ))
    return results


def _keyword_score(
    content: str, candidates: list[tuple[Path, str]]
) -> list[RelatedNote]:
    query_tokens = _tokenize(content)
    if not query_tokens:
        return []
    results = []
    for path, text in candidates:
        note_tokens = _tokenize(text)
        if not note_tokens:
            continue
        score = _jaccard(query_tokens, note_tokens)
        results.append(RelatedNote(
            path=path, title=_title_from_path(path),
            score=score, excerpt=text[:160],
        ))
    return results


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def _strip_frontmatter(text: str) -> str:
    return _FRONTMATTER_RE.sub("", text, count=1)


def _title_from_path(path: Path) -> str:
    return path.stem


def generate_wikilinks_block(related: list[RelatedNote]) -> str:
    if not related:
        return ""
    lines = [_RELATED_HEADING, ""]
    for r in related:
        lines.append(f"- [[{r.title}]] — similarity {r.score:.2f}")
    return "\n".join(lines) + "\n"


def update_back_references(
    new_note_path: Path, related: list[RelatedNote], new_note_title: str
) -> int:
    updated = 0
    for r in related:
        try:
            if _append_backlink(r.path, new_note_title):
                updated += 1
        except (OSError, UnicodeDecodeError):
            continue
    return updated


def _append_backlink(note_path: Path, new_title: str) -> bool:
    if not note_path.exists():
        return False
    text = note_path.read_text(encoding="utf-8")
    link = f"[[{new_title}]]"
    if _RELATED_HEADING in text:
        if link in text:
            return False
        new_text = _insert_into_related(text, link)
    else:
        sep = "\n" if not text.endswith("\n") else ""
        new_text = f"{text}{sep}\n{_RELATED_HEADING}\n\n- {link}\n"
    note_path.write_text(new_text, encoding="utf-8")
    return True


def _insert_into_related(text: str, link: str) -> str:
    idx = text.index(_RELATED_HEADING)
    head = text[:idx]
    tail = text[idx:]
    parts = tail.split("\n", 2)
    heading_line = parts[0]
    rest = parts[2] if len(parts) > 2 else ""
    bullet = f"- {link}"
    new_tail = f"{heading_line}\n\n{bullet}\n{rest}" if rest else f"{heading_line}\n\n{bullet}\n"
    return head + new_tail


def update_mocs(
    new_note_title: str, moc_paths: list[str], vault: Path
) -> int:
    updated = 0
    link = f"[[{new_note_title}]]"
    for moc_rel in moc_paths:
        moc_file = vault / moc_rel
        try:
            if _append_moc_entry(moc_file, link):
                updated += 1
        except (OSError, UnicodeDecodeError):
            continue
    return updated


def _append_moc_entry(moc_file: Path, link: str) -> bool:
    if not moc_file.exists():
        return False
    text = moc_file.read_text(encoding="utf-8")
    if link in text:
        return False
    sep = "\n" if not text.endswith("\n") else ""
    moc_file.write_text(f"{text}{sep}- {link}\n", encoding="utf-8")
    return True


def ensure_tags(tags: Iterable[str], existing: Iterable[str] | None = None) -> list[str]:
    seen: set[str] = set()
    if existing:
        seen.update(t.lower() for t in existing)
    out: list[str] = []
    for tag in tags:
        if not tag:
            continue
        norm = tag.strip()
        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(norm)
    return out
