# ============================================================================
# ArkaOS - UserPromptSubmit Hook (Windows / PowerShell 5.1+)
#
# Thin wrapper - mirror of config/hooks/user-prompt-submit.sh. ONE python
# process (core.hooks.user_prompt_submit) builds the whole per-prompt
# payload: V1 migration + sync notices, per-turn cache invalidation, the
# Synapse 12-layer context, KB auto-inject, token hygiene, the persistent
# [ARKA:ROUTE] reminder, and the workflow classifier that marks the session
# flow-required. This file only resolves the interpreter and delegates;
# with no usable interpreter it emits the static L0 constitution fallback
# and exits 0 (fail-open, dependency-free), same as the .sh.
#
# WHY A WRAPPER AND NOT A PORT
# The previous version was a native reimplementation of an older .sh: it
# called scripts/synapse-bridge.py directly and ported the migration check,
# sync notice and route reminder to PowerShell - but the producer kept
# evolving, and the port silently fell behind. In particular it never
# called the workflow classifier, so the wf-required marker was never
# created on Windows: the per-prompt half of the evidence flow (and the
# whole compliance chain behind the Stop hook) was dead on this platform.
# Same failure mode as session-start.ps1 (twin drift). One producer, two
# thin wrappers.
#
# Minimum PowerShell: 5.1. This file stays pure ASCII; every non-ASCII byte
# in the output comes from Python's UTF-8 stdout.
# ============================================================================

$ErrorActionPreference = 'SilentlyContinue'

# Force UTF-8 on both sides of the pipe. Python emits UTF-8; without this
# PS 5.1 decodes it as the ANSI codepage (cp1252 on pt-PT/pt-BR machines)
# and injected context arrives as mojibake - the #395/#396 failure mode.
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING = 'utf-8'

# Same fallback CONTENT as _ARKA_L0_FALLBACK in the .sh twin.
$l0Fallback = '{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "[Constitution] NON-NEGOTIABLE: branch-isolation, security-gate, mandatory-qa, evidence-flow, arkaos-not-yes-man, excellence-mandate | QUALITY-GATE: marta-cqo, eduardo-copy, francisca-tech-ux | MUST (28) incl.: squad-routing, spec-driven, conventional-commits, test-coverage, subagent-discipline, persona-vs-artifact"}}'

# Test seam - mirror of the .sh flag so the fallback content can be
# asserted deterministically on either platform.
if ($env:ARKA_HOOK_FORCE_FALLBACK) {
    Write-Output $l0Fallback
    exit 0
}

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

# The MODULE file is the guard: an older installed snapshot without it
# would delegate into "No module named ..." (exit 1, empty output) instead
# of degrading to the constitution fallback.
$moduleFile = if ($repo) { Join-Path $repo 'core/hooks/user_prompt_submit.py' } else { '' }

if ($repo -and $moduleFile -and (Test-Path -LiteralPath $moduleFile) -and $env:ARKA_PY) {
    $env:PYTHONPATH = $repo
    Push-Location -LiteralPath $repo
    try {
        & $env:ARKA_PY -m core.hooks.user_prompt_submit
        if ($LASTEXITCODE -eq 0) { Pop-Location; exit 0 }
    } catch {
        # fall through to the constitution fallback
    }
    Pop-Location
}

# --- Degraded fallback: L0 constitution context, valid JSON, exit 0 --------
Write-Output $l0Fallback
exit 0
