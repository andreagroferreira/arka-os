"""SubagentStop — consolidated entrypoint (F2-4, Claude Code reform).

Fires when a dispatched subagent (Task tool) finishes. Two jobs, both
WARN-only (this hook never blocks — the subagent already ran):

1. Persist the subagent's final output to the session store so the
   orchestrator's audit trail includes what each specialist produced
   (the ArkaOS QG story: nothing a specialist ships is invisible).
2. Run the same honesty checks the Stop hook runs on the main turn —
   phantom-action (does the output narrate effects with no tool calls?)
   and meta-tag presence — and, when the output looks deliverable-shaped,
   emit a stderr nudge to route it through the Quality Gate.

Telemetry (warn mode, same discipline as the Stop hook): one line per
subagent to ``~/.arkaos/telemetry/subagent-stop.jsonl``. Gate flag
``ARKA_SUBAGENT_QA`` = ``warn`` (default) | ``off``.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from core.hooks._shared import (
    ensure_root_on_path,
    get_str,
    read_stdin_json,
    resolve_arkaos_root,
    safe_session_id,
)

_TELEMETRY = Path.home() / ".arkaos" / "telemetry" / "subagent-stop.jsonl"
# A subagent output "looks deliverable-shaped" when it claims a build/fix
# a human would want gated — a cheap heuristic, warn-only, never blocks.
_DELIVERABLE_RE = None  # compiled lazily


def _qa_mode() -> str:
    mode = os.environ.get("ARKA_SUBAGENT_QA", "").strip().lower()
    return mode if mode in ("warn", "off") else "warn"


def _read_transcript(path: str) -> str | None:
    if not path:
        return None
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return None


def _final_assistant_text(transcript_path: str, raw: str | None) -> str:
    try:
        from core.workflow.flow_enforcer import _load_last_assistant_messages

        msgs = _load_last_assistant_messages(transcript_path, 1, raw_text=raw)
        return msgs[-1] if msgs else ""
    except Exception:  # best-effort — hook never breaks
        return ""


def _persist_output(session_id: str, agent_id: str, text: str) -> None:
    if not session_id or not text:
        return
    try:
        from core.evals.sanitizer import SanitizerConfigMissing, sanitize_text
        from core.memory.session_store import AgentOutput, SessionStore

        try:
            clean, _counts = sanitize_text(text[:4000])
        except SanitizerConfigMissing:
            clean = ""  # no sanitizer config => metadata only (recipes precedent)
        store = SessionStore(session_id)
        store.save_agent_output(AgentOutput(
            agent_id=agent_id or "subagent",
            phase_id="subagent-stop",
            output=clean,
            at=datetime.now(UTC).isoformat(),
        ))
    except Exception:  # persistence is best-effort
        pass


def _looks_deliverable(text: str) -> bool:
    global _DELIVERABLE_RE
    if _DELIVERABLE_RE is None:
        import re
        _DELIVERABLE_RE = re.compile(
            r"\b(implemented|created|added|fixed|refactored|built|wrote|"
            r"shipped|migrated|deployed)\b",
            re.IGNORECASE,
        )
    return bool(_DELIVERABLE_RE.search(text))


def _run_qa(text: str, raw: str | None) -> dict:
    result = {"phantom": "skipped", "meta_tag": "skipped", "deliverable": False}
    try:
        from core.governance.meta_tag_check import check_meta_tag
        from core.governance.phantom_action_check import check_phantom_actions

        phantom = check_phantom_actions(text, raw)
        result["phantom"] = "pass" if phantom.passed else "phantom-action"
        meta = check_meta_tag(text)
        result["meta_tag"] = "present" if meta.passed else "missing"
        result["deliverable"] = _looks_deliverable(text)
    except Exception:  # QA is best-effort — never break the hook
        pass
    return result


def _record(session_id: str, agent_id: str, qa: dict) -> None:
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "mode": "warn",
        "session_id": session_id,
        "agent_id": agent_id,
        **qa,
    }
    try:
        _TELEMETRY.parent.mkdir(parents=True, exist_ok=True)
        with _TELEMETRY.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def _nudge(agent_id: str, qa: dict) -> str:
    parts = []
    if qa.get("phantom") == "phantom-action":
        parts.append("narrates effects with no tool calls in the subagent turn")
    if qa.get("meta_tag") == "missing":
        parts.append("no [arka:meta] line")
    if qa.get("deliverable") and parts:
        return (
            f"[arka:subagent-qa] {agent_id or 'subagent'} output looks"
            f" deliverable-shaped but {'; '.join(parts)} — route it through"
            f" the Quality Gate before accepting."
        )
    return ""


def main(stdin_json: dict | None = None) -> int:
    if stdin_json is None:
        stdin_json, _ = read_stdin_json()
    root = resolve_arkaos_root()
    ensure_root_on_path(root)

    session_id = get_str(stdin_json, "session_id")
    if session_id and not safe_session_id(session_id):
        return 0
    agent_id = get_str(stdin_json, "subagent_type") or get_str(stdin_json, "agent_type")
    transcript_path = get_str(stdin_json, "transcript_path")

    if _qa_mode() == "off":
        return 0

    raw = _read_transcript(transcript_path)
    text = _final_assistant_text(transcript_path, raw)
    if not text:
        return 0

    _persist_output(session_id, agent_id, text)
    qa = _run_qa(text, raw)
    _record(session_id, agent_id, qa)

    nudge = _nudge(agent_id, qa)
    if nudge:
        print(nudge, file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
