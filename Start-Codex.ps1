[CmdletBinding()]
param(
    [ValidateSet('Start', 'Doctor', 'Repair')][string]$Mode = 'Start',
    [string]$CodexHome = (Join-Path $env:USERPROFILE '.codex'),
    [string]$Python = '',
    [int]$WindowTimeoutSeconds = 30,
    [switch]$NoActivate,
    [switch]$Json,
    [switch]$UseRecoveryResources
)
$ErrorActionPreference = 'Stop'

function Find-Python {
    if ($Python) {
        $command = Get-Command $Python -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command) { return $command.Source }
        if (Test-Path -LiteralPath $Python -PathType Leaf) { return $Python }
        throw 'Requested Python executable not found.'
    }
    $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundled) { return $bundled }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command -and $command.Source -notmatch '\\Microsoft\\WindowsApps\\') { return $command.Source }
    throw 'Python 3.12+ is required. Pass -Python with an installed executable.'
}

function Get-CodexWindows {
    # Avoid matching a separately installed ChatGPT application by name alone.
    @(Get-Process -Name ChatGPT -ErrorAction SilentlyContinue | Where-Object {
        try { $_.MainWindowHandle -ne 0 -and $_.Path -eq $script:appExe } catch { $false }
    })
}

function Invoke-ResourceTool([string]$Action) {
    $result = & $script:pythonExe -B (Join-Path $PSScriptRoot 'repair.py') $Action --resources $script:resources --home $CodexHome
    $code = $LASTEXITCODE
    if ($code -notin @(0, 1)) { throw "Resource tool failed (exit $code). No app reset was performed." }
    if (-not $Json -or $Mode -ne 'Doctor') { $result | Out-Host }
    return $code
}

function Read-State {
    if (Test-Path -LiteralPath $script:statePath) {
        try { return Get-Content -LiteralPath $script:statePath -Raw | ConvertFrom-Json } catch { return $null }
    }
    return $null
}

function Write-State {
    New-Item -ItemType Directory -Path (Split-Path -Parent $script:statePath) -Force | Out-Null
    $temporary = "$script:statePath.tmp"
    @{ package = $script:package.PackageFullName; verifiedUtc = [DateTime]::UtcNow.ToString('o') } |
        ConvertTo-Json | Set-Content -LiteralPath $temporary -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $script:statePath -Force
}

$lock = New-Object System.Threading.Mutex($false, 'Local\CodexWindowsRecovery')
$acquired = $false
try {
    $acquired = $lock.WaitOne(0)
    if (-not $acquired) { throw 'Another recovery launcher is already running.' }
    $script:package = Get-AppxPackage -Name OpenAI.Codex | Select-Object -First 1
    if (-not $script:package) { throw 'OpenAI.Codex is not registered for this Windows user.' }
    $appId = "$($script:package.PackageFamilyName)!App"
    if (-not (Get-StartApps | Where-Object AppID -eq $appId)) { throw 'Codex Windows app entry is missing.' }

    if ($Mode -eq 'Start' -and -not $UseRecoveryResources) {
        if (-not $NoActivate) {
            Start-Process -FilePath explorer.exe -ArgumentList "shell:AppsFolder\$appId"
        }
        Write-Output 'Original Codex Windows app entry launched. Recovery checks were skipped.'
        exit 0
    }

    $script:appExe = Join-Path $script:package.InstallLocation 'app\ChatGPT.exe'
    $script:resources = Join-Path $script:package.InstallLocation 'app\resources'
    $script:pythonExe = Find-Python
    & $script:pythonExe -B -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 2)'
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12+ is required.' }
    $script:statePath = Join-Path $CodexHome 'windows-recovery\state.json'
    $resourceRoot = Join-Path $CodexHome 'plugin-resources'
    $key = 'CODEX_ELECTRON_BUNDLED_PLUGINS_RESOURCES_PATH'
    $environmentValue = [Environment]::GetEnvironmentVariable($key, 'User')
    $state = Read-State
    $versionChanged = -not $state -or $state.package -ne $script:package.PackageFullName
    $action = if ($Mode -eq 'Doctor' -or $versionChanged) { 'doctor' } else { 'quick-check' }
    $check = Invoke-ResourceTool $action

    if ($Mode -eq 'Doctor') {
        $report = [ordered]@{
            version = [string]$script:package.Version
            packageStatus = [string]$script:package.Status
            versionChanged = [bool]$versionChanged
            resourceIntegrity = if ($check -eq 0) { 'verified' } else { 'repair_required' }
            userEnvironmentConfigured = ($environmentValue -eq $resourceRoot)
            visibleWindows = (Get-CodexWindows).Count
            note = 'File integrity does not prove plugin permissions or end-to-end functionality.'
        }
        if ($Json) { $report | ConvertTo-Json } else { [pscustomobject]$report | Format-List }
        if ($check -ne 0) { exit 1 }
        exit 0
    }

    if ($Mode -eq 'Repair' -or $check -ne 0) {
        if (Get-Process -Name ChatGPT -ErrorAction SilentlyContinue | Where-Object {
            try { $_.Path -eq $script:appExe } catch { $true }
        }) { throw 'Close Codex normally before repairing. No processes were stopped.' }
        if ((Invoke-ResourceTool 'repair') -ne 0) { throw 'Repaired resources failed verification.' }
        Write-State
    }
    elseif ($versionChanged) { Write-State }

    if ($environmentValue -ne $resourceRoot) {
        if ($environmentValue) { throw 'A different user resource override exists; left unchanged. Review it before proceeding.' }
        [Environment]::SetEnvironmentVariable($key, $resourceRoot, 'User')
        Write-Warning 'Resource override configured. Sign out of Windows and sign in once before testing package activation. Do not reset Codex.'
        exit 3
    }
    if ($NoActivate) { exit 0 }
    Start-Process -FilePath explorer.exe -ArgumentList "shell:AppsFolder\$appId"
    $deadline = (Get-Date).AddSeconds($WindowTimeoutSeconds)
    while ((Get-CodexWindows).Count -eq 0 -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
    if ((Get-CodexWindows).Count -eq 0) {
        throw 'Activation requested, but no visible Codex window was observed within the timeout. Run -Mode Doctor; no process was killed.'
    }
    Write-Output 'Codex window observed. Plugin actions still require an end-to-end test.'
}
catch {
    Write-Error $_ -ErrorAction Continue
    exit 2
}
finally {
    if ($acquired) { $lock.ReleaseMutex() }
    $lock.Dispose()
}
