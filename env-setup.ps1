# ============================================================================
# ArkaOS - Environment Setup (Windows / PowerShell 5.1+)
#
# Port of env-setup.sh. Interactively prompts the user for the ArkaOS
# service keys and the MCP integration keys defined in mcps/registry.json,
# then persists them to:
#
#   %USERPROFILE%\.arkaos\arkaos-env.ps1
#
# A sourcing line is appended to the user's PowerShell profile so the
# variables become available in every new PowerShell session:
#
#   . "$HOME\.arkaos\arkaos-env.ps1"
#
# Unlike the bash counterpart we do NOT touch ~/.zshrc (irrelevant on
# Windows) and we do NOT use setx or [Environment]::SetEnvironmentVariable
# to write to the user registry hive - keeping the env in a transparent
# PS1 file on disk matches the reversibility of the .env + source flow
# the bash version offers.
#
# NOTE: the PowerShell state lives under `.arkaos` (v2 canonical path).
# The bash twin (env-setup.sh) continues to write to `.arka-os` (v1 path)
# because the v1 bash tooling in `bin/arka*` reads `.env` from there.
# Bash and PowerShell env-var state are independent (different shells
# have different environments), so the two scripts targeting different
# directories is not a functional issue.
#
# Pure ASCII on purpose. Any typographic characters rendered in the
# banner are built at runtime from [char] codes.
# ============================================================================

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# --- Paths -----------------------------------------------------------------
$arkaEnvDir  = Join-Path $env:USERPROFILE '.arkaos'
$arkaEnvFile = Join-Path $arkaEnvDir 'arkaos-env.ps1'
$scriptDir   = $PSScriptRoot
$registry    = Join-Path $scriptDir 'mcps\registry.json'

$null = New-Item -ItemType Directory -Force -Path $arkaEnvDir -ErrorAction SilentlyContinue

# --- Banner ----------------------------------------------------------------
$tl = [char]0x2554; $tr = [char]0x2557
$bl = [char]0x255A; $br = [char]0x255D
$h  = [char]0x2550; $v  = [char]0x2551
$width = 62
$bar = [string]$h * $width

Write-Host ''
Write-Host ("  $tl$bar$tr") -ForegroundColor Cyan
Write-Host ("  $v  ArkaOS - Environment Setup                                 $v") -ForegroundColor Cyan
Write-Host ("  $v  Configure API keys for MCP integrations                    $v") -ForegroundColor Cyan
Write-Host ("  $bl$bar$br") -ForegroundColor Cyan
Write-Host ''

# --- Load existing env file (so we can preserve already-set values) -------
# Source by dot-sourcing the file into a nested scope via `. <file>`. This
# sets every `$env:KEY = "..."` line on the caller for the remainder of
# this script run.
if (Test-Path -LiteralPath $arkaEnvFile) {
    try {
        . $arkaEnvFile
        Write-Host "Loaded existing configuration from $arkaEnvFile" -ForegroundColor Green
        Write-Host ''
    } catch {
        Write-Host "! Existing env file could not be sourced: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host ''
    }
}

# --- Guidance lookup table -------------------------------------------------
$guidance = @{
    CLICKUP_API_KEY     = 'Go to ClickUp > Settings > Apps > Generate API Token'
    CLICKUP_TEAM_ID     = 'Go to ClickUp > Settings > Spaces > Team ID in URL'
    FIRECRAWL_API_KEY   = 'Go to firecrawl.dev > Dashboard > API Keys'
    PG_HOST             = 'Your PostgreSQL host (e.g. localhost, db.supabase.co)'
    PG_PORT             = 'Your PostgreSQL port (default: 5432)'
    PG_USER             = 'Your PostgreSQL username'
    PG_PASSWORD         = 'Your PostgreSQL password'
    PG_DATABASE         = 'Your PostgreSQL database name'
    DISCORD_TOKEN       = 'Go to discord.com/developers > New App > Bot > Token'
    WHATSAPP_API_TOKEN  = 'Go to developers.facebook.com > WhatsApp > API Setup > Token'
    WHATSAPP_PHONE_ID   = 'Go to developers.facebook.com > WhatsApp > API Setup > Phone Number ID'
    TEAMS_APP_ID        = 'Go to portal.azure.com > App Registrations > Application (client) ID'
    TEAMS_APP_SECRET    = 'Go to portal.azure.com > App Registrations > Certificates & Secrets > New'
    MEMORY_BANK_ROOT    = 'Directory for persistent memory storage (default: ~/memory-bank)'
}

function Get-Guidance([string]$varName) {
    if ($guidance.ContainsKey($varName)) { return $guidance[$varName] }
    return 'Check the MCP documentation for this variable'
}

# --- Core helper: set + persist one env var --------------------------------
# Updates an in-memory map of vars, which gets flushed to the file at the
# end. This avoids the bash-style incremental grep/sed dance and is both
# atomic and cross-platform clean.
$envVars = @{}

# Pre-seed from the current environment so values already set (either by
# the sourced env file above or by the user's shell) are preserved when we
# rewrite the file.
foreach ($envEntry in Get-ChildItem Env:) {
    $envVars[$envEntry.Name] = $envEntry.Value
}

function Prompt-EnvVar {
    param(
        [string]$Name,
        [string]$Guidance
    )
    $currentValue = [Environment]::GetEnvironmentVariable($Name, 'Process')
    if (-not $currentValue) { $currentValue = $envVars[$Name] }

    if ($currentValue -and $currentValue -notlike '${*}') {
        Write-Host "  + $Name (already configured)" -ForegroundColor Green
        return [pscustomobject]@{ Configured = $false; Skipped = $false }
    }

    Write-Host $Name -ForegroundColor Blue
    Write-Host "  -> $Guidance" -ForegroundColor Yellow
    $value = Read-Host '  Value (press Enter to skip)'
    if ($value) {
        $envVars[$Name] = $value
        # Also set in the current process so follow-up checks see it.
        Set-Item -Path "Env:$Name" -Value $value
        Write-Host '  + Saved' -ForegroundColor Green
        Write-Host ''
        return [pscustomobject]@{ Configured = $true; Skipped = $false }
    }
    Write-Host '  - Skipped' -ForegroundColor Yellow
    Write-Host ''
    return [pscustomobject]@{ Configured = $false; Skipped = $true }
}

# --- ArkaOS service keys ---------------------------------------------------
Write-Host '[ArkaOS Service Keys]' -ForegroundColor Blue
Write-Host '  These keys enable AI features like Whisper transcription and LLM routing.'
Write-Host ''

$serviceKeys = @(
    @{ Name = 'OPENAI_API_KEY';       Guidance = 'Go to platform.openai.com > API Keys' }
    @{ Name = 'GEMINI_API_KEY';       Guidance = 'Go to aistudio.google.com > API Keys' }
    @{ Name = 'OPENROUTER_API_KEY';   Guidance = 'Go to openrouter.ai > Dashboard > Keys' }
    @{ Name = 'REPLICATE_API_TOKEN';  Guidance = 'Go to replicate.com > Account > API Tokens' }
    @{ Name = 'FAL_KEY';              Guidance = 'Go to fal.ai > Dashboard > Keys' }
)

$serviceConfigured = 0
$serviceSkipped = 0
foreach ($entry in $serviceKeys) {
    $result = Prompt-EnvVar -Name $entry.Name -Guidance $entry.Guidance
    if ($result.Configured) { $serviceConfigured++ }
    if ($result.Skipped)    { $serviceSkipped++ }
}

Write-Host "  Service keys: $serviceConfigured configured, $serviceSkipped skipped" -ForegroundColor Cyan
Write-Host ''

# --- MCP integration keys --------------------------------------------------
Write-Host '[MCP Integration Keys]' -ForegroundColor Blue
Write-Host ''

$mcpVars = @()
if (Test-Path -LiteralPath $registry) {
    try {
        $reg = Get-Content -Raw -LiteralPath $registry -Encoding UTF8 | ConvertFrom-Json
        if ($reg.mcpServers) {
            $collected = @()
            foreach ($serverProp in $reg.mcpServers.PSObject.Properties) {
                $server = $serverProp.Value
                if ($server.required_env) {
                    foreach ($needed in @($server.required_env)) {
                        if ($needed) { $collected += [string]$needed }
                    }
                }
            }
            $mcpVars = $collected | Sort-Object -Unique
        }
    } catch {
        Write-Host "! Could not parse ${registry}: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

$configured = 0
$skipped = 0
if (-not $mcpVars -or $mcpVars.Count -eq 0) {
    Write-Host 'No environment variables to configure.' -ForegroundColor Green
} else {
    foreach ($varName in $mcpVars) {
        $result = Prompt-EnvVar -Name $varName -Guidance (Get-Guidance $varName)
        if ($result.Configured) { $configured++ }
        if ($result.Skipped)    { $skipped++ }
    }
}

# --- Flush to the env file -------------------------------------------------
# The bash version uses grep/sed line rewriting; we instead always rewrite
# the whole file from the in-memory map, keeping only the variables that
# are actually relevant to ArkaOS (service keys + MCP vars). This avoids
# leaking unrelated process env into the file.
$relevantVars = @()
$relevantVars += @($serviceKeys | ForEach-Object { $_.Name })
$relevantVars += @($mcpVars)
$relevantVars = $relevantVars | Where-Object { $_ } | Sort-Object -Unique

$envFileContent = @(
    '# ArkaOS environment variables',
    '# Auto-generated by env-setup.ps1 - safe to regenerate.',
    '# Source with: . $HOME\.arkaos\arkaos-env.ps1',
    ''
)
foreach ($name in $relevantVars) {
    $current = [Environment]::GetEnvironmentVariable($name, 'Process')
    if (-not $current) { continue }
    # Single-quote and escape any embedded single quotes by doubling.
    $escaped = $current -replace "'", "''"
    $envFileContent += "`$env:$name = '$escaped'"
}

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($arkaEnvFile, ($envFileContent -join [Environment]::NewLine), $utf8NoBom)
Write-Host "+ Env file written: $arkaEnvFile" -ForegroundColor Green

# --- Wire into the PowerShell profile --------------------------------------
# $PROFILE is an automatic variable pointing at the current user's profile
# script path. Create it if missing and append a sourcing line the first
# time.
$profilePath = $PROFILE
$profileDir = Split-Path -Parent $profilePath
if (-not (Test-Path -LiteralPath $profileDir)) {
    $null = New-Item -ItemType Directory -Force -Path $profileDir -ErrorAction SilentlyContinue
}
if (-not (Test-Path -LiteralPath $profilePath)) {
    [System.IO.File]::WriteAllText($profilePath, '', $utf8NoBom)
}

$sourceLine = ". `"$arkaEnvFile`""
$profileContent = ''
try { $profileContent = Get-Content -Raw -LiteralPath $profilePath -Encoding UTF8 } catch { }

if ($profileContent -notlike "*$arkaEnvFile*") {
    $append = @(
        '',
        '# ArkaOS Environment',
        ('if (Test-Path "{0}") {{ . "{0}" }}' -f $arkaEnvFile),
        ''
    ) -join [Environment]::NewLine
    [System.IO.File]::AppendAllText($profilePath, $append, $utf8NoBom)
    Write-Host "+ Added env sourcing to PowerShell profile ($profilePath)" -ForegroundColor Green
}

# --- Capability detection --------------------------------------------------
Write-Host ''
Write-Host '[Capability Detection]' -ForegroundColor Blue
$capsScriptUnix = Join-Path $scriptDir 'departments\kb\scripts\kb-check-capabilities.sh'
$capsScriptPs1  = Join-Path $scriptDir 'departments\kb\scripts\kb-check-capabilities.ps1'
$globalCapsSh   = Join-Path $env:USERPROFILE '.claude\skills\arka-knowledge\scripts\kb-check-capabilities.sh'
$globalCapsPs1  = Join-Path $env:USERPROFILE '.claude\skills\arka-knowledge\scripts\kb-check-capabilities.ps1'

if (Test-Path -LiteralPath $capsScriptPs1) {
    & $capsScriptPs1
} elseif (Test-Path -LiteralPath $globalCapsPs1) {
    & $globalCapsPs1
} elseif (Test-Path -LiteralPath $capsScriptUnix -PathType Leaf) {
    Write-Host '  ! Capability check is only available as a bash script on this installation.' -ForegroundColor Yellow
    Write-Host "    Expected a PowerShell port at: $capsScriptPs1" -ForegroundColor DarkGray
} elseif (Test-Path -LiteralPath $globalCapsSh -PathType Leaf) {
    Write-Host '  ! Global capability check is only available as a bash script.' -ForegroundColor Yellow
} else {
    Write-Host '  ! Capability check script not found - run the installer first.' -ForegroundColor Yellow
}

# --- Summary ---------------------------------------------------------------
Write-Host ''
Write-Host '=== Environment Setup Complete ===' -ForegroundColor Green
Write-Host "  Service keys: $serviceConfigured configured"
Write-Host "  MCP keys:     $configured configured, $skipped skipped"
Write-Host "  Env file:     $arkaEnvFile"
Write-Host "  Capabilities: $(Join-Path $arkaEnvDir 'capabilities.json')"
Write-Host ''
Write-Host 'Open a new PowerShell window (or run ". $PROFILE") to load the variables.' -ForegroundColor Cyan
Write-Host '==================================' -ForegroundColor Green
