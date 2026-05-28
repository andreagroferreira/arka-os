"""Force Specialist Dispatch — PreToolUse enforcement for write tools.

Blocks Tier-1 squad leads (Paulo, Ines, Daniel, etc.) from writing to
specialist-owned files (e.g., *.vue, **/app/Services/**) without first
dispatching the specialist via the Agent tool. The current persona is
read from the most recent `[arka:routing]` or `[arka:dispatch]` marker
in the session transcript.

Bypass: emit `[arka:specialist-bypass <reason>]` in the same assistant
message immediately before the Write/Edit. Empty reason is rejected.
Used bypasses are logged to telemetry for accountability.

Feature flag: `hooks.specialistEnforcement` in ~/.arkaos/config.json.

Architectural note (per ADR 2026-05-28-specialist-dispatch-subagent-
blindspot): the enforcer is a NEGATIVE gate on the parent transcript
only. Subagent writes pass through as `no-routing-tag` because Claude
Code isolates subagent transcripts from the parent. The positive
`owner-match` path is exercised when the parent emits `[arka:dispatch]`
inline (e.g., the orchestrator impersonating a specialist) and remains
for forward compatibility if parent-transcript visibility ever ships.

Read by: config/hooks/pre-tool-use.sh between the KB-gate and the
flow-gate. Same Decision JSON contract as core.workflow.flow_enforcer.
"""

import json
import re
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import yaml

from core.shared import safe_session_id as _safe_session_id_module
from core.workflow.flow_enforcer import _load_last_assistant_messages

try:
    import fcntl  # POSIX only
    _HAS_FLOCK = True
except ImportError:
    _HAS_FLOCK = False


@contextmanager
def _locked_append(path: Path):
    """Append to `path` under an exclusive advisory lock (POSIX flock)."""
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


# ─── Constants ──────────────────────────────────────────────────────────

CONFIG_PATH = Path.home() / ".arkaos" / "config.json"
TELEMETRY_PATH = (
    Path.home() / ".arkaos" / "telemetry" / "specialist-dispatch.jsonl"
)
OWNERSHIP_YAML_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "config"
    / "agent-ownership.yaml"
)

GATED_TOOLS: frozenset[str] = frozenset(
    {"Write", "Edit", "MultiEdit", "NotebookEdit"}
)

# Marker regexes — see docs/adr/2026-05-28-specialist-dispatch-...md
ROUTING_RE = re.compile(
    r"\[arka:routing\]\s*[\w-]+\s*->\s*(\w+)", re.IGNORECASE
)
DISPATCH_RE = re.compile(
    r"\[arka:dispatch\]\s*[\w-]+\s*->\s*([\w-]+)", re.IGNORECASE
)
BYPASS_RE = re.compile(
    r"\[arka:specialist-bypass\s+([^\]]+?)\s*\]", re.IGNORECASE
)

ASSISTANT_WINDOW = 20


# ─── Data ───────────────────────────────────────────────────────────────


@dataclass
class Decision:
    """Outcome of specialist-enforcement evaluation."""

    allow: bool
    reason: str
    current_persona: str | None = None
    required_owners: list[str] = field(default_factory=list)
    marker_found: str | None = None
    bypass_used: bool = False
    bypass_reason: str | None = None
    target_file: str | None = None

    def to_stderr_message(self) -> str:
        if self.allow:
            return ""
        persona = self.current_persona or "lead"
        owners = ", ".join(self.required_owners) or "specialist"
        target = self.target_file or "this file"
        return (
            f"[ARKA:SPECIALIST] {persona} (lead) is not authorised to write "
            f"{target}. Required owners: {owners}. Choose one: (1) dispatch "
            f"the specialist via the Agent tool AND emit "
            f"`[arka:dispatch] {persona} -> <specialist>` immediately before "
            f"the dispatch call (NON-NEGOTIABLE constitution rule "
            f"`dispatch-must-be-announced`), OR (2) add "
            f"`[arka:specialist-bypass <reason>]` to the same assistant "
            f"message to override (logged for accountability)."
        )


@dataclass
class _Ctx:
    """Mutable evaluation context passed through pipeline stages."""

    tool_name: str
    transcript_path: str
    session_id: str
    cwd: str
    tool_input: dict
    file_path: str = ""
    messages: list[str] = field(default_factory=list)
    persona: str | None = None
    marker: str | None = None
    config: dict = field(default_factory=dict)


# ─── Config + Ownership loaders ────────────────────────────────────────


def _feature_flag_on() -> bool:
    """Check `hooks.specialistEnforcement` in ~/.arkaos/config.json."""
    if not CONFIG_PATH.exists():
        return False
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return bool(data.get("hooks", {}).get("specialistEnforcement", False))


def _empty_ownership() -> dict:
    return {
        "version": 1,
        "leads": [],
        "c_suite": [],
        "ownership": [],
        "lead_allowed": [],
    }


@lru_cache(maxsize=1)
def _load_ownership() -> dict:
    """Load ownership rules from YAML. Cached per-process.

    Each `python3 -` heredoc invocation from the bash hook is a fresh
    interpreter, so the cache scope is one tool call — no TTL needed.
    Tests call `_load_ownership.cache_clear()` when monkeypatching.
    """
    if not OWNERSHIP_YAML_PATH.exists():
        return _empty_ownership()
    try:
        with OWNERSHIP_YAML_PATH.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except (yaml.YAMLError, OSError):
        return _empty_ownership()
    return data


# ─── Glob matching (B2 refactor: split tokenizer from matcher) ─────────


def _glob_token(pattern: str, i: int) -> tuple[str, int]:
    """Translate the glob character at `pattern[i]` to a regex fragment.

    Returns (fragment, next_index). Handles `**/`, `**`, `*`, `?`, brace
    expansion `{a,b,c}`, and escapes regex meta-characters.
    """
    c = pattern[i]
    if c == "*" and i + 1 < len(pattern) and pattern[i + 1] == "*":
        if i + 2 < len(pattern) and pattern[i + 2] == "/":
            return r"(?:.*/)?", i + 3
        return r".*", i + 2
    if c == "*":
        return r"[^/]*", i + 1
    if c == "?":
        return r"[^/]", i + 1
    if c in r".()[]+\|^$":
        return "\\" + c, i + 1
    if c == "{":
        close = pattern.find("}", i + 1)
        if close == -1:
            return re.escape(c), i + 1
        options = pattern[i + 1:close].split(",")
        return "(?:" + "|".join(re.escape(o) for o in options) + ")", close + 1
    return c, i + 1


@lru_cache(maxsize=256)
def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Compile a glob pattern (with ** support) into an anchored regex."""
    parts: list[str] = []
    i = 0
    while i < len(pattern):
        fragment, i = _glob_token(pattern, i)
        parts.append(fragment)
    return re.compile("^" + "".join(parts) + "$")


def _glob_match(pattern: str, path: str) -> bool:
    """Match `path` against `pattern` with `**` recursive-glob support."""
    return bool(_glob_to_regex(pattern).match(path.replace("\\", "/")))


# ─── Persona, bypass, ownership resolution ─────────────────────────────


def _resolve_persona(messages: list[str]) -> tuple[str | None, str | None]:
    """Find the current persona, scanning newest-to-oldest assistant turns.

    Dispatch tag wins over routing because dispatching is more specific.
    """
    for text in reversed(messages):
        dispatch = DISPATCH_RE.search(text)
        if dispatch:
            return dispatch.group(1).lower(), "dispatch"
        routing = ROUTING_RE.search(text)
        if routing:
            return routing.group(1).lower(), "routing"
    return None, None


def _find_bypass(messages: list[str]) -> str | None:
    """Return bypass reason from LAST assistant message, or None.

    Scope is strict: only the immediately preceding assistant message can
    grant a bypass. Empty / whitespace reasons are rejected.
    """
    if not messages:
        return None
    match = BYPASS_RE.search(messages[-1])
    if not match:
        return None
    reason = match.group(1).strip()
    return reason if reason else None


def _match_ownership(
    file_path: str, rules: list[dict]
) -> tuple[list[str] | None, str | None]:
    """Return (owners, rule_reason) of FIRST matching rule, or (None, None)."""
    for rule in rules:
        pattern = rule.get("pattern", "")
        if pattern and _glob_match(pattern, file_path):
            return list(rule.get("owners", []) or []), rule.get("reason")
    return None, None


def _is_lead_allowed(file_path: str, patterns: list[str]) -> bool:
    """Check lead_allowed against full path AND basename for convenience."""
    base = file_path.split("/")[-1]
    return any(
        _glob_match(p, file_path) or _glob_match(p, base) for p in patterns
    )


# ─── Pipeline stages (B1 refactor) ─────────────────────────────────────


def _check_tool_gated(ctx: _Ctx) -> Decision | None:
    if ctx.tool_name not in GATED_TOOLS:
        return Decision(allow=True, reason="tool-not-gated")
    return None


def _check_feature_flag(ctx: _Ctx) -> Decision | None:
    if not _feature_flag_on():
        return Decision(allow=True, reason="feature-flag-off")
    return None


def _populate_context(ctx: _Ctx) -> None:
    """Extract file_path, load ownership config, load + resolve transcript."""
    if ctx.tool_input and isinstance(ctx.tool_input, dict):
        ctx.file_path = str(
            ctx.tool_input.get("file_path")
            or ctx.tool_input.get("notebook_path")
            or ""
        )
    ctx.config = _load_ownership()
    ctx.messages = _load_last_assistant_messages(
        ctx.transcript_path, ASSISTANT_WINDOW
    )
    ctx.persona, ctx.marker = _resolve_persona(ctx.messages)


def _check_no_persona(ctx: _Ctx) -> Decision | None:
    if ctx.persona is None:
        return Decision(
            allow=True, reason="no-routing-tag", target_file=ctx.file_path,
        )
    return None


def _check_c_suite(ctx: _Ctx) -> Decision | None:
    c_suite = {x.lower() for x in ctx.config.get("c_suite", [])}
    if ctx.persona in c_suite:
        return Decision(
            allow=True, reason="c-suite-override",
            current_persona=ctx.persona, marker_found=ctx.marker,
            target_file=ctx.file_path,
        )
    return None


def _check_lead_allowed_file(ctx: _Ctx) -> Decision | None:
    allowed = ctx.config.get("lead_allowed", []) or []
    if _is_lead_allowed(ctx.file_path, allowed):
        return Decision(
            allow=True, reason="lead-allowed-file",
            current_persona=ctx.persona, marker_found=ctx.marker,
            target_file=ctx.file_path,
        )
    return None


def _decide_open_access(
    ctx: _Ctx, owners: list[str], rule_reason: str | None
) -> Decision:
    reason = f"open-access:{rule_reason}" if rule_reason else "open-access"
    return Decision(
        allow=True, reason=reason, current_persona=ctx.persona,
        marker_found=ctx.marker, target_file=ctx.file_path,
        required_owners=owners,
    )


def _decide_owner_match(ctx: _Ctx, owners: list[str]) -> Decision:
    return Decision(
        allow=True, reason=f"owner-match:{ctx.persona}",
        current_persona=ctx.persona, marker_found=ctx.marker,
        target_file=ctx.file_path, required_owners=owners,
    )


def _decide_bypass(ctx: _Ctx, owners: list[str], reason: str) -> Decision:
    return Decision(
        allow=True, reason="bypass-with-reason",
        current_persona=ctx.persona, marker_found=ctx.marker,
        target_file=ctx.file_path, required_owners=owners,
        bypass_used=True, bypass_reason=reason,
    )


def _decide_block(ctx: _Ctx, owners: list[str]) -> Decision:
    owners_lower = sorted({o.lower() for o in owners})
    return Decision(
        allow=False,
        reason=f"lead-blocked:{ctx.persona}-not-in-[{','.join(owners_lower)}]",
        current_persona=ctx.persona, marker_found=ctx.marker,
        target_file=ctx.file_path, required_owners=owners,
    )


def _resolve_with_owners(ctx: _Ctx, owners: list[str], rule_reason: str | None) -> Decision:
    """Pick the right Decision when ownership rule matched."""
    if "*" in owners:
        return _decide_open_access(ctx, owners, rule_reason)
    if ctx.persona in {o.lower() for o in owners}:
        return _decide_owner_match(ctx, owners)
    bypass = _find_bypass(ctx.messages)
    if bypass:
        return _decide_bypass(ctx, owners, bypass)
    return _decide_block(ctx, owners)


def _resolve_ownership_outcome(ctx: _Ctx) -> Decision:
    """Final branch: match ownership rules and resolve to a Decision."""
    owners, rule_reason = _match_ownership(
        ctx.file_path, ctx.config.get("ownership", []) or []
    )
    if owners is None:
        return Decision(
            allow=True, reason="no-ownership-rule",
            current_persona=ctx.persona, marker_found=ctx.marker,
            target_file=ctx.file_path,
        )
    return _resolve_with_owners(ctx, owners, rule_reason)


# ─── Public API ─────────────────────────────────────────────────────────


def evaluate(
    tool_name: str,
    transcript_path: str,
    session_id: str = "",
    cwd: str = "",
    tool_input: dict | None = None,
) -> Decision:
    """Decide whether a Write/Edit/MultiEdit/NotebookEdit may proceed."""
    ctx = _Ctx(
        tool_name=tool_name, transcript_path=transcript_path,
        session_id=session_id, cwd=cwd, tool_input=tool_input or {},
    )
    for early_check in (_check_tool_gated, _check_feature_flag):
        decision = early_check(ctx)
        if decision is not None:
            return decision
    _populate_context(ctx)
    for late_check in (_check_no_persona, _check_c_suite, _check_lead_allowed_file):
        decision = late_check(ctx)
        if decision is not None:
            return decision
    return _resolve_ownership_outcome(ctx)


def record_telemetry(
    session_id: str,
    tool: str,
    decision: Decision,
    cwd: str = "",
    target_file: str = "",
) -> None:
    """Append a structured record to the specialist-dispatch telemetry log.

    Drops the record silently when session_id fails the safe-id check
    (path-traversal mitigation, CWE-22).
    """
    safe = _safe_session_id_module.safe_session_id(session_id)
    if safe is None:
        return
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": safe,
        "tool": tool,
        "cwd": cwd,
        "target_file": target_file or decision.target_file or "",
        **asdict(decision),
    }
    try:
        with _locked_append(TELEMETRY_PATH) as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # Telemetry write failure must never block the hook.
