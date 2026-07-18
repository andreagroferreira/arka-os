"""Stop — consolidated entrypoint (PR-6 v4.1.0 hook hygiene).

Replaces the ~16 python3/jq spawn sites of the old ``stop.sh`` with ONE
python process. WARN mode: this hook NEVER blocks — always exits 0.

Section order preserved exactly:
    1. DNA fidelity check (persona from last dispatch/routing marker)
    2. stop_hook_active loop guard
    3. Native usage cost capture (runs BEFORE the WF_MARKER gate — the
       llm-cost blind spot covers ALL sessions)
    4. WF_MARKER gate (/tmp/arkaos-wf-required/<session>)
    5. Flow completion validation + soft-block checks (meta_tag_found,
       [arka:meta], kb-cite, sycophancy, closing marker, skill proposer,
       kb=N reconciliation) → telemetry entry (mode: warn)
    6. Gate checkpoint persistence (core/workflow/gate_checkpoint.py)
    7. Stop-lint batch enqueue (detached scoped lint —
       core/governance/stop_lint.py, warn-only telemetry)
    8. Auto-documentor enqueue (flow-required + QG APPROVED + external
       research heuristic)
    9. Belt-and-braces WF_MARKER removal

The transcript is read from disk ONCE and shared across native-usage,
flow validation, gate checkpoint, and the auto-doc external-research
heuristic (the old hook parsed it four times).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from core.hooks._shared import (
    ensure_root_on_path,
    get_str,
    read_stdin_json,
    repo_path,
    resolve_arkaos_root,
    safe_session_id,
)
from core.shared.temp_paths import arkaos_temp_dir

_DISPATCH_RE = re.compile(
    r"\[arka:dispatch\][ \t]*[A-Za-z0-9_-]+[ \t]*->[ \t]*([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)
_ROUTING_RE = re.compile(
    r"\[arka:routing\][ \t]*[A-Za-z0-9_-]+[ \t]*->[ \t]*([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)

_EXTERNAL_MARKERS = (
    "WebFetch", "WebSearch", "mcp__context7", "mcp__firecrawl",
    "http://", "https://",
)


def _read_transcript(transcript_path: str) -> str | None:
    """Single shared disk read for the whole hook invocation."""
    if not transcript_path:
        return None
    try:
        return Path(transcript_path).read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError:
        return None


def _extract_persona(assistant_msg: str) -> str:
    """Dispatch marker wins over routing; latest match wins."""
    dispatch_hits = _DISPATCH_RE.findall(assistant_msg)
    if dispatch_hits:
        return dispatch_hits[-1].lower()
    routing_hits = _ROUTING_RE.findall(assistant_msg)
    if routing_hits:
        return routing_hits[-1].lower()
    return ""


def _dna_fidelity(assistant_msg: str, session_id: str) -> None:
    if not assistant_msg or not session_id:
        return
    persona = _extract_persona(assistant_msg)
    if not persona:
        return
    try:
        from core.governance.dna_fidelity import check_fidelity, record_fidelity
        violations = check_fidelity(persona, assistant_msg)
        record_fidelity(persona, session_id, violations)
    except Exception:
        pass


def _native_usage(transcript_path: str, session_id: str, raw: str | None) -> None:
    if not transcript_path or not session_id:
        return
    try:
        from core.runtime.native_usage import record_native_usage
        record_native_usage(transcript_path, session_id, raw_text=raw)
    except Exception:
        pass


def _write_tmp_state(subdir: str, safe_sid: str, payload: dict) -> None:
    """Owner-only /tmp state file (umask 0o077 — PR25 v2.46.1)."""
    prev_umask = os.umask(0o077)
    try:
        state_dir = arkaos_temp_dir(subdir)
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / f"{safe_sid}.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
    finally:
        os.umask(prev_umask)


def _flow_checks(
    session_id: str, transcript_path: str, cwd: str,
    effort_level: str, raw: str | None,
) -> None:
    """Sections 5-6: soft-block checks + telemetry + gate checkpoint."""
    try:
        from core.workflow.flow_enforcer import (
            TELEMETRY_PATH,
            _load_last_assistant_messages,
            clear_flow_required,
        )
    except Exception:
        return

    # Parse once; the last message drives every check, the 20-window
    # feeds the gate checkpoint.
    messages = _load_last_assistant_messages(
        transcript_path, n=20, raw_text=raw
    )
    last = messages[-1] if messages else ""

    gate4 = bool(re.search(r"\[arka:gate:4\]", last, re.IGNORECASE))
    phase13 = bool(re.search(r"\[arka:phase:13\]", last, re.IGNORECASE))
    trivial = bool(re.search(r"\[arka:trivial\]", last, re.IGNORECASE))
    closing_ok = gate4 or phase13 or trivial

    # v4.1.0 — persist gate transitions for structured resume.
    try:
        from core.workflow.gate_checkpoint import checkpoint as _gate_checkpoint
        _gate_checkpoint(
            transcript_path, session_id, project=cwd, messages=messages
        )
    except Exception:
        pass

    # Interaction Reform PR3 — a turn whose furthest gate is Gate 2 means
    # a plan is on the table awaiting the user; record it so the next
    # user message can be classified as approval (plan_approval state).
    # Scope to the CURRENT turn's messages (QG 2026-07-09, PR4
    # prerequisite #1, re-review): scanning the whole 20-message window
    # would re-trigger on a PRIOR turn's [arka:gate:2] still in the
    # window and silently invalidate a live approval. Turn-scoping keeps
    # the mid-turn fix (gate:2 + a separate marker-less summary in the
    # same turn) while never spanning turns. Falls back to the last
    # message only when the transcript can't be turn-parsed.
    try:
        from core.governance.phantom_action_check import (
            current_turn_assistant_texts,
        )
        from core.workflow import plan_approval
        from core.workflow.gate_checkpoint import extract_latest_gate
        turn = current_turn_assistant_texts(raw)
        scan = turn if turn is not None else [last]
        if session_id and extract_latest_gate(scan) == 2:
            plan_approval.mark_presented(session_id)
    except Exception:
        pass

    meta_tag_found = bool(re.search(r"\[arka:meta\]", last, re.IGNORECASE))

    sycophancy_signals: list = []
    sycophancy_confidence = 0.0
    is_sycophantic = False
    try:
        from core.governance.sycophancy_detector import detect_sycophancy
        sv = detect_sycophancy(last)
        sycophancy_signals = sv.signals
        sycophancy_confidence = sv.confidence
        is_sycophantic = sv.is_sycophantic
    except Exception:
        pass

    cite_passed = True
    cite_reason = "trivial"
    cite_count = 0
    cite_topic_score = 0.0
    safe_sid: str | None = None
    try:
        from core.governance.kb_cite_check import check_citation
        cr = check_citation(last)
        cite_passed = cr.passed
        cite_reason = cr.reason
        cite_count = cr.citation_count
        cite_topic_score = cr.topic_score
        safe_sid = safe_session_id(session_id)
        if safe_sid:
            _write_tmp_state("arkaos-cite", safe_sid, {
                "passed": cr.passed,
                "reason": cr.reason,
                "suggestion": cr.suggestion,
                "citation_count": cr.citation_count,
                "topic_score": cr.topic_score,
            })
    except Exception:
        pass

    try:
        from core.governance.skill_proposer import evaluate as _eval_skill
        _eval_skill(last)
    except Exception:
        pass

    meta_passed = True
    meta_reason = "trivial"
    try:
        from core.governance.meta_tag_check import check_meta_tag
        mr = check_meta_tag(last)
        meta_passed = mr.passed
        meta_reason = mr.reason
        if safe_sid:
            _write_tmp_state("arkaos-meta", safe_sid, {
                "passed": mr.passed,
                "reason": mr.reason,
                "suggestion": mr.suggestion,
            })
    except Exception:
        pass

    # Structural honesty PR-2 — kb=N reconciliation (warn-only).
    kb_reported = None
    kb_injected = None
    kb_inflated = False
    try:
        from core.governance.meta_tag_check import (
            parse_reported_kb,
            reconcile_kb_count,
        )
        kb_reported = parse_reported_kb(last)
        if safe_sid:
            injected_path = (
                arkaos_temp_dir("arkaos-kb-injected") / f"{safe_sid}.json"
            )
            if injected_path.exists():
                injected_data = json.loads(
                    injected_path.read_text(encoding="utf-8")
                )
                raw_injected = injected_data.get("kb_injected")
                kb_injected = (
                    int(raw_injected) if raw_injected is not None else None
                )
        reconciled = reconcile_kb_count(kb_reported, kb_injected)
        kb_reported = reconciled["kb_reported"]
        kb_injected = reconciled["kb_injected"]
        kb_inflated = reconciled["kb_inflated"]
    except Exception:
        pass

    closing_check_passed = True
    closing_check_reason = "trivial"
    try:
        from core.governance.closing_marker_check import check_closing_marker
        cmr = check_closing_marker(last)
        closing_check_passed = cmr.passed
        closing_check_reason = cmr.reason
        if safe_sid:
            _write_tmp_state("arkaos-closing", safe_sid, {
                "passed": cmr.passed,
                "reason": cmr.reason,
                "suggestion": cmr.suggestion,
            })
    except Exception:
        pass

    # Prompt-surface P0 2026-07-08 — phantom-action check (warn-only).
    # Narrated effects without a tool call in the turn = the action did
    # not happen (evidence-flow: evidence, never narration).
    phantom_passed = True
    phantom_reason = "no-claims"
    phantom_claims: list = []
    try:
        from core.governance.phantom_action_check import check_phantom_actions
        pr = check_phantom_actions(last, raw)
        phantom_passed = pr.passed
        phantom_reason = pr.reason
        phantom_claims = pr.claims
        if safe_sid:
            _write_tmp_state("arkaos-phantom", safe_sid, {
                "passed": pr.passed,
                "reason": pr.reason,
                "claims": pr.claims,
                "suggestion": pr.suggestion,
            })
    except Exception:
        pass

    # Context-monitor tool-loop signal (warn-only): turn-boundary scan
    # over the transcript sees every call, fast-pathed ones included.
    loop_detected = False
    loop_tool = ""
    loop_repeats = 0
    loop_pattern = ""
    try:
        from core.governance.tool_loop_check import check_tool_loops
        lv = check_tool_loops(raw)
        loop_detected = lv.detected
        loop_tool = lv.tool
        loop_repeats = lv.repeats
        loop_pattern = lv.pattern
        if lv.detected and safe_sid:
            _write_tmp_state("arkaos-tool-loop", safe_sid, {
                "tool": lv.tool,
                "repeats": lv.repeats,
                "pattern": lv.pattern,
                "total_tool_uses": lv.total_tool_uses,
            })
    except Exception:
        pass

    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "session_id": session_id,
        "cwd": cwd,
        "event": "stop-hook-flow-check",
        "closing_marker_found": closing_ok,
        "phase13": phase13,
        "trivial": trivial,
        "meta_tag_found": meta_tag_found,
        "sycophancy_is_flagged": is_sycophantic,
        "sycophancy_signals": sycophancy_signals,
        "sycophancy_confidence": sycophancy_confidence,
        "kb_cite_passed": cite_passed,
        "kb_cite_reason": cite_reason,
        "kb_cite_count": cite_count,
        "kb_cite_topic_score": cite_topic_score,
        "meta_tag_check_passed": meta_passed,
        "meta_tag_check_reason": meta_reason,
        "kb_reported": kb_reported,
        "kb_injected": kb_injected,
        "kb_inflated": kb_inflated,
        "closing_marker_check_passed": closing_check_passed,
        "closing_marker_check_reason": closing_check_reason,
        "phantom_check_passed": phantom_passed,
        "phantom_check_reason": phantom_reason,
        "phantom_claims": phantom_claims,
        "tool_loop_detected": loop_detected,
        "tool_loop_tool": loop_tool,
        "tool_loop_repeats": loop_repeats,
        "tool_loop_pattern": loop_pattern,
        "effort_level": effort_level,
        "mode": "warn",
    }
    try:
        TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TELEMETRY_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception:
        pass

    with contextlib.suppress(Exception):
        clear_flow_required(session_id)


def _auto_doc_enqueue(
    session_id: str, transcript_path: str, raw: str | None
) -> None:
    """Section 8: fire-and-forget auto-documentor job enqueue."""
    try:
        from core.jobs.auto_doc_worker import enqueue_job
        from core.workflow.flow_enforcer import _load_last_assistant_messages
    except Exception:
        return
    if not session_id or not transcript_path:
        return

    try:
        msgs = _load_last_assistant_messages(transcript_path, 1, raw_text=raw)
        last = msgs[-1] if msgs else ""
    except Exception:
        last = ""

    qg_approved = bool(re.search(r"\[arka:qg:approved\]", last, re.IGNORECASE))
    if not qg_approved:
        qg_log = Path.home() / ".arkaos" / "telemetry" / "qg.jsonl"
        if qg_log.exists():
            try:
                for line in reversed(
                    qg_log.read_text(encoding="utf-8").splitlines()
                ):
                    if not line.strip():
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if rec.get("session_id") == session_id:
                        qg_approved = (
                            rec.get("verdict", "").upper() == "APPROVED"
                        )
                        break
            except Exception:
                pass
    if not qg_approved:
        return

    data = raw if raw is not None else ""
    if not any(marker in data for marker in _EXTERNAL_MARKERS):
        return
    with contextlib.suppress(Exception):
        enqueue_job(session_id, transcript_path, "APPROVED")


def _session_memory_enabled() -> bool:
    """``memory.sessionMemory`` (default True) + env kill-switch."""
    if os.environ.get("ARKA_SESSION_MEMORY", "").strip() == "0":
        return False
    config_path = Path.home() / ".arkaos" / "config.json"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    memory_cfg = data.get("memory") or {}
    return bool(memory_cfg.get("sessionMemory", True))


def _enqueue_turn_capture(session_id: str, transcript_path: str, cwd: str) -> None:
    """F1-A2: fire-and-forget semantic turn capture — runs for EVERY
    turn (before the WF_MARKER gate), all cost paid in the detached
    worker, never on this hook."""
    if not session_id or not transcript_path or not _session_memory_enabled():
        return
    repo = repo_path()
    if not repo or not Path(repo).is_dir():
        return
    try:
        import subprocess
        import sys as _sys
        subprocess.Popen(
            [_sys.executable, "-m", "core.memory.turn_capture",
             session_id, transcript_path, cwd or ""],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ, "PYTHONPATH": repo},
            start_new_session=True,  # same pattern as _enqueue_cognition_capture
        )
    except Exception:
        pass


def _enqueue_stop_lint(session_id: str, cwd: str) -> None:
    """Section 7: detached scoped lint batch — deterministic evidence
    lands in telemetry (stop-lint.jsonl), never on the 5s hook budget."""
    if not cwd or not Path(cwd).is_dir():
        return
    try:
        from core.governance.stop_lint import mode as stop_lint_mode
        if stop_lint_mode() == "off":
            return
        repo = repo_path()
        if not repo or not Path(repo).is_dir():
            return
        import subprocess
        import sys as _sys
        subprocess.Popen(
            [_sys.executable, "-m", "core.governance.stop_lint",
             cwd, session_id or ""],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ, "PYTHONPATH": repo},
            start_new_session=True,  # same pattern as _enqueue_turn_capture
        )
    except Exception:  # best-effort, hook never breaks
        pass


def _enqueue_routing_rebuild() -> None:
    """F1-B1: throttled detached rebuild of routing-scores.json (mtime
    > 1h). One stat on the hot path; the aggregation runs detached."""
    try:
        from core.governance.routing_feedback import stale
        if not stale(max_age_seconds=3600):
            return
        repo = repo_path()
        if not repo or not Path(repo).is_dir():
            return
        import subprocess
        import sys as _sys
        subprocess.Popen(
            [_sys.executable, "-m", "core.governance.routing_feedback_cli",
             "rebuild"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ, "PYTHONPATH": repo},
            start_new_session=True,
        )
    except Exception:
        pass


def main(stdin_json: dict | None = None) -> int:
    if stdin_json is None:
        stdin_json, _ = read_stdin_json()
    root = resolve_arkaos_root()
    ensure_root_on_path(root)

    session_id = get_str(stdin_json, "session_id")
    transcript_path = get_str(stdin_json, "transcript_path")
    stop_hook_active = get_str(stdin_json, "stop_hook_active")
    cwd = get_str(stdin_json, "cwd")
    effort_level = get_str(stdin_json, "effort", "level") or os.environ.get(
        "CLAUDE_EFFORT", ""
    )
    assistant_msg = get_str(stdin_json, "assistant_message")

    _dna_fidelity(assistant_msg, session_id)

    # Prevent infinite loops when Stop was triggered by its own decision.
    if stop_hook_active == "true":
        return 0

    raw = _read_transcript(transcript_path)

    _native_usage(transcript_path, session_id, raw)

    with contextlib.suppress(Exception):
        _enqueue_turn_capture(session_id, transcript_path, cwd)

    _enqueue_routing_rebuild()

    # Only evaluate sessions where the classifier flagged creation intent.
    wf_marker = arkaos_temp_dir("arkaos-wf-required") / session_id if session_id else None
    if wf_marker is None or not safe_session_id(session_id) or not wf_marker.is_file():
        return 0

    if (Path(root) / "core" / "workflow" / "flow_enforcer.py").is_file():
        _flow_checks(session_id, transcript_path, cwd, effort_level, raw)

    _enqueue_stop_lint(session_id, cwd)

    _auto_doc_enqueue(session_id, transcript_path, raw)

    # Belt-and-braces marker removal (session id already allowlisted).
    with contextlib.suppress(OSError):
        wf_marker.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        # Stop hook must never break the turn.
        raise SystemExit(0) from None
