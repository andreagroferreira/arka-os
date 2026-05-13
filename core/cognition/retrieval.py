"""Hooks-as-retrieval prototype for the ArkaOS Cognitive Layer.

After each tool call, the PostToolUse hook calls into this module to
extract likely entities from the tool output, find relevant notes in the
Obsidian vault, and write a small JSON cache that the UserPromptSubmit
hook injects into the next turn as an ``[arka:context]`` advisory.

This is the prototype unblocked by Claude Code 2.1.122 (late-binding
``ToolSearch`` + hook-block isolation, see KB note
2026-04-29-claude-code-2-1-122-and-2-1-123). It uses filesystem grep
(ripgrep when available, Python fallback otherwise) instead of running
a separate MCP server with embeddings — a deliberate "smallest thing
that could possibly work" choice per the 2026-05-13 Conclave ADR.

Performance budget: ≤ 800 ms p95 per ``capture_context`` call. The
PostToolUse hook enforces this with a hard timeout; the function itself
caps entities (20), vault hits (5), and ripgrep wall time (1 s).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from core.runtime.user_paths import user_data_root

_CACHE_DIRNAME = "context-cache"
_DEFAULT_TTL_SECONDS = 600
_MAX_ENTITIES = 20
_MAX_VAULT_HITS = 5
_RIPGREP_TIMEOUT_S = 1.0
_PY_FALLBACK_MAX_FILES = 500

# Common-word stoplist — kept tiny on purpose; we want to capture short
# domain terms like "auth" or "DSL" but cut out the highest-frequency
# English filler tokens that dominate any tool output.
_STOPLIST = frozenset(
    {
        "The", "And", "But", "For", "Not", "With", "From", "This", "That",
        "When", "Where", "Then", "Else", "True", "False", "None", "Null",
        "Error", "Warning", "Info", "Debug", "Trace", "Yes", "No", "Run",
        "Read", "Write", "Edit", "Delete", "Show", "Find", "List",
    }
)

_FILE_PATH = re.compile(r"(?:^|\s)((?:[\w.-]+/)+[\w.-]+\.[a-zA-Z]{1,6})")
_CAMEL_OR_PASCAL = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b")
_AT_MENTION = re.compile(r"@([\w./_-]+)")
_PROPER_NOUN = re.compile(r"\b([A-Z][a-zA-Z]{2,})\b")


@dataclass
class ContextHit:
    """One vault note that matches one or more extracted entities."""

    entity: str
    vault_path: str
    snippet: str
    score: float = 1.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ContextCache:
    """The JSON payload persisted per session."""

    session_id: str
    captured_at: str
    ttl_seconds: int
    hits: list[ContextHit] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "captured_at": self.captured_at,
            "ttl_seconds": self.ttl_seconds,
            "hits": [h.to_dict() for h in self.hits],
        }


def extract_entities(text: str) -> list[str]:
    """Pull file paths, identifiers, and proper nouns out of *text*.

    Returns a deduplicated, capped list ready for vault search. Cheap
    enough to call on every PostToolUse invocation.
    """
    if not text:
        return []
    seen: set[str] = set()
    out: list[str] = []

    def push(tok: str) -> None:
        tok = tok.strip(" .,;:!?\"'()[]{}")
        if not tok or tok in _STOPLIST or tok in seen:
            return
        if tok.isdigit():
            return
        seen.add(tok)
        out.append(tok)
        return

    for m in _FILE_PATH.finditer(text):
        push(m.group(1))
    for m in _AT_MENTION.finditer(text):
        push(m.group(1))
    for m in _CAMEL_OR_PASCAL.finditer(text):
        push(m.group(1))
    for m in _PROPER_NOUN.finditer(text):
        if len(out) >= _MAX_ENTITIES:
            break
        push(m.group(1))
    return out[:_MAX_ENTITIES]


def search_vault(entities: list[str], vault_path: str) -> list[ContextHit]:
    """Find Obsidian notes that mention any of the extracted entities.

    Uses ripgrep when available (sub-second across thousands of notes),
    falls back to a pure-Python scan capped at ``_PY_FALLBACK_MAX_FILES``
    files so the hook timeout stays safe on Windows or minimal Linux
    installs without ripgrep.
    """
    vault = Path(vault_path).expanduser()
    if not entities or not vault.is_dir():
        return []
    if _ripgrep_available():
        hits = _search_ripgrep(entities, vault)
    else:
        hits = _search_python(entities, vault)
    return hits[:_MAX_VAULT_HITS]


def capture_context(
    session_id: str,
    tool_output: str,
    vault_path: str,
    cache_dir: Path | None = None,
) -> ContextCache:
    """Run extract + search and persist the cache. Returns the cache.

    Idempotent across overlapping calls in the same second: a second
    invocation overwrites the first. Empty hits still produce a file
    so the UserPromptSubmit reader sees a fresh ``captured_at`` and
    doesn't mistake a quiet turn for stale data.
    """
    entities = extract_entities(tool_output)
    hits = search_vault(entities, vault_path) if entities else []
    cache = ContextCache(
        session_id=session_id,
        captured_at=datetime.now(timezone.utc).isoformat(),
        ttl_seconds=_DEFAULT_TTL_SECONDS,
        hits=hits,
    )
    _write_cache(cache, cache_dir or _default_cache_dir())
    return cache


def read_context(
    session_id: str,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    cache_dir: Path | None = None,
) -> list[ContextHit]:
    """Read cached hits for *session_id* if still within TTL."""
    path = (cache_dir or _default_cache_dir()) / f"{session_id}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    captured = data.get("captured_at", "")
    if not _within_ttl(captured, ttl_seconds):
        return []
    return [ContextHit(**h) for h in data.get("hits", [])]


def format_advisory(hits: list[ContextHit], max_chars: int = 1200) -> str:
    """Render hits into a compact `[arka:context]` advisory string."""
    if not hits:
        return ""
    lines = ["[arka:context] KB matches from last turn:"]
    for h in hits:
        line = f"- {h.entity} → {h.vault_path}: {h.snippet[:160]}"
        if sum(len(l) for l in lines) + len(line) > max_chars:
            break
        lines.append(line)
    return "\n".join(lines)


def _default_cache_dir() -> Path:
    return user_data_root() / _CACHE_DIRNAME


def _write_cache(cache: ContextCache, cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{cache.session_id}.json"
    tmp = cache_dir / f"{cache.session_id}.json.tmp"
    tmp.write_text(json.dumps(cache.to_dict(), indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _within_ttl(captured_iso: str, ttl_seconds: int) -> bool:
    try:
        captured = datetime.fromisoformat(captured_iso)
    except ValueError:
        return False
    now = datetime.now(timezone.utc)
    if captured.tzinfo is None:
        captured = captured.replace(tzinfo=timezone.utc)
    return (now - captured).total_seconds() <= ttl_seconds


def _ripgrep_available() -> bool:
    try:
        subprocess.run(
            ["rg", "--version"], check=True, capture_output=True, timeout=1.0
        )
        return True
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


def _search_ripgrep(entities: list[str], vault: Path) -> list[ContextHit]:
    pattern = "|".join(re.escape(e) for e in entities)
    cmd = [
        "rg", "--json", "--max-count", "1", "--smart-case",
        "-tmd", "-e", pattern, str(vault),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=_RIPGREP_TIMEOUT_S
        )
    except subprocess.SubprocessError:
        return []
    return _parse_ripgrep_json(result.stdout, vault, entities)


def _parse_ripgrep_json(stdout: str, vault: Path, entities: list[str]) -> list[ContextHit]:
    hits: list[ContextHit] = []
    seen: set[str] = set()
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "match":
            continue
        data = event.get("data", {})
        path = data.get("path", {}).get("text", "")
        if not path or path in seen:
            continue
        seen.add(path)
        text = data.get("lines", {}).get("text", "").strip()
        matched_entity = _pick_matched_entity(text, entities)
        rel = _relative_to_vault(path, vault)
        hits.append(ContextHit(entity=matched_entity, vault_path=rel, snippet=text))
    return hits


def _search_python(entities: list[str], vault: Path) -> list[ContextHit]:
    pattern = re.compile("|".join(re.escape(e) for e in entities), re.IGNORECASE)
    files = list(vault.rglob("*.md"))[:_PY_FALLBACK_MAX_FILES]
    hits: list[ContextHit] = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        match = pattern.search(text)
        if not match:
            continue
        snippet_start = max(0, match.start() - 40)
        snippet_end = min(len(text), match.end() + 80)
        snippet = text[snippet_start:snippet_end].replace("\n", " ").strip()
        hits.append(
            ContextHit(
                entity=match.group(0),
                vault_path=str(f.relative_to(vault)),
                snippet=snippet,
            )
        )
        if len(hits) >= _MAX_VAULT_HITS:
            break
    return hits


def _pick_matched_entity(text: str, entities: list[str]) -> str:
    lower = text.lower()
    for e in entities:
        if e.lower() in lower:
            return e
    return entities[0] if entities else ""


def _relative_to_vault(absolute: str, vault: Path) -> str:
    try:
        return str(Path(absolute).relative_to(vault))
    except ValueError:
        return absolute


def _vault_path_or_none() -> str | None:
    """Resolve the configured vault path or return None when missing.

    Hooks call this; they must never crash because profile.json is absent.
    """
    try:
        from core.runtime.path_resolver import load_profile
        return load_profile().vault_path
    except Exception:
        return None


def _cli_capture(argv: list[str]) -> int:
    """Stdin → capture_context. Used by the PostToolUse hook."""
    import sys
    if len(argv) < 2:
        return 2
    session_id = argv[1]
    vault = _vault_path_or_none()
    if not vault:
        return 0  # silent skip when no profile
    tool_output = sys.stdin.read()
    capture_context(session_id, tool_output, vault)
    return 0


def _cli_inject(argv: list[str]) -> int:
    """Print advisory for *session_id*. Used by the UserPromptSubmit hook."""
    if len(argv) < 2:
        return 2
    session_id = argv[1]
    advisory = format_advisory(read_context(session_id))
    if advisory:
        print(advisory)
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        return 2
    cmd = argv[1]
    if cmd == "capture":
        return _cli_capture(argv[1:])
    if cmd == "inject":
        return _cli_inject(argv[1:])
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
