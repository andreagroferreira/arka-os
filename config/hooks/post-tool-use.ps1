# ============================================================================
# ArkaOS — PostToolUse Hook (Gotchas Memory) (Windows / PowerShell 5.1+)
#
# Port of config/hooks/post-tool-use.sh. Detects errors emitted by tool runs
# and records recurring patterns in a local gotchas file so ArkaOS can learn
# which mistakes repeat across projects.
#
# Contract:
# - Reads a hook payload JSON from stdin (tool_name, tool_output, exit_code,
#   cwd).
# - Always exits 0 and writes `{}` on stdout — PostToolUse does not inject
#   context.
# - Side effect: updates %USERPROFILE%\.arkaos\gotchas.json and
#   %USERPROFILE%\.arkaos\hook-metrics.json.
#
# State files live under the canonical v2 runtime directory `~/.arkaos/`.
# Older builds of the bash twin used `~/.arka-os/` (with a dash); the
# bash hook has been fixed in the same commit series, and the installer
# update path now carries legacy state forward on the first update.
# ============================================================================

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# Hard timeout budget for the whole hook: 5 seconds (same as settings).
$sw = [System.Diagnostics.Stopwatch]::StartNew()

# ─── Helper functions (used by both gotchas and metrics blocks) ───────
# Defined at module scope so the metrics-write block at the bottom of
# the file can still reach them when `shouldProcessGotchas` is false
# and the gotchas branch is skipped.

function Acquire-FileLock {
    param([string]$LockPath, [int]$TimeoutMs = 3000)
    $deadline = [Environment]::TickCount + $TimeoutMs
    while ([Environment]::TickCount -lt $deadline) {
        try {
            $fs = [System.IO.File]::Open(
                $LockPath,
                [System.IO.FileMode]::OpenOrCreate,
                [System.IO.FileAccess]::ReadWrite,
                [System.IO.FileShare]::None
            )
            return $fs
        } catch {
            Start-Sleep -Milliseconds 50
        }
    }
    return $null
}

# PS 5.1's `Set-Content -Encoding UTF8` writes a BOM; tools that parse
# UTF-8 strictly (jq, python's json module, etc.) treat the BOM as a
# stray character. Always write JSON state files BOM-less via the .NET
# API with an explicit UTF8Encoding($false).
function Write-JsonAtomic {
    param([string]$Path, [string]$Json)
    $tmp = "$Path.tmp"
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($tmp, $Json, $utf8NoBom)
    Move-Item -Force -LiteralPath $tmp -Destination $Path
}

# PS 5.1 `ConvertTo-Json` on a single-item collection serializes as a
# bare object, not a single-element array. We always want `[...]` on
# disk, even with 0 or 1 entries, so state files stay homogeneous and
# round-trip cleanly. This helper forces array wrapping by serializing
# each item and joining manually.
function ConvertTo-JsonArray {
    param($Items, [int]$Depth = 10)
    $arr = @($Items)
    if ($arr.Count -eq 0) { return '[]' }
    $parts = foreach ($item in $arr) {
        $item | ConvertTo-Json -Depth $Depth -Compress
    }
    return '[' + ($parts -join ',') + ']'
}

# ArrayList survives ConvertTo-Json as a proper JSON array even with
# 0 or 1 elements, unlike `@()` which PS 5.1 happily collapses.
function New-StringArrayList {
    param([string[]]$Initial)
    $list = New-Object System.Collections.ArrayList
    if ($Initial) {
        foreach ($s in $Initial) {
            if ($null -ne $s -and $s -ne '') { [void]$list.Add($s) }
        }
    }
    return ,$list
}

# ─── Read hook payload from stdin (with empty-stdin tolerance) ────────
# On Claude Code Windows v2.1.97 the hook stdin pipe is opened but the
# parent writes zero bytes before closing (upstream bug — see
# Projects/ARKA OS/Windows Handoff.md canary data). We still want to
# log the metric that proves the hook fired, so instead of early-exiting
# on empty stdin we just skip the gotchas-processing block and fall
# through to the metrics write + final '{}' at the bottom of the file.
$stdinText = [Console]::In.ReadToEnd()
$shouldProcessGotchas = $true
$payload = $null
$toolName = ''
$toolOutput = ''
$exitCode = '0'
$cwd = ''

if ([string]::IsNullOrWhiteSpace($stdinText)) {
    $shouldProcessGotchas = $false
} else {
    try {
        $payload = $stdinText | ConvertFrom-Json
    } catch {
        $shouldProcessGotchas = $false
    }
}

if ($shouldProcessGotchas -and $null -ne $payload) {
    $toolName   = if ($null -ne $payload.tool_name)   { [string]$payload.tool_name   } else { '' }
    $toolOutput = if ($null -ne $payload.tool_output) { [string]$payload.tool_output } else { '' }
    $exitCode   = if ($null -ne $payload.exit_code)   { [string]$payload.exit_code   } else { '0' }
    $cwd        = if ($null -ne $payload.cwd)         { [string]$payload.cwd         } else { '' }

    # --- Flow marker cache write (v2 ALLOW accelerator) ------------------
    # Mirror of the bash hook: detect [arka:routing] or [arka:trivial] in
    # $payload.assistant_message and persist via core.workflow.marker_cache.
    # Non-blocking — any failure is swallowed.
    try {
        $sessionIdPtu = if ($null -ne $payload.session_id) { [string]$payload.session_id } else { '' }
        $assistantMsg = if ($null -ne $payload.assistant_message) { [string]$payload.assistant_message } else { '' }
        if ($sessionIdPtu -and $assistantMsg) {
            $routingRe = [regex]'(?i)\[arka:routing\]\s*([A-Za-z_-]+)\s*->\s*([A-Za-z_-]+)'
            $trivialRe = [regex]'(?i)\[arka:trivial\]\s*\S+'
            $markerKind = ''
            $markerDept = ''
            $markerLead = ''
            $routingMatch = $routingRe.Match($assistantMsg)
            if ($routingMatch.Success) {
                $markerKind = 'routing'
                $markerDept = $routingMatch.Groups[1].Value
                $markerLead = $routingMatch.Groups[2].Value
            } elseif ($trivialRe.IsMatch($assistantMsg)) {
                $markerKind = 'trivial'
            }
            if ($markerKind) {
                $arkaosRootPtu = $env:ARKAOS_ROOT
                if (-not $arkaosRootPtu) {
                    $repoPathFile = Join-Path $env:USERPROFILE '.arkaos\.repo-path'
                    if (Test-Path -LiteralPath $repoPathFile) {
                        try {
                            $arkaosRootPtu = (Get-Content -Raw -LiteralPath $repoPathFile -Encoding UTF8).Trim()
                        } catch { }
                    }
                }
                if (-not $arkaosRootPtu) {
                    $arkaosRootPtu = Join-Path $env:USERPROFILE '.arkaos'
                }
                # Locate Python (venv-first, then system).
                $pythonForMarker = $null
                $venvPy = Join-Path $env:USERPROFILE '.arkaos\venv\Scripts\python.exe'
                if (Test-Path -LiteralPath $venvPy) {
                    $pythonForMarker = $venvPy
                } else {
                    foreach ($cmd in 'python3','python','py') {
                        $resolved = Get-Command $cmd -ErrorAction SilentlyContinue
                        if ($resolved) { $pythonForMarker = $resolved.Source; break }
                    }
                }
                if ($pythonForMarker) {
                    $pyCode = @"
import os
try:
    from core.workflow.marker_cache import write_marker
    write_marker(
        os.environ.get('SESSION_ID_PTU', ''),
        os.environ.get('MARKER_KIND', ''),
        os.environ.get('MARKER_DEPT', ''),
        os.environ.get('MARKER_LEAD', ''),
    )
except Exception:
    pass
"@
                    $psi = New-Object System.Diagnostics.ProcessStartInfo
                    $psi.FileName = $pythonForMarker
                    $psi.Arguments = "-c `"$($pyCode -replace '"','\"' -replace "`r?`n",'; ')`""
                    $psi.UseShellExecute = $false
                    $psi.CreateNoWindow = $true
                    $psi.RedirectStandardOutput = $true
                    $psi.RedirectStandardError = $true
                    [void]$psi.EnvironmentVariables.Add('SESSION_ID_PTU', $sessionIdPtu)
                    [void]$psi.EnvironmentVariables.Add('MARKER_KIND', $markerKind)
                    [void]$psi.EnvironmentVariables.Add('MARKER_DEPT', $markerDept)
                    [void]$psi.EnvironmentVariables.Add('MARKER_LEAD', $markerLead)
                    [void]$psi.EnvironmentVariables.Add('PYTHONPATH', $arkaosRootPtu)
                    try {
                        $proc = [System.Diagnostics.Process]::Start($psi)
                        if (-not $proc.WaitForExit(1500)) { try { $proc.Kill() } catch { } }
                    } catch { }
                }
            }
        }
    } catch { }

    # ─── Only process when there is actually an error ─────────────────
    $errorPattern = '(?i)(error:|fatal:|exception:|failed|ENOENT|EACCES|EPERM|panic:)'
    if ($exitCode -eq '0' -or [string]::IsNullOrEmpty($exitCode)) {
        if ($toolOutput -notmatch $errorPattern) {
            $shouldProcessGotchas = $false
        }
    }
}

# Paths that the metrics block needs are declared up here, outside the
# gotchas-processing branch, so the metrics write at the very bottom of
# the file works even when `shouldProcessGotchas` is false (empty stdin,
# invalid JSON, no error pattern, etc.).
$arkaosRuntimeDir = Join-Path $env:USERPROFILE '.arkaos'
$null = New-Item -ItemType Directory -Force -Path $arkaosRuntimeDir -ErrorAction SilentlyContinue

# Gotchas processing lives inside a `do { ... } while ($false)` single-
# iteration loop so any inner step that used to `exit 0` can now `break`
# out of the gotchas block without bypassing the metrics write.
if ($shouldProcessGotchas) { do {

# ─── Extract first meaningful error line ─────────────────────────────
$lines = $toolOutput -split "`r?`n"
$errorLineRegex = '(?i)(error|fatal|exception|failed|ENOENT|EACCES|EPERM|panic|cannot|not found|permission denied)'
$errorLine = $null
foreach ($ln in $lines) {
    if ($ln -match $errorLineRegex) { $errorLine = $ln; break }
}
if ([string]::IsNullOrWhiteSpace($errorLine)) {
    # Fallback: first-5-lines-tail-1, same as `head -5 | tail -1` in bash.
    $firstFive = @($lines | Select-Object -First 5)
    if ($firstFive.Count -gt 0) { $errorLine = $firstFive[-1] }
}
if ([string]::IsNullOrWhiteSpace($errorLine)) {
    break
}

# ─── Normalize pattern (matches bash sed chain exactly) ───────────────
$pattern = $errorLine
$pattern = $pattern -replace '[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}[^ ]*', 'TIMESTAMP'
$pattern = $pattern -replace '[0-9a-f]{7,40}', 'HASH'
$pattern = $pattern -replace 'line [0-9]+', 'line N'
$pattern = $pattern -replace ':[0-9]+:', ':N:'
if ($pattern.Length -gt 200) { $pattern = $pattern.Substring(0, 200) }
if ([string]::IsNullOrWhiteSpace($pattern)) {
    break
}

# ─── Categorize ───────────────────────────────────────────────────────
$category = 'general'
if     ($errorLine -match '(?i)(artisan|eloquent|laravel|blade|migration|composer|php )')                  { $category = 'laravel' }
elseif ($errorLine -match '(?i)(npm|node|vue|react|nuxt|next|vite|webpack|typescript|tsx|jsx)')            { $category = 'frontend' }
elseif ($errorLine -match '(?i)(git |merge|rebase|checkout|branch|commit|push|pull)')                     { $category = 'git' }
elseif ($errorLine -match '(?i)(sql|postgres|mysql|database|migration|table|column|constraint)')           { $category = 'database' }
elseif ($errorLine -match '(?i)(permission|denied|EACCES|EPERM|chmod|chown|sudo)')                         { $category = 'permissions' }
elseif ($errorLine -match '(?i)(test|assert|expect|jest|phpunit|bats|coverage)')                           { $category = 'testing' }

# ─── Match fix suggestion from gotchas-fixes.json ─────────────────────
$arkaSkillRoot = if ($env:ARKA_OS) { $env:ARKA_OS } else { Join-Path $env:USERPROFILE '.claude\skills\arka' }
$fixesFile = Join-Path $arkaSkillRoot 'config\gotchas-fixes.json'
if (-not (Test-Path -LiteralPath $fixesFile)) {
    $repoPathFile = Join-Path $arkaSkillRoot '.repo-path'
    if (Test-Path -LiteralPath $repoPathFile) {
        try {
            $repoPath = (Get-Content -Raw -LiteralPath $repoPathFile -Encoding UTF8).Trim()
            if ($repoPath) {
                $candidate = Join-Path $repoPath 'config\gotchas-fixes.json'
                if (Test-Path -LiteralPath $candidate) { $fixesFile = $candidate }
            }
        } catch { }
    }
}

$suggestion = ''
if (Test-Path -LiteralPath $fixesFile) {
    try {
        $fixes = (Get-Content -Raw -LiteralPath $fixesFile -Encoding UTF8 | ConvertFrom-Json).fixes
        foreach ($fix in @($fixes)) {
            if ($fix.pattern_match -and ($errorLine -imatch [string]$fix.pattern_match)) {
                $suggestion = [string]$fix.suggestion
                break
            }
        }
    } catch { }
}

# ─── Detect active project ────────────────────────────────────────────
$project = ''
if ($cwd) {
    try {
        $repoPathFile = Join-Path $arkaSkillRoot '.repo-path'
        if (Test-Path -LiteralPath $repoPathFile) {
            $repoPath = (Get-Content -Raw -LiteralPath $repoPathFile -Encoding UTF8).Trim()
            $projectsDir = Join-Path $repoPath 'projects'
            if ($repoPath -and (Test-Path -LiteralPath $projectsDir -PathType Container)) {
                foreach ($projDir in (Get-ChildItem -LiteralPath $projectsDir -Directory -ErrorAction SilentlyContinue)) {
                    $projectPathFile = Join-Path $projDir.FullName '.project-path'
                    if (Test-Path -LiteralPath $projectPathFile) {
                        $projPath = (Get-Content -Raw -LiteralPath $projectPathFile -Encoding UTF8).Trim()
                        if ($projPath -and $cwd.StartsWith($projPath)) {
                            $project = $projDir.Name
                            break
                        }
                    }
                }
            }
        }
    } catch { }
    if (-not $project) { $project = Split-Path -Leaf $cwd.TrimEnd('\','/') }
}

# ─── Update ~/.arkaos/gotchas.json (best-effort under a file lock) ────
# $arkaosRuntimeDir was declared at the top of the script so the metrics
# block can always reach it.
$gotchasFile  = Join-Path $arkaosRuntimeDir 'gotchas.json'
$gotchasLock  = Join-Path $arkaosRuntimeDir 'gotchas.lock'

$lock = Acquire-FileLock -LockPath $gotchasLock
if ($null -ne $lock) {
    try {
        $now = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

        $gotchas = @()
        if (Test-Path -LiteralPath $gotchasFile) {
            try {
                $raw = Get-Content -Raw -LiteralPath $gotchasFile -Encoding UTF8
                if ($raw -and $raw.Trim()) {
                    $parsed = $raw | ConvertFrom-Json
                    $gotchas = @($parsed)
                }
            } catch {
                $gotchas = @()
            }
        }

        $existingIdx = -1
        for ($i = 0; $i -lt $gotchas.Count; $i++) {
            if ([string]$gotchas[$i].pattern -eq $pattern) {
                $existingIdx = $i
                break
            }
        }

        if ($existingIdx -ge 0) {
            $entry = $gotchas[$existingIdx]
            $entry.count      = [int]$entry.count + 1
            $entry.last_seen  = $now
            if ($project) {
                $existingProjects = @()
                if ($entry.projects) { $existingProjects = @($entry.projects) }
                if ($existingProjects -notcontains $project) {
                    $existingProjects += $project
                }
                $entry.projects = (New-StringArrayList -Initial $existingProjects)
            }
            if ($suggestion -and [string]::IsNullOrEmpty([string]$entry.suggestion)) {
                $entry | Add-Member -NotePropertyName suggestion -NotePropertyValue $suggestion -Force
            }
            $gotchas[$existingIdx] = $entry
        } else {
            $fullPattern = if ($errorLine.Length -gt 500) { $errorLine.Substring(0, 500) } else { $errorLine }
            $projectsList = if ($project) {
                New-StringArrayList -Initial @($project)
            } else {
                New-StringArrayList
            }
            $newEntry = [pscustomobject][ordered]@{
                pattern       = $pattern
                full_pattern  = $fullPattern
                category      = $category
                tool          = $toolName
                count         = 1
                first_seen    = $now
                last_seen     = $now
                projects      = $projectsList
                suggestion    = if ($suggestion) { $suggestion } else { $null }
            }
            $gotchas = @($gotchas) + $newEntry
        }

        # Keep top 100 by count desc. Force array with @() after the
        # pipeline — PS 5.1 unwraps to a scalar when only one remains.
        $gotchas = @($gotchas | Sort-Object -Property count -Descending | Select-Object -First 100)

        Write-JsonAtomic -Path $gotchasFile -Json (ConvertTo-JsonArray -Items $gotchas -Depth 10)
    } catch {
        # Swallow — gotchas tracking is best-effort, must not fail the hook.
    } finally {
        $lock.Close()
        $lock.Dispose()
    }
}

} while ($false) }  # end: do/while single-iteration + if ($shouldProcessGotchas)

# ─── Log hook metrics (best-effort) ───────────────────────────────────
$metricsFile = Join-Path $arkaosRuntimeDir 'hook-metrics.json'
$metricsLock = Join-Path $arkaosRuntimeDir 'hook-metrics.lock'
$metricsLockHandle = Acquire-FileLock -LockPath $metricsLock -TimeoutMs 2000
if ($null -ne $metricsLockHandle) {
    try {
        $metrics = @()
        if (Test-Path -LiteralPath $metricsFile) {
            try {
                $raw = Get-Content -Raw -LiteralPath $metricsFile -Encoding UTF8
                if ($raw -and $raw.Trim()) { $metrics = @(($raw | ConvertFrom-Json)) }
            } catch { $metrics = @() }
        }
        $metrics = @($metrics) + ([pscustomobject]@{
            hook        = 'post-tool-use'
            duration_ms = [int]$sw.ElapsedMilliseconds
            timestamp   = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        })
        if ($metrics.Count -gt 500) { $metrics = @($metrics[-500..-1]) }
        Write-JsonAtomic -Path $metricsFile -Json (ConvertTo-JsonArray -Items $metrics -Depth 5)
    } catch {
        # Metrics are non-critical.
    } finally {
        $metricsLockHandle.Close()
        $metricsLockHandle.Dispose()
    }
}

# Silent output — PostToolUse does not inject context.
'{}'
