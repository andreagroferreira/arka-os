"""PreToolUse — consolidated entrypoint (PR-6 v4.1.0 hook hygiene).

Replaces the 5-8 python3/jq spawns of the old ``pre-tool-use.sh`` heredocs
with ONE python process. Gate order is preserved exactly:

    1. KB-first research gate  (core/workflow/research_gate.py)
    2. Specialist-dispatch gate (core/workflow/specialist_enforcer.py)
    3. Fast allow for non-flow-gated tools
    4. CostGovernor budget check (stdlib-only — MUST run even when the
       yaml-needing enforcers degrade; see ADR 2026-07-04-cost-governor)
    5. Evidence-flow gate (core/workflow/flow_enforcer.py)

Behavior contract (unchanged from the bash version):
    - allow  → no stdout, exit 0 (nudges/warnings on stderr)
    - deny   → stderr message + permissionDecision=deny JSON, exit 2
    - env bypasses (ARKA_BYPASS_FLOW, ARKA_BYPASS_KB_FIRST) and feature
      flags are honored inside the delegated modules
    - every module import is lazy try/except: a PyYAML-less python3
      degrades each gate to allow, identical to the old heredocs

The transcript is parsed at most ONCE per invocation and shared between
the specialist and flow gates via their ``messages=`` params.
"""

from __future__ import annotations

import sys
from pathlib import Path

from core.hooks._shared import (
    emit_deny_json,
    ensure_root_on_path,
    get_str,
    read_stdin_json,
    resolve_arkaos_root,
)

_FLOW_GATED_TOOLS = frozenset({
    "Write", "Edit", "MultiEdit", "NotebookEdit", "Task", "Skill", "Bash",
})
_SPECIALIST_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})
_ASSISTANT_WINDOW = 20


def _query_hint(tool_input: dict) -> str:
    """Mirror `jq -r '.tool_input.query // .prompt // .url' | head -c 500`."""
    for key in ("query", "prompt", "url"):
        value = tool_input.get(key)
        if value is not None and value is not False:
            return str(value)[:500]
    return ""


class _MessagesOnce:
    """Parse the transcript at most once, lazily, across both gates.

    ``peek()`` never triggers a read — gates that have their own cheaper
    early-outs (feature flag off, marker-cache hit) pass ``peek()`` so the
    module self-loads only when it really needs the transcript. ``load()``
    is called by the first gate that has already decided it needs messages.
    """

    def __init__(self, transcript_path: str):
        self._path = transcript_path
        self._messages: list[str] | None = None

    def peek(self) -> list[str] | None:
        return self._messages

    def load(self) -> list[str] | None:
        if self._messages is None:
            try:
                from core.workflow.flow_enforcer import (
                    _load_last_assistant_messages,
                )
                self._messages = _load_last_assistant_messages(
                    self._path, _ASSISTANT_WINDOW
                )
            except Exception:
                return None
        return self._messages


def _deny(stderr_msg: str) -> int:
    if stderr_msg:
        print(stderr_msg, file=sys.stderr)
    emit_deny_json(stderr_msg)
    return 2


def _kb_gate(root: str, tool_name: str, session_id: str, query: str) -> int | None:
    """KB-first gate. Returns 2 on deny, None to continue."""
    if not (Path(root) / "core" / "workflow" / "research_gate.py").is_file():
        return None
    try:
        from core.workflow.research_gate import (
            evaluate_research_gate,
            record_telemetry,
        )
    except Exception:
        return None  # kb-gate-import-failed → allow (old heredoc contract)
    decision = evaluate_research_gate(
        tool_name=tool_name, session_id=session_id, query=query
    )
    try:
        record_telemetry(session_id=session_id, tool=tool_name, decision=decision)
    except Exception:
        pass
    if not decision.allow:
        return _deny(decision.to_stderr_message())
    if decision.nudge and decision.to_stderr_message():
        print(decision.to_stderr_message(), file=sys.stderr)
    return None


def _specialist_gate(
    root: str,
    tool_name: str,
    transcript_path: str,
    session_id: str,
    cwd: str,
    tool_input: dict,
    messages: _MessagesOnce,
) -> int | None:
    """Specialist-dispatch gate. Returns 2 on deny, None to continue."""
    if tool_name not in _SPECIALIST_TOOLS:
        return None
    module_path = Path(root) / "core" / "workflow" / "specialist_enforcer.py"
    if not module_path.is_file():
        return None
    try:
        from core.workflow.specialist_enforcer import (
            _feature_flag_on,
            evaluate,
            record_telemetry,
        )
    except Exception:
        return None  # specialist-import-failed → allow
    # Load (and share) the transcript only when the gate will actually
    # scan it — flag-off sessions keep the zero-read fast path.
    shared = messages.peek()
    if shared is None and _feature_flag_on():
        shared = messages.load()
    decision = evaluate(
        tool_name=tool_name,
        transcript_path=transcript_path,
        session_id=session_id,
        cwd=cwd,
        tool_input=tool_input,
        messages=shared,
    )
    try:
        record_telemetry(
            session_id=session_id,
            tool=tool_name,
            decision=decision,
            cwd=cwd,
            target_file=str(tool_input.get("file_path", "")),
            model_requested=str(tool_input.get("model", "")),
        )
    except Exception:
        pass
    if not decision.allow:
        return _deny(decision.to_stderr_message())
    return None


def _budget_check(session_id: str) -> tuple[bool, str]:
    """CostGovernor gate (stdlib-only). Returns (allow, warning)."""
    try:
        from core.runtime.cost_governor import check as _check
        gov = _check(session_id)
        return gov.allow, gov.to_warning()
    except Exception:
        return True, ""


def _flow_gate(
    root: str,
    tool_name: str,
    transcript_path: str,
    session_id: str,
    cwd: str,
    tool_input: dict,
    messages: _MessagesOnce,
) -> int:
    """Budget + evidence-flow gate. Returns final exit code."""
    # Budget fires even when the flow enforcer degrades (PR-5 contract).
    budget_allow, budget_warning = _budget_check(session_id)
    if budget_warning:
        print(budget_warning, file=sys.stderr)
    if not budget_allow:
        return _deny(budget_warning)

    try:
        from core.workflow.flow_enforcer import evaluate, record_telemetry
    except Exception:
        return 0  # enforcer-import-failed → allow
    decision = evaluate(
        tool_name=tool_name,
        transcript_path=transcript_path,
        session_id=session_id,
        cwd=cwd,
        tool_input=tool_input,
        # peek() only: when the specialist gate already parsed, reuse it;
        # otherwise let evaluate() keep its lazy early-outs (feature flag,
        # env bypass, classifier flag, marker cache) before reading.
        messages=messages.peek(),
    )
    try:
        record_telemetry(
            session_id=session_id, tool=tool_name, decision=decision, cwd=cwd
        )
    except Exception:
        pass
    if decision.allow:
        return 0
    return _deny(decision.to_stderr_message())


def main(stdin_json: dict | None = None) -> int:
    if stdin_json is None:
        stdin_json, _ = read_stdin_json()
    root = resolve_arkaos_root()
    ensure_root_on_path(root)

    tool_name = get_str(stdin_json, "tool_name")
    transcript_path = get_str(stdin_json, "transcript_path")
    session_id = get_str(stdin_json, "session_id")
    cwd = get_str(stdin_json, "cwd")
    tool_input = stdin_json.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}

    messages = _MessagesOnce(transcript_path)

    code = _kb_gate(root, tool_name, session_id, _query_hint(tool_input))
    if code is not None:
        return code

    code = _specialist_gate(
        root, tool_name, transcript_path, session_id, cwd, tool_input, messages
    )
    if code is not None:
        return code

    # Fast allow: not a flow-gated tool (Bash stays — classified per-command
    # by the enforcer via bash_is_effect()).
    if tool_name not in _FLOW_GATED_TOOLS:
        return 0
    if not (Path(root) / "core" / "workflow" / "flow_enforcer.py").is_file():
        return 0

    return _flow_gate(
        root, tool_name, transcript_path, session_id, cwd, tool_input, messages
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        # Fail open — the bash version piped every heredoc through
        # `2>/dev/null` and exited 0 on internal errors.
        raise SystemExit(0)
