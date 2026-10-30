# No external test modules, network, real installer, or real Studio process.
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\plugins\augelab\skills\augelab\scripts\setup-windows.ps1"

function Assert($Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}
function Assert-Throws([scriptblock]$Action, [string]$Pattern) {
    try { & $Action } catch {
        Assert ($_.Exception.Message -match $Pattern) "Unexpected error: $($_.Exception.Message)"
        return
    }
    throw "Expected an error matching $Pattern"
}

$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('AugeLabPluginTests-' + [Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($testRoot)
$fixture = Join-Path $testRoot 'fake-installer.exe'
[IO.File]::WriteAllText($fixture, 'This is test data, not an executable.')
$hash = [Security.Cryptography.SHA256]::Create()
try { $script:fixtureHash = [BitConverter]::ToString($hash.ComputeHash([IO.File]::ReadAllBytes($fixture))).Replace('-', '').ToLowerInvariant() }
finally { $hash.Dispose() }
$script:installerFixture = $fixture

try {
    Assert-InstallerHash $fixture $script:fixtureHash
    Assert-Throws { Assert-InstallerHash $fixture ('0' * 64) } 'SHA-256 mismatch'
    Write-Host 'PASS valid bytes accepted; mismatched bytes rejected'

    # Stub only external boundaries. Exercise setup decisions and hash verification.
    function Get-InstallerConfig {
        [pscustomobject]@{ sha256 = $script:fixtureHash; executable = 'AugeLab AI Studio.exe' }
    }
    function Find-InstalledStudio { param($PreferredDirectory); return $script:existing }
    function Test-StudioMcp { return $script:ready }
    function Save-StudioInstaller { $script:downloads++; return $script:installerFixture }
    function Invoke-StudioInstaller {
        param($Path, $Directory, $AI)
        $script:installs++
        $script:lastDirectory = $Directory
        $script:lastAI = $AI
        if ($script:installFails) { throw 'installer failed' }
    }
    function Get-StudioExecutable {
        param($Directory)
        if ($script:launcherFound) { return (Join-Path $Directory 'AugeLab AI Studio.exe') }
        return $null
    }
    function Get-Process { param($Name, $ErrorAction); return @() }
    function Start-InstalledStudio { param($Executable); $script:launches++ }
    function Reset-Scenario {
        $script:existing = $null
        $script:ready = $false
        $script:downloads = 0
        $script:installs = 0
        $script:launches = 0
        $script:launcherFound = $true
        $script:installFails = $false
    }
    $newDirectory = Join-Path $testRoot 'Destination with spaces'

    Reset-Scenario
    $result = Invoke-AugeLabSetup -CheckOnly -InstallDir $newDirectory
    Assert ($result.status -eq 'checked' -and -not $result.changed) 'CheckOnly result'
    Assert (($script:downloads + $script:installs + $script:launches) -eq 0) 'CheckOnly mutated state'
    Write-Host 'PASS missing Studio inspection has no side effects'

    Reset-Scenario
    $script:ready = $true
    $result = Invoke-AugeLabSetup -InstallDir $newDirectory
    Assert ($result.mcpReady -and -not $result.installedNow) 'Working MCP not reused'
    Assert (($script:downloads + $script:installs + $script:launches) -eq 0) 'Working MCP reinstalled'
    Write-Host 'PASS working MCP skips install even with custom Studio location'

    Reset-Scenario
    $script:existing = 'C:\Existing Studio\AugeLab AI Studio.exe'
    $result = Invoke-AugeLabSetup -InstallDir $newDirectory -McpWaitSeconds 0
    Assert ($result.executable -eq $script:existing -and -not $result.installedNow) 'Existing Studio not reused'
    Assert (($script:downloads + $script:installs) -eq 0 -and $script:launches -eq 1) 'Existing Studio installed again'
    Write-Host 'PASS existing Studio starts without download or reinstall'

    Reset-Scenario
    $result = Invoke-AugeLabSetup -InstallDir $newDirectory -McpWaitSeconds 0 -IncludeAI
    Assert ($script:downloads -eq 1 -and $script:installs -eq 1 -and $script:launches -eq 1) 'Fresh install did not run once'
    Assert ($script:lastDirectory -eq $newDirectory -and $script:lastAI) 'Installer options lost'
    Assert ($result.installedNow -and $result.status -eq 'needs-activation-or-mcp') 'Unactivated install reported ready'
    Write-Host 'PASS fresh setup installs once and reports activation/MCP still needed'

    Reset-Scenario
    $script:installFails = $true
    Assert-Throws { Invoke-AugeLabSetup -InstallDir $newDirectory -McpWaitSeconds 0 } 'installer failed'
    Assert ($script:installs -eq 1 -and $script:launches -eq 0) 'Failed install retried or launched'
    Write-Host 'PASS failed installer stops without retry or launch'

    Reset-Scenario
    $script:launcherFound = $false
    Assert-Throws { Invoke-AugeLabSetup -InstallDir $newDirectory -McpWaitSeconds 0 } 'launcher is missing'
    Assert ($script:launches -eq 0) 'Missing launcher reported successful'
    Write-Host 'PASS exit code zero without launcher is not success'

    Reset-Scenario
    $occupied = Join-Path $testRoot 'Occupied'
    [void][IO.Directory]::CreateDirectory($occupied)
    Assert-Throws { Invoke-AugeLabSetup -InstallDir $occupied -McpWaitSeconds 0 } 'destination already exists'
    Assert ($script:downloads -eq 0 -and $script:installs -eq 0) 'Existing destination overwritten'
    Write-Host 'PASS unknown existing directory is preserved'

    Reset-Scenario
    $result = Invoke-AugeLabSetup -DownloadOnly -InstallDir $newDirectory
    Assert ($result.status -eq 'downloaded' -and -not $result.executed -and $script:installs -eq 0) 'DownloadOnly executed installer'
    Assert-Throws { Invoke-AugeLabSetup -InstallDir 'relative\path' } 'absolute Windows directory'
    Assert-Throws { Invoke-AugeLabSetup -CheckOnly -DownloadOnly } 'Choose CheckOnly or DownloadOnly'
    Write-Host 'PASS download-only and invalid-argument boundaries'
} finally {
    # No recursive deletion: these are the only test files/directories created.
    [IO.File]::Delete($fixture)
    if ([IO.Directory]::Exists((Join-Path $testRoot 'Occupied'))) {
        [IO.Directory]::Delete((Join-Path $testRoot 'Occupied'))
    }
    [IO.Directory]::Delete($testRoot)
}
