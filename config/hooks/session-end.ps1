# ============================================================================
# ArkaOS — SessionEnd Hook (Windows / PowerShell 5.1+)
#
# Parity with config/hooks/session-end.sh. Thin wrapper: reads the stdin JSON
# payload and pipes it to ONE python process (core.hooks.session_end), which
# owns the entire behaviour. Fail-open: no usable interpreter => exit 0.
# ============================================================================

$ErrorActionPreference = 'SilentlyContinue'
$stdinText = [Console]::In.ReadToEnd()

# Shared resolver (venv-first, yaml-verified). Mirrors _lib/arka_python.sh.
$arkaLib = Join-Path $PSScriptRoot "_lib\arka_python.ps1"
if (Test-Path -LiteralPath $arkaLib) { . $arkaLib }

if (Get-Command Resolve-ArkaRoot -ErrorAction SilentlyContinue) {
    $env:ARKAOS_ROOT = Resolve-ArkaRoot
} elseif ([string]::IsNullOrWhiteSpace($env:ARKAOS_ROOT)) {
    $repoPathFile = Join-Path $HOME ".arkaos/.repo-path"
    if (Test-Path $repoPathFile) {
        $env:ARKAOS_ROOT = (Get-Content $repoPathFile -Raw).Trim()
    } elseif (Test-Path (Join-Path $HOME ".arkaos")) {
        $env:ARKAOS_ROOT = (Join-Path $HOME ".arkaos")
    } else {
        $env:ARKAOS_ROOT = if ($env:ARKA_OS) { $env:ARKA_OS } else { Join-Path $HOME ".claude/skills/arkaos" }
    }
}

$pythonExe = $env:ARKA_PY
if (-not $pythonExe) { exit 0 }
if (-not (Test-Path -LiteralPath (Join-Path $env:ARKAOS_ROOT "core/hooks/session_end.py"))) {
    $selfRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
    if (Test-Path -LiteralPath (Join-Path $selfRoot "core/hooks/session_end.py")) {
        $env:ARKAOS_ROOT = $selfRoot
    } else { exit 0 }
}

$env:PYTHONPATH = "$($env:ARKAOS_ROOT)$([IO.Path]::PathSeparator)$($env:PYTHONPATH)"
$stdinText | & $pythonExe -m core.hooks.session_end
exit 0
