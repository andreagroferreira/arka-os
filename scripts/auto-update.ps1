# ============================================================================
# ArkaOS — background auto-update, Windows twin of auto-update.sh (#548)
#
# Invoked by the menu bar "Check for updates" action or manually via
# `npx arkaos autoupdate run`. Same contract as the .sh twin: positional
# `--force` skips the version comparison; every failure path logs and
# exits 0 — a broken check must never surface as a crashing login item.
#
# Flow: registry check (short timeout) -> compare with the installed
# version (~/.arkaos/install-manifest.json) -> headless `npx -y
# arkaos@latest update` -> toast notification with the outcome. Project
# sync stays supervised: update.js resets sync-state.json, so the next
# Claude session surfaces [arka:update-available] and /arka update runs
# there.
#
# Encoding: this file is UTF-8 WITH BOM on purpose — Windows PowerShell
# 5.1 (what the menu bar invokes) reads BOM-less scripts as ANSI and
# mangles the accented pt-PT notification copy.
# ============================================================================
$ErrorActionPreference = "SilentlyContinue"

$ArkaHome = Join-Path $env:USERPROFILE ".arkaos"
$LogDir = Join-Path $ArkaHome "logs"
$Log = Join-Path $LogDir "auto-update.log"
$LockDir = Join-Path $ArkaHome "auto-update.lock"
$Manifest = Join-Path $ArkaHome "install-manifest.json"
$Optout = Join-Path $ArkaHome "autoupdate.optout"
$ProfileJson = Join-Path $ArkaHome "profile.json"
$RegistryUrl = "https://registry.npmjs.org/arkaos/latest"

$Force = $args -contains "--force"

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function Write-Log([string]$Message) {
    $stamp = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
    Add-Content -Path $Log -Value "$stamp $Message" -Encoding UTF8
}

# Keep the log bounded (~1MB cap, keep the newest half).
function Invoke-RotateLog {
    $item = Get-Item -Path $Log -ErrorAction SilentlyContinue
    if ($item -and $item.Length -gt 1048576) {
        $lines = Get-Content -Path $Log -Encoding UTF8
        $keep = $lines | Select-Object -Last ([int]($lines.Count / 2))
        Set-Content -Path $Log -Value $keep -Encoding UTF8
    }
}

function Get-JsonField([string]$File, [string]$Field) {
    try {
        $data = Get-Content -Path $File -Raw -Encoding UTF8 | ConvertFrom-Json
        return [string]$data.$Field
    } catch {
        return ""
    }
}

function Send-Notification([string]$Message) {
    Write-Log "notify: $Message"
    # Toast via WinRT (Windows PowerShell 5.1) — best-effort, log-only on
    # failure (matches the .sh posture: notify must never break the run).
    try {
        [void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
        [void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]
        $template = @"
<toast><visual><binding template="ToastGeneric"><text>ArkaOS</text><text>$([System.Security.SecurityElement]::Escape($Message))</text></binding></visual></toast>
"@
        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        $toast = New-Object Windows.UI.Notifications.ToastNotification($xml)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("ArkaOS").Show($toast)
    } catch {
        Write-Log "notify: toast unavailable ($($_.Exception.Message))"
    }
}

# Notification copy follows the installed profile language (pt -> pt-PT).
$LangCode = ""
if (Test-Path $ProfileJson) { $LangCode = Get-JsonField $ProfileJson "language" }

function Get-UpdatedMessage([string]$Version) {
    if ($LangCode -eq "pt") {
        return "Atualizado para v$Version. Os projetos sincronizam na próxima sessão Claude."
    }
    return "Updated to v$Version. Projects sync on your next Claude session."
}

function Get-FailedMessage([string]$Version) {
    if ($LangCode -eq "pt") {
        return "Falha no auto-update (v$Version). Corre: npx arkaos@latest update"
    }
    return "Auto-update failed (v$Version). Run: npx arkaos@latest update"
}

Invoke-RotateLog

# -- Opt-out and install guards ------------------------------------------
if (Test-Path $Optout) {
    Write-Log "skip: user opt-out marker present"
    exit 0
}
if (-not (Test-Path $Manifest)) {
    Write-Log "skip: no install-manifest.json - ArkaOS not installed"
    exit 0
}

# -- Lock (New-Item on an existing dir throws = atomic); reclaim stale
#    locks older than 2h ------------------------------------------------
$lockAcquired = $false
try {
    New-Item -ItemType Directory -Path $LockDir -ErrorAction Stop | Out-Null
    $lockAcquired = $true
} catch {
    $lock = Get-Item -Path $LockDir -ErrorAction SilentlyContinue
    if ($lock -and $lock.LastWriteTime -lt (Get-Date).AddMinutes(-120)) {
        Write-Log "reclaiming stale lock"
        Remove-Item -Path $LockDir -Force -ErrorAction SilentlyContinue
        try {
            New-Item -ItemType Directory -Path $LockDir -ErrorAction Stop | Out-Null
            $lockAcquired = $true
        } catch {
            Write-Log "skip: lock contention"
            exit 0
        }
    } else {
        Write-Log "skip: another auto-update run holds the lock"
        exit 0
    }
}

try {
    $Installed = Get-JsonField $Manifest "version"
    if (-not $Installed) {
        Write-Log "skip: could not read installed version from manifest"
        exit 0
    }

    $Latest = ""
    try {
        $response = Invoke-RestMethod -Uri $RegistryUrl -TimeoutSec 15 -ErrorAction Stop
        $Latest = [string]$response.version
    } catch {
        Write-Log "skip: registry unreachable (offline?)"
        exit 0
    }
    if (-not $Latest) {
        Write-Log "skip: could not parse registry response"
        exit 0
    }

    # Only ever move FORWARD: a dev/prerelease install newer than the
    # registry `latest` must not be silently downgraded (QG, Francisca).
    function Get-VersionKey([string]$Version) {
        $core = ($Version -split "[-+]")[0]
        $nums = @([regex]::Matches($core, "\d+") | ForEach-Object { [int]$_.Value })
        while ($nums.Count -lt 3) { $nums += 0 }
        # Prerelease sorts below its release: stable gets the higher flag.
        $stable = if ($Version -notmatch "-") { 1 } else { 0 }
        return ($nums[0], $nums[1], $nums[2], $stable)
    }

    function Test-IsNewer([string]$Candidate, [string]$Current) {
        $a = Get-VersionKey $Candidate
        $b = Get-VersionKey $Current
        for ($i = 0; $i -lt 4; $i++) {
            if ($a[$i] -gt $b[$i]) { return $true }
            if ($a[$i] -lt $b[$i]) { return $false }
        }
        return $false
    }

    if (-not $Force) {
        if ($Latest -eq $Installed) {
            Write-Log "up to date (v$Installed)"
            exit 0
        }
        if (-not (Test-IsNewer $Latest $Installed)) {
            Write-Log "installed v$Installed is ahead of registry v$Latest - skip"
            exit 0
        }
    }

    if (-not (Get-Command npx -ErrorAction SilentlyContinue)) {
        Write-Log "skip: npx unavailable - cannot apply v$Latest"
        exit 0
    }

    Write-Log "updating v$Installed -> v$Latest"
    # npx is npx.cmd - route through cmd (CreateProcess cannot exec batch
    # files); output appended to the same log as the .sh twin.
    cmd.exe /c "npx -y arkaos@latest update" 2>&1 | Add-Content -Path $Log -Encoding UTF8
    if ($LASTEXITCODE -eq 0) {
        Write-Log "update to v$Latest succeeded"
        Send-Notification (Get-UpdatedMessage $Latest)
    } else {
        Write-Log "update to v$Latest FAILED (see log above)"
        Send-Notification (Get-FailedMessage $Latest)
    }
} finally {
    if ($lockAcquired) {
        Remove-Item -Path $LockDir -Force -ErrorAction SilentlyContinue
    }
}
exit 0
