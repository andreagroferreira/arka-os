"""Evidence-flow enforcement for write-mutation tools.

Invoked by the Claude Code `PreToolUse` hook. Decides whether a `Write`,
`Edit`, or `MultiEdit` tool call may proceed, based on markers observed
in the last N assistant messages of the session transcript.

Design contract:
- Stateless transcript parse (no /tmp state for decisions).
- Side effects limited to reading the transcript path supplied by the hook.
- Signals permission when the assistant has emitted one of the flow markers:
  `[arka:routing]`, `[arka:trivial]`, or `[arka:gate:` (v4.1 evidence flow).
  The legacy 13-phase `[arka:phase:` marker remains accepted during the
  v4.1 deprecation window.
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

from core.shared import safe_session_id as _safe_session_id_module
from core.workflow import flow_authorization, marker_cache

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

# PR11 v2.33.0 — Discovery vs Effect tool taxonomy (Conclave Phase 5).
#
# DISCOVERY tools (no routing required): Read, Grep, Glob, ToolSearch,
# the various read-only MCP tools (Obsidian search, claude-mem search,
# Context7 query), AskUserQuestion. These never mutate user state.
#
# EFFECT tools (routing required): tools below produce visible state
# changes — write to filesystem, dispatch agents, invoke skills,
# mutate the notebook. Each requires a flow marker
# ([arka:routing] or [arka:trivial]) in the recent assistant messages.
#
# Bash is special: command-by-command classification via bash_is_effect().
# Pure read commands (cat, ls, grep, git status, etc.) are DISCOVERY.
# Mutating commands (rm, mv, git commit/push, npm install, etc.) are
# EFFECT. Unknown commands default to EFFECT (safer).

EFFECT_TOOLS_ALWAYS: frozenset[str] = frozenset({
    "Write", "Edit", "MultiEdit", "NotebookEdit",
    "Task", "Skill",  # Agent dispatch + skill invocation cascade to effect
})

# Backwards-compatible alias for callers that import GATED_TOOLS.
GATED_TOOLS: frozenset[str] = EFFECT_TOOLS_ALWAYS

# Bash classifier — whitelist of safe DISCOVERY first-tokens.
_BASH_DISCOVERY_FIRST: frozenset[str] = frozenset({
    # File reading
    "cat", "head", "tail", "less", "more", "tee",
    # Directory + search
    "ls", "find", "locate", "tree", "stat", "file",
    # Text search / processing (read-only)
    "grep", "ag", "rg", "wc", "sort", "uniq", "tr", "cut", "awk", "fmt",
    # System info
    "pwd", "whoami", "id", "hostname", "uname", "date", "df", "du",
    "free", "uptime", "echo", "printf", "true", "false",
    # Process info
    "ps", "pgrep", "jobs",
    # Tool version queries (no side-effect)
    "which", "type", "command", "where",
    # Common toolchain read-only entry points (subcommand checked below)
    "git", "npm", "yarn", "pnpm", "pip", "pip3", "uv", "poetry",
    "brew", "apt", "snap", "winget", "choco", "ollama", "docker",
    "python", "python3", "node", "ruby", "php", "go", "rustc",
    "curl", "wget",  # default to read; mutation via flags below
    # Shell builtins / control
    "test", "[", "if", "while", "for", "case", "function", "return",
    "exit", "source", ".", "set", "export", "alias", "unalias",
    "shopt", "trap", "wait", "eval", "exec",
    # Test runners (read state but don't mutate canonical files)
    "pytest", "jest", "vitest", "phpunit", "pest", "rspec", "mocha",
    "go", "cargo",
})

# Bash classifier — patterns that indicate mutation (anywhere in command).
_BASH_EFFECT_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p) for p in [
        # File-system mutation
        r"(^|[\s|;&])rm\s", r"(^|[\s|;&])mv\s", r"(^|[\s|;&])cp\s+-[rRf]",
        r"(^|[\s|;&])dd\s", r"(^|[\s|;&])truncate\s",
        r"(^|[\s|;&])touch\s", r"(^|[\s|;&])mkdir\s", r"(^|[\s|;&])rmdir\s",
        r"(^|[\s|;&])ln\s+-s", r"(^|[\s|;&])chmod\s", r"(^|[\s|;&])chown\s",
        # In-place edit
        r"sed\s+-i", r"perl\s+-i", r"awk\s+-i\s",
        # Process control
        r"(^|[\s|;&])kill\s", r"(^|[\s|;&])killall\s", r"(^|[\s|;&])pkill\s",
        # Elevation
        r"(^|[\s|;&])sudo\s", r"(^|[\s|;&])su\s+-",
        # Git mutation
        r"git\s+(commit|push|merge|rebase|reset\s+--hard|checkout\s+-[Bb]|tag\s|stash|cherry-pick|revert|branch\s+-[dD])",
        # Package mutation
        r"npm\s+(install|i|publish|uninstall|update|run\s+publish)",
        r"yarn\s+(add|remove|install|publish|upgrade)",
        r"pnpm\s+(add|remove|install|publish|update)",
        r"pip3?\s+install", r"pip3?\s+uninstall",
        r"uv\s+pip\s+install", r"poetry\s+(add|remove|install|publish)",
        r"brew\s+(install|uninstall|upgrade|cleanup)",
        r"apt(-get)?\s+(install|remove|purge|upgrade)",
        r"snap\s+(install|remove|refresh)",
        r"winget\s+(install|uninstall|upgrade)",
        r"choco\s+(install|uninstall|upgrade)",
        # GitHub mutation
        r"gh\s+(pr\s+create|release\s+create|issue\s+create|repo\s+create|secret\s+set)",
        r"gh\s+pr\s+merge", r"gh\s+pr\s+close", r"gh\s+repo\s+delete",
        # Docker mutation
        r"docker\s+(build|push|run|create|rm|kill|stop|start|restart|exec)",
        # Network transfer (mutates remote)
        r"(^|[\s|;&])scp\s",
        # rsync is intentionally not in the blacklist nor in the discovery
        # whitelist — default-deny path classifies it as EFFECT. Users
        # who genuinely need rsync (including --dry-run) emit a routing
        # marker; safer than guessing intent from flags.
        # Redirects to file (overwrite or append)
        r">\s*[^&\s]", r">>\s*[^&\s]",
    ]
)


def bash_is_effect(command: str) -> bool:
    """Classify a Bash command as EFFECT (requires routing) or DISCOVERY (free).

    Algorithm (default-deny for unknowns):
      1. Empty command → False (no effect).
      2. Any blacklist pattern matches anywhere in the command → True.
      3. First non-pipe token is in the discovery whitelist → False.
      4. Otherwise → True (unknown commands default to requiring routing).

    Pipes and command chaining are scanned as a whole — if any segment
    has an effect verb, the entire chain is classified EFFECT.
    """
    if not command or not command.strip():
        return False
    stripped = command.strip()
    for pattern in _BASH_EFFECT_PATTERNS:
        if pattern.search(stripped):
            return True
    first_tokens = stripped.split(None, 1)
    if not first_tokens:
        return False
    first = first_tokens[0]
    # Strip leading env-var assignments like FOO=bar baz qux
    while "=" in first and first_tokens:
        first_tokens = first_tokens[1].split(None, 1) if len(first_tokens) > 1 else []
        first = first_tokens[0] if first_tokens else ""
    if not first:
        return False
    if first in _BASH_DISCOVERY_FIRST:
        return False
    # Unknown command — default to requiring routing.
    return True

ROUTING_RE = re.compile(r"\[arka:routing\]\s*[\w-]+\s*->\s*\w+", re.IGNORECASE)
TRIVIAL_RE = re.compile(r"\[arka:trivial\]\s*\S+", re.IGNORECASE)
GATE_RE = re.compile(r"\[arka:gate:[1-4]\]", re.IGNORECASE)
# Legacy 13-phase marker — accepted during the v4.1 deprecation window.
PHASE_RE = re.compile(r"\[arka:phase:\d+(\.\d+)?\]", re.IGNORECASE)

# Re-export for backward compatibility with any external importers that
# relied on the module-level symbols before the core.shared extraction.
SAFE_SESSION_ID_RE = _safe_session_id_module.SAFE_SESSION_ID_RE
_safe_session_id = _safe_session_id_module.safe_session_id

# PR53 v2.70.0 — widened from 6 to 20. The 6-message window was too
# tight for long multi-PR sessions: after a single PR's worth of test
# runs / commits / npm publishes (each producing a substantive assistant
# message), the [arka:routing] line aged out and the enforcer blocked
# subsequent Edit/Write calls even though the operator was clearly mid-
# scope. 20 covers ~2-3 PRs of tool work without re-emitting the
# routing line. Transcript remains the authoritative source per
# docs/adr/2026-04-17-binding-flow-enforcement.md — this just widens
# how far back we look before declaring the marker absent.
ASSISTANT_WINDOW = 20
CONFIG_PATH = Path.home() / ".arkaos" / "config.json"
BYPASS_AUDIT_PATH = Path.home() / ".arkaos" / "audit" / "bypass.log"
TELEMETRY_PATH = Path.home() / ".arkaos" / "telemetry" / "enforcement.jsonl"
FLOW_REQUIRED_DIR = Path("/tmp/arkaos-wf-required")


@dataclass
class Decision:
    """Outcome of enforcement evaluation for a single tool call."""

    allow: bool
    reason: str
    marker_found: str | None = None
    phase_observed: str | None = None
    bypass_used: bool = False
    warning: str = ""

    def to_stderr_message(self) -> str:
        if self.allow:
            return self.warning
        # Recovery that actually works, given Claude Code exposes no
        # current-message text to hooks (the inline `ARKA_BYPASS_FLOW=1`
        # never reached this separate hook process — a documented trap).
        return (
            f"[ARKA:ENFORCEMENT] No routing marker for "
            f"{flow_authorization.GRACE_CAP}+ turns. Emit "
            f"`[arka:routing] <dept> -> <lead>` (or `[arka:trivial] "
            f"<reason>`) at the START of your reply — it authorises this "
            f"turn and every turn after. To turn enforcement off set "
            f"hooks.hardEnforcement=false in ~/.arkaos/config.json; to "
            f"bypass programmatically export ARKA_BYPASS_FLOW=1 in Claude "
            f"Code's own environment (settings.json env), not inline on a "
            f"command. Reason: {self.reason}."
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


def _load_last_assistant_messages(
    transcript_path: str, n: int, raw_text: str | None = None
) -> list[str]:
    """Read the last `n` assistant messages from a JSONL transcript.

    ``raw_text`` lets callers that already read the transcript (PR-6 hook
    consolidation — parse once per hook invocation) skip the disk read.
    """
    if raw_text is None:
        path = Path(transcript_path) if transcript_path else None
        if path is None or not path.exists():
            return []
        raw_text = path.read_text(encoding="utf-8", errors="replace")
    messages: list[str] = []
    for line in raw_text.splitlines():
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
            gate_match = GATE_RE.search(text)
            phase_match = PHASE_RE.search(text)
            if gate_match:
                phase_observed = gate_match.group(0)
            elif phase_match:
                phase_observed = phase_match.group(0)
        if marker_found is None:
            if ROUTING_RE.search(text):
                marker_found = "routing"
            elif TRIVIAL_RE.search(text):
                marker_found = "trivial"
            elif GATE_RE.search(text):
                marker_found = "gate"
            elif PHASE_RE.search(text):
                marker_found = "phase"
    return marker_found, phase_observed


def evaluate(
    tool_name: str,
    transcript_path: str,
    session_id: str = "",
    cwd: str = "",
    tool_input: dict | None = None,
    messages: list[str] | None = None,
) -> Decision:
    """Decide whether a tool call may proceed.

    Returns a Decision. Caller is responsible for translating `allow=False`
    into the appropriate hook exit code or permissionDecision output.

    PR11 v2.33.0 expanded the gated set beyond Write/Edit/MultiEdit to
    cover all EFFECT tools (NotebookEdit, Task, Skill) and to classify
    Bash commands per-command via ``bash_is_effect``.

    ``messages`` (PR-6 hook consolidation): pre-parsed assistant messages.
    When None (default) the transcript is read from ``transcript_path`` —
    backward compatible with all existing callers.
    """
    is_gated = tool_name in EFFECT_TOOLS_ALWAYS
    if not is_gated and tool_name == "Bash":
        bash_cmd = ""
        if tool_input and isinstance(tool_input, dict):
            bash_cmd = str(tool_input.get("command", ""))
        is_gated = bash_is_effect(bash_cmd)
    if not is_gated:
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

    if messages is None:
        messages = _load_last_assistant_messages(
            transcript_path, ASSISTANT_WINDOW
        )
    marker_found, phase_observed = _scan_markers(messages)

    if marker_found is not None:
        # Persist a confirmed authorization so this survives compaction and
        # the 20-message window rolling — the fix for the 652 false blocks.
        flow_authorization.confirm(session_id, marker_found)
        return Decision(
            allow=True,
            reason=f"marker-found:{marker_found}",
            marker_found=marker_found,
            phase_observed=phase_observed,
        )

    # No marker in the transcript window. The current turn's marker is
    # structurally invisible to hooks, so fall back to persistent auth
    # before ever blocking.
    if flow_authorization.is_confirmed(session_id):
        return Decision(
            allow=True, reason="session-authorized", phase_observed=phase_observed
        )

    # Same turn, already graced: let the rest of the turn's tools through.
    if flow_authorization.has_turn_grace(session_id):
        return Decision(
            allow=True, reason="turn-grace", phase_observed=phase_observed
        )

    # First effect-tool of a turn with no confirmed auth. A hard deny here
    # is a false positive (the assistant may have routed in this very
    # message — invisible to us). Grace it with a warning; escalate to a
    # real block only after GRACE_CAP consecutive graced turns without any
    # confirmation (a normally-routing session confirms by turn 2).
    grace = flow_authorization.register_grace(session_id)
    if grace.escalate:
        return Decision(
            allow=False,
            reason=f"no-marker-and-grace-exhausted-after-{grace.count}-turns",
            phase_observed=phase_observed,
        )
    flow_authorization.grant_turn_grace(session_id)
    return Decision(
        allow=True,
        reason=f"first-tool-grace:{grace.count}",
        phase_observed=phase_observed,
        warning=(
            f"[arka:suggest] Effect tool allowed without an observable "
            f"routing marker (grace {grace.count}/{flow_authorization.GRACE_CAP}). "
            f"Emit `[arka:routing] <dept> -> <lead>` at the start of your "
            f"reply to authorise this session."
        ),
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
