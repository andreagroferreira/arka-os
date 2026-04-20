"""External research gate — nudges toward Obsidian-first, denies on repeat.

Intercepts calls to Context7, WebSearch, WebFetch and Firecrawl MCP tools.
Runs AFTER flow_enforcer in the PreToolUse hook chain. Independent gate:
both must pass. Feature-flagged behind `hooks.kbFirst` (default false).

Behaviour contract (plan 2026-04-20-intelligence-v2, §Épico B):
    1. Tool not in RESEARCH_EXTERNAL_TOOLS   → allow.
    2. `hooks.kbFirst` flag off              → allow.
    3. `ARKA_BYPASS_KB_FIRST=1` env var      → allow + audit.
    4. Obsidian was consulted this turn      → allow.
    5. First violation in current turn       → allow with nudge.
    6. Second violation in current turn      → deny.

Nudge tone is European Portuguese, natural — not aggressive. The gate is
a safety net; the primary KB-first mechanism is the Synapse L2.5 context
injection. See core/synapse/kb_cache.py for the obsidian-query marker.
"""

from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from core.shared import safe_session_id as _safe_session_id_module
from core.synapse import kb_cache

try:
    import fcntl
    _HAS_FLOCK = True
except ImportError:
    _HAS_FLOCK = False


RESEARCH_EXTERNAL_TOOLS: frozenset[str] = frozenset({
    "mcp__context7__query-docs",
    "mcp__context7__resolve-library-id",
    "WebSearch",
    "WebFetch",
    "mcp__firecrawl__firecrawl_search",
    "mcp__firecrawl__firecrawl_scrape",
    "mcp__firecrawl__firecrawl_crawl",
    "mcp__firecrawl__firecrawl_map",
    "mcp__firecrawl__firecrawl_extract",
})

# Re-export for backward compatibility with any external importers.
SAFE_SESSION_ID_RE = _safe_session_id_module.SAFE_SESSION_ID_RE
CONFIG_PATH = Path.home() / ".arkaos" / "config.json"
BYPASS_AUDIT_PATH = Path.home() / ".arkaos" / "audit" / "kb_first_bypass.log"
TELEMETRY_PATH = Path.home() / ".arkaos" / "telemetry" / "kb_first.jsonl"
VIOLATION_DIR = Path("/tmp/arkaos-kb-violation")


def _violation_dir() -> Path:
    override = os.environ.get("ARKA_KB_VIOLATION_DIR", "").strip()
    if override:
        return Path(override)
    return VIOLATION_DIR

_NUDGE_TOP_N = 3
_NOTE_TITLE_STOP = {
    "a", "o", "e", "de", "da", "do", "em", "para", "com", "um", "uma",
    "the", "and", "or", "of", "to", "for", "in", "on", "by",
}


@dataclass
class Decision:
    """Outcome of research-gate evaluation for a single tool call."""

    allow: bool
    reason: str
    nudge: bool = False
    bypass_used: bool = False
    kb_hits_hint: list[str] = field(default_factory=list)
    stderr_msg: str = ""

    def to_stderr_message(self) -> str:
        return self.stderr_msg


@contextmanager
def _locked_append(path: Path):
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


_safe_session_id = _safe_session_id_module.safe_session_id


def _feature_flag_on() -> bool:
    if not CONFIG_PATH.exists():
        return False
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return bool(data.get("hooks", {}).get("kbFirst", False))


def _bypass_env_active() -> bool:
    return os.environ.get("ARKA_BYPASS_KB_FIRST", "").strip() == "1"


def _audit_bypass(session_id: str, tool: str) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "tool": tool,
        "reason": os.environ.get("ARKA_BYPASS_KB_FIRST_REASON", ""),
    }
    with _locked_append(BYPASS_AUDIT_PATH) as fh:
        fh.write(json.dumps(entry) + "\n")


def record_telemetry(session_id: str, tool: str, decision: Decision) -> None:
    """Append a structured record to the KB-first telemetry log."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "tool": tool,
        **asdict(decision),
    }
    with _locked_append(TELEMETRY_PATH) as fh:
        fh.write(json.dumps(entry) + "\n")


def _violation_path(session_id: str) -> Path | None:
    safe = _safe_session_id(session_id)
    if safe is None:
        return None
    return _violation_dir() / safe


def _has_prior_violation(session_id: str) -> bool:
    path = _violation_path(session_id)
    return path is not None and path.exists()


def _mark_violation(session_id: str, tool: str) -> None:
    path = _violation_path(session_id)
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = json.dumps({"tool": tool, "ts": datetime.now(timezone.utc).isoformat()})
    # Race contract: two concurrent tool calls on the same session may
    # both observe "no prior violation" and both emit the first-violation
    # nudge. This is intentional — a nudge is cheap and both calls were
    # genuinely first-ish. Deny is reserved for the SECOND violation
    # after the first marker is on disk, which is what a plain
    # ``write_text`` (non-exclusive, last-writer-wins) gives us. Tested
    # by ``test_concurrent_violation_markers_race_safe``.
    try:
        path.write_text(entry, encoding="utf-8")
    except OSError:
        pass


def invalidate_violation(session_id: str) -> None:
    """Clear the per-turn violation marker. Called by UserPromptSubmit."""
    path = _violation_path(session_id)
    if path is None:
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _resolve_vault_path() -> Path | None:
    env_vault = os.environ.get("ARKAOS_VAULT", "").strip()
    if env_vault and Path(env_vault).exists():
        return Path(env_vault)
    config = Path.home() / "Documents" / "Personal"
    if config.exists():
        return config
    return None


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[A-Za-zÀ-ÿ0-9]{3,}", text.lower())
    return {w for w in words if w not in _NOTE_TITLE_STOP}


def _score_note(query_tokens: set[str], note_path: Path) -> int:
    name_tokens = _tokenize(note_path.stem)
    return len(query_tokens & name_tokens)


def _search_vault_titles(query: str, vault: Path, top_n: int) -> list[str]:
    tokens = _tokenize(query)
    if not tokens:
        return []
    ranked: list[tuple[int, float, str]] = []
    try:
        iterator = vault.rglob("*.md")
    except OSError:
        return []
    for note in iterator:
        try:
            score = _score_note(tokens, note)
        except OSError:
            continue
        if score <= 0:
            continue
        ranked.append((score, -note.stat().st_mtime, note.stem))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    return [stem for _, _, stem in ranked[:top_n]]


def _build_nudge(query: str, tool_name: str, vault: Path | None) -> tuple[str, list[str]]:
    titles = _search_vault_titles(query, vault, _NUDGE_TOP_N) if vault else []
    if titles:
        bullets = "\n".join(f"  - [[{t}]]" for t in titles)
        body = (
            f"[arka:kb-nudge] O teu cérebro (Obsidian) tem possíveis notas relevantes:\n"
            f"{bullets}\n\n"
            f"Consulta-as via `mcp__obsidian__search_notes` antes de ir a {tool_name}. "
            f"Se tiverem lacuna, segue externamente e documenta de volta."
        )
    else:
        body = (
            f"[arka:kb-nudge] Antes de ir a {tool_name}, corre primeiro "
            f"`mcp__obsidian__search_notes` — pode não haver nota ainda, e nesse "
            f"caso documenta de volta depois da consulta externa."
        )
    return body, titles


def _build_deny_message(titles: list[str], tool_name: str) -> str:
    if titles:
        bullets = ", ".join(f"[[{t}]]" for t in titles)
        return (
            f"[ARKA:KB-FIRST] O teu cérebro tem {bullets}. "
            f"Consulta primeiro via `mcp__obsidian__search_notes` antes de {tool_name}."
        )
    return (
        f"[ARKA:KB-FIRST] Consulta primeiro `mcp__obsidian__search_notes` "
        f"antes de chamar {tool_name}. Se não houver nota, documenta depois."
    )


def _early_allow(tool_name: str, session_id: str) -> Decision | None:
    if tool_name not in RESEARCH_EXTERNAL_TOOLS:
        return Decision(allow=True, reason="tool-not-gated")
    if not _feature_flag_on():
        return Decision(allow=True, reason="feature-flag-off")
    if _bypass_env_active():
        _audit_bypass(session_id, tool_name)
        return Decision(allow=True, reason="env-bypass", bypass_used=True)
    if kb_cache.obsidian_queried_this_turn(session_id):
        return Decision(allow=True, reason="kb-consulted")
    return None


def evaluate_research_gate(
    tool_name: str,
    session_id: str = "",
    query: str = "",
) -> Decision:
    """Decide whether an external research tool call may proceed."""
    early = _early_allow(tool_name, session_id)
    if early is not None:
        return early

    vault = _resolve_vault_path()
    nudge_msg, titles = _build_nudge(query, tool_name, vault)

    if _has_prior_violation(session_id):
        return Decision(
            allow=False,
            reason="kb-first-required",
            kb_hits_hint=titles,
            stderr_msg=_build_deny_message(titles, tool_name),
        )

    _mark_violation(session_id, tool_name)
    return Decision(
        allow=True,
        reason="first-violation-nudge",
        nudge=True,
        kb_hits_hint=titles,
        stderr_msg=nudge_msg,
    )
