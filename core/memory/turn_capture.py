"""Detached turn-capture worker (F1-A2 — memory/learning reform).

Enqueued by the Stop hook via ``Popen(start_new_session=True)`` — ALL
embedding/summarisation cost is paid here, off-turn, never on a hook's
hot path. Pipeline per turn:

    transcript tail → summary → sanitize (MANDATORY — recipes precedent:
    no sanitizer config ⇒ text is refused, metadata-only record) →
    importance → embed (multi-backend, provenance declared) → store →
    precompute cross-session semantic neighbours into the session cache
    PRODUCED FOR the F1-A3 retrieval layer (no reader exists in this PR)
    → amortised maintenance (embedding backfill + retention prune).

CLI: ``python3 -m core.memory.turn_capture <session_id> <transcript_path> [cwd]``
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from core.knowledge.embedding_backends import EmbeddingResult, embed
from core.memory.semantic_store import SessionMemoryStore, TurnRecord

_TAIL_BYTES = 262_144  # bounded transcript read
_SUMMARY_CHARS = 600
_CACHE_DIRNAME = "context-cache"
_NEIGHBOUR_K = 3
_BACKFILL_BATCH = 10


def _config_enabled() -> bool:
    """``memory.sessionMemory`` (default True) + env kill-switch."""
    if os.environ.get("ARKA_SESSION_MEMORY", "").strip() == "0":
        return False
    config_path = Path.home() / ".arkaos" / "config.json"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    memory_cfg = data.get("memory") or {}
    return bool(memory_cfg.get("sessionMemory", True))


def _read_tail(transcript_path: str) -> str:
    path = Path(transcript_path)
    if not path.is_file():
        return ""
    size = path.stat().st_size
    with path.open("rb") as fh:
        fh.seek(max(0, size - _TAIL_BYTES))
        return fh.read().decode("utf-8", "replace")


def _last_assistant_text(transcript_path: str, raw: str) -> str:
    try:
        from core.workflow.flow_enforcer import _load_last_assistant_messages
        msgs = _load_last_assistant_messages(transcript_path, 1, raw_text=raw)
        return msgs[-1] if msgs else ""
    except Exception:
        return ""


def _parse_tool_uses(raw: str) -> tuple[list[str], list[str]]:
    """Collect tool names + touched file paths from the transcript tail."""
    tools: list[str] = []
    paths: list[str] = []
    for line in raw.splitlines()[-400:]:
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        content = (entry.get("message") or {}).get("content") or []
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name = str(block.get("name") or "")
            if name and name not in tools:
                tools.append(name)
            file_path = (block.get("input") or {}).get("file_path")
            if isinstance(file_path, str) and file_path not in paths:
                paths.append(file_path)
    return tools[:20], paths[:20]


def _sanitized_summary(text: str) -> tuple[str, bool]:
    """Sanitize or refuse — unsanitized text is never persisted."""
    if not text:
        return "", True
    try:
        from core.evals.sanitizer import SanitizerConfigMissing, sanitize_text
    except Exception:
        return "", False
    try:
        clean, _counts = sanitize_text(text[:_SUMMARY_CHARS])
        return clean, True
    except SanitizerConfigMissing:
        return "", False


_MCP_TOOL_RE = re.compile(r"^mcp__[^_]((?!__).)*__")


def _safe_tool_names(tools: list[str], sanitized_ok: bool) -> list[str]:
    """Tool names are metadata but not neutral: ``mcp__<server>__<tool>``
    carries an operator-chosen server segment that can name a client.
    Sanitizer available → redact through it; unavailable → strip the
    server segment entirely (fail closed, v2.18.0 precedent)."""
    if sanitized_ok:
        try:
            from core.evals.sanitizer import sanitize_text
            return [sanitize_text(name)[0] for name in tools]
        except Exception:
            pass
    return [_MCP_TOOL_RE.sub("mcp__", name) for name in tools]


def _importance(text: str, tools: list[str]) -> float:
    score = 0.5
    lowered = text.lower()
    if re.search(r"\berror\b|\bfailed\b|\bexception\b|traceback", lowered):
        score += 0.2
    if re.search(r"\[arka:qg:|verdict|approved|rejected", lowered):
        score += 0.15
    if any(t in ("Write", "Edit", "NotebookEdit") for t in tools):
        score += 0.1
    return min(score, 1.0)


def _cache_path(session_id: str) -> Path:
    cache_dir = Path.home() / ".arkaos" / _CACHE_DIRNAME
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"session-memory-{session_id}.json"


def _precompute_cache(
    store: SessionMemoryStore, record: TurnRecord, session_id: str
) -> None:
    """Rank cross-session neighbours NOW so the next prompt just reads."""
    if record.embedding is not None:
        items = store.semantic_neighbors(
            record.embedding, record.project_name or None,
            top_k=_NEIGHBOUR_K, exclude_session=session_id,
            backend=record.embedding_backend, model=record.embedding_model,
        )
        retrieval = "semantic"
    else:
        items, retrieval = [], "keyword-degraded"
    payload = {
        "version": 1,
        "session_id": session_id,
        "computed_at": datetime.now(UTC).isoformat(),
        "retrieval": retrieval,
        "embedding_backend": record.embedding_backend,
        "embedding_model": record.embedding_model,
        "dims": record.dims,
        "items": [
            {"summary": i["summary"][:200], "project_name": i["project_name"],
             "ts": i["ts"], "score": i["score"], "retrieval": i["retrieval"]}
            for i in items
        ],
    }
    target = _cache_path(session_id)
    # Unique tmp per writer: overlapping workers for the same session must
    # not share a tmp path, or write+replace stops being atomic.
    fd, tmp_name = tempfile.mkstemp(
        dir=target.parent, prefix=f"{target.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, indent=2))
        os.replace(tmp_name, target)
    except OSError:
        Path(tmp_name).unlink(missing_ok=True)


def _maintenance(store: SessionMemoryStore) -> None:
    """Amortised per run: small embedding backfill + retention prune."""
    for candidate in store.backfill_candidates(_BACKFILL_BATCH):
        result: EmbeddingResult = embed(candidate.summary)
        if result.vector is not None:
            store.update_embedding(
                candidate.id, result.vector, result.backend, result.model
            )
    store.prune()


def capture_turn(session_id: str, transcript_path: str, cwd: str = "") -> int:
    if not _config_enabled() or not session_id:
        return 0
    raw = _read_tail(transcript_path)
    if not raw:
        return 0
    text = _last_assistant_text(transcript_path, raw)
    tools, paths = _parse_tool_uses(raw)
    summary, sanitized_ok = _sanitized_summary(text)
    tools = _safe_tool_names(tools, sanitized_ok)
    if not sanitized_ok:
        paths = []  # refuse anything textual when the sanitizer is absent
    result: EmbeddingResult = embed(summary) if summary else EmbeddingResult()
    record = TurnRecord(
        ts=datetime.now(UTC).isoformat(),
        session_id=session_id,
        project_name=Path(cwd).name if cwd else "",
        cwd=cwd,
        summary=summary,
        tools_used=tools,
        file_paths=paths,
        importance=_importance(text, tools),
        embedding=result.vector,
        embedding_backend=result.backend,
        embedding_model=result.model,
        dims=result.dims,
    )
    store = SessionMemoryStore()
    store.save(record)
    _precompute_cache(store, record, session_id)
    _maintenance(store)
    return 0


_MAINTENANCE_MAX_BATCHES = 50


def run_maintenance() -> int:
    """Nightly job (F1-A4, scheduler python_module): full embedding
    backfill in batches, retention prune, vacuum. Off-turn by design —
    the per-turn worker only amortises a small slice of this."""
    if not _config_enabled():
        return 0
    from core.memory.semantic_store import default_db_path

    if not default_db_path().is_file():
        return 0
    store = SessionMemoryStore()
    for _ in range(_MAINTENANCE_MAX_BATCHES):
        candidates = store.backfill_candidates(_BACKFILL_BATCH)
        if not candidates:
            break
        for candidate in candidates:
            result = embed(candidate.summary)
            if result.vector is None:
                return 0  # backend degraded — retry next night, never spin
            store.update_embedding(
                candidate.id, result.vector, result.backend, result.model
            )
    store.prune()
    store.vacuum()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if args and args[0] == "maintenance":
        try:
            return run_maintenance()
        except Exception:  # detached job must die quietly
            return 0
    if len(args) < 2:
        print(
            "usage: python3 -m core.memory.turn_capture"
            " (<session_id> <transcript_path> [cwd] | maintenance)"
        )
        return 2
    try:
        return capture_turn(args[0], args[1], args[2] if len(args) > 2 else "")
    except Exception:  # detached worker must die quietly
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
