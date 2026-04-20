"""Auto-documentor — extracts session learnings and writes to Obsidian.

Parses the Claude Code transcript JSONL after Quality Gate approval,
synthesises learnings about external sources consulted, decisions made,
and deliverables produced, then invokes the Obsidian cataloger + relator
(Task #4 modules) to file structured, wikilinked notes into the vault.

The synthesis step is runtime- and model-agnostic: it delegates to the
active `LLMProvider` (see `core.runtime.llm_provider`). This module
NEVER picks a model — the provider / runtime / env does. When no
provider is available or the call fails, it falls through to a
deterministic template synthesiser that preserves every extracted fact.

ADR/Plan references:
- ~/.arkaos/plans/2026-04-20-intelligence-v2.md (Task #7 — Épico B)
- ~/.arkaos/plans/2026-04-20-llm-agnostic.md (Task #12/#13 — LLMProvider)
- core/obsidian/cataloger.py, core/obsidian/relator.py (Task #4)
"""

from __future__ import annotations

import json
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from core.obsidian import cataloger as _cataloger
from core.obsidian import relator as _relator
from core.obsidian.writer import ObsidianWriter
from core.shared import safe_session_id as _safe_session_id_module

try:
    import fcntl  # POSIX only
    _HAS_FLOCK = True
except ImportError:
    _HAS_FLOCK = False


# Re-export for backward compatibility with any external importers.
SAFE_SESSION_ID_RE = _safe_session_id_module.SAFE_SESSION_ID_RE

AUTO_DOC_TELEMETRY_PATH = Path.home() / ".arkaos" / "telemetry" / "auto_doc.jsonl"

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

_AUTO_DOC_SUFFIX = "Auto-documented by ArkaOS"
_LLM_MAX_TOKENS = 1500

_SYSTEM_PROMPT = (
    "You are ArkaOS's auto-documentor. Produce a concise knowledge note "
    "(150-300 words) summarising the session. Structure: short intro, "
    "then markdown sections for Key Facts, Decisions, and Sources. "
    "Preserve every URL and file path verbatim. Use Obsidian wikilinks "
    "([[Topic]]) for reusable concepts. Do not include preamble, sign-off, "
    "or meta commentary about the model or prompt. Output only markdown."
)


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


# ─── Synthesis ─────────────────────────────────────────────────────────


def synthesize(learning: Learning) -> str:
    """Produce a markdown body for the learning.

    Delegates to the active `LLMProvider` via `_call_llm`. If the
    provider is unavailable, returns empty text, or raises, falls
    through to a deterministic template that preserves every extracted
    fact. No model name ever crosses this boundary.
    """
    llm_out = _call_llm(learning)
    if llm_out:
        return llm_out
    return _template_synthesize(learning)


def _call_llm(learning: Learning) -> str:
    from core.runtime import get_llm_provider
    from core.runtime.llm_provider import LLMUnavailable

    try:
        provider = get_llm_provider()
        if not provider.is_available():
            return ""
        prompt = _build_synthesis_prompt(learning)
        response = provider.complete(
            prompt, max_tokens=_LLM_MAX_TOKENS, system=_SYSTEM_PROMPT
        )
        return response.text.strip()
    except LLMUnavailable:
        return ""
    except Exception:  # noqa: BLE001 — LLM path must never crash the doc job
        return ""


def _build_synthesis_prompt(learning: Learning) -> str:
    lines = [f"Topic: {learning.topic}", ""]
    if learning.content.strip():
        lines.append("Session blob:")
        lines.append(learning.content.strip())
        lines.append("")
    if learning.sources:
        lines.append("Sources consulted:")
        for src in learning.sources[:20]:
            lines.append(f"- {src}")
        lines.append("")
    if learning.decisions:
        lines.append("Decisions recorded:")
        for dec in learning.decisions[:10]:
            lines.append(f"- {dec}")
        lines.append("")
    if learning.metadata:
        meta_pairs = sorted(learning.metadata.items())
        lines.append("Metadata:")
        for key, value in meta_pairs:
            lines.append(f"- {key}: {value}")
        lines.append("")
    lines.append(
        "Write the note now. Obey the system prompt. Output only markdown."
    )
    return "\n".join(lines)


def _extract_key_facts(learning: Learning, limit: int = 5) -> list[str]:
    """Pull 3-5 bullet candidates from the learning content.

    Used by the template fallback so both the LLM and template paths
    produce a ``## Key Facts`` section in the same order as
    ``_SYSTEM_PROMPT`` requires.
    """
    text = (learning.content or "").strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    bullets: list[str] = []
    for para in paragraphs:
        for raw in para.splitlines():
            line = raw.strip().lstrip("-*• ").strip()
            # Skip markdown section headings; they aren't facts.
            if not line or line.startswith("#"):
                continue
            if line.startswith(">") or line.startswith("`"):
                continue
            if len(line) < 8:
                continue
            bullets.append(line[:240])
            if len(bullets) >= limit:
                return bullets
        if len(bullets) >= limit:
            break
    return bullets


def _template_synthesize(learning: Learning) -> str:
    # Section order mirrors _SYSTEM_PROMPT: Key Facts → Decisions →
    # Sources. Keeping both synthesis paths aligned means downstream
    # consumers (MOC generation, relator) never branch on provider.
    parts: list[str] = [f"# {learning.topic}", ""]
    parts.append(f"> {_AUTO_DOC_SUFFIX}.")
    parts.append("")
    if learning.content.strip():
        parts.append(learning.content.strip())
        parts.append("")
    key_facts = _extract_key_facts(learning)
    if key_facts:
        parts.append("## Key Facts")
        parts.append("")
        for fact in key_facts:
            parts.append(f"- {fact}")
        parts.append("")
    if learning.decisions:
        parts.append("## Decisions")
        parts.append("")
        for dec in learning.decisions[:10]:
            parts.append(f"- {dec}")
        parts.append("")
    if learning.sources:
        parts.append("## Sources")
        parts.append("")
        for src in learning.sources[:20]:
            parts.append(f"- {src}")
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
) -> Path | None:
    body = synthesize(learning)
    meta = dict(learning.metadata)
    meta.setdefault("title", learning.topic[:80])
    meta.setdefault("session", session_id)
    meta.setdefault("auto_documented", True)
    try:
        plan = _cataloger.plan(body, meta)
    except ValueError as exc:
        _log_auto_doc_event(
            session_id=session_id,
            event="classification-failed",
            topic=learning.topic,
            reason=str(exc),
        )
        return None
    if plan is None:
        _log_auto_doc_event(
            session_id=session_id,
            event="succeeded-empty",
            topic=learning.topic,
            reason="cataloger returned no plan",
        )
        return None
    note_path = _cataloger.execute(plan, body, writer)
    _relate_note(note_path, body, vault_path, plan)
    _log_auto_doc_event(
        session_id=session_id,
        event="succeeded-wrote-note",
        topic=learning.topic,
        reason=str(note_path),
    )
    return note_path


@contextmanager
def _locked_append(path: Path):
    """Append to ``path`` under an exclusive advisory lock (POSIX flock).

    Mirrors the pattern in ``core/workflow/flow_enforcer._locked_append``
    — see that module for the platform-fallback rationale.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = path.open("a", encoding="utf-8")
    try:
        if _HAS_FLOCK:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        yield fh
    finally:
        if _HAS_FLOCK:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        fh.close()


def _log_auto_doc_event(
    *,
    session_id: str,
    event: str,
    topic: str,
    reason: str,
) -> None:
    """Append a structured auto-doc telemetry entry, degrade silently."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "event": event,
        "topic": topic[:120],
        "reason": reason[:240],
    }
    try:
        with _locked_append(AUTO_DOC_TELEMETRY_PATH) as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        # Telemetry failures must never break the doc job.
        return


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
    return _safe_session_id_module.safe_session_id(session_id) is not None
