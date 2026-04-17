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

if ([string]::IsNullOrWhiteSpace($env:ARKAOS_ROOT)) {
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

$python = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python -ErrorAction SilentlyContinue }
if (-not $python) { exit 0 }

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

$pyScript | & $python.Source - | Out-Null

# Belt-and-braces marker cleanup (safe even if the Python block crashed).
if ($sessionId -match '^[A-Za-z0-9._-]{1,128}$') {
    Remove-Item -LiteralPath $wfMarker -ErrorAction SilentlyContinue
}

exit 0
