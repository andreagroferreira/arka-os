# ============================================================================
# ArkaOS — CwdChanged Hook (Windows / PowerShell 5.1+)
#
# Port of config/hooks/cwd-changed.sh. Fires when the working directory
# changes. Detects ecosystem and stack so Claude knows which squad and
# tooling apply to the project.
#
# Contract:
# - Reads a JSON object on stdin with a `cwd` field.
# - Emits `{"additionalContext": "..."}` on stdout when context is found,
#   or nothing (and exit 0) when there is nothing to say.
# ============================================================================

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# ─── Read hook payload from stdin (with empty-stdin fallback) ─────────
# On Claude Code Windows v2.1.97 the hook pipe is opened but the parent
# writes zero bytes before closing — every hook gets empty stdin on
# Windows. Instead of silent-exiting, fall back to `$env:CLAUDE_PROJECT_DIR`
# (the one env var CC Windows does set on hook invocations) and run the
# normal ecosystem / stack detection against it. This means a Windows
# user who `cd`s into a different project inside Claude Code still gets
# the [arka:project-context] line based on the project root CC knows
# about, even with the stdin delivery bug.
$stdinText = [Console]::In.ReadToEnd()
$newCwd = $null

if (-not [string]::IsNullOrWhiteSpace($stdinText)) {
    try {
        $payload = $stdinText | ConvertFrom-Json
        if ($payload.cwd) { $newCwd = [string]$payload.cwd }
    } catch {
        # Malformed payload — fall through to the env-var fallback.
    }
}

if ([string]::IsNullOrWhiteSpace($newCwd) -and $env:CLAUDE_PROJECT_DIR) {
    $newCwd = $env:CLAUDE_PROJECT_DIR
}

if ([string]::IsNullOrWhiteSpace($newCwd)) { exit 0 }
if (-not (Test-Path -LiteralPath $newCwd -PathType Container)) { exit 0 }

# ─── Detect ecosystem from ecosystems.json ─────────────────────────────
$ecosystemsFile = Join-Path $env:USERPROFILE '.claude\skills\arka\knowledge\ecosystems.json'
$ecosystem = ''
$ecosystemName = ''

if (Test-Path -LiteralPath $ecosystemsFile) {
    try {
        $eco = Get-Content -Raw -LiteralPath $ecosystemsFile -Encoding UTF8 | ConvertFrom-Json
        if ($eco.ecosystems) {
            # Pass 1: substring match of any project name in the cwd path.
            foreach ($ecoProp in $eco.ecosystems.PSObject.Properties) {
                $ecoId = $ecoProp.Name
                $ecoObj = $ecoProp.Value
                $projects = @($ecoObj.projects)
                foreach ($proj in $projects) {
                    if ($proj -and $newCwd.Contains([string]$proj)) {
                        $ecosystem = $ecoId
                        $ecosystemName = if ($ecoObj.name) { [string]$ecoObj.name } else { $ecoId }
                        break
                    }
                }
                if ($ecosystem) { break }
            }

            # Pass 2: if the path looks Herd-hosted, match by directory basename.
            if (-not $ecosystem -and $newCwd -match 'herd') {
                $dirName = Split-Path -Leaf $newCwd.TrimEnd('\','/')
                foreach ($ecoProp in $eco.ecosystems.PSObject.Properties) {
                    $ecoId = $ecoProp.Name
                    $ecoObj = $ecoProp.Value
                    $projects = @($ecoObj.projects)
                    foreach ($proj in $projects) {
                        if ($proj -eq $dirName) {
                            $ecosystem = $ecoId
                            $ecosystemName = if ($ecoObj.name) { [string]$ecoObj.name } else { $ecoId }
                            break
                        }
                    }
                    if ($ecosystem) { break }
                }
            }
        }
    } catch {
        # Malformed ecosystems.json — degrade gracefully.
    }
}

# ─── Detect stack ──────────────────────────────────────────────────────
$stack = 'unknown'

$composerJson  = Join-Path $newCwd 'composer.json'
$packageJson   = Join-Path $newCwd 'package.json'
$pyprojectToml = Join-Path $newCwd 'pyproject.toml'

if (Test-Path -LiteralPath $composerJson) {
    $stack = 'laravel'
} elseif (Test-Path -LiteralPath $packageJson) {
    try {
        $pkgText = Get-Content -Raw -LiteralPath $packageJson -Encoding UTF8
        if     ($pkgText -like '*"nuxt"*')  { $stack = 'nuxt' }
        elseif ($pkgText -like '*"next"*')  { $stack = 'nextjs' }
        elseif ($pkgText -like '*"react"*') { $stack = 'react' }
        elseif ($pkgText -like '*"vue"*')   { $stack = 'vue' }
        else                                 { $stack = 'node' }
    } catch {
        $stack = 'node'
    }
} elseif (Test-Path -LiteralPath $pyprojectToml) {
    $stack = 'python'
}

# ─── Check for project descriptor ─────────────────────────────────────
$dirName = Split-Path -Leaf $newCwd.TrimEnd('\','/')
$projectsDir   = Join-Path $env:USERPROFILE '.claude\skills\arka\projects'
$descriptorFile = Join-Path $projectsDir "$dirName.md"
$descriptorDir  = Join-Path (Join-Path $projectsDir $dirName) 'PROJECT.md'

$descriptor = ''
if (Test-Path -LiteralPath $descriptorFile) {
    $descriptor = $descriptorFile
} elseif (Test-Path -LiteralPath $descriptorDir) {
    $descriptor = $descriptorDir
}

# ─── Build context output ─────────────────────────────────────────────
$context = ''

if ($ecosystem) {
    $context = "[arka:project-context] Ecosystem: $ecosystemName ($ecosystem) | Stack: $stack | Use /arka-$ecosystem for dedicated squad routing."
} elseif ($stack -ne 'unknown') {
    $context = "[arka:project-context] Stack: $stack | No ecosystem assigned. Use /arka onboard to register this project."
}

if ($descriptor) {
    $context = "$context Descriptor: $descriptor"
}

if ($context) {
    [pscustomobject]@{ additionalContext = $context } | ConvertTo-Json -Compress
}
