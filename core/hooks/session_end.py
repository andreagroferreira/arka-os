"""SessionEnd — consolidated entrypoint (F2-4, Claude Code reform).

Fires when a Claude Code session ends cleanly. Writes a final session
digest immediately — the PreCompact hook only fires on context
compaction, so a short session that never compacts left no record. Also
marks the session ended in the session store.

WARN/best-effort only: never blocks, always exits 0. The digest is
sanitized (recipes precedent) and content-hashed for dedup, same shape
as the PreCompact digest.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from core.hooks._shared import (
    ensure_root_on_path,
    get_str,
    read_stdin_json,
    resolve_arkaos_root,
    safe_session_id,
)

_DIGEST_DIR = Path.home() / ".arkaos" / "session-digests"
_TAIL_MSGS = 5
_MSG_CHARS = 500


def _read_transcript(path: str) -> str | None:
    if not path:
        return None
    try:
        # errors="replace" + ValueError: never raise on an invalid-UTF-8
        # transcript or a null-byte path (this hook promises exit 0 always,
        # and write_digest must reach _end_session).
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return None


def _last_assistant_texts(transcript_path: str, raw: str | None) -> list[str]:
    try:
        from core.workflow.flow_enforcer import _load_last_assistant_messages

        return _load_last_assistant_messages(transcript_path, _TAIL_MSGS, raw_text=raw)
    except Exception:
        return []


def _sanitize(text: str) -> str:
    try:
        from core.evals.sanitizer import SanitizerConfigMissing, sanitize_text

        try:
            clean, _counts = sanitize_text(text)
            return clean
        except SanitizerConfigMissing:
            return ""  # no config => omit the excerpt, keep the digest metadata
    except Exception:
        return ""


def _digest_id(session_id: str, seed: str) -> str:
    basis = f"{session_id or 'default'}-{seed[:200]}".encode("utf-8", "replace")
    return hashlib.sha256(basis).hexdigest()[:16]


def write_digest(session_id: str, transcript_path: str) -> Path | None:
    raw = _read_transcript(transcript_path)
    messages = _last_assistant_texts(transcript_path, raw)
    seed = messages[-1] if messages else ""
    digest_id = _digest_id(session_id, seed)
    short = (session_id or "default")[:8]
    sanitized = [_sanitize(m[:_MSG_CHARS]) for m in messages]
    excerpt = "\n\n".join(s for s in sanitized if s) \
        or "(no sanitizable transcript excerpt)"
    body = (
        "---\n"
        "type: session-digest\n"
        f"session_id: {session_id}\n"
        f"digest_id: {digest_id}\n"
        "trigger: session-end\n"
        f"ended_at: {datetime.now(UTC).isoformat()}\n"
        "---\n\n"
        f"# Session Digest — {digest_id}\n\n"
        "## Closing messages (sanitized)\n\n"
        f"{excerpt}\n"
    )
    try:
        _DIGEST_DIR.mkdir(parents=True, exist_ok=True)
        path = _DIGEST_DIR / f"digest-{short}-{digest_id}.md"
        path.write_text(body, encoding="utf-8")
        return path
    except OSError:
        return None


def _end_session(session_id: str) -> None:
    try:
        from core.memory.session_store import SessionStore

        SessionStore(session_id).end_session()
    except Exception:
        pass


def main(stdin_json: dict | None = None) -> int:
    if stdin_json is None:
        stdin_json, _ = read_stdin_json()
    root = resolve_arkaos_root()
    ensure_root_on_path(root)

    session_id = get_str(stdin_json, "session_id")
    if session_id and not safe_session_id(session_id):
        return 0
    transcript_path = get_str(stdin_json, "transcript_path")

    write_digest(session_id, transcript_path)
    _end_session(session_id)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
