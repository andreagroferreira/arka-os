# ============================================================================
# ArkaOS - SessionStart Hook (Windows / PowerShell 5.1+)
#
# Thin wrapper - mirror of config/hooks/session-start.sh. ONE python process
# (core.hooks.session_start) builds the whole payload: the visible banner in
# "systemMessage" AND the operating contracts in
# hookSpecificOutput.additionalContext. This file only resolves the
# interpreter and delegates; whenever it cannot reach that producer — no
# repo root, no module file, no interpreter, or the module itself exiting
# non-zero — it emits a static banner and exits 0 (fail-open,
# dependency-free).
#
# WHY A WRAPPER AND NOT A PORT
# The previous version reimplemented the banner natively in PowerShell. It
# was a faithful port of the *older* .sh, from the era when the .sh built the
# banner in bash. When the .sh became a thin wrapper delegating to Python,
# this file did not follow - so on Windows the four contract blocks
# (EVIDENCE-FLOW, META-TAG, AUTHORITY, MODEL-FABRIC) were computed by nobody
# and never reached the model, while the Linux side got them every session.
# Reimplementing the blocks here would duplicate the producer and recreate
# the same drift one release later, so this file delegates instead. The
# twin-parity test in tests/python/test_hook_output_contract.py is what
# holds that open: it asserts both wrappers run `-m core.hooks
# .session_start`, and fails if either stops.
#
# Minimum PowerShell: 5.1 (shipped with every Windows 10+). No pwsh 7 prereq.
# This file stays pure ASCII; every non-ASCII byte in the output comes from
# Python's UTF-8 stdout, which is why the encoding setup below is required.
# ============================================================================

$ErrorActionPreference = 'SilentlyContinue'

# Captured BEFORE any location change - inside a compound command the CWD
# would resolve after the push (QG blocker F1-A3: cross-project leak).
$env:ARKA_HOOK_CWD = (Get-Location).Path

# Force UTF-8 on both sides of the pipe. Python emits UTF-8; without this
# PS 5.1 decodes it as the ANSI codepage (cp1252 on pt-PT/pt-BR machines)
# and the banner arrives as mojibake - the failure mode tracked in #395/#396.
# PYTHONIOENCODING covers the producer, OutputEncoding the consumer.
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING = 'utf-8'

# --- Shared Python resolver (sets $env:ARKA_PY, provides Resolve-ArkaRoot) ---
$arkaLib = Join-Path $PSScriptRoot '_lib\arka_python.ps1'
if (Test-Path -LiteralPath $arkaLib) { . $arkaLib }

# --- Resolve the repo root ---
# .repo-path can point at a purged npx cache; Resolve-ArkaRoot falls through
# to the ~/.arkaos/lib snapshot instead of returning a dead root.
$repo = ''
if (Get-Command Resolve-ArkaRoot -ErrorAction SilentlyContinue) {
    $repo = Resolve-ArkaRoot
} else {
    $repoPathFile = Join-Path $HOME '.arkaos/.repo-path'
    if (Test-Path -LiteralPath $repoPathFile) {
        $repo = (Get-Content -Raw -LiteralPath $repoPathFile -Encoding UTF8).Trim()
    }
}

# The MODULE file is the guard, not just core/: an older installed snapshot
# without it would delegate into "No module named ..." (exit 1, empty output
# - a broken SessionStart instead of a degraded banner).
$moduleFile = if ($repo) { Join-Path $repo 'core/hooks/session_start.py' } else { '' }

if ($repo -and $moduleFile -and (Test-Path -LiteralPath $moduleFile) -and $env:ARKA_PY) {
    $env:PYTHONPATH = $repo
    Push-Location -LiteralPath $repo
    try {
        & $env:ARKA_PY -m core.hooks.session_start
        if ($LASTEXITCODE -eq 0) { Pop-Location; exit 0 }
    } catch {
        # fall through to the degraded banner
    }
    Pop-Location
}

# --- Degraded fallback: static banner, valid JSON, exit 0 ------------------
# Same contract as the .sh fallback. Built from [char] codes so this source
# file needs no particular encoding to produce correct output.
#
# The message names the SYMPTOM, not a cause. Four conditions reach this
# line (see the guard above) and only one of them is a missing interpreter;
# the fourth — the module running and exiting non-zero — asserts the
# opposite. The .sh twin execs, so its fallback is unreachable once an
# interpreter is launched and the narrower wording survived there; this
# port falls through on $LASTEXITCODE, which is what made it false. Sending
# a Windows operator with a healthy Python to debug their Python, when the
# real fault is a stale ~/.arkaos/.repo-path, costs more than the wording
# saves. `npx arkaos doctor` diagnoses all four.
$tri = [char]0x25B2
$oAcute = [char]0x00F3
$emDash = [char]0x2014
$banner = "`n  $tri  A R K A   O S`n     The Operating System for AI Agent Teams`n`n  Ol$oAcute, founder`n  degraded: ArkaOS core not reachable $emDash run npx arkaos doctor"
[pscustomobject]@{ systemMessage = $banner } | ConvertTo-Json -Compress
exit 0
