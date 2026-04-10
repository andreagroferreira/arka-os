# ============================================================================
# ArkaOS Dashboard - Start FastAPI + Nuxt servers (Windows / PowerShell 5.1+)
#
# Port of scripts/start-dashboard.sh. Same contract:
# - Finds free TCP ports starting from ARKAOS_DASHBOARD_UI_PORT (default 3333).
# - Stops any previously-started dashboard processes recorded in the PID file.
# - Launches the FastAPI backend (scripts/dashboard-api.py) as a background
#   process with logs redirected to %USERPROFILE%\.arkaos\api.log.
# - Waits up to ~10 s for the API health endpoint.
# - Launches the Nuxt frontend in whichever mode is available: pre-built
#   .output, existing node_modules (dev mode), or install-then-dev.
# - Records the child PIDs and ports, prints a summary, and opens the
#   browser at the UI URL.
#
# Pure ASCII source on purpose (PS 5.1 reads source as ANSI by default).
# Box-drawing characters for the summary are built from [char] codes.
# ============================================================================

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# --- Paths -----------------------------------------------------------------
if ($env:ARKAOS_ROOT) {
    $arkaosRoot = $env:ARKAOS_ROOT
} else {
    $arkaosRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}
$dashboardDir = Join-Path $arkaosRoot 'dashboard'
$arkaosHome   = Join-Path $env:USERPROFILE '.arkaos'
$pidFile      = Join-Path $arkaosHome 'dashboard.pid'
$portFile     = Join-Path $arkaosHome 'dashboard.ports'
$apiLog       = Join-Path $arkaosHome 'api.log'

$null = New-Item -ItemType Directory -Force -Path $arkaosHome -ErrorAction SilentlyContinue

# --- Kill existing dashboard processes -------------------------------------
if (Test-Path -LiteralPath $pidFile) {
    try {
        $existingPids = Get-Content -LiteralPath $pidFile -Encoding ASCII -ErrorAction SilentlyContinue
        foreach ($line in $existingPids) {
            $pidValue = 0
            if ([int]::TryParse($line.Trim(), [ref]$pidValue) -and $pidValue -gt 0) {
                try { Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue } catch { }
            }
        }
    } catch { }
    Remove-Item -LiteralPath $pidFile, $portFile -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

# --- Find an available TCP port --------------------------------------------
# Windows-native port probe: try to bind a TcpListener on loopback. If the
# bind succeeds the port is free; otherwise increment and retry. No reliance
# on lsof / Get-NetTCPConnection (the former does not exist on Windows, the
# latter requires the NetTCPIP module and is slower for a spin loop).
function Find-Port([int]$start) {
    $port = $start
    while ($true) {
        $listener = $null
        try {
            $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
            $listener.Start()
            return $port
        } catch {
            $port++
            if ($port -gt 65535) {
                throw "No free port available above $start"
            }
        } finally {
            if ($listener) { try { $listener.Stop() } catch { } }
        }
    }
}

$defaultUi = if ($env:ARKAOS_DASHBOARD_UI_PORT) { [int]$env:ARKAOS_DASHBOARD_UI_PORT } else { 3333 }
$uiPort = Find-Port $defaultUi

$defaultApi = if ($env:ARKAOS_DASHBOARD_API_PORT) { [int]$env:ARKAOS_DASHBOARD_API_PORT } else { $uiPort + 1 }
$apiPort = Find-Port $defaultApi

Write-Host ''
Write-Host '  ArkaOS Dashboard'
Write-Host '  -----------------'

# --- Locate Python ---------------------------------------------------------
# Prefer the ArkaOS venv python recorded in the install manifest so the
# dashboard API runs against the same interpreter the installer uses.
function Find-Python {
    $manifest = Join-Path $arkaosHome 'install-manifest.json'
    if (Test-Path -LiteralPath $manifest) {
        try {
            $m = Get-Content -Raw -LiteralPath $manifest -Encoding UTF8 | ConvertFrom-Json
            if ($m.pythonCmd -and (Test-Path -LiteralPath $m.pythonCmd)) {
                return $m.pythonCmd
            }
        } catch { }
    }
    $venvPy = Join-Path $arkaosHome 'venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPy) { return $venvPy }
    foreach ($cmd in 'python','python3','py') {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($found) { return $found.Source }
    }
    return $null
}

$python = Find-Python
if (-not $python) {
    Write-Host '  Error: no usable Python interpreter found.' -ForegroundColor Red
    Write-Host '  Install Python 3.11+ and rerun.'             -ForegroundColor DarkGray
    exit 1
}

# --- Start FastAPI backend -------------------------------------------------
Write-Host "  Starting API on :$apiPort..."
$dashboardApi = Join-Path $arkaosRoot 'scripts\dashboard-api.py'

# Start-Process inherits the parent's environment, so setting ARKAOS_ROOT
# here is enough to pass it to the child.
$savedArkaosRoot = $env:ARKAOS_ROOT
$env:ARKAOS_ROOT = $arkaosRoot
try {
    $apiProc = Start-Process -FilePath $python `
        -ArgumentList @($dashboardApi, '--port', "$apiPort") `
        -WorkingDirectory $arkaosRoot `
        -RedirectStandardOutput $apiLog `
        -RedirectStandardError  $apiLog `
        -NoNewWindow `
        -PassThru
} finally {
    $env:ARKAOS_ROOT = $savedArkaosRoot
}

# --- Health check (up to ~10s) --------------------------------------------
$apiReady = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500
    if ($apiProc.HasExited) { break }
    try {
        $resp = Invoke-WebRequest `
            -Uri "http://localhost:$apiPort/api/overview" `
            -UseBasicParsing `
            -TimeoutSec 1 `
            -ErrorAction Stop
        if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
            $apiReady = $true
            break
        }
    } catch { }
}

if ($apiReady) {
    Write-Host "  API: http://localhost:$apiPort" -ForegroundColor Green
} else {
    Write-Host "  ! API may still be starting (check log: $apiLog)" -ForegroundColor Yellow
    if (Test-Path -LiteralPath $apiLog) {
        try {
            $lastError = (Get-Content -LiteralPath $apiLog -Tail 3 -ErrorAction SilentlyContinue | Select-Object -First 1)
            if ($lastError) {
                Write-Host "  Last error: $lastError" -ForegroundColor DarkGray
            }
        } catch { }
    }
    # Do not exit - API may still be loading; continue with the UI.
}

# --- Start Nuxt frontend ---------------------------------------------------
$uiProc = $null
$nuxtOutput = Join-Path $dashboardDir '.output'
$nuxtNodeModules = Join-Path $dashboardDir 'node_modules'
$nuxtServer = Join-Path $nuxtOutput 'server\index.mjs'

function Start-NuxtDev {
    param([int]$Port, [int]$ApiPort, [string]$WorkingDir)
    # `npx nuxt dev --port <n>` works from cmd.exe; PowerShell resolves npx
    # via the npx.cmd shim installed with Node.js.
    $savedApi = $env:NUXT_PUBLIC_API_BASE
    $env:NUXT_PUBLIC_API_BASE = "http://localhost:$ApiPort"
    try {
        return Start-Process -FilePath 'npx' `
            -ArgumentList @('nuxt','dev','--port',"$Port") `
            -WorkingDirectory $WorkingDir `
            -NoNewWindow `
            -PassThru
    } finally {
        $env:NUXT_PUBLIC_API_BASE = $savedApi
    }
}

if (Test-Path -LiteralPath $nuxtServer) {
    Write-Host "  Starting UI on :$uiPort..."
    $savedPort = $env:PORT
    $savedApi  = $env:NUXT_PUBLIC_API_BASE
    $env:PORT = "$uiPort"
    $env:NUXT_PUBLIC_API_BASE = "http://localhost:$apiPort"
    try {
        $uiProc = Start-Process -FilePath 'node' `
            -ArgumentList @($nuxtServer) `
            -WorkingDirectory $dashboardDir `
            -NoNewWindow `
            -PassThru
    } finally {
        $env:PORT = $savedPort
        $env:NUXT_PUBLIC_API_BASE = $savedApi
    }
} elseif (Test-Path -LiteralPath $nuxtNodeModules) {
    Write-Host "  Starting UI (dev) on :$uiPort..."
    $uiProc = Start-NuxtDev -Port $uiPort -ApiPort $apiPort -WorkingDir $dashboardDir
} else {
    # Auto-install and start
    Write-Host '  Installing dashboard dependencies...'
    $installer = if (Get-Command pnpm -ErrorAction SilentlyContinue) { 'pnpm' } else { 'npm' }
    try {
        Start-Process -FilePath $installer `
            -ArgumentList @('install','--silent') `
            -WorkingDirectory $dashboardDir `
            -NoNewWindow `
            -Wait `
            -PassThru | Out-Null
    } catch {
        Write-Host "  ! Dashboard install failed ($installer). API-only mode." -ForegroundColor Yellow
    }
    if (Test-Path -LiteralPath $nuxtNodeModules) {
        Write-Host "  Starting UI (dev) on :$uiPort..."
        $uiProc = Start-NuxtDev -Port $uiPort -ApiPort $apiPort -WorkingDir $dashboardDir
    } else {
        Write-Host '  ! Dashboard install did not create node_modules. API-only mode.' -ForegroundColor Yellow
    }
}

# --- Save state ------------------------------------------------------------
# PID file and port file are plain ASCII so other scripts (npx arkaos
# dashboard stop, bash readers) can parse them identically to the .sh
# version.
$pidLines = @()
if ($apiProc) { $pidLines += [string]$apiProc.Id }
if ($uiProc)  { $pidLines += [string]$uiProc.Id }
[System.IO.File]::WriteAllText($pidFile, ($pidLines -join [Environment]::NewLine), [System.Text.ASCIIEncoding]::new())

$portLines = @("API_PORT=$apiPort")
if ($uiProc) { $portLines += "UI_PORT=$uiPort" }
[System.IO.File]::WriteAllText($portFile, ($portLines -join [Environment]::NewLine), [System.Text.ASCIIEncoding]::new())

# --- Print summary box -----------------------------------------------------
$tl = [char]0x250C; $tr = [char]0x2510
$bl = [char]0x2514; $br = [char]0x2518
$h  = [char]0x2500; $v  = [char]0x2502
$width = 38
$bar = [string]$h * $width

Write-Host ''
Write-Host ("  $tl$bar$tr")
Write-Host ("  $v  API: http://localhost:$apiPort" + (' ' * ($width - 23 - "$apiPort".Length)) + "$v")
if ($uiProc) {
    Write-Host ("  $v  UI:  http://localhost:$uiPort" + (' ' * ($width - 23 - "$uiPort".Length)) + "$v")
}
Write-Host ("  $bl$bar$br")
Write-Host ''
Write-Host '  Stop: npx arkaos dashboard stop'
Write-Host "        or: Stop-Process -Id (Get-Content '$pidFile')"
Write-Host ''

# --- Open the browser at the UI URL ----------------------------------------
if ($uiProc) {
    Start-Sleep -Seconds 5
    try {
        Start-Process "http://localhost:$uiPort" | Out-Null
    } catch {
        # Silent: user can click the link in the terminal instead.
    }
}
