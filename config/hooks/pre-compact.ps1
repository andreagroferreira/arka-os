# ============================================================================
# ArkaOS - PreCompact Hook (Session Digest) (Windows / PowerShell 5.1+)
#
# Port of config/hooks/pre-compact.sh. Fires before Claude Code compacts the
# context window. Saves a markdown digest of the session so nothing is lost.
#
# Contract:
# - Reads a JSON payload from stdin with `session_id`, `transcript`, and
#   optionally `messages`.
# - Writes `%USERPROFILE%\.arkaos\session-digests\<ts>-<id>.md`.
# - Prunes the digest directory to the 50 most recent entries.
# - Logs a metrics row to `hook-metrics.json`.
# - Emits `{}` on stdout - no context injection.
#
# State files live under the canonical v2 runtime directory `~/.arkaos/`.
# Older builds of the bash twin used `~/.arka-os/` (with a dash); the
# bash hook has been fixed in the same commit series, and the installer
# update path now carries legacy state forward on the first update.
#
# File is pure ASCII on purpose; PS 5.1 reads source files as ANSI by
# default, which would mojibake any embedded Unicode. Typographic chars
# used in the output markdown are built from [char] codes at runtime.
# ============================================================================

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$sw = [System.Diagnostics.Stopwatch]::StartNew()

# --- Read stdin --------------------------------------------------------
$stdinText = [Console]::In.ReadToEnd()
$payload = $null
if (-not [string]::IsNullOrWhiteSpace($stdinText)) {
    try { $payload = $stdinText | ConvertFrom-Json } catch { $payload = $null }
}

$sessionId  = if ($payload -and $payload.session_id) { [string]$payload.session_id } else { 'unknown' }
$transcript = if ($payload -and $payload.transcript) { [string]$payload.transcript } else { '' }

# --- Paths -------------------------------------------------------------
# $arkaosRuntimeDir is declared up-front so the metrics block at the
# bottom of the file can always reach it, even when we skip the digest
# write below on empty stdin.
$arkaosRuntimeDir = Join-Path $env:USERPROFILE '.arkaos'
$null = New-Item -ItemType Directory -Force -Path $arkaosRuntimeDir -ErrorAction SilentlyContinue

# --- Empty-stdin guard (Windows CC v2.1.97 upstream bug) --------------
# Claude Code on Windows currently opens the hook stdin pipe but writes
# zero bytes, so `$payload.messages` and `$payload.transcript` are both
# empty. Writing a `(no transcript available)` digest in that case just
# spams the session-digests directory with empty files and risks
# evicting real digests when the 50-file rotation runs.
#
# Fast-path: if there is nothing to digest, skip the file write entirely
# but still fall through to the metrics block so we can prove the hook
# fired. Mirrors the `shouldProcess` pattern used in post-tool-use.ps1.
$hasContent = $false
if ($transcript) { $hasContent = $true }
if (-not $hasContent -and $payload -and $payload.messages) {
    try {
        foreach ($m in @($payload.messages)) {
            if ($m.role -eq 'assistant' -and $null -ne $m.content -and [string]$m.content) {
                $hasContent = $true
                break
            }
        }
    } catch { }
}

# When $hasContent is false we still compute the digest path variables
# below (they have no side effects) but everything that writes to disk
# under the digest directory is wrapped in `if ($hasContent)` so we
# can't spam ghost digests or prune real ones on empty input.

$digestDir  = Join-Path $arkaosRuntimeDir 'session-digests'
$timestamp  = (Get-Date).ToString('yyyyMMdd-HHmmss')
$shortId    = if ($sessionId.Length -ge 8) { $sessionId.Substring(0, 8) } else { $sessionId }
$digestFile = Join-Path $digestDir "$timestamp-$shortId.md"

if ($hasContent) {
    $null = New-Item -ItemType Directory -Force -Path $digestDir -ErrorAction SilentlyContinue
}

# --- Extract tail of transcript (last 50 lines) -----------------------
$tailLines = '(no transcript available)'
if ($transcript) {
    $split = $transcript -split "`r?`n"
    if ($split.Count -gt 50) {
        $tailLines = ($split[-50..-1] -join "`n")
    } else {
        $tailLines = ($split -join "`n")
    }
}

# --- Extract last 5 assistant messages --------------------------------
# Walks payload.messages, takes the subset where role == "assistant",
# grabs the last up-to-five .content values, and joins them with blank
# lines. The bash twin (config/hooks/pre-compact.sh) is fixed at the
# same time by replacing `jq '... | last(5) | ...'` (a no-op) with the
# `[-5:]` array slice.
$assistantMsgs = ''
if ($payload -and $payload.messages) {
    try {
        $assistantContents = @()
        foreach ($m in @($payload.messages)) {
            if ($m.role -eq 'assistant' -and $null -ne $m.content) {
                $assistantContents += [string]$m.content
            }
        }
        if ($assistantContents.Count -gt 0) {
            $lastFive = if ($assistantContents.Count -gt 5) {
                $assistantContents[-5..-1]
            } else {
                $assistantContents
            }
            # Single newline matches the bash `jq '... | .[]'` iteration.
            $assistantMsgs = ($lastFive -join "`n")
        }
    } catch {
        # Malformed messages array - fall back to empty, like bash `|| true`.
    }
}

# --- Build digest markdown -----------------------------------------
$emdash = [char]0x2014
$nowHuman = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
$assistantBlock = if ($assistantMsgs) { $assistantMsgs } else { '_(none captured)_' }

# $utf8NoBom is also used by the metrics block below, so declare it
# outside the $hasContent branch.
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)

if ($hasContent) {
    $digest = @"
---
type: session-digest
session_id: $sessionId
timestamp: $timestamp
trigger: pre-compact
---

# Session Digest $emdash $timestamp

**Session:** ``$sessionId``
**Saved at:** $nowHuman
**Trigger:** Context compaction

## Last Assistant Messages

$assistantBlock

## Transcript Tail (last 50 lines)

``````
$tailLines
``````
"@

    # Write BOM-less UTF-8 so other tools that read these files (grep, jq,
    # python) behave consistently across platforms.
    [System.IO.File]::WriteAllText($digestFile, $digest, $utf8NoBom)

    # --- Prune to last 50 digests -------------------------------------
    try {
        $digests = @(
            Get-ChildItem -LiteralPath $digestDir -Filter '*.md' -ErrorAction SilentlyContinue |
                Sort-Object LastWriteTime -Descending
        )
        if ($digests.Count -gt 50) {
            $toRemove = $digests[50..($digests.Count - 1)]
            foreach ($f in $toRemove) {
                Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {
        # Best-effort cleanup.
    }
}

# --- Metrics (shared shape with post-tool-use) ------------------------
function Acquire-FileLock {
    param([string]$LockPath, [int]$TimeoutMs = 2000)
    $deadline = [Environment]::TickCount + $TimeoutMs
    while ([Environment]::TickCount -lt $deadline) {
        try {
            return [System.IO.File]::Open(
                $LockPath,
                [System.IO.FileMode]::OpenOrCreate,
                [System.IO.FileAccess]::ReadWrite,
                [System.IO.FileShare]::None
            )
        } catch {
            Start-Sleep -Milliseconds 50
        }
    }
    return $null
}

function ConvertTo-JsonArray {
    param($Items, [int]$Depth = 5)
    $arr = @($Items)
    if ($arr.Count -eq 0) { return '[]' }
    $parts = foreach ($item in $arr) { $item | ConvertTo-Json -Depth $Depth -Compress }
    return '[' + ($parts -join ',') + ']'
}

$metricsFile = Join-Path $arkaosRuntimeDir 'hook-metrics.json'
$metricsLock = Join-Path $arkaosRuntimeDir 'hook-metrics.lock'
$lock = Acquire-FileLock -LockPath $metricsLock
if ($null -ne $lock) {
    try {
        $metrics = @()
        if (Test-Path -LiteralPath $metricsFile) {
            try {
                $raw = Get-Content -Raw -LiteralPath $metricsFile -Encoding UTF8
                if ($raw -and $raw.Trim()) { $metrics = @(($raw | ConvertFrom-Json)) }
            } catch { $metrics = @() }
        }
        $metrics = @($metrics) + ([pscustomobject]@{
            hook        = 'pre-compact'
            duration_ms = [int]$sw.ElapsedMilliseconds
            timestamp   = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        })
        if ($metrics.Count -gt 500) { $metrics = @($metrics[-500..-1]) }

        $tmp = "$metricsFile.tmp"
        [System.IO.File]::WriteAllText($tmp, (ConvertTo-JsonArray -Items $metrics -Depth 5), $utf8NoBom)
        Move-Item -Force -LiteralPath $tmp -Destination $metricsFile
    } catch {
        # Non-critical.
    } finally {
        $lock.Close()
        $lock.Dispose()
    }
}

# Silent output.
'{}'
