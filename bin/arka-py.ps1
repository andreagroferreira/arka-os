# ============================================================================
# ArkaOS - Python entrypoint (Windows / PowerShell 5.1+)
#
# Port of bin/arka-py. Resolves the ArkaOS interpreter (venv-first, via the
# shared PowerShell resolver) and execs it, so SKILL.md commands never run a
# bare `python` that lacks ArkaOS deps (pyyaml, ...).
#
# Usage:  arka-py -m core.sync.update_orchestrator ...
# Normally invoked through its .cmd shim (bin/arka-py.cmd).
# ============================================================================
$ErrorActionPreference = "Stop"

# ─── Source the shared resolver, from the repo or the installed location ──
$self = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$libs = @(
    (Join-Path $self "..\config\hooks\_lib\arka_python.ps1"),
    (Join-Path (if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }) ".arkaos\config\hooks\_lib\arka_python.ps1")
)
foreach ($lib in $libs) {
    if (Test-Path -LiteralPath $lib) { . $lib; break }
}
if (-not $env:ARKA_PY) { $env:ARKA_PY = "python" }

# ─── Make `-m core.*` resolvable regardless of cwd ────────────────────────
$root = $env:ARKAOS_ROOT
if (-not $root) {
    $rp = Join-Path (if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }) ".arkaos\.repo-path"
    if (Test-Path -LiteralPath $rp) { $root = (Get-Content -LiteralPath $rp -Raw).Trim() }
}
if ($root -and (Test-Path -LiteralPath $root)) {
    $sep = [IO.Path]::PathSeparator
    $env:PYTHONPATH = if ($env:PYTHONPATH) { "$root$sep$env:PYTHONPATH" } else { $root }
}

& $env:ARKA_PY @args
exit $LASTEXITCODE
