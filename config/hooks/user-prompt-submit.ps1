# ============================================================================
# ArkaOS v2 - UserPromptSubmit Hook (Synapse Bridge) (Windows / PowerShell 5.1+)
#
# Port of config/hooks/user-prompt-submit.sh. Calls the Python Synapse bridge
# for 8-layer context injection, with a pure-PowerShell fallback for
# installations where Python is unavailable or the bridge is missing.
#
# Contract:
# - Reads a JSON payload from stdin (userInput / message / raw).
# - Emits a single-line JSON object on stdout:
#       {"additionalContext": "<sync-notice><synapse-or-fallback>"}
# - Side effect: writes one line to the cache metrics JSONL.
#
# Target latency: <100ms (hook timeout is 10s in settings).
#
# File is pure ASCII. Any typographic characters that need to appear in the
# output are built from [char] codes at runtime so PS 5.1's default ANSI
# source read cannot mojibake them.
# ============================================================================

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# --- Read stdin ------------------------------------------------------------
$stdinText = [Console]::In.ReadToEnd()
$payload = $null
if (-not [string]::IsNullOrWhiteSpace($stdinText)) {
    try { $payload = $stdinText | ConvertFrom-Json } catch { $payload = $null }
}

# --- V1 migration detection ------------------------------------------------
# The old logic fired whenever any v1 skill directory existed on disk and
# the migrated-from-v1 marker was absent. That is too noisy on a Windows
# install that has v2 running correctly alongside leftover v1 skill dirs
# (common when a user installed via `npx arkaos install` after having
# previously used v1): the hook early-returned with the MIGRATION message
# on every single user prompt, drowning out the Synapse context.
#
# The presence of a valid v2 install manifest at `~/.arkaos/install-
# manifest.json` is the canonical signal that v2 is functional. If we
# see that file, skip the migration nag — the user has clearly already
# moved to v2, even if the explicit `migrated-from-v1` flag file was
# never created.
$v2Manifest = Join-Path $env:USERPROFILE '.arkaos\install-manifest.json'
$v2Installed = Test-Path -LiteralPath $v2Manifest

if (-not $v2Installed) {
    $v1Paths = @(
        (Join-Path $env:USERPROFILE '.claude\skills\arka-os'),
        (Join-Path $env:USERPROFILE '.claude\skills\arkaos')
    )
    $migrationMarker = Join-Path $env:USERPROFILE '.arkaos\migrated-from-v1'

    foreach ($v1 in $v1Paths) {
        if ((Test-Path -LiteralPath $v1 -PathType Container) -and -not (Test-Path -LiteralPath $migrationMarker)) {
            $msg = "[MIGRATION] ArkaOS v1 detected at $v1. Run: npx arkaos migrate - This will backup v1, preserve your data, and install v2. See: https://github.com/andreagroferreira/arka-os#install"
            [pscustomobject]@{ additionalContext = $msg } | ConvertTo-Json -Compress
            exit 0
        }
    }
}

# --- Performance timing ----------------------------------------------------
$sw = [System.Diagnostics.Stopwatch]::StartNew()

# --- Flow marker cache invalidation (v2 — new turn resets ALLOW cache) ---
# Runs before the Synapse bridge so a stuck Python call cannot leave a
# stale marker across turns. Non-blocking — all failures swallowed.
try {
    $sessionIdUps = ''
    if ($payload -and $payload.session_id) {
        $sessionIdUps = [string]$payload.session_id
    }
    if ($sessionIdUps) {
        $arkaosRootUps = $env:ARKAOS_ROOT
        if (-not $arkaosRootUps) {
            $repoPathFileUps = Join-Path $env:USERPROFILE '.arkaos\.repo-path'
            if (Test-Path -LiteralPath $repoPathFileUps) {
                try {
                    $arkaosRootUps = (Get-Content -Raw -LiteralPath $repoPathFileUps -Encoding UTF8).Trim()
                } catch { }
            }
        }
        if (-not $arkaosRootUps) {
            $arkaosRootUps = Join-Path $env:USERPROFILE '.arkaos'
        }
        $pythonForInvalidate = $null
        $venvPyUps = Join-Path $env:USERPROFILE '.arkaos\venv\Scripts\python.exe'
        if (Test-Path -LiteralPath $venvPyUps) {
            $pythonForInvalidate = $venvPyUps
        } else {
            foreach ($cmd in 'python3','python','py') {
                $resolvedUps = Get-Command $cmd -ErrorAction SilentlyContinue
                if ($resolvedUps) { $pythonForInvalidate = $resolvedUps.Source; break }
            }
        }
        if ($pythonForInvalidate) {
            $pyCode = "import os`ntry:`n    from core.workflow.marker_cache import invalidate_marker`n    invalidate_marker(os.environ.get('SESSION_ID_UPS',''))`nexcept Exception:`n    pass`ntry:`n    from core.synapse.kb_cache import invalidate_obsidian_query`n    invalidate_obsidian_query(os.environ.get('SESSION_ID_UPS',''))`nexcept Exception:`n    pass"
            $psi = New-Object System.Diagnostics.ProcessStartInfo
            $psi.FileName = $pythonForInvalidate
            $psi.Arguments = "-c `"$($pyCode -replace '"','\"' -replace "`r?`n",'; ')`""
            $psi.UseShellExecute = $false
            $psi.CreateNoWindow = $true
            $psi.RedirectStandardOutput = $true
            $psi.RedirectStandardError = $true
            [void]$psi.EnvironmentVariables.Add('SESSION_ID_UPS', $sessionIdUps)
            [void]$psi.EnvironmentVariables.Add('PYTHONPATH', $arkaosRootUps)
            try {
                $procUps = [System.Diagnostics.Process]::Start($psi)
                if (-not $procUps.WaitForExit(1500)) { try { $procUps.Kill() } catch { } }
            } catch { }
        }
    }
} catch { }

# --- Sync version detection ------------------------------------------------
$syncNotice = ''
$arkaosHome    = Join-Path $env:USERPROFILE '.arkaos'
$syncStatePath = Join-Path $arkaosHome 'sync-state.json'
$repoPathFile  = Join-Path $arkaosHome '.repo-path'

$currentVersion = ''
if (Test-Path -LiteralPath $repoPathFile) {
    try {
        $repoPath = (Get-Content -Raw -LiteralPath $repoPathFile -Encoding UTF8).Trim()
        if ($repoPath) {
            $vFile = Join-Path $repoPath 'VERSION'
            $pkgFile = Join-Path $repoPath 'package.json'
            if (Test-Path -LiteralPath $vFile) {
                $currentVersion = (Get-Content -Raw -LiteralPath $vFile -Encoding UTF8).Trim()
            } elseif (Test-Path -LiteralPath $pkgFile) {
                try {
                    $currentVersion = [string]((Get-Content -Raw -LiteralPath $pkgFile -Encoding UTF8 | ConvertFrom-Json).version)
                } catch { }
            }
        }
    } catch { }
}

if ($currentVersion) {
    $syncedVersion = 'none'
    if (Test-Path -LiteralPath $syncStatePath) {
        try {
            $ss = Get-Content -Raw -LiteralPath $syncStatePath -Encoding UTF8 | ConvertFrom-Json
            if ($ss.version) { $syncedVersion = [string]$ss.version }
        } catch { }
    }
    if ($currentVersion -ne $syncedVersion) {
        $syncNotice = "[arka:update-available] ArkaOS v$currentVersion installed (synced: $syncedVersion). Run /arka update to sync all projects. "
    }
}

# --- Resolve ARKAOS_ROOT (env var -> .repo-path -> ~/.arkaos -> fallback) --
if ($env:ARKAOS_ROOT) {
    $arkaosRoot = $env:ARKAOS_ROOT
} elseif (Test-Path -LiteralPath $repoPathFile) {
    try {
        $arkaosRoot = (Get-Content -Raw -LiteralPath $repoPathFile -Encoding UTF8).Trim()
    } catch {
        $arkaosRoot = $null
    }
}
if (-not $arkaosRoot) {
    if (Test-Path -LiteralPath $arkaosHome -PathType Container) {
        $arkaosRoot = $arkaosHome
    } else {
        # Portable fallback - matches the shell hook's final branch.
        $arkaosRoot = if ($env:ARKA_OS) { $env:ARKA_OS } else { Join-Path $env:USERPROFILE '.claude\skills\arkaos' }
    }
}

# --- Cache dir -------------------------------------------------------------
# Windows equivalent of /tmp: use the per-user temp dir so constitution
# caches are isolated per user.
$cacheRoot = [System.IO.Path]::GetTempPath()
$cacheDir  = Join-Path $cacheRoot 'arkaos-context-cache'
$null = New-Item -ItemType Directory -Force -Path $cacheDir -ErrorAction SilentlyContinue
$cacheTtlSeconds = 300

# --- Extract user input ----------------------------------------------------
$userInput = ''
if ($payload) {
    if ($payload.userInput) {
        $userInput = [string]$payload.userInput
    } elseif ($payload.message) {
        $userInput = [string]$payload.message
    }
}
if (-not $userInput) {
    # Fallback: truncate raw stdin (mirrors `head -c 2000` from bash).
    if ($stdinText.Length -gt 2000) {
        $userInput = $stdinText.Substring(0, 2000)
    } else {
        $userInput = $stdinText
    }
}

# --- Helper: locate a usable Python interpreter ----------------------------
function Find-Python {
    # Prefer the ArkaOS venv python if the install manifest tells us where it is.
    $manifestPath = Join-Path $env:USERPROFILE '.arkaos\install-manifest.json'
    if (Test-Path -LiteralPath $manifestPath) {
        try {
            $m = Get-Content -Raw -LiteralPath $manifestPath -Encoding UTF8 | ConvertFrom-Json
            if ($m.pythonCmd -and (Test-Path -LiteralPath $m.pythonCmd)) {
                return $m.pythonCmd
            }
        } catch { }
    }
    # Fallback to the typical Windows venv layout.
    $venvPy = Join-Path $env:USERPROFILE '.arkaos\venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPy) { return $venvPy }
    # System python. python3 is rare on Windows; `python` and `py -3` are typical.
    foreach ($cmd in 'python3','python','py') {
        $resolved = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($resolved) { return $resolved.Source }
    }
    return $null
}

# --- Try Python Synapse bridge ---------------------------------------------
$pythonResult = ''
$bridgeScript = Join-Path $arkaosRoot 'scripts\synapse-bridge.py'
$python = Find-Python

if ($python -and (Test-Path -LiteralPath $bridgeScript)) {
    try {
        $bridgeInput = [pscustomobject]@{ user_input = $userInput } | ConvertTo-Json -Compress

        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $python
        # PS 5.1 / .NET Framework: ProcessStartInfo only exposes `Arguments`
        # as a single command-line string. Quote both paths so spaces work.
        $psi.Arguments = "`"$bridgeScript`" --root `"$arkaosRoot`""
        $psi.RedirectStandardInput  = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError  = $true
        $psi.UseShellExecute        = $false
        $psi.CreateNoWindow         = $true
        $psi.StandardInputEncoding  = [System.Text.UTF8Encoding]::new($false)
        $psi.StandardOutputEncoding = [System.Text.UTF8Encoding]::new($false)
        # Set ARKAOS_ROOT in the child environment.
        if ($psi.EnvironmentVariables.ContainsKey('ARKAOS_ROOT')) {
            $psi.EnvironmentVariables['ARKAOS_ROOT'] = $arkaosRoot
        } else {
            [void]$psi.EnvironmentVariables.Add('ARKAOS_ROOT', $arkaosRoot)
        }

        $proc = [System.Diagnostics.Process]::Start($psi)
        $proc.StandardInput.Write($bridgeInput)
        $proc.StandardInput.Close()
        # Cap the bridge call at 8 seconds so a stuck bridge cannot burn the
        # full 10-second hook budget.
        if (-not $proc.WaitForExit(8000)) {
            try { $proc.Kill() } catch { }
        } else {
            $bridgeOutput = $proc.StandardOutput.ReadToEnd()
            if ($bridgeOutput) {
                try {
                    $parsed = $bridgeOutput | ConvertFrom-Json
                    if ($parsed.context_string) {
                        $pythonResult = [string]$parsed.context_string
                    }
                } catch { }
            }
        }
    } catch {
        $pythonResult = ''
    }
}

# --- Fallback: pure-PowerShell context -------------------------------------
if (-not $pythonResult) {
    # L0 Constitution (5-min cache)
    $l0CacheFile = Join-Path $cacheDir 'l0-constitution'
    $l0 = ''
    $cacheFresh = $false
    if (Test-Path -LiteralPath $l0CacheFile) {
        try {
            $ageSeconds = ((Get-Date) - (Get-Item -LiteralPath $l0CacheFile).LastWriteTime).TotalSeconds
            if ($ageSeconds -lt $cacheTtlSeconds) {
                $l0 = (Get-Content -Raw -LiteralPath $l0CacheFile -Encoding UTF8).Trim()
                if ($l0) { $cacheFresh = $true }
            }
        } catch { }
    }
    if (-not $cacheFresh) {
        $l0 = '[Constitution] NON-NEGOTIABLE: branch-isolation, obsidian-output, authority-boundaries, security-gate, context-first, solid-clean-code, spec-driven, human-writing, squad-routing, full-visibility, sequential-validation, mandatory-qa, arka-supremacy | QUALITY-GATE: marta-cqo, eduardo-copy, francisca-tech-ux | MUST: conventional-commits, test-coverage, pattern-matching, actionable-output, memory-persistence'
        try {
            $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
            [System.IO.File]::WriteAllText($l0CacheFile, $l0, $utf8NoBom)
        } catch { }
    }

    # L4 Git branch
    $l4 = ''
    try {
        $branchOutput = & git rev-parse --abbrev-ref HEAD 2>$null
        if ($LASTEXITCODE -eq 0 -and $branchOutput) {
            $branch = $branchOutput.Trim()
            if ($branch -and $branch -ne 'main' -and $branch -ne 'master' -and $branch -ne 'dev') {
                $l4 = "[branch:$branch]"
            }
        }
    } catch { }

    # L7 Time
    $hour = [int](Get-Date -Format 'HH')
    if     ($hour -ge 5  -and $hour -lt 12) { $l7 = '[time:morning]' }
    elseif ($hour -ge 12 -and $hour -lt 18) { $l7 = '[time:afternoon]' }
    else                                     { $l7 = '[time:evening]' }

    $pythonResult = (@($l0, $l4, $l7) | Where-Object { $_ }) -join ' '
}

# --- Persistent Routing Reminder -------------------------------------------
# High-salience tag - ensures squad routing persists across conversation turns,
# and enforces visible KB citation when chunks are present.
# See: docs/superpowers/specs/2026-04-14-persistent-routing-reminder-design.md
$routeReminder = '[arka:route] Every response MUST route through a department squad. No generic assistant replies. Announce the squad before responding. When [knowledge:N chunks] is present in this context, you MUST cite at least one source and acknowledge KB was consulted; if absent on a non-trivial ArkaOS topic, query Obsidian before responding.'

# --- Output ----------------------------------------------------------------
$additionalContext = "$syncNotice$routeReminder $pythonResult"
[pscustomobject]@{ additionalContext = $additionalContext } | ConvertTo-Json -Compress

# --- Metrics (JSONL append) ------------------------------------------------
$elapsed = [int]$sw.ElapsedMilliseconds
if ($elapsed -gt 0) {
    try {
        $metricsLine = [pscustomobject]@{ hook = 'user-prompt-submit-v2'; ms = $elapsed } | ConvertTo-Json -Compress
        $metricsFile = Join-Path $cacheDir 'hook-metrics.jsonl'
        $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
        # Append mode: read existing bytes, append new line, write back.
        # Small enough that this is cheaper than opening a FileStream.
        $existing = ''
        if (Test-Path -LiteralPath $metricsFile) {
            $existing = [System.IO.File]::ReadAllText($metricsFile, $utf8NoBom)
        }
        [System.IO.File]::WriteAllText($metricsFile, "$existing$metricsLine`n", $utf8NoBom)
    } catch {
        # Metrics are best-effort.
    }
}
