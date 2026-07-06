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

$env:ARKA_PY = Resolve-ArkaPython
