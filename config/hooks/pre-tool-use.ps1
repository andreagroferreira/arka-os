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

$python = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python -ErrorAction SilentlyContinue }
if (-not $python) { exit 0 }

# --- KB-first gate (Task #6, runs before flow-marker gate) ---
$queryHint = ""
if ($inp.tool_input) {
    if ($inp.tool_input.query) { $queryHint = [string]$inp.tool_input.query }
    elseif ($inp.tool_input.prompt) { $queryHint = [string]$inp.tool_input.prompt }
    elseif ($inp.tool_input.url) { $queryHint = [string]$inp.tool_input.url }
    if ($queryHint.Length -gt 500) { $queryHint = $queryHint.Substring(0, 500) }
}

$researchGatePy = Join-Path $env:ARKAOS_ROOT "core/workflow/research_gate.py"
if (Test-Path $researchGatePy) {
    $env:TOOL_NAME = $toolName
    $env:SESSION_ID = $sessionId
    $env:QUERY_HINT = $queryHint

    $kbScript = @'
import json
import os
import sys

sys.path.insert(0, os.environ["ARKAOS_ROOT"])
try:
    from core.workflow.research_gate import evaluate_research_gate, record_telemetry
except Exception:
    print(json.dumps({"allow": True, "nudge": False, "reason": "kb-gate-import-failed"}))
    sys.exit(0)

decision = evaluate_research_gate(
    tool_name=os.environ.get("TOOL_NAME", ""),
    session_id=os.environ.get("SESSION_ID", ""),
    query=os.environ.get("QUERY_HINT", ""),
)
try:
    record_telemetry(
        session_id=os.environ.get("SESSION_ID", ""),
        tool=os.environ.get("TOOL_NAME", ""),
        decision=decision,
    )
except Exception:
    pass
print(json.dumps({
    "allow": decision.allow,
    "nudge": decision.nudge,
    "reason": decision.reason,
    "stderr_msg": decision.to_stderr_message(),
}))
'@

    $kbDecisionJson = $kbScript | & $python.Source -
    if (-not [string]::IsNullOrWhiteSpace($kbDecisionJson)) {
        try {
            $kbDecision = $kbDecisionJson | ConvertFrom-Json
        } catch { $kbDecision = $null }

        if ($kbDecision -and -not $kbDecision.allow) {
            [Console]::Error.WriteLine($kbDecision.stderr_msg)
            $denyOut = @{
                hookSpecificOutput = @{
                    hookEventName = "PreToolUse"
                    permissionDecision = "deny"
                    permissionDecisionReason = $kbDecision.stderr_msg
                }
            } | ConvertTo-Json -Compress -Depth 5
            Write-Output $denyOut
            exit 2
        }

        if ($kbDecision -and $kbDecision.nudge -and -not [string]::IsNullOrWhiteSpace($kbDecision.stderr_msg)) {
            [Console]::Error.WriteLine($kbDecision.stderr_msg)
        }
    }
}

# --- Specialist-dispatch gate (between KB-gate and flow-gate) ---
# Blocks Tier-1 leads from writing to specialist-owned files without
# dispatching first. Only fires for file-mutation tools.
$specialistPy = Join-Path $env:ARKAOS_ROOT "core/workflow/specialist_enforcer.py"
if ((Test-Path $specialistPy) -and ($toolName -in @("Write","Edit","MultiEdit","NotebookEdit"))) {
    $toolInputJson = "{}"
    if ($inp.tool_input) {
        $toolInputJson = ($inp.tool_input | ConvertTo-Json -Compress -Depth 10)
    }
    $env:TOOL_NAME = $toolName
    $env:TRANSCRIPT_PATH = $transcriptPath
    $env:SESSION_ID = $sessionId
    $env:CWD = $cwd
    $env:TOOL_INPUT_JSON = $toolInputJson

    $spScript = @'
import json
import os
import sys

sys.path.insert(0, os.environ["ARKAOS_ROOT"])
try:
    from core.workflow.specialist_enforcer import evaluate, record_telemetry
except Exception:
    print(json.dumps({"allow": True, "reason": "specialist-import-failed"}))
    sys.exit(0)

try:
    tool_input = json.loads(os.environ.get("TOOL_INPUT_JSON", "{}"))
except json.JSONDecodeError:
    tool_input = {}

decision = evaluate(
    tool_name=os.environ.get("TOOL_NAME", ""),
    transcript_path=os.environ.get("TRANSCRIPT_PATH", ""),
    session_id=os.environ.get("SESSION_ID", ""),
    cwd=os.environ.get("CWD", ""),
    tool_input=tool_input,
)
try:
    record_telemetry(
        session_id=os.environ.get("SESSION_ID", ""),
        tool=os.environ.get("TOOL_NAME", ""),
        decision=decision,
        cwd=os.environ.get("CWD", ""),
        target_file=str(tool_input.get("file_path", "")),
    )
except Exception:
    pass
print(json.dumps({
    "allow": decision.allow,
    "reason": decision.reason,
    "stderr_msg": decision.to_stderr_message(),
}))
'@

    $spDecisionJson = $spScript | & $python.Source -
    if (-not [string]::IsNullOrWhiteSpace($spDecisionJson)) {
        try {
            $spDecision = $spDecisionJson | ConvertFrom-Json
        } catch { $spDecision = $null }

        if ($spDecision -and -not $spDecision.allow) {
            [Console]::Error.WriteLine($spDecision.stderr_msg)
            $denyOut = @{
                hookSpecificOutput = @{
                    hookEventName = "PreToolUse"
                    permissionDecision = "deny"
                    permissionDecisionReason = $spDecision.stderr_msg
                }
            } | ConvertTo-Json -Compress -Depth 5
            Write-Output $denyOut
            exit 2
        }
    }
}

# --- Fast allow: not a flow-gated tool ---
if ($toolName -ne "Write" -and $toolName -ne "Edit" -and $toolName -ne "MultiEdit") {
    exit 0
}

$enforcerPy = Join-Path $env:ARKAOS_ROOT "core/workflow/flow_enforcer.py"
if (-not (Test-Path $enforcerPy)) { exit 0 }

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
