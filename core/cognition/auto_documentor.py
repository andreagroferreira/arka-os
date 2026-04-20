"""Auto-documentor — extracts session learnings and writes to Obsidian.

Parses the Claude Code transcript JSONL after Quality Gate approval,
synthesises learnings about external sources consulted, decisions made,
and deliverables produced, then invokes the Obsidian cataloger + relator
(Task #4 modules) to file structured, wikilinked notes into the vault.

Model routing is dynamic: a complexity heuristic over the learning
content chooses haiku / sonnet / opus. Nothing is hardcoded per task
type. The actual LLM call is abstracted behind `_call_llm` and falls
back to a deterministic template when no SDK is wired — this keeps the
module testable and unblocks the SDK integration as a follow-up.

ADR/Plan references:
- ~/.arkaos/plans/2026-04-20-intelligence-v2.md (Task #7 — Épico B)
- core/obsidian/cataloger.py, core/obsidian/relator.py (Task #4)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, Optional

from core.obsidian import cataloger as _cataloger
from core.obsidian import relator as _relator
from core.obsidian.writer import ObsidianWriter


SAFE_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

_ARCHITECTURAL_KEYWORDS = (
    "architecture", "adr", "decision", "trade-off", "tradeoff",
    "design pattern", "refactor", "migration", "schema", "bounded context",
)
_ANALYSIS_KEYWORDS = (
    "analysis", "investigation", "compare", "benchmark", "evaluate",
    "profile", "review", "audit",
)
_URL_RE = re.compile(r"https?://[^\s\)\]\"']+")
_FILE_PATH_RE = re.compile(r"(?:^|[\s`'])(/[A-Za-z0-9_./\-]+\.[A-Za-z0-9]+)")
_ROUTING_MARKER_RE = re.compile(
    r"\[arka:routing\]\s*([\w-]+)\s*->\s*(\w+)", re.IGNORECASE
)
_DECISION_CUES = (
    "decided to", "chose ", "selected ", "going with", "i'll use",
    "we'll use", "opted for", "the approach is", "rationale:",
)
_EXTERNAL_RESEARCH_TOOLS = frozenset({
    "WebFetch", "WebSearch",
    "mcp__context7__query-docs", "mcp__context7__resolve-library-id",
    "mcp__firecrawl__firecrawl_search",
    "mcp__firecrawl__firecrawl_scrape",
    "mcp__firecrawl__firecrawl_crawl",
    "mcp__firecrawl__firecrawl_extract",
})

_HAIKU_MAX_CHARS = 600
_OPUS_MIN_CHARS = 4000


@dataclass
class Learning:
    """One synthesisable learning extracted from a session transcript."""

    topic: str
    content: str
    sources: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    decisions: list[str] = field(default_factory=list)


# ─── Extraction ────────────────────────────────────────────────────────


def extract_learnings(transcript_path: Path) -> list[Learning]:
    """Parse a transcript and return structured Learning records."""
    records = _load_transcript(transcript_path)
    if not records:
        return []
    sources = _extract_sources(records)
    decisions = _extract_decisions(records)
    deliverables = _extract_deliverables(records)
    content = _build_content_blob(records, decisions, deliverables)
    if not content.strip() and not sources and not decisions:
        return []
    metadata = _detect_metadata(content, records)
    topic = _derive_topic(records, metadata)
    return [Learning(
        topic=topic,
        content=content,
        sources=sources,
        metadata=metadata,
        decisions=decisions,
    )]


def _load_transcript(path: Path) -> list[dict]:
    if path is None or not path.exists():
        return []
    out: list[dict] = []
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _iter_content_items(record: dict) -> Iterable[dict]:
    content = record.get("content")
    if content is None:
        content = record.get("message", {}).get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                yield item
    elif isinstance(content, str):
        yield {"type": "text", "text": content}


def _role_of(record: dict) -> str:
    return record.get("role") or record.get("message", {}).get("role") or ""


def _text_of(record: dict) -> str:
    parts: list[str] = []
    for item in _iter_content_items(record):
        if "text" in item:
            parts.append(str(item["text"]))
    return "\n".join(parts)


def _extract_sources(records: list[dict]) -> list[str]:
    seen: set[str] = set()
    sources: list[str] = []
    for rec in records:
        for item in _iter_content_items(rec):
            if item.get("type") == "tool_use":
                _collect_tool_use_sources(item, sources, seen)
        text = _text_of(rec)
        for url in _URL_RE.findall(text):
            if url not in seen:
                seen.add(url)
                sources.append(url)
    return sources


def _collect_tool_use_sources(item: dict, sources: list[str], seen: set) -> None:
    tool = item.get("name", "")
    if tool not in _EXTERNAL_RESEARCH_TOOLS:
        return
    params = item.get("input") or {}
    for key in ("url", "query", "libraryName", "topic"):
        val = params.get(key)
        if isinstance(val, str) and val and val not in seen:
            seen.add(val)
            sources.append(val)


def _extract_decisions(records: list[dict]) -> list[str]:
    decisions: list[str] = []
    for rec in records:
        if _role_of(rec) != "assistant":
            continue
        text = _text_of(rec)
        for match in _ROUTING_MARKER_RE.finditer(text):
            decisions.append(f"routed: {match.group(1)} -> {match.group(2)}")
        for line in text.splitlines():
            low = line.lower().strip()
            if any(cue in low for cue in _DECISION_CUES) and len(line) < 400:
                decisions.append(line.strip())
    return _dedupe_keep_order(decisions)


def _extract_deliverables(records: list[dict]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for rec in records:
        for item in _iter_content_items(rec):
            if item.get("type") != "tool_use":
                continue
            if item.get("name") not in ("Write", "Edit", "MultiEdit"):
                continue
            path = (item.get("input") or {}).get("file_path", "")
            if path and path not in seen:
                seen.add(path)
                out.append(path)
    return out


def _build_content_blob(
    records: list[dict], decisions: list[str], deliverables: list[str]
) -> str:
    user_prompts = [
        _text_of(r) for r in records if _role_of(r) == "user"
    ]
    assistant_finals = [
        _text_of(r) for r in records if _role_of(r) == "assistant"
    ][-3:]
    sections: list[str] = []
    if user_prompts:
        sections.append("## Request\n\n" + user_prompts[0].strip()[:800])
    if decisions:
        sections.append("## Decisions\n\n" + "\n".join(f"- {d}" for d in decisions[:10]))
    if deliverables:
        sections.append("## Deliverables\n\n" + "\n".join(f"- `{p}`" for p in deliverables[:20]))
    if assistant_finals:
        sections.append("## Summary\n\n" + assistant_finals[-1].strip()[:1200])
    return "\n\n".join(sections)


def _detect_metadata(content: str, records: list[dict]) -> dict:
    low = content.lower()
    meta: dict = {"source": "session-transcript"}
    for rec in records:
        if _role_of(rec) != "assistant":
            continue
        text = _text_of(rec)
        for match in _ROUTING_MARKER_RE.finditer(text):
            meta["dept"] = match.group(1).lower()
            meta["agent"] = match.group(2).lower()
            break
        if "dept" in meta:
            break
    if "laravel" in low or "php" in low:
        meta["stack"] = "Laravel"
    elif "nuxt" in low or "vue" in low:
        meta["stack"] = "Vue"
    elif "next.js" in low or "react" in low:
        meta["stack"] = "React"
    elif "python" in low or "pydantic" in low:
        meta["stack"] = "Python"
    return meta


def _derive_topic(records: list[dict], metadata: dict) -> str:
    for rec in records:
        if _role_of(rec) != "user":
            continue
        text = _text_of(rec).strip()
        if text:
            first_line = text.splitlines()[0][:120]
            return first_line or "Session Learning"
    return metadata.get("dept", "Session Learning").title()


def _dedupe_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


# ─── Model routing ─────────────────────────────────────────────────────


def choose_model(learning: Learning) -> str:
    """Return 'haiku' | 'sonnet' | 'opus' based on content complexity."""
    low = learning.content.lower()
    length = len(learning.content)
    if any(kw in low for kw in _ARCHITECTURAL_KEYWORDS):
        return "opus"
    if length >= _OPUS_MIN_CHARS and len(learning.decisions) >= 3:
        return "opus"
    if length <= _HAIKU_MAX_CHARS and len(learning.decisions) <= 1:
        return "haiku"
    if any(kw in low for kw in _ANALYSIS_KEYWORDS):
        return "sonnet"
    if length >= _HAIKU_MAX_CHARS:
        return "sonnet"
    return "haiku"


# ─── Synthesis ─────────────────────────────────────────────────────────


def synthesize(learning: Learning, model_hint: str) -> str:
    """Produce a markdown body for the learning.

    Calls `_call_llm` when a real LLM integration is wired; otherwise
    falls back to a deterministic template that preserves all extracted
    information. The template path is what ships in Task #7.
    """
    llm_out = _call_llm(learning, model_hint)
    if llm_out:
        return llm_out
    return _template_synthesize(learning, model_hint)


def _call_llm(learning: Learning, model_hint: str) -> str:
    return ""


def _template_synthesize(learning: Learning, model_hint: str) -> str:
    parts = [f"# {learning.topic}", ""]
    parts.append(f"> Auto-documented via ArkaOS ({model_hint}).")
    parts.append("")
    if learning.content.strip():
        parts.append(learning.content.strip())
        parts.append("")
    if learning.sources:
        parts.append("## Sources")
        parts.append("")
        for src in learning.sources[:20]:
            parts.append(f"- {src}")
        parts.append("")
    if learning.decisions:
        parts.append("## Key decisions")
        parts.append("")
        for dec in learning.decisions[:10]:
            parts.append(f"- {dec}")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


# ─── Orchestration ─────────────────────────────────────────────────────


def document_session(
    transcript_path: Path,
    session_id: str,
    vault_path: Path,
    qg_verdict: str,
) -> list[Path]:
    """Run the full pipeline. Returns the paths of every note written."""
    if qg_verdict != "APPROVED":
        return []
    if not _safe_session_id(session_id):
        return []
    transcript_path = Path(transcript_path)
    learnings = extract_learnings(transcript_path)
    if not learnings:
        return []
    writer = ObsidianWriter(vault_path=vault_path)
    written: list[Path] = []
    for learning in learnings:
        note_path = _document_one(learning, writer, vault_path, session_id)
        if note_path:
            written.append(note_path)
    return written


def _document_one(
    learning: Learning,
    writer: ObsidianWriter,
    vault_path: Path,
    session_id: str,
) -> Optional[Path]:
    model_hint = choose_model(learning)
    body = synthesize(learning, model_hint)
    meta = dict(learning.metadata)
    meta.setdefault("title", learning.topic[:80])
    meta.setdefault("session", session_id)
    meta.setdefault("auto_documented", True)
    meta.setdefault("model_hint", model_hint)
    try:
        plan = _cataloger.plan(body, meta)
    except ValueError:
        return None
    note_path = _cataloger.execute(plan, body, writer)
    _relate_note(note_path, body, vault_path, plan)
    return note_path


def _relate_note(note_path: Path, body: str, vault_path: Path, plan) -> None:
    try:
        related = _relator.find_related(
            content=body, vault=vault_path, exclude=note_path
        )
    except Exception:
        return
    if related:
        _append_related_block(note_path, related)
        _relator.update_back_references(note_path, related, note_path.stem)
    if plan.applicable_mocs:
        _relator.update_mocs(note_path.stem, list(plan.applicable_mocs), vault_path)


def _append_related_block(note_path: Path, related) -> None:
    try:
        current = note_path.read_text(encoding="utf-8")
    except OSError:
        return
    block = _relator.generate_wikilinks_block(related)
    if not block or "## Related" in current:
        return
    sep = "" if current.endswith("\n") else "\n"
    try:
        note_path.write_text(current + sep + "\n" + block, encoding="utf-8")
    except OSError:
        return


def _safe_session_id(session_id: str) -> bool:
    if not isinstance(session_id, str) or not session_id:
        return False
    return bool(SAFE_SESSION_ID_RE.match(session_id))
