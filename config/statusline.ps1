# ============================================================================
# ARKA OS — Two-Line Color-Coded Status Line for Claude Code (Windows port)
# Receives JSON via stdin, outputs formatted two-line status bar.
#
# Paridade 1:1 com config/statusline.sh. Usa ConvertFrom-Json nativo — no jq
# or bc dependency, works on stock Windows PowerShell 5.1 and PowerShell 7.
#
# Why a separate file instead of invoking the bash script: Windows has no
# POSIX shell on the default PATH, and wrapping via `wsl bash -c ...` adds
# ~150 ms per statusline render. This port matches the canonical schema
# documented by Claude Code's statusline payload (model.display_name,
# context_window.used_percentage, cost.total_cost_usd, etc.) — NOT the
# experimental statusline-v2.sh schema, which is broken.
# ============================================================================

$ErrorActionPreference = 'SilentlyContinue'

# Force UTF-8 on stdout so the Unicode box-drawing characters (█ ░ ▲)
# render correctly on Windows PowerShell 5.1, which otherwise emits
# cp1252 to the host and shows "?" in place of the blocks.
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

# ─── Read stdin ────────────────────────────────────────────────────────────
$raw = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($raw)) {
    # Claude Code may invoke the statusline with no payload at startup.
    # Emit a minimal banner so the bar is never blank.
    Write-Output ([char]0x25B2 + 'ARKA')
    return
}

# ─── Parse JSON ────────────────────────────────────────────────────────────
try {
    $j = $raw | ConvertFrom-Json
} catch {
    Write-Output ([char]0x25B2 + 'ARKA | json parse failed')
    return
}

# Safe nested property access. PSCustomObject returns $null silently for
# missing members, which is the behavior we want — mimics jq's `// default`.
function Get-Field($obj, $path, $default) {
    $cur = $obj
    foreach ($seg in $path -split '\.') {
        if ($null -eq $cur) { return $default }
        $cur = $cur.$seg
    }
    if ($null -eq $cur) { return $default }
    return $cur
}

$model    = [string](Get-Field $j 'model.display_name' 'unknown')
$cwd      = [string](Get-Field $j 'cwd' '')
$projDir  = [string](Get-Field $j 'workspace.project_dir' '')
$pctRaw   = Get-Field $j 'context_window.used_percentage' 0
$inTok    = [int64](Get-Field $j 'context_window.total_input_tokens' 0)
$outTok   = [int64](Get-Field $j 'context_window.total_output_tokens' 0)
$cost     = [double](Get-Field $j 'cost.total_cost_usd' 0)
$durMs    = [int64](Get-Field $j 'cost.total_duration_ms' 0)
$added    = [int64](Get-Field $j 'cost.total_lines_added' 0)
$removed  = [int64](Get-Field $j 'cost.total_lines_removed' 0)

$pct = [int][math]::Floor([double]$pctRaw)
if ($pct -lt 0)   { $pct = 0 }
if ($pct -gt 100) { $pct = 100 }

# ─── Project name ─────────────────────────────────────────────────────────
$workDir = if ($cwd) { $cwd } else { $projDir }
if ([string]::IsNullOrEmpty($workDir)) {
    $dirName = 'arka'
} else {
    $dirName = Split-Path -Leaf $workDir
}

# ─── Git branch ───────────────────────────────────────────────────────────
# No file cache: PowerShell startup already dominates the render cost, the
# git call is ~20 ms on NTFS, and caching across renders is unsafe because
# Claude Code can render the statusline from multiple cwd's concurrently.
$branch = ''
if ($workDir -and (Test-Path -LiteralPath $workDir)) {
    $branch = & git -C $workDir rev-parse --abbrev-ref HEAD 2>$null
    if ($null -eq $branch) { $branch = '' }
    $branch = ([string]$branch).Trim()
}

# ─── ANSI colors ──────────────────────────────────────────────────────────
$ESC         = [char]27
$C_RESET     = "$ESC[0m"
$C_CYAN      = "$ESC[0;36m"
$C_DIM       = "$ESC[2m"
$C_WHITE     = "$ESC[1;37m"
$C_GREEN     = "$ESC[0;32m"
$C_YELLOW    = "$ESC[1;33m"
$C_RED       = "$ESC[0;31m"
$C_BLINK_RED = "$ESC[5;31m"

if     ($pct -ge 90) { $C_BAR = $C_BLINK_RED }
elseif ($pct -ge 80) { $C_BAR = $C_RED }
elseif ($pct -ge 60) { $C_BAR = $C_YELLOW }
else                 { $C_BAR = $C_GREEN }

# ─── Format tokens (K/M, invariant culture so pt-PT doesn't emit "12,3K") ──
function Format-Tokens($n) {
    $inv = [cultureinfo]::InvariantCulture
    if ($n -ge 1000000) {
        return ([double]($n / 1000000.0)).ToString('0.0', $inv) + 'M'
    } elseif ($n -ge 1000) {
        return ([double]($n / 1000.0)).ToString('0.0', $inv) + 'K'
    } else {
        return "$n"
    }
}

$inFmt  = Format-Tokens $inTok
$outFmt = Format-Tokens $outTok

# ─── Progress bar (10 chars) ──────────────────────────────────────────────
# Floor the division: 95 % → 9 blocks, matching the bash integer division.
# PowerShell's `/` returns double, so [int] alone would round-to-even and
# drift on odd multiples of 5.
$filled = [int][math]::Floor($pct / 10.0)
$empty  = 10 - $filled
$block  = [char]0x2588  # █
$shade  = [char]0x2591  # ░
$bar    = ([string]$block * $filled) + ([string]$shade * $empty)

# ─── Format duration ──────────────────────────────────────────────────────
$secs = [int64][math]::Floor($durMs / 1000.0)
if ($secs -ge 3600) {
    $h = [int][math]::Floor($secs / 3600.0)
    $m = [int][math]::Floor(($secs % 3600) / 60.0)
    $timeFmt = "${h}h${m}m"
} elseif ($secs -ge 60) {
    $m = [int][math]::Floor($secs / 60.0)
    $r = [int]($secs % 60)
    $timeFmt = "${m}m${r}s"
} else {
    $timeFmt = "${secs}s"
}

# ─── Format cost (invariant culture: always "$0.00", never "$0,00") ───────
$costFmt = '$' + ([double]$cost).ToString('0.00', [cultureinfo]::InvariantCulture)

# ─── Build Line 1: Context bar ────────────────────────────────────────────
$triangle = [char]0x25B2  # ▲
$line1 = "${C_CYAN}${triangle}ARKA${C_RESET}  ${C_WHITE}${dirName}${C_RESET}"
if ($branch -and $branch -ne 'main' -and $branch -ne 'master') {
    $line1 += "  ${C_DIM}on${C_RESET} ${C_GREEN}${branch}${C_RESET}"
}
$line1 += "  ${C_DIM}|${C_RESET}  ${model}"

# ─── Build Line 2: Metrics bar ────────────────────────────────────────────
$line2  = "${C_BAR}${bar} ${pct}%${C_RESET}"
$line2 += "  ${C_DIM}|${C_RESET}  ${inFmt} in ${outFmt} out"
$line2 += "  ${C_DIM}|${C_RESET}  ${C_GREEN}+${added}${C_RESET} ${C_RED}-${removed}${C_RESET}"
$line2 += "  ${C_DIM}|${C_RESET}  ${timeFmt}"
$line2 += "  ${C_DIM}|${C_RESET}  ${costFmt}"

Write-Output $line1
Write-Output $line2
