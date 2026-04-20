"""Mandatory 13-phase flow enforcement for write-mutation tools.

Invoked by the Claude Code `PreToolUse` hook. Decides whether a `Write`,
`Edit`, or `MultiEdit` tool call may proceed, based on markers observed
in the last N assistant messages of the session transcript.

Design contract:
- Stateless transcript parse (no /tmp state for decisions).
- Side effects limited to reading the transcript path supplied by the hook.
- Signals permission when the assistant has emitted one of the flow markers:
  `[arka:routing]`, `[arka:trivial]`, or `[arka:phase:`.
- Respects `ARKA_BYPASS_FLOW=1` env var (installer/`/arka update` internal).
- Honors feature flag `hooks.hardEnforcement` in `~/.arkaos/config.json`.
- Gated tool list is closed: anything outside it is always allowed.
"""

import json
import os
import re
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from core.workflow import marker_cache

try:
    import fcntl  # POSIX only
    _HAS_FLOCK = True
except ImportError:
    _HAS_FLOCK = False


@contextmanager
def _locked_append(path: Path):
    """Append to `path` under an exclusive advisory lock (POSIX flock).

    On Windows or any platform without fcntl, falls back to a plain append
    (single-process writers remain safe; cross-process interleaving is
    mitigated by `O_APPEND` atomicity for writes up to PIPE_BUF).
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

GATED_TOOLS: frozenset[str] = frozenset({"Write", "Edit", "MultiEdit"})

ROUTING_RE = re.compile(r"\[arka:routing\]\s*[\w-]+\s*->\s*\w+", re.IGNORECASE)
TRIVIAL_RE = re.compile(r"\[arka:trivial\]\s*\S+", re.IGNORECASE)
PHASE_RE = re.compile(r"\[arka:phase:\d+\]", re.IGNORECASE)
SAFE_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

ASSISTANT_WINDOW = 6
CONFIG_PATH = Path.home() / ".arkaos" / "config.json"
BYPASS_AUDIT_PATH = Path.home() / ".arkaos" / "audit" / "bypass.log"
TELEMETRY_PATH = Path.home() / ".arkaos" / "telemetry" / "enforcement.jsonl"
FLOW_REQUIRED_DIR = Path("/tmp/arkaos-wf-required")


def _safe_session_id(session_id: str) -> str | None:
    """Validate session_id against a strict allowlist (prevents path traversal).

    Returns the id if safe, or None if it contains path separators, dots-dots,
    or characters outside `[A-Za-z0-9._-]`. Callers MUST treat None as reject.
    """
    if not session_id or not isinstance(session_id, str):
        return None
    if not SAFE_SESSION_ID_RE.match(session_id):
        return None
    return session_id


@dataclass
class Decision:
    """Outcome of enforcement evaluation for a single tool call."""

    allow: bool
    reason: str
    marker_found: str | None = None
    phase_observed: str | None = None
    bypass_used: bool = False

    def to_stderr_message(self) -> str:
        if self.allow:
            return ""
        return (
            f"[ARKA:ENFORCEMENT] Flow marker missing. "
            f"Emit `[arka:routing] <dept> -> <lead>` or `[arka:trivial] <reason>` "
            f"before any `Write`/`Edit`/`MultiEdit`. Reason: {self.reason}"
        )


def _feature_flag_on() -> bool:
    if not CONFIG_PATH.exists():
        return False
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return bool(data.get("hooks", {}).get("hardEnforcement", False))


def _bypass_env_active() -> bool:
    return os.environ.get("ARKA_BYPASS_FLOW", "").strip() == "1"


def _audit_bypass(session_id: str, tool: str, cwd: str) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "tool": tool,
        "cwd": cwd,
        "reason": os.environ.get("ARKA_BYPASS_REASON", ""),
    }
    with _locked_append(BYPASS_AUDIT_PATH) as fh:
        fh.write(json.dumps(entry) + "\n")


def record_telemetry(
    session_id: str, tool: str, decision: Decision, cwd: str
) -> None:
    """Append a structured record to the enforcement telemetry log."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "tool": tool,
        "cwd": cwd,
        **asdict(decision),
    }
    with _locked_append(TELEMETRY_PATH) as fh:
        fh.write(json.dumps(entry) + "\n")


def _flow_required_for_session(session_id: str) -> bool:
    """Check whether the UserPromptSubmit classifier flagged this session."""
    safe = _safe_session_id(session_id)
    if safe is None:
        return False
    marker = FLOW_REQUIRED_DIR / safe
    return marker.exists()


def _extract_text(content: object) -> str:
    """Flatten Claude transcript message content into a single string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if "text" in item:
                    parts.append(str(item["text"]))
                elif item.get("type") == "tool_use":
                    parts.append(f"<tool_use:{item.get('name', '')}>")
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return ""


def _load_last_assistant_messages(transcript_path: str, n: int) -> list[str]:
    """Read the last `n` assistant messages from a JSONL transcript."""
    path = Path(transcript_path) if transcript_path else None
    if path is None or not path.exists():
        return []
    messages: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        role = record.get("role") or record.get("message", {}).get("role")
        if role != "assistant":
            continue
        content = record.get("content")
        if content is None:
            content = record.get("message", {}).get("content")
        text = _extract_text(content)
        if text:
            messages.append(text)
    return messages[-n:]


def _scan_markers(messages: list[str]) -> tuple[str | None, str | None]:
    """Return (marker_found, phase_observed) across the given messages."""
    marker_found: str | None = None
    phase_observed: str | None = None
    for text in messages:
        if phase_observed is None:
            phase_match = PHASE_RE.search(text)
            if phase_match:
                phase_observed = phase_match.group(0)
        if marker_found is None:
            if ROUTING_RE.search(text):
                marker_found = "routing"
            elif TRIVIAL_RE.search(text):
                marker_found = "trivial"
            elif PHASE_RE.search(text):
                marker_found = "phase"
    return marker_found, phase_observed


def evaluate(
    tool_name: str,
    transcript_path: str,
    session_id: str = "",
    cwd: str = "",
) -> Decision:
    """Decide whether a tool call may proceed.

    Returns a Decision. Caller is responsible for translating `allow=False`
    into the appropriate hook exit code or permissionDecision output.
    """
    if tool_name not in GATED_TOOLS:
        return Decision(allow=True, reason="tool-not-gated")

    if not _feature_flag_on():
        return Decision(allow=True, reason="feature-flag-off")

    if _bypass_env_active():
        _audit_bypass(session_id, tool_name, cwd)
        return Decision(allow=True, reason="env-bypass", bypass_used=True)

    if not _flow_required_for_session(session_id):
        return Decision(allow=True, reason="classifier-did-not-match")

    cached = marker_cache.read_marker(session_id)
    if cached is not None:
        cached_type = cached.get("marker_type", "")
        return Decision(
            allow=True,
            reason=f"marker-cache-hit:{cached_type}",
            marker_found=cached_type or None,
        )

    messages = _load_last_assistant_messages(transcript_path, ASSISTANT_WINDOW)
    marker_found, phase_observed = _scan_markers(messages)

    if marker_found is None:
        return Decision(
            allow=False,
            reason=f"no-flow-marker-in-last-{ASSISTANT_WINDOW}-assistant-messages",
            phase_observed=phase_observed,
        )

    return Decision(
        allow=True,
        reason=f"marker-found:{marker_found}",
        marker_found=marker_found,
        phase_observed=phase_observed,
    )


def mark_flow_required(session_id: str) -> None:
    """Invoked by UserPromptSubmit when classifier matches creation intent."""
    safe = _safe_session_id(session_id)
    if safe is None:
        return
    FLOW_REQUIRED_DIR.mkdir(parents=True, exist_ok=True)
    marker = FLOW_REQUIRED_DIR / safe
    marker.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")


def clear_flow_required(session_id: str) -> None:
    """Clear the flow-required marker (end of session / rollout tooling)."""
    safe = _safe_session_id(session_id)
    if safe is None:
        return
    marker = FLOW_REQUIRED_DIR / safe
    if marker.exists():
        marker.unlink()
