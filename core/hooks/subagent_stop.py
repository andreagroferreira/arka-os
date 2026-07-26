"""SubagentStop — consolidated entrypoint (F2-4, Claude Code reform).

Fires when a dispatched subagent (Task tool) finishes. Two jobs, both
WARN-only (this hook never blocks — the subagent already ran):

1. Persist the subagent's final output to the session store so the
   orchestrator's audit trail includes what each specialist produced
   (the ArkaOS QG story: nothing a specialist ships is invisible).
2. Run the same honesty checks the Stop hook runs on the main turn —
   phantom-action (does the output narrate effects with no tool calls?)
   and meta-tag presence — and, when the output looks deliverable-shaped,
   emit the nudge on stdout as ``hookSpecificOutput.additionalContext``
   so the orchestrator routes it through the Quality Gate (hook stderr
   is discarded at exit 0 — a stderr nudge would be inert).
3. For Quality Gate reviewers, capture the verdict verbatim to the
   reviewer ledger and hand the orchestrator the verdict line plus the
   artifact path — the reviewer's direct channel, which no aggregator
   paraphrase sits in front of (``core/governance/reviewer_ledger.py``).

Telemetry (warn mode, same discipline as the Stop hook): one line per
subagent to ``~/.arkaos/telemetry/subagent-stop.jsonl``. Gate flag
``ARKA_SUBAGENT_QA`` = ``warn`` (default) | ``off``.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from core.hooks._shared import (
    emit_additional_context,
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
        # errors="replace": an invalid-UTF-8 transcript must not raise
        # UnicodeDecodeError (this hook promises never to block). ValueError
        # guards a null-byte path arriving from stdin JSON.
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return None


def _final_assistant_text(transcript_path: str, raw: str | None) -> str:
    """The SUBAGENT's last message — sidechain scope, not the main turn.

    Reading the raw tail returned the parent's in-flight turn instead:
    at SubagentStop time the last main-scope record is the one holding
    the Task call, which serialises as ``<tool_use:Agent>``. Every
    persisted reviewer output on disk was that 16-byte placeholder.
    """
    try:
        from core.workflow.transcript_scope import split_by_scope

        if raw is not None:
            split = split_by_scope(raw)
            if split.sidechain:
                return split.sidechain[-1]

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
            # QG reviewers keep their words: the ledger is local-only
            # (0600) and is not the training corpus this fail-closed
            # branch protects. core/governance/reviewer_ledger.py.
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


def _record_reviewer(session_id: str, agent_id: str, text: str) -> dict | None:
    """Cross-check capture of a QG reviewer's verdict (see the ledger).

    Independent of the PostToolUse writer: the two sources dedupe on the
    output hash, so a divergence between them is a tamper signal rather
    than a silent overwrite.
    """
    try:
        from core.governance.reviewer_ledger import record_reviewer_output

        return record_reviewer_output(
            session_id=session_id,
            reviewer_id=agent_id,
            raw_output=text,
            source="subagent-stop",
        )
    except Exception:
        return None


def _reviewer_channel(record: dict | None) -> str:
    """Francisca's direct line to the orchestrator: verdict + artifact path.

    SubagentStop additionalContext reaches the ORCHESTRATOR, so the
    reviewer's own verdict and the path to its verbatim record arrive
    without passing through the aggregator's prose.
    """
    if not record:
        return ""
    reviewer = record.get("reviewer_id", "reviewer")
    verdict = (record.get("verdict") or {}).get("verdict")
    path = record.get("path", "")
    if not verdict:
        if record.get("parse_error"):
            return (
                f"[arka:qg:reviewer-verdict] {reviewer} verdict-unparsed"
                f" ({record['parse_error']}) artifact={path} — read the"
                f" artifact and quote it verbatim; do not summarise."
            )
        return ""
    blockers = (record.get("verdict") or {}).get("blockers") or []
    return (
        f"[arka:qg:reviewer-verdict] {reviewer} {verdict}"
        f" blockers={len(blockers)} artifact={path} — reproduce this"
        f" verdict VERBATIM to the operator; paraphrase is a relay."
    )


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
    ledger_record = _record_reviewer(session_id, agent_id, text)
    qa = _run_qa(text, raw)
    _record(session_id, agent_id, qa)

    # The nudge must reach the ORCHESTRATOR. Claude Code discards hook
    # stderr at exit 0 (it only surfaces stderr on a deny/exit 2), so a
    # stderr nudge here would be inert. additionalContext on stdout is the
    # channel the model actually receives.
    parts = [p for p in (_reviewer_channel(ledger_record), _nudge(agent_id, qa)) if p]
    if parts:
        emit_additional_context("SubagentStop", "\n".join(parts))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
