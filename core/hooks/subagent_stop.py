"""SubagentStop — consolidated entrypoint (F2-4, Claude Code reform).

Fires when a dispatched subagent (Task tool) finishes. Three jobs, all
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


def _subagent_text(stdin_json: dict, transcript_path: str, raw: str | None) -> str:
    """The SUBAGENT's own last message, from the payload the runtime sends.

    ``last_assistant_message`` carries the subagent's final text directly
    ("avoids the need to read and parse the transcript file", per the
    2.1.220 hook contract); ``agent_transcript_path`` points at the
    subagent's OWN jsonl (``<session>/subagents/agent-<id>.jsonl``).

    Neither is the parent transcript at ``transcript_path``: that file
    holds only main-scope records, so reading its tail returned the
    orchestrator's in-flight turn — serialised as ``<tool_use:Agent>``,
    which is what every persisted reviewer output on disk contained.
    """
    direct = get_str(stdin_json, "last_assistant_message")
    if direct.strip():
        return direct

    agent_transcript = get_str(stdin_json, "agent_transcript_path")
    if agent_transcript and agent_transcript != transcript_path:
        scoped = _last_message(agent_transcript, None)
        if scoped:
            return scoped

    # No subagent-scoped source: fall back for the QA checks only. The
    # ledger never writes from here — see _attributable().
    return _last_message(transcript_path, raw)


def _last_message(path: str, raw: str | None) -> str:
    try:
        from core.workflow.flow_enforcer import _load_last_assistant_messages

        msgs = _load_last_assistant_messages(path, 1, raw_text=raw)
        return msgs[-1] if msgs else ""
    except Exception:  # best-effort — hook never breaks
        return ""


def _attributable(stdin_json: dict, transcript_path: str) -> bool:
    """True only when the text provably came from the subagent itself.

    Fail closed on attribution: a ledger record is signed evidence
    carrying a reviewer's name, so writing one from an unprovable source
    fabricates it. Missing a verdict is recoverable; a hashed record of
    words the reviewer never wrote is not.
    """
    if get_str(stdin_json, "last_assistant_message").strip():
        return True
    agent_transcript = get_str(stdin_json, "agent_transcript_path")
    return bool(agent_transcript) and agent_transcript != transcript_path


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


def _ledger_capture(
    stdin_json: dict, session_id: str, agent_id: str, text: str
) -> dict | None:
    """Capture to the ledger only when attribution is proven."""
    transcript_path = get_str(stdin_json, "transcript_path")
    if not _attributable(stdin_json, transcript_path):
        return None
    return _record_reviewer(session_id, agent_id, text)


def _reviewer_channel(record: dict | None) -> str:
    """The reviewer's direct line to the orchestrator: verdict + artifact.

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
        f" blockers={len(blockers)} artifact={path} — read the artifact"
        f" and quote the verdict verbatim to the operator; do not"
        f" summarise or paraphrase it."
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
    text = _subagent_text(stdin_json, transcript_path, raw)
    if not text:
        return 0

    _persist_output(session_id, agent_id, text)
    ledger = _ledger_capture(stdin_json, session_id, agent_id, text)
    qa = _run_qa(text, raw)
    _record(session_id, agent_id, qa)
    _emit(ledger, agent_id, qa)
    return 0


def _emit(ledger: dict | None, agent_id: str, qa: dict) -> None:
    """Reviewer verdict line + QA nudge, both to the ORCHESTRATOR.

    Claude Code discards hook stderr at exit 0 (it only surfaces stderr
    on a deny/exit 2), so additionalContext on stdout is the channel the
    model actually receives.
    """
    parts = [p for p in (_reviewer_channel(ledger), _nudge(agent_id, qa)) if p]
    if parts:
        emit_additional_context("SubagentStop", "\n".join(parts))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
