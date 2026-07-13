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
blindspot, amended by P0.2): the enforcer is a NEGATIVE gate on the
parent transcript only. Subagent writes pass through because Claude
Code isolates subagent transcripts from the parent. The positive
`owner-match` path is exercised when the parent emits `[arka:dispatch]`
inline (e.g., the orchestrator impersonating a specialist) and remains
for forward compatibility if parent-transcript visibility ever ships.

Fail-open closed (P0.2): a marker that rolls out of the 20-message
window no longer reopens the gate — the persona observed in the window
is persisted per session+transcript (specialist_authorization) and
restored when the window shows nothing, deciding exactly as if the
marker were visible. The old blanket `no-routing-tag` (72% of all
telemetry) splits into `never-routed` (session never emitted a marker;
still ALLOW — hardening THAT is a separate, telemetry-gated decision)
and `subagent-scope` (sidechain evaluation; ADR behavior, now
measurable). The window itself counts main-scope messages only
(transcript_scope), so interleaved subagent records cannot evict the
marker.

Read by: config/hooks/pre-tool-use.sh between the KB-gate and the
flow-gate. Same Decision JSON contract as core.workflow.flow_enforcer.
"""

import contextlib
import json
import re
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import yaml

from core.shared import safe_session_id as _safe_session_id_module
from core.workflow import specialist_authorization, transcript_scope

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
            with contextlib.suppress(OSError):
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
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
ROSTER_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "config"
    / "agent-roster.json"
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
# Single-line, length-bounded body: the lazy `([^\]]+?)\s*` form
# backtracked catastrophically on an unclosed marker (4000 trailing
# spaces = 22s) — inside a BLOCKING PreToolUse hook, on model-emitted
# text. 400 chars is far above any substantive reason; beyond it the
# marker simply does not parse and the gate stays closed.
BYPASS_RE = re.compile(
    r"\[arka:specialist-bypass\s+([^\]\n]{1,400})\]", re.IGNORECASE
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
    # Alias resolution (PR-1): the marker said "diana", the rules say
    # "frontend-dev" — record both so telemetry can prove the fix.
    persona_raw: str | None = None
    alias_resolved: bool = False
    # Fail-open taxonomy (P0.2): where the persona came from ("window" |
    # "persisted" | ""), whether the ACTIVE scope is a sidechain, and how
    # far the marker sits from the window's end (None = not in window).
    persona_source: str = ""
    is_sidechain: bool = False
    msgs_since_marker: int | None = None

    def to_stderr_message(self) -> str:
        """The message a blocked session reads.

        Rewritten after the 2026-07-12 incident, where a session read the
        old text and went looking for a bug to justify a bypass. Three
        changes carry the weight: it refuses the false diagnosis up front,
        it hands over the correct path already filled in (two copyable
        lines), and it demotes the bypass to what it is — an audited
        exception the operator sees. The old text also called EVERY
        persona "(lead)", so a blocked specialist was told she was a lead:
        that actively fed the "the gate is buggy" story.
        """
        if self.allow:
            return ""
        persona = self.current_persona or "unrouted"
        owner = (self.required_owners or ["the owning specialist"])[0]
        owners = ", ".join(self.required_owners) or "the owning specialist"
        target = self.target_file or "this file"
        return (
            f"[ARKA:SPECIALIST] BLOCKED. {target} is owned by: {owners} "
            f"— dispatch any ONE of them. You are {persona}.\n"
            f"This is NOT a bug. The gate is working as designed. Retrying "
            f"this Write will fail again, every time.\n"
            f"DO THIS — two lines, and the specialist writes with no block:\n"
            f"    [arka:dispatch] {persona} -> {owner}\n"
            f"    Task(subagent_type=\"{owner}\", prompt=\"<what you were "
            f"about to write>\")\n"
            f"Audited exception (visible to the operator in the "
            f"specialist-dispatch telemetry: `arka-py -m "
            f"core.governance.specialist_telemetry_cli today`) — ONLY if "
            f"no specialist can do this:\n"
            f"    [arka:specialist-bypass owner={owner} reason=<24+ chars "
            f"explaining why a specialist cannot>]"
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
    persona_raw: str | None = None
    alias_resolved: bool = False
    config: dict = field(default_factory=dict)
    preloaded_messages: list[str] | None = None
    persona_source: str = ""
    # None = self-detect from the transcript; the consolidated hook passes
    # the value it computed while parsing (parse-once contract, PR-6).
    is_sidechain: bool | None = None
    msgs_since_marker: int | None = None


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


def _load_aliases() -> dict[str, str]:
    """First-name -> owner slug, from the generated roster.

    Sessions dispatch by human name (``-> diana``); ownership rules name
    slugs (``frontend-dev``). Without this, the RIGHT specialist was
    blocked from her own files — 22 of 189 measured blocks. The roster
    only emits aliases that are unambiguous among gate owners, and never
    guesses (core/agents/roster_manifest.py::build_aliases).
    """
    try:
        data = json.loads(ROSTER_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    aliases = data.get("aliases")
    return aliases if isinstance(aliases, dict) else {}


def _normalize_persona(raw: str) -> tuple[str, bool]:
    """Return (slug, alias_resolved). Unknown names pass through."""
    slug = _load_aliases().get(raw)
    return (slug, True) if slug else (raw, False)


def _resolve_persona(
    messages: list[str],
) -> tuple[str | None, str | None, str | None, bool]:
    """Find the current persona: (slug, marker, raw, alias_resolved).

    Dispatch tag wins over routing because dispatching is more specific.
    The name is normalized through the roster aliases, so a marker that
    names the human (``-> diana``) matches an ownership rule that names
    the slug (``frontend-dev``).
    """
    for text in reversed(messages):
        dispatch = DISPATCH_RE.search(text)
        if dispatch:
            raw = dispatch.group(1).lower()
            slug, resolved = _normalize_persona(raw)
            return slug, "dispatch", raw, resolved
        routing = ROUTING_RE.search(text)
        if routing:
            raw = routing.group(1).lower()
            slug, resolved = _normalize_persona(raw)
            return slug, "routing", raw, resolved
    return None, None, None, False


# A bypass must cost more than doing the right thing. Before the
# 2026-07-12 incident the only barrier was a non-empty string, and the
# deny message advertised the bypass beside the dispatch as an equal
# option — the single place in the whole prompt surface that taught it.
_MIN_BYPASS_REASON = 24
_EMPTY_REASONS = (
    "typo", "quick fix", "quickfix", "trivial", "urgent", "just this once",
    "small change", "minor", "one char", "fast", "quick typo fix",
    "just a quick typo fix", "just a quick typo fix honestly",
    "nothing important", "it is faster this way",
)
# Structured form the deny message teaches: `owner=<slug> reason=<text>`.
_BYPASS_STRUCTURED_RE = re.compile(
    r"^owner=(?P<owner>[\w-]+)\s+reason=(?P<reason>.*)$",
    re.IGNORECASE | re.DOTALL,
)


def _reason_is_substantive(reason: str) -> bool:
    """A reason must say something. QG redo 1 caught the hole: the floor
    was applied to the WHOLE marker body, so
    ``owner=senior-dev reason=`` (24 chars of boilerplate, empty reason)
    opened the gate — with the deny message teaching that very template.
    The floor now applies to the reason ALONE."""
    reason = reason.strip()
    if len(reason) < _MIN_BYPASS_REASON:
        return False
    normalized = reason.lower().strip(" .!,;")
    return normalized not in _EMPTY_REASONS


def _find_bypass(messages: list[str], owners: list[str] | None = None) -> str | None:
    """Return the bypass reason from the LAST assistant message, or None.

    Scope is strict: only the immediately preceding assistant message can
    grant a bypass. The structured form is required in spirit — a bare
    legacy reason is still accepted for one release, but it must clear the
    same substance floor. When ``owners`` is given, a structured
    ``owner=`` that names someone other than an actual owner is rejected:
    a bypass may not invent its own justification target.
    """
    if not messages:
        return None
    match = BYPASS_RE.search(messages[-1])
    if not match:
        return None
    body = match.group(1).strip()
    structured = _BYPASS_STRUCTURED_RE.match(body)
    if structured:
        if owners:
            claimed = structured.group("owner").lower()
            if claimed not in {o.lower() for o in owners}:
                return None
        reason = structured.group("reason")
    else:
        reason = body
    return reason.strip() if _reason_is_substantive(reason) else None


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


def _scope_fields(ctx: _Ctx) -> dict:
    """The P0.2 taxonomy fields every post-populate Decision carries."""
    return {
        "persona_source": ctx.persona_source,
        "is_sidechain": bool(ctx.is_sidechain),
        "msgs_since_marker": ctx.msgs_since_marker,
    }


def _check_tool_gated(ctx: _Ctx) -> Decision | None:
    if ctx.tool_name not in GATED_TOOLS:
        return Decision(allow=True, reason="tool-not-gated")
    return None


def _check_feature_flag(ctx: _Ctx) -> Decision | None:
    if not _feature_flag_on():
        return Decision(allow=True, reason="feature-flag-off")
    return None


def _msgs_since_marker(messages: list[str]) -> int | None:
    for i, text in enumerate(reversed(messages)):
        if DISPATCH_RE.search(text) or ROUTING_RE.search(text):
            return i
    return None


def _populate_context(ctx: _Ctx) -> None:
    """Extract file_path, load ownership, resolve persona (P0.2 fail-open)."""
    if ctx.tool_input and isinstance(ctx.tool_input, dict):
        ctx.file_path = str(
            ctx.tool_input.get("file_path")
            or ctx.tool_input.get("notebook_path")
            or ""
        )
    ctx.config = _load_ownership()
    if ctx.preloaded_messages is not None:
        ctx.messages = ctx.preloaded_messages[-ASSISTANT_WINDOW:]
    else:
        split = transcript_scope.split_from_path(ctx.transcript_path)
        ctx.messages = split.main[-ASSISTANT_WINDOW:]
        if ctx.is_sidechain is None:
            ctx.is_sidechain = split.active_sidechain
    ctx.is_sidechain = bool(ctx.is_sidechain)
    _resolve_or_restore_persona(ctx)


def _resolve_or_restore_persona(ctx: _Ctx) -> None:
    """Persist-on-observe + consult-before-allow (P0.2, mirrors #297).

    Marker in the window -> persist the resolved persona. Window empty of
    markers -> a valid persisted persona for THIS session+transcript
    decides as if the marker were still visible — including deciding
    BLOCK. Sidechain evaluations never consult the parent's persistence
    (the dispatched specialist must keep writing with no block, per the
    ADR).
    """
    ctx.persona, ctx.marker, ctx.persona_raw, ctx.alias_resolved = (
        _resolve_persona(ctx.messages)
    )
    if ctx.persona is not None:
        ctx.persona_source = "window"
        ctx.msgs_since_marker = _msgs_since_marker(ctx.messages)
        specialist_authorization.confirm(
            ctx.session_id, ctx.transcript_path,
            persona=ctx.persona, marker=ctx.marker or "",
            persona_raw=ctx.persona_raw, alias_resolved=ctx.alias_resolved,
        )
    elif not ctx.is_sidechain:
        restored = specialist_authorization.confirmed(
            ctx.session_id, ctx.transcript_path
        )
        if restored:
            ctx.persona = restored["persona"]
            ctx.marker = restored.get("marker") or None
            ctx.persona_raw = restored.get("persona_raw")
            ctx.alias_resolved = bool(restored.get("alias_resolved"))
            ctx.persona_source = "persisted"


def _check_no_persona(ctx: _Ctx) -> Decision | None:
    if ctx.persona is None:
        # Taxonomy (P0.2): the old blanket "no-routing-tag" (72% of all
        # telemetry) splits into what actually happened.
        reason = "subagent-scope" if ctx.is_sidechain else "never-routed"
        return Decision(
            allow=True, reason=reason, target_file=ctx.file_path,
            **_scope_fields(ctx),
        )
    return None


def _check_c_suite(ctx: _Ctx) -> Decision | None:
    c_suite = {x.lower() for x in ctx.config.get("c_suite", [])}
    if ctx.persona in c_suite:
        return Decision(
            allow=True, reason="c-suite-override",
            current_persona=ctx.persona, marker_found=ctx.marker,
            target_file=ctx.file_path, **_scope_fields(ctx),
        )
    return None


def _check_lead_allowed_file(ctx: _Ctx) -> Decision | None:
    allowed = ctx.config.get("lead_allowed", []) or []
    if _is_lead_allowed(ctx.file_path, allowed):
        return Decision(
            allow=True, reason="lead-allowed-file",
            current_persona=ctx.persona, marker_found=ctx.marker,
            target_file=ctx.file_path, **_scope_fields(ctx),
        )
    return None


def _decide_open_access(
    ctx: _Ctx, owners: list[str], rule_reason: str | None
) -> Decision:
    reason = f"open-access:{rule_reason}" if rule_reason else "open-access"
    return Decision(
        allow=True, reason=reason, current_persona=ctx.persona,
        marker_found=ctx.marker, target_file=ctx.file_path,
        required_owners=owners, **_scope_fields(ctx),
    )


def _decide_owner_match(ctx: _Ctx, owners: list[str]) -> Decision:
    return Decision(
        allow=True, reason=f"owner-match:{ctx.persona}",
        current_persona=ctx.persona, marker_found=ctx.marker,
        target_file=ctx.file_path,
        persona_raw=ctx.persona_raw, alias_resolved=ctx.alias_resolved,
        required_owners=owners, **_scope_fields(ctx),
    )


def _decide_bypass(ctx: _Ctx, owners: list[str], reason: str) -> Decision:
    return Decision(
        allow=True, reason="bypass-with-reason",
        current_persona=ctx.persona, marker_found=ctx.marker,
        target_file=ctx.file_path,
        persona_raw=ctx.persona_raw, alias_resolved=ctx.alias_resolved,
        required_owners=owners, bypass_used=True, bypass_reason=reason,
        **_scope_fields(ctx),
    )


def _decide_block(ctx: _Ctx, owners: list[str]) -> Decision:
    owners_lower = sorted({o.lower() for o in owners})
    return Decision(
        allow=False,
        reason=f"lead-blocked:{ctx.persona}-not-in-[{','.join(owners_lower)}]",
        current_persona=ctx.persona, marker_found=ctx.marker,
        target_file=ctx.file_path,
        persona_raw=ctx.persona_raw, alias_resolved=ctx.alias_resolved,
        required_owners=owners, **_scope_fields(ctx),
    )


def _resolve_with_owners(ctx: _Ctx, owners: list[str], rule_reason: str | None) -> Decision:
    """Pick the right Decision when ownership rule matched."""
    if "*" in owners:
        return _decide_open_access(ctx, owners, rule_reason)
    if ctx.persona in {o.lower() for o in owners}:
        return _decide_owner_match(ctx, owners)
    bypass = _find_bypass(ctx.messages, owners)
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
            target_file=ctx.file_path, **_scope_fields(ctx),
        )
    return _resolve_with_owners(ctx, owners, rule_reason)


# ─── Public API ─────────────────────────────────────────────────────────


def evaluate(
    tool_name: str,
    transcript_path: str,
    session_id: str = "",
    cwd: str = "",
    tool_input: dict | None = None,
    messages: list[str] | None = None,
    is_sidechain: bool | None = None,
) -> Decision:
    """Decide whether a Write/Edit/MultiEdit/NotebookEdit may proceed.

    ``messages`` (PR-6 hook consolidation): pre-parsed assistant messages;
    when None the transcript is read from ``transcript_path``.
    ``is_sidechain`` (P0.2): the active scope, when the caller computed it
    while parsing; None self-detects (only possible without ``messages``).
    """
    ctx = _Ctx(
        tool_name=tool_name, transcript_path=transcript_path,
        session_id=session_id, cwd=cwd, tool_input=tool_input or {},
        preloaded_messages=messages, is_sidechain=is_sidechain,
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
    model_requested: str = "",
) -> None:
    """Append a structured record to the specialist-dispatch telemetry log.

    Drops the record silently when session_id fails the safe-id check
    (path-traversal mitigation, CWE-22).

    ``model_requested`` carries the ``model`` param of the dispatched tool
    call when the caller has one (Agent dispatches), so ``/arka costs`` can
    later cross-check requested vs billed model tiers. Warn-only metadata —
    empty string when the tool has no model concept (Write/Edit).
    """
    safe = _safe_session_id_module.safe_session_id(session_id)
    if safe is None:
        return
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "session_id": safe,
        "tool": tool,
        "cwd": cwd,
        "target_file": target_file or decision.target_file or "",
        "model_requested": model_requested,
        **asdict(decision),
    }
    try:
        with _locked_append(TELEMETRY_PATH) as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # Telemetry write failure must never block the hook.
