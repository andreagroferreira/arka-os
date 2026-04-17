# ============================================================================
# ArkaOS v2 — PreToolUse Hook (Windows PowerShell)
#
# Parity with config/hooks/pre-tool-use.sh. Blocks Write/Edit/MultiEdit when
# the mandatory 13-phase flow is required for the session AND the assistant
# has not emitted a flow marker in its last 3 messages of the transcript.
#
# Delegates the decision to core/workflow/flow_enforcer.py.
#
# Exit 0 = allow (silent). Exit 2 = deny + structured hookSpecificOutput JSON.
# ============================================================================

$ErrorActionPreference = "SilentlyContinue"

# --- Read stdin JSON ---
$inputJson = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($inputJson)) { exit 0 }

try {
    $inp = $inputJson | ConvertFrom-Json
} catch {
    exit 0
}

$toolName = [string]$inp.tool_name
$transcriptPath = [string]$inp.transcript_path
$sessionId = [string]$inp.session_id
$cwd = [string]$inp.cwd

# --- Fast allow: not a gated tool ---
if ($toolName -ne "Write" -and $toolName -ne "Edit" -and $toolName -ne "MultiEdit") {
    exit 0
}

# --- Resolve ARKAOS_ROOT ---
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

# --- Delegate to Python enforcer ---
$env:TOOL_NAME = $toolName
$env:TRANSCRIPT_PATH = $transcriptPath
$env:SESSION_ID = $sessionId
$env:CWD = $cwd

$pyScript = @'
import json
import os
import sys

sys.path.insert(0, os.environ["ARKAOS_ROOT"])
try:
    from core.workflow.flow_enforcer import evaluate, record_telemetry
except Exception:
    print(json.dumps({"allow": True, "reason": "enforcer-import-failed"}))
    sys.exit(0)

decision = evaluate(
    tool_name=os.environ.get("TOOL_NAME", ""),
    transcript_path=os.environ.get("TRANSCRIPT_PATH", ""),
    session_id=os.environ.get("SESSION_ID", ""),
    cwd=os.environ.get("CWD", ""),
)
try:
    record_telemetry(
        session_id=os.environ.get("SESSION_ID", ""),
        tool=os.environ.get("TOOL_NAME", ""),
        decision=decision,
        cwd=os.environ.get("CWD", ""),
    )
except Exception:
    pass
print(json.dumps({
    "allow": decision.allow,
    "reason": decision.reason,
    "stderr_msg": decision.to_stderr_message(),
}))
'@

$decisionJson = $pyScript | & $python.Source -
if ([string]::IsNullOrWhiteSpace($decisionJson)) { exit 0 }

try {
    $decision = $decisionJson | ConvertFrom-Json
} catch {
    exit 0
}

if ($decision.allow) { exit 0 }

# --- Deny path ---
[Console]::Error.WriteLine($decision.stderr_msg)

$denyOut = @{
    hookSpecificOutput = @{
        hookEventName = "PreToolUse"
        permissionDecision = "deny"
        permissionDecisionReason = $decision.stderr_msg
    }
} | ConvertTo-Json -Compress -Depth 5

Write-Output $denyOut
exit 2
