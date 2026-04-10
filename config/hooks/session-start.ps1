# ============================================================================
# ArkaOS — SessionStart Hook (Windows / PowerShell 5.1+)
#
# Port of config/hooks/session-start.sh. Must remain behaviourally identical:
# - Same profile lookup, time-based greeting, version-drift detection.
# - Same JSON output contract: {"systemMessage": "<...>"} on stdout.
#
# Minimum PowerShell: 5.1 (shipped with every Windows 10+). No pwsh 7 prereq.
# Box-drawing characters are built from [char] codes so this file stays pure
# ASCII and avoids source-encoding pitfalls with PS 5.1 default ANSI reads.
# ============================================================================

$ErrorActionPreference = 'Stop'
# Force UTF-8 on stdout so ConvertTo-Json does not emit mojibake box chars.
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$arkaosHome = Join-Path $env:USERPROFILE '.arkaos'

# ─── Profile ───────────────────────────────────────────────────────────
$name    = 'founder'
$company = 'WizardingCode'
$version = '2.x'

$profilePath = Join-Path $arkaosHome 'profile.json'
if (Test-Path -LiteralPath $profilePath) {
    try {
        # $profile is an automatic variable in PowerShell — use $arkaosProfile.
        $arkaosProfile = Get-Content -Raw -LiteralPath $profilePath -Encoding UTF8 | ConvertFrom-Json
        if ($arkaosProfile.name)      { $name    = [string]$arkaosProfile.name }
        elseif ($arkaosProfile.role)  { $name    = [string]$arkaosProfile.role }
        if ($arkaosProfile.company)   { $company = [string]$arkaosProfile.company }
    } catch {
        # Corrupt profile — keep defaults and continue.
    }
}

$repoPathFile = Join-Path $arkaosHome '.repo-path'
if (Test-Path -LiteralPath $repoPathFile) {
    try {
        $repo = (Get-Content -Raw -LiteralPath $repoPathFile -Encoding UTF8).Trim()
        if ($repo) {
            $versionFile = Join-Path $repo 'VERSION'
            if (Test-Path -LiteralPath $versionFile) {
                $version = (Get-Content -Raw -LiteralPath $versionFile -Encoding UTF8).Trim()
            }
        }
    } catch { }
}

# ─── Time greeting ─────────────────────────────────────────────────────
$hour = [int](Get-Date -Format 'HH')
if     ($hour -ge 5  -and $hour -lt 12) { $greeting = 'Bom dia' }
elseif ($hour -ge 12 -and $hour -lt 19) { $greeting = 'Boa tarde' }
else                                     { $greeting = 'Boa noite' }

# ─── Version drift ─────────────────────────────────────────────────────
$drift = ''
$syncStatePath = Join-Path $arkaosHome 'sync-state.json'
if (Test-Path -LiteralPath $syncStatePath) {
    try {
        $syncState = Get-Content -Raw -LiteralPath $syncStatePath -Encoding UTF8 | ConvertFrom-Json
        $synced = if ($null -ne $syncState.version) { [string]$syncState.version } else { 'none' }
        if ($synced -ne $version) {
            $drift = "`n[arka:update-available] Core v$version != synced v$synced. Run /arka update."
        }
    } catch {
        $drift = "`n[arka:update-available] Sync state unreadable. Run /arka update."
    }
} else {
    $drift = "`n[arka:update-available] Never synced. Run /arka update."
}

# ─── Build ASCII header from char codes ───────────────────────────────
$tl  = [char]0x2554  # ╔
$tr  = [char]0x2557  # ╗
$bl  = [char]0x255A  # ╚
$br  = [char]0x255D  # ╝
$h   = [char]0x2550  # ═
$v   = [char]0x2551  # ║
$bar = [string]($h.ToString() * 46)

$topLine    = "$tl$bar$tr"
$bottomLine = "$bl$bar$br"
$empty      = "$v" + (' ' * 46) + "$v"
function Pad-Line([string]$text) {
    $innerWidth = 46
    $padLeft  = [int](($innerWidth - $text.Length) / 2)
    $padRight = $innerWidth - $text.Length - $padLeft
    return "$v" + (' ' * $padLeft) + $text + (' ' * $padRight) + "$v"
}

$lines = @(
    $topLine
    $empty
    (Pad-Line 'A R K A   O S')
    $empty
    (Pad-Line 'The Operating System for AI Teams')
    (Pad-Line 'by WizardingCode')
    $empty
    $bottomLine
    ''
    "$greeting, $name ($company)"
    "ArkaOS v$version | 65 agents | 17 departments | 244+ skills$drift"
)

$msg = "`n" + ($lines -join "`n")

# ─── Output as systemMessage JSON (single line, same contract as .sh) ──
[pscustomobject]@{ systemMessage = $msg } | ConvertTo-Json -Compress
