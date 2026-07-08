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
# Windows PowerShell 5.1 cannot parse an inline `if`-expression passed as a
# command argument (e.g. `Join-Path (if (...) {...} else {...}) "..."`); it is
# a PowerShell 7-only construct, so the whole script fails to parse under 5.1
# and every `arka-py ...` call dies. Resolve the home base into a variable
# first — the assignment form of `if` IS valid in 5.1.
$base = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
$libs = @(
    (Join-Path $self "..\config\hooks\_lib\arka_python.ps1"),
    (Join-Path $base ".arkaos\config\hooks\_lib\arka_python.ps1")
)
foreach ($lib in $libs) {
    if (Test-Path -LiteralPath $lib) { . $lib; break }
}
if (-not $env:ARKA_PY) { $env:ARKA_PY = "python" }

# ─── Make `-m core.*` resolvable regardless of cwd ────────────────────────
$root = $env:ARKAOS_ROOT
if (-not $root) {
    # Reuse $base (5.1-safe) instead of an inline `if`-expression argument.
    $rp = Join-Path $base ".arkaos\.repo-path"
    if (Test-Path -LiteralPath $rp) { $root = (Get-Content -LiteralPath $rp -Raw).Trim() }
}
if ($root -and (Test-Path -LiteralPath $root)) {
    $sep = [IO.Path]::PathSeparator
    $env:PYTHONPATH = if ($env:PYTHONPATH) { "$root$sep$env:PYTHONPATH" } else { $root }
}

& $env:ARKA_PY @args
exit $LASTEXITCODE
