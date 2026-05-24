#!/usr/bin/env bash
# ============================================================================
# ArkaOS v2 — Stop Hook (Flow Completion Validator, WARN mode v1)
#
# When the classifier marked the session as flow-required, this hook checks
# whether the final assistant message contains [arka:phase:13] or
# [arka:trivial]. If absent, a structured warning is appended to
# ~/.arkaos/telemetry/enforcement.jsonl. The hook NEVER blocks in v1.
#
# Promotion to strict mode is planned for v2.21.0 after ≥ 2 weeks of clean
# telemetry. Until then, this hook is observation only.
#
# Timeout: 5s | Always exit 0.
# ============================================================================

input=$(cat)

SESSION_ID=""
TRANSCRIPT_PATH=""
STOP_HOOK_ACTIVE=""
CWD=""
if command -v jq &>/dev/null; then
  SESSION_ID=$(echo "$input" | jq -r '.session_id // ""' 2>/dev/null)
  TRANSCRIPT_PATH=$(echo "$input" | jq -r '.transcript_path // ""' 2>/dev/null)
  STOP_HOOK_ACTIVE=$(echo "$input" | jq -r '.stop_hook_active // ""' 2>/dev/null)
  CWD=$(echo "$input" | jq -r '.cwd // ""' 2>/dev/null)
fi

# Prevent infinite loops when Stop hook was triggered by its own decision.
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  exit 0
fi

# Only evaluate sessions where the classifier flagged a creation intent.
WF_MARKER="/tmp/arkaos-wf-required/$SESSION_ID"
if [ -z "$SESSION_ID" ] || [ ! -f "$WF_MARKER" ]; then
  exit 0
fi

# Resolve ARKAOS_ROOT
if [ -z "${ARKAOS_ROOT:-}" ]; then
  if [ -f "$HOME/.arkaos/.repo-path" ]; then
    ARKAOS_ROOT=$(cat "$HOME/.arkaos/.repo-path")
  elif [ -d "$HOME/.arkaos" ]; then
    ARKAOS_ROOT="$HOME/.arkaos"
  else
    ARKAOS_ROOT="${ARKA_OS:-$HOME/.claude/skills/arkaos}"
  fi
fi

if ! command -v python3 &>/dev/null; then
  exit 0
fi
if [ ! -f "$ARKAOS_ROOT/core/workflow/flow_enforcer.py" ]; then
  exit 0
fi

# Reuse the last-messages reader to check for a closing phase marker.
SESSION_ID_VAL="$SESSION_ID" \
TRANSCRIPT_PATH_VAL="$TRANSCRIPT_PATH" \
CWD_VAL="$CWD" \
ARKAOS_ROOT_VAL="$ARKAOS_ROOT" \
python3 - <<'PY' 2>/dev/null
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.environ["ARKAOS_ROOT_VAL"])
try:
    from core.workflow.flow_enforcer import (
        _load_last_assistant_messages,
        TELEMETRY_PATH,
        clear_flow_required,
    )
except Exception:
    sys.exit(0)

session_id = os.environ.get("SESSION_ID_VAL", "")
transcript_path = os.environ.get("TRANSCRIPT_PATH_VAL", "")
cwd = os.environ.get("CWD_VAL", "")

# Only inspect the very last assistant message for closing markers.
messages = _load_last_assistant_messages(transcript_path, n=1)
last = messages[-1] if messages else ""

phase13 = bool(re.search(r"\[arka:phase:13\]", last, re.IGNORECASE))
trivial = bool(re.search(r"\[arka:trivial\]", last, re.IGNORECASE))
closing_ok = phase13 or trivial

# PR12 v2.34.0 — Transparency tag measurement (warn-only).
# The [arka:meta] tag should appear on every substantive response that
# consulted KB / research / persona. Absence here is recorded so we can
# measure compliance before promoting to enforcement in a later PR.
meta_tag_found = bool(re.search(r"\[arka:meta\]", last, re.IGNORECASE))

# PR13 v2.35.0 — Sycophancy detection (warn-only).
# Heuristic detector records when a response shows agreement-without-
# critique, pure-agreement-standalone, recommendation-without-reference-
# company, or missing-critic-verdict signals. Telemetry only; never
# blocks. Promotion to hard enforce is a later PR after baseline data.
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

# PR18 v2.40.0 — KB citation soft-block. Records whether the closing
# assistant message cited the vault on an ArkaOS topic. Result is also
# persisted to /tmp/arkaos-cite/<session>.json so the next UserPromptSubmit
# can surface a nudge if passed=False. Non-blocking; never raises.
cite_passed = True
cite_reason = "trivial"
cite_count = 0
cite_topic_score = 0.0
cite_suggestion: str | None = None
try:
    from core.governance.kb_cite_check import check_citation
    cr = check_citation(last)
    cite_passed = cr.passed
    cite_reason = cr.reason
    cite_count = cr.citation_count
    cite_topic_score = cr.topic_score
    cite_suggestion = cr.suggestion
    # PR18 security fix: session_id comes from the runtime via stdin JSON
    # and is untrusted. Reuse the shared allowlist before building any
    # filesystem path. Reject (skip write) on anything outside
    # [A-Za-z0-9._-]{1,128} — no `..`, no slashes, no whitespace, no NUL.
    try:
        from core.shared.safe_session_id import safe_session_id as _safe_sid
        safe_sid = _safe_sid(session_id)
    except Exception:
        safe_sid = None
    if safe_sid:
        # PR25 v2.46.1 — restrict cite-file permissions on shared
        # multi-user systems. umask(0o077) makes the directory and the
        # JSON file owner-only (mode 0600 / 0700). No-op on single-user
        # dev boxes; defence in depth otherwise.
        prev_umask = os.umask(0o077)
        try:
            cite_dir = Path("/tmp/arkaos-cite")
            cite_dir.mkdir(parents=True, exist_ok=True)
            cite_path = cite_dir / f"{safe_sid}.json"
            cite_payload = {
                "passed": cr.passed,
                "reason": cr.reason,
                "suggestion": cr.suggestion,
                "citation_count": cr.citation_count,
                "topic_score": cr.topic_score,
            }
            cite_path.write_text(json.dumps(cite_payload), encoding="utf-8")
        finally:
            os.umask(prev_umask)
except Exception:
    pass

# PR30 v2.49.0 — Meta-tag soft block. Mirrors the KB cite-check
# pipeline. Records whether the closing message carried the required
# [arka:meta] one-liner; persists result to /tmp/arkaos-meta/<session>.json
# so the next UserPromptSubmit can surface a nudge if missing.
meta_passed = True
meta_reason = "trivial"
meta_suggestion: str | None = None
try:
    from core.governance.meta_tag_check import check_meta_tag
    mr = check_meta_tag(last)
    meta_passed = mr.passed
    meta_reason = mr.reason
    meta_suggestion = mr.suggestion
    if safe_sid:
        prev_umask = os.umask(0o077)
        try:
            meta_dir = Path("/tmp/arkaos-meta")
            meta_dir.mkdir(parents=True, exist_ok=True)
            meta_path = meta_dir / f"{safe_sid}.json"
            meta_path.write_text(
                json.dumps({
                    "passed": mr.passed,
                    "reason": mr.reason,
                    "suggestion": mr.suggestion,
                }),
                encoding="utf-8",
            )
        finally:
            os.umask(prev_umask)
except Exception:
    pass

entry = {
    "ts": datetime.now(timezone.utc).isoformat(),
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
    "mode": "warn",
}

try:
    TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TELEMETRY_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
except Exception:
    pass

# Clean up the session marker once Stop has evaluated.
try:
    clear_flow_required(session_id)
except Exception:
    pass
PY

# ─── Auto-documentor enqueue (fire-and-forget) ──────────────────────────
# Queues a background job when:
#   (a) the session was flagged flow-required (classifier match above),
#   (b) Quality Gate approved — last assistant message carries
#       `[arka:qg:approved]`, OR the most recent entry for this session
#       in ~/.arkaos/telemetry/qg.jsonl has verdict APPROVED, AND
#   (c) at least one external research tool was invoked this session
#       (URL, WebFetch/WebSearch, Context7, Firecrawl in the transcript).
# The actual documentation runs async via `core/jobs/auto_doc_worker.py`;
# this block never blocks Stop — 2s Python budget, errors swallowed.
if command -v timeout &>/dev/null; then
  _ARKA_AUTO_DOC_RUNNER=(timeout 2s python3 -)
elif command -v gtimeout &>/dev/null; then
  _ARKA_AUTO_DOC_RUNNER=(gtimeout 2s python3 -)
else
  _ARKA_AUTO_DOC_RUNNER=(python3 -)
fi

SESSION_ID_VAL="$SESSION_ID" \
TRANSCRIPT_PATH_VAL="$TRANSCRIPT_PATH" \
CWD_VAL="$CWD" \
ARKAOS_ROOT_VAL="$ARKAOS_ROOT" \
"${_ARKA_AUTO_DOC_RUNNER[@]}" <<'PY' 2>/dev/null || true
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.environ["ARKAOS_ROOT_VAL"])
try:
    from core.jobs.auto_doc_worker import enqueue_job
    from core.workflow.flow_enforcer import _load_last_assistant_messages
except Exception:
    sys.exit(0)

session_id = os.environ.get("SESSION_ID_VAL", "")
transcript_path = os.environ.get("TRANSCRIPT_PATH_VAL", "")
if not session_id or not transcript_path:
    sys.exit(0)

last = ""
try:
    msgs = _load_last_assistant_messages(transcript_path, n=1)
    last = msgs[-1] if msgs else ""
except Exception:
    last = ""

qg_approved = bool(re.search(r"\[arka:qg:approved\]", last, re.IGNORECASE))
if not qg_approved:
    qg_log = Path.home() / ".arkaos" / "telemetry" / "qg.jsonl"
    if qg_log.exists():
        try:
            for line in reversed(qg_log.read_text(encoding="utf-8").splitlines()):
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("session_id") == session_id:
                    qg_approved = rec.get("verdict", "").upper() == "APPROVED"
                    break
        except Exception:
            pass
if not qg_approved:
    sys.exit(0)

# Heuristic check that some external research happened this session.
external_markers = (
    "WebFetch", "WebSearch", "mcp__context7", "mcp__firecrawl",
    "http://", "https://",
)
has_external = False
try:
    data = Path(transcript_path).read_text(encoding="utf-8", errors="replace")
    has_external = any(marker in data for marker in external_markers)
except Exception:
    has_external = False
if not has_external:
    sys.exit(0)

try:
    enqueue_job(session_id, transcript_path, "APPROVED")
except Exception:
    pass
PY

# Belt-and-braces: remove the marker at shell level in case the Python
# block above crashed before reaching clear_flow_required(). Session_id
# is already validated by the Python helper; this shell remove is scoped
# to the exact marker path and is idempotent.
case "$SESSION_ID" in
  *[!A-Za-z0-9._-]*|"") ;;  # reject unsafe/empty session ids
  *) rm -f "$WF_MARKER" 2>/dev/null ;;
esac

exit 0
