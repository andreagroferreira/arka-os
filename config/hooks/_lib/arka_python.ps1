# ArkaOS shared Python resolver (PowerShell side) — single source of truth.
#
# Windows mirror of config/hooks/_lib/arka_python.sh and
# installer/python-resolver.js. Prefers the ~/.arkaos venv (has pyyaml/
# pydantic); never silently falls back to a system python that lacks ArkaOS
# deps. Dot-source this file: it sets $env:ARKA_PY.
#
# Resolution order:
#   1. $env:ARKAOS_PYTHON (explicit override), if it exists.
#   2. The ArkaOS venv — Scripts\python.exe (Windows) then bin/python.
#   3. Any python3/python/py on PATH that can `import yaml`.
#   4. Bare `python` as a last resort.

function Resolve-ArkaPython {
    if ($env:ARKAOS_PYTHON -and (Test-Path -LiteralPath $env:ARKAOS_PYTHON)) {
        return $env:ARKAOS_PYTHON
    }

    $base = if ($env:USERPROFILE) { $env:USERPROFILE } elseif ($HOME) { $HOME } else { "" }
    if ($base) {
        $candidates = @(
            (Join-Path $base ".arkaos\venv\Scripts\python.exe"),
            (Join-Path $base ".arkaos/venv/bin/python"),
            (Join-Path $base ".arkaos\.venv\Scripts\python.exe"),
            (Join-Path $base ".arkaos/.venv/bin/python")
        )
        foreach ($c in $candidates) {
            if (Test-Path -LiteralPath $c) { return $c }
        }
    }

    foreach ($name in @("python3", "python", "py")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) {
            & $cmd.Source -c "import yaml" 2>$null
            if ($LASTEXITCODE -eq 0) { return $cmd.Source }
        }
    }

    return "python"
}

# Windows mirror of arka_resolve_root() in arka_python.sh: env override wins
# unconditionally; guessed candidates must contain core/sync/__init__.py
# (the full-package marker — `.repo-path` points at an npx cache that
# `npm cache clean` can purge; ~/.arkaos/lib is the installer's snapshot).
function Resolve-ArkaRoot {
    if (-not [string]::IsNullOrWhiteSpace($env:ARKAOS_ROOT)) {
        return $env:ARKAOS_ROOT
    }
    $base = if ($env:USERPROFILE) { $env:USERPROFILE } elseif ($HOME) { $HOME } else { "" }
    $repo = ""
    $repoPathFile = Join-Path $base ".arkaos\.repo-path"
    if ($base -and (Test-Path -LiteralPath $repoPathFile)) {
        $repo = (Get-Content $repoPathFile -Raw).Trim()
    }
    if ($repo -and (Test-Path -LiteralPath (Join-Path $repo "core\sync\__init__.py"))) {
        return $repo
    }
    $lib = Join-Path $base ".arkaos\lib"
    if ($base -and (Test-Path -LiteralPath (Join-Path $lib "core\sync\__init__.py"))) {
        return $lib
    }
    if ($repo -and (Test-Path -LiteralPath $repo)) {
        return $repo
    }
    if ($base -and (Test-Path -LiteralPath (Join-Path $base ".arkaos"))) {
        return (Join-Path $base ".arkaos")
    }
    if ($env:ARKA_OS) { return $env:ARKA_OS }
    return (Join-Path $base ".claude\skills\arkaos")
}

$env:ARKA_PY = Resolve-ArkaPython
