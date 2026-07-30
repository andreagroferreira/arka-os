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
#   3. Any python3/python/py on PATH that can `import yaml`, skipping the
#      Microsoft Store App Execution Aliases (see Test-StoreAlias).
#   4. Bare `python` as a last resort.

function Test-StoreAlias {
    <#
    .SYNOPSIS
        True when a resolved command is a Microsoft Store App Execution Alias.

    .DESCRIPTION
        %LOCALAPPDATA%\Microsoft\WindowsApps holds zero-length reparse points
        that Get-Command resolves like any other executable. On a default
        Windows install `python3.exe` there points at the Python install
        manager, and *running* it — which the probe below does, with
        `-c "import yaml"` — makes the manager download and install a full
        CPython into the current working directory.

        For a hook that is a catastrophic side effect: the cwd is the user's
        project, so a background hook silently drops a ~3700-file Python/
        tree and a python_install_<timestamp>.log into their repo. Observed
        on Windows 10, Python install manager 26.3.

        Probing an alias can never help anyway: the stub carries no site
        packages, so the `import yaml` check it exists to answer would fail
        after paying the install.
    #>
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    return $Path -match '\\Microsoft\\WindowsApps\\'
}

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

    # "python" before "python3": on Windows a real interpreter answers to
    # the former, while the latter is usually only the Store alias.
    foreach ($name in @("python", "py", "python3")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and -not (Test-StoreAlias $cmd.Source)) {
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
