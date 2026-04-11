# ============================================================================
# ArkaOS - Claude Code Wrapper (Windows / PowerShell 5.1+)
#
# Port of bin/arka-claude. Displays the branded greeting deterministically
# (no LLM involved) and then hands control to `claude` with any forwarded
# arguments.
#
# Usage: arka-claude [any claude args...]
#
# This script is normally invoked through its .cmd shim (bin/arka-claude.cmd)
# so it works from cmd.exe, PowerShell, and Windows Terminal without the
# caller having to remember the `powershell -File ...` invocation.
#
# Pure ASCII on purpose: PS 5.1 reads source files as ANSI by default.
# Box-drawing characters are built at runtime from [char] codes.
# ============================================================================

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$arkaosHome = Join-Path $env:USERPROFILE '.arkaos'

# --- Profile ---------------------------------------------------------------
$name    = 'founder'
$company = 'WizardingCode'
$version = '2.x'

$profilePath = Join-Path $arkaosHome 'profile.json'
if (Test-Path -LiteralPath $profilePath) {
    try {
        $arkaosProfile = Get-Content -Raw -LiteralPath $profilePath -Encoding UTF8 | ConvertFrom-Json
        if ($arkaosProfile.name)     { $name    = [string]$arkaosProfile.name }
        elseif ($arkaosProfile.role) { $name    = [string]$arkaosProfile.role }
        if ($arkaosProfile.company)  { $company = [string]$arkaosProfile.company }
    } catch { }
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

# --- Time greeting ---------------------------------------------------------
$hour = [int](Get-Date -Format 'HH')
if     ($hour -ge 5  -and $hour -lt 12) { $greeting = 'Bom dia' }
elseif ($hour -ge 12 -and $hour -lt 19) { $greeting = 'Boa tarde' }
else                                     { $greeting = 'Boa noite' }

# --- Version drift ---------------------------------------------------------
$driftMsg = ''
$syncStatePath = Join-Path $arkaosHome 'sync-state.json'
if (Test-Path -LiteralPath $syncStatePath) {
    try {
        $ss = Get-Content -Raw -LiteralPath $syncStatePath -Encoding UTF8 | ConvertFrom-Json
        $synced = if ($null -ne $ss.version) { [string]$ss.version } else { 'none' }
        if ($synced -ne $version) {
            $driftMsg = 'Update available: run /arka update to sync'
        }
    } catch { }
}

# --- Build ASCII header ----------------------------------------------------
# Box drawing chars as runtime literals (not embedded in source).
$tl = [char]0x2554; $tr = [char]0x2557
$bl = [char]0x255A; $br = [char]0x255D
$h  = [char]0x2550; $v  = [char]0x2551
$sep = [char]0x2502  # light vertical bar used in the stat line
$innerWidth = 46
$barLine = ([string]$h * $innerWidth)
$emptyBox = "$v" + (' ' * $innerWidth) + "$v"

function Pad-Centered([string]$text, [int]$width) {
    $padLeft  = [int](($width - $text.Length) / 2)
    $padRight = $width - $text.Length - $padLeft
    return (' ' * $padLeft) + $text + (' ' * $padRight)
}

# --- Display ---------------------------------------------------------------
Write-Host ''
Write-Host ("  $tl$barLine$tr")                                 -ForegroundColor Green
Write-Host ("  $v" + (' ' * $innerWidth) + "$v")                -ForegroundColor Green
Write-Host ("  $v")                                             -NoNewline -ForegroundColor Green
Write-Host (Pad-Centered 'A R K A   O S' $innerWidth)          -NoNewline -ForegroundColor White
Write-Host ("$v")                                               -ForegroundColor Green
Write-Host ("  $v" + (' ' * $innerWidth) + "$v")                -ForegroundColor Green
Write-Host ("  $v")                                             -NoNewline -ForegroundColor Green
Write-Host (Pad-Centered 'The Operating System for AI Teams' $innerWidth) -NoNewline -ForegroundColor DarkGray
Write-Host ("$v")                                               -ForegroundColor Green
Write-Host ("  $v")                                             -NoNewline -ForegroundColor Green
Write-Host (Pad-Centered 'by WizardingCode' $innerWidth)        -NoNewline -ForegroundColor DarkGray
Write-Host ("$v")                                               -ForegroundColor Green
Write-Host ("  $v" + (' ' * $innerWidth) + "$v")                -ForegroundColor Green
Write-Host ("  $bl$barLine$br")                                 -ForegroundColor Green
Write-Host ''

Write-Host "  $greeting, $name " -NoNewline -ForegroundColor Cyan
Write-Host "($company)"           -ForegroundColor DarkGray
Write-Host ("  ArkaOS v$version $sep 65 agents $sep 17 departments $sep 244+ skills") -ForegroundColor DarkGray
if ($driftMsg) {
    Write-Host ''
    Write-Host "  ! $driftMsg" -ForegroundColor Yellow
}
Write-Host ''

# --- Launch Claude ---------------------------------------------------------
# The bash wrapper uses `exec claude "$@"` which replaces the shell.
# PowerShell has no exec equivalent; `& claude @args` spawns a child and
# blocks until it exits. The net effect for the user is the same.
$claude = Get-Command claude -ErrorAction SilentlyContinue
if (-not $claude) {
    Write-Host ''
    Write-Host '  Error: `claude` not found on PATH.' -ForegroundColor Red
    Write-Host '  Install Claude Code for Windows and re-run arka-claude.' -ForegroundColor DarkGray
    exit 127
}

& claude @args
exit $LASTEXITCODE
