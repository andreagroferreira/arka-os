"""SubagentStop — consolidated entrypoint (F2-4, Claude Code reform).

Fires when a dispatched subagent (Task tool) finishes. Three jobs, all
WARN-only (this hook never blocks — the subagent already ran):

1. Persist the subagent's final output to the session store so the
   orchestrator's audit trail includes what each specialist produced
   (the ArkaOS QG story: nothing a specialist ships is invisible).
2. Run the same honesty checks the Stop hook runs on the main turn —
   phantom-action (does the output narrate effects with no tool calls?)
   and meta-tag presence — and record the result to telemetry.
3. For Quality Gate reviewers and the aggregator, capture the output
   verbatim to the reviewer ledger (``core/governance/reviewer_ledger``)
   so no aggregator paraphrase sits between a verdict and the operator.

This hook writes NOTHING to stdout. SubagentStop's additionalContext is
"delivered to the subagent" (2.1.220 contract), so anything emitted here
wakes the agent that just stopped rather than informing the
orchestrator. The orchestrator is told at its own turn end, by the Stop
hook.

Telemetry (warn mode, same discipline as the Stop hook): one line per
subagent to ``~/.arkaos/telemetry/subagent-stop.jsonl``. Gate flag
``ARKA_SUBAGENT_QA`` = ``warn`` (default) | ``off``.
"""

from __future__ import annotations

import json
import os
import re
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
# What flow_enforcer._extract_text yields when a turn's last content
# block is a tool call rather than prose.
_PLACEHOLDER_RE = re.compile(r"(<tool_use:[^>]*>\s*)+")
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


def _subagent_text(
    stdin_json: dict, transcript_path: str, raw: str | None
) -> tuple[str, str]:
    """The SUBAGENT's own last message and WHERE it came from.

    The source tag is what gates the ledger — see ``_attributable``.

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
        return direct, "payload"

    agent_transcript = get_str(stdin_json, "agent_transcript_path")
    if agent_transcript and not _same_file(agent_transcript, transcript_path):
        scoped = _last_message(agent_transcript, None)
        if scoped:
            return scoped, "agent-transcript"

    # No subagent-scoped source. The text below is the PARENT's — usable
    # for the QA counters, never for a ledger record.
    return _last_message(transcript_path, raw), "parent"


def _same_file(candidate: str, parent: str) -> bool:
    """True when both paths resolve to the same file.

    A plain string comparison is bypassed by a symlink or a relative
    path pointing back at the parent transcript — the source of the
    round-1 fabrication.
    """
    if candidate == parent:
        return True
    try:
        return Path(candidate).resolve() == Path(parent).resolve()
    except (OSError, ValueError):
        return False


def _last_message(path: str, raw: str | None) -> str:
    try:
        from core.workflow.flow_enforcer import _load_last_assistant_messages

        msgs = _load_last_assistant_messages(path, 1, raw_text=raw)
        return msgs[-1] if msgs else ""
    except Exception:  # best-effort — hook never breaks
        return ""


def _attributable(source: str, text: str) -> bool:
    """True only when the text provably came from the subagent itself.

    Keyed on where the text ACTUALLY came from, not on which payload
    field was present: an ``agent_transcript_path`` that is empty or
    unreadable silently falls through to the parent, and gating on the
    field alone would sign the orchestrator's words with a reviewer's
    name — the round-1 failure.

    A tool-call placeholder (``<tool_use:Write>``) is not a verdict
    either; it is what a transcript tail serialises to when the agent's
    last act was a tool call.
    """
    if source not in ("payload", "agent-transcript"):
        return False
    stripped = text.strip()
    return bool(stripped) and not _PLACEHOLDER_RE.fullmatch(stripped)


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
    source: str, session_id: str, agent_id: str, text: str
) -> dict | None:
    """Capture to the ledger only when attribution is proven."""
    if not _attributable(source, text):
        return None
    return _record_reviewer(session_id, agent_id, text)


def _nudge(agent_id: str, qa: dict) -> str:
    """The QA concern in one line, or "" when there is none.

    No longer emitted here — SubagentStop context wakes the subagent it
    describes, and a Quality Gate verdict is deliverable-shaped by
    construction, so this re-entered every reviewer that omitted an
    ``[arka:meta]`` line (65 measured re-entries). The Stop hook carries
    it to the orchestrator instead.
    """
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
    text, source = _subagent_text(stdin_json, transcript_path, raw)
    if not text:
        return 0

    _persist_output(session_id, agent_id, text)
    ledger = _ledger_capture(source, session_id, agent_id, text)
    qa = _run_qa(text, raw)
    _record(session_id, agent_id, qa)
    _queue_for_orchestrator(session_id, ledger, _nudge(agent_id, qa))
    return 0


def _queue_for_orchestrator(
    session_id: str, ledger: dict | None, nudge: str
) -> None:
    """Hand the orchestrator its notice via the Stop hook, not this one.

    The 2.1.220 contract is explicit: SubagentStop's additionalContext is
    "delivered to the subagent; the subagent continues so it can act on
    it", while Stop's is "delivered to the model". Emitting here woke the
    agent that just finished — 65 measured re-entries, and 15 ledger
    records for 3 reviewer dispatches. The notice is queued instead and
    read at the orchestrator's own turn end
    (``core.governance.reviewer_ledger.queue_notice``).
    """
    if not session_id or (ledger is None and not nudge):
        return
    try:
        from core.governance.reviewer_ledger import queue_notice

        queue_notice(session_id, ledger, nudge)
    except Exception:  # notices are best-effort — the hook never breaks
        pass


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
