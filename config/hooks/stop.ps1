# ============================================================================
# ArkaOS v2 — Stop Hook (Windows PowerShell, WARN mode v1)
#
# Parity with config/hooks/stop.sh. Observes whether a flow-required session
# closed with [arka:phase:13] or [arka:trivial]. Logs to telemetry; never
# blocks in v1.
# ============================================================================

$ErrorActionPreference = "SilentlyContinue"

$inputJson = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($inputJson)) { exit 0 }

try {
    $inp = $inputJson | ConvertFrom-Json
} catch {
    exit 0
}

$sessionId = [string]$inp.session_id
$transcriptPath = [string]$inp.transcript_path
$stopHookActive = [string]$inp.stop_hook_active
$cwd = [string]$inp.cwd

if ($stopHookActive -eq "true") { exit 0 }

$wfMarker = Join-Path "/tmp/arkaos-wf-required" $sessionId
if ([string]::IsNullOrWhiteSpace($sessionId) -or -not (Test-Path $wfMarker)) {
    exit 0
}

# Resolve ARKAOS_ROOT via the validated shared resolver: .repo-path can
# point at a purged npx cache; fall through to the ~/.arkaos/lib snapshot
# instead of exporting a dead root.
$arkaLibEarly = Join-Path $PSScriptRoot "_lib\arka_python.ps1"
if (Test-Path -LiteralPath $arkaLibEarly) { . $arkaLibEarly }
if (Get-Command Resolve-ArkaRoot -ErrorAction SilentlyContinue) {
    $env:ARKAOS_ROOT = Resolve-ArkaRoot
} elseif ([string]::IsNullOrWhiteSpace($env:ARKAOS_ROOT)) {
    # Legacy chain (pre-snapshot _lib deployment)
    $repoPathFile = Join-Path $HOME ".arkaos/.repo-path"
    if (Test-Path $repoPathFile) {
        $env:ARKAOS_ROOT = (Get-Content $repoPathFile -Raw).Trim()
    } elseif (Test-Path (Join-Path $HOME ".arkaos")) {
        $env:ARKAOS_ROOT = (Join-Path $HOME ".arkaos")
    } else {
        $env:ARKAOS_ROOT = if ($env:ARKA_OS) { $env:ARKA_OS } else { Join-Path $HOME ".claude/skills/arkaos" }
    }
}

$enforcerPy = Join-Path $env:ARKAOS_ROOT "core/workflow/flow_enforcer.py"
if (-not (Test-Path $enforcerPy)) { exit 0 }

# Shared resolver (venv-first, yaml-verified). Mirrors _lib/arka_python.sh.
$arkaLib = Join-Path $PSScriptRoot "_lib\arka_python.ps1"
if (Test-Path -LiteralPath $arkaLib) { . $arkaLib }
$pythonExe = $env:ARKA_PY
if (-not $pythonExe) { exit 0 }

$env:SESSION_ID_VAL = $sessionId
$env:TRANSCRIPT_PATH_VAL = $transcriptPath
$env:CWD_VAL = $cwd

$pyScript = @'
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.environ["ARKAOS_ROOT"])
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

messages = _load_last_assistant_messages(transcript_path, n=1)
last = messages[-1] if messages else ""

phase13 = bool(re.search(r"\[arka:phase:13\]", last, re.IGNORECASE))
trivial = bool(re.search(r"\[arka:trivial\]", last, re.IGNORECASE))

entry = {
    "ts": datetime.now(timezone.utc).isoformat(),
    "session_id": session_id,
    "cwd": cwd,
    "event": "stop-hook-flow-check",
    "closing_marker_found": phase13 or trivial,
    "phase13": phase13,
    "trivial": trivial,
    "mode": "warn",
}

try:
    TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TELEMETRY_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
except Exception:
    pass

try:
    clear_flow_required(session_id)
except Exception:
    pass
'@

$pyScript | & $pythonExe - | Out-Null

# ─── Auto-documentor enqueue (fire-and-forget) ─────────────────────────
# Queues a background job when classifier flagged flow, QG approved, and
# external research happened. Never blocks the Stop hook.
$env:SESSION_ID_VAL = $sessionId
$env:TRANSCRIPT_PATH_VAL = $transcriptPath
$env:CWD_VAL = $cwd
$env:ARKAOS_ROOT = $env:ARKAOS_ROOT

$autoDocScript = @'
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.environ.get("ARKAOS_ROOT", ""))
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
'@

try {
    $autoDocScript | & $pythonExe - | Out-Null
} catch {
    # Swallow — enqueue is fire-and-forget.
}

# ─── Governance parity (skill capture + warn-only detectors) ───────────
# config/hooks/stop.sh delegates the whole event to `python -m
# core.hooks.stop`, which runs seventeen core modules. This port
# reimplements the event inline and reached only two of them, so four
# detectors that exist, are tested and are wired on POSIX never ran on
# Windows at all — most visibly skill_proposer, whose constitution rule
# (mandatory-skill-evaluation) mandates a capability sweep after every
# completed task.
#
# Scope is deliberately the NON-ENFORCEMENT subset: these four write
# proposals and diagnostic state only. The gating checks
# (closing_marker_check, meta_tag_check, kb_cite_check, dna_fidelity)
# are left out of this change — they feed enforcement surfaces and
# deserve their own baseline on Windows before being switched on.
$governanceScript = @'
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ.get("ARKAOS_ROOT", ""))
try:
    from core.workflow.flow_enforcer import _load_last_assistant_messages
except Exception:
    sys.exit(0)

transcript_path = os.environ.get("TRANSCRIPT_PATH_VAL", "")
session_id = os.environ.get("SESSION_ID_VAL", "")
if not transcript_path:
    sys.exit(0)

try:
    msgs = _load_last_assistant_messages(transcript_path, n=1)
    last = msgs[-1] if msgs else ""
except Exception:
    last = ""

raw = None
try:
    raw = Path(transcript_path).read_text(encoding="utf-8", errors="replace")
except Exception:
    raw = None


def _write_tmp_state(prefix, sid, payload):
    """Mirror of core.hooks.stop._write_tmp_state (best-effort)."""
    if not sid:
        return
    try:
        import json

        from core.shared.temp_paths import arkaos_temp_dir

        target = arkaos_temp_dir(prefix)
        target.mkdir(parents=True, exist_ok=True)
        (target / f"{sid}.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
    except Exception:
        pass


safe_sid = None
try:
    from core.shared.safe_session_id import safe_session_id

    safe_sid = safe_session_id(session_id)
except Exception:
    safe_sid = None

# 1. Capability capture — the constitution rule this port was missing.
try:
    from core.governance.skill_proposer import evaluate as _eval_skill

    _eval_skill(last)
except Exception:
    pass

# 2. Sycophancy (warn-only telemetry).
try:
    from core.governance.sycophancy_detector import detect_sycophancy

    sv = detect_sycophancy(last)
    if sv.is_sycophantic and safe_sid:
        _write_tmp_state("arkaos-sycophancy", safe_sid, {
            "is_sycophantic": sv.is_sycophantic,
            "signals": sv.signals,
            "confidence": sv.confidence,
        })
except Exception:
    pass

# 3. Phantom actions — narrated effects with no tool call in the turn.
try:
    from core.governance.phantom_action_check import check_phantom_actions

    pr = check_phantom_actions(last, raw)
    if safe_sid:
        _write_tmp_state("arkaos-phantom", safe_sid, {
            "passed": pr.passed,
            "reason": pr.reason,
            "claims": pr.claims,
            "suggestion": pr.suggestion,
        })
except Exception:
    pass

# 4. Tool loops.
try:
    from core.governance.tool_loop_check import check_tool_loops

    lv = check_tool_loops(raw)
    if lv.detected and safe_sid:
        _write_tmp_state("arkaos-tool-loop", safe_sid, {
            "tool": lv.tool,
            "repeats": lv.repeats,
            "pattern": lv.pattern,
            "total_tool_uses": lv.total_tool_uses,
        })
except Exception:
    pass
'@

try {
    $governanceScript | & $pythonExe - | Out-Null
} catch {
    # Swallow — governance observation must never affect the Stop hook.
}

# Belt-and-braces marker cleanup (safe even if the Python block crashed).
if ($sessionId -match '^[A-Za-z0-9._-]{1,128}$') {
    Remove-Item -LiteralPath $wfMarker -ErrorAction SilentlyContinue
}

exit 0
