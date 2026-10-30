#requires -Version 5.1
<###
Downloads and installs the published Windows EXE when Studio is missing.
CheckOnly never downloads, installs, starts Studio, or modifies configuration.
DownloadOnly verifies the EXE without executing it. Neither mode activates a license.
###>
[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$DownloadOnly,
    [switch]$IncludeAI,
    [string]$InstallDir,
    [ValidateRange(0, 60)][int]$McpWaitSeconds = 20
)

$ErrorActionPreference = 'Stop'
$script:SetupDirectory = $PSScriptRoot
$script:McpEndpoint = 'http://127.0.0.1:8765/mcp'

function Get-InstallerConfig {
    Get-Content -LiteralPath (Join-Path $script:SetupDirectory 'windows-installer.json') -Raw |
        ConvertFrom-Json
}

function Get-StudioExecutable([string]$Directory) {
    $path = Join-Path $Directory (Get-InstallerConfig).executable
    if (Test-Path -LiteralPath $path -PathType Leaf) { return $path }
    return $null
}

function Find-InstalledStudio([string]$PreferredDirectory) {
    $directories = @($PreferredDirectory)
    foreach ($base in @($env:LOCALAPPDATA, $env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if ($base) {
            $directories += Join-Path $base 'Programs\AugeLab Studio'
            $directories += Join-Path $base 'AugeLab Studio'
        }
    }
    foreach ($root in @('HKCU:', 'HKLM:')) {
        foreach ($view in @('Software', 'Software\WOW6432Node')) {
            $key = "$root\$view\Microsoft\Windows\CurrentVersion\Uninstall\AugeLab Studio"
            $registration = Get-ItemProperty -LiteralPath $key -ErrorAction SilentlyContinue
            if ($registration -and $registration.InstallLocation) {
                $directories += $registration.InstallLocation
            }
        }
    }
    foreach ($directory in $directories | Where-Object { $_ } | Select-Object -Unique) {
        $executable = Get-StudioExecutable $directory
        if ($executable) { return $executable }
    }
    return $null
}

function New-SetupHttpClient([int]$TimeoutSeconds) {
    Add-Type -AssemblyName System.Net.Http
    $handler = [Net.Http.HttpClientHandler]::new()
    $handler.AllowAutoRedirect = $false
    $client = [Net.Http.HttpClient]::new($handler)
    $client.Timeout = [TimeSpan]::FromSeconds($TimeoutSeconds)
    return $client
}

function Test-StudioMcp {
    $client = New-SetupHttpClient 2
    $response = $null
    try {
        $client.DefaultRequestHeaders.Accept.ParseAdd('application/json, text/event-stream')
        $body = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"augelab-plugin-setup","version":"0.1.5"}}}'
        $content = [Net.Http.StringContent]::new($body, [Text.Encoding]::UTF8, 'application/json')
        $response = $client.PostAsync($script:McpEndpoint, $content).GetAwaiter().GetResult()
        if (-not $response.IsSuccessStatusCode) { return $false }
        $text = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        $messages = @($text)
        if ($response.Content.Headers.ContentType.MediaType -eq 'text/event-stream') {
            $messages = @($text -split '\r?\n' | Where-Object { $_ -match '^data:' } |
                ForEach-Object { $_ -replace '^data:\s*', '' })
        }
        foreach ($message in $messages) {
            try { $rpc = $message | ConvertFrom-Json } catch { continue }
            if ($rpc.id -eq 1 -and $rpc.result.protocolVersion -and
                $rpc.result.serverInfo.name -match '(?i)augelab|studio') { return $true }
        }
        return $false
    } catch {
        return $false
    } finally {
        if ($response) {
            if ($response.Headers.Contains('Mcp-Session-Id')) {
                $client.DefaultRequestHeaders.Add('Mcp-Session-Id',
                    ($response.Headers.GetValues('Mcp-Session-Id') | Select-Object -First 1))
                try { $client.DeleteAsync($script:McpEndpoint).GetAwaiter().GetResult().Dispose() } catch { }
            }
            $response.Dispose()
        }
        $client.Dispose()
    }
}

function Assert-InstallerHash([string]$Path, [string]$Expected) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $actual = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $sha.Dispose() }
    if ($Expected -notmatch '^[a-f0-9]{64}$' -or $actual -ne $Expected) {
        throw 'Installer SHA-256 mismatch. Nothing was executed. Update the plugin to obtain the reviewed installer pin.'
    }
}

function Save-StudioInstaller {
    $config = Get-InstallerConfig
    $uri = [Uri]$config.url
    if ($uri.Scheme -ne 'https' -or
        $uri.Host -ne 'studio-desktop-application.s3.eu-central-1.amazonaws.com') {
        throw 'The installer must come from the official AugeLab S3 HTTPS endpoint.'
    }
    $cache = Join-Path $env:LOCALAPPDATA 'AugeLab\plugin-setup'
    [void][IO.Directory]::CreateDirectory($cache)
    $destination = Join-Path $cache ("AugeLab-Ai-Studio-" + $config.sha256 + '.exe')
    if (Test-Path -LiteralPath $destination -PathType Leaf) {
        Assert-InstallerHash $destination $config.sha256
        return $destination
    }
    # A private, unique staging name prevents concurrent downloads from sharing bytes.
    $partial = Join-Path $cache ([Guid]::NewGuid().ToString('N') + '.partial')
    $client = New-SetupHttpClient 900
    $response = $null
    try {
        Write-Host 'Downloading the official AugeLab Studio Windows installer...'
        $response = $client.GetAsync($uri).GetAwaiter().GetResult()
        [void]$response.EnsureSuccessStatusCode()
        $stream = [IO.File]::Create($partial)
        try { [void]$response.Content.CopyToAsync($stream).GetAwaiter().GetResult() } finally { $stream.Dispose() }
        Assert-InstallerHash $partial $config.sha256
        Move-Item -LiteralPath $partial -Destination $destination -Force
        return $destination
    } finally {
        if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Force }
        if ($response) { $response.Dispose() }
        $client.Dispose()
    }
}

function Invoke-StudioInstaller([string]$Path, [string]$Directory, [bool]$AI) {
    # Start-Process joins ArgumentList on Windows; quote the destination explicitly.
    if ($Directory.Contains('"')) { throw 'The installation directory cannot contain quotes.' }
    $arguments = '--silent --install-dir "' + $Directory.TrimEnd('\') + '" --start-menu-shortcut'
    if ($AI) { $arguments += ' --ai' }
    Write-Host 'Installing AugeLab Studio. This can take several minutes.'
    $process = Start-Process -FilePath $Path -ArgumentList $arguments -WindowStyle Hidden -PassThru -Wait
    if ($process.ExitCode -ne 0) {
        throw "Studio installer exited with code $($process.ExitCode). See %TEMP%\augelab-installer-startup.log. No automatic retry was made."
    }
}

function Start-InstalledStudio([string]$Executable) {
    # Studio is an interactive desktop app that the user needs to see for activation.
    Start-Process -FilePath $Executable -WorkingDirectory (Split-Path -Parent $Executable) | Out-Null
}

function Invoke-AugeLabSetup {
    param([switch]$CheckOnly, [switch]$DownloadOnly, [switch]$IncludeAI,
        [string]$InstallDir, [int]$McpWaitSeconds = 20)
    if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem -or
        $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
        throw 'Automatic EXE installation requires Windows x64. Use the official Studio installer for your operating system.'
    }
    if ($CheckOnly -and $DownloadOnly) { throw 'Choose CheckOnly or DownloadOnly, not both.' }
    if (-not $InstallDir) { $InstallDir = Join-Path $env:LOCALAPPDATA 'Programs\AugeLab Studio' }
    if (-not [IO.Path]::IsPathRooted($InstallDir) -or $InstallDir.Contains('"')) {
        throw 'InstallDir must be an absolute Windows directory without quotes.'
    }
    if ($DownloadOnly) {
        return [pscustomobject]@{ status = 'downloaded'; installer = (Save-StudioInstaller); executed = $false }
    }
    $executable = Find-InstalledStudio $InstallDir
    $ready = Test-StudioMcp
    if ($CheckOnly) {
        return [pscustomobject]@{ status = 'checked'; executable = $executable; mcpReady = $ready; changed = $false }
    }
    if ($ready) {
        return [pscustomobject]@{ status = 'mcp-ready'; executable = $executable; installedNow = $false; mcpReady = $true }
    }
    $installedNow = $false
    if (-not $executable) {
        # Refuse to overwrite an incomplete/custom directory without user repair.
        if (Test-Path -LiteralPath $InstallDir) {
            throw 'The destination already exists but no Studio launcher was found. Select a new InstallDir or repair the existing installation.'
        }
        $installer = Save-StudioInstaller
        Assert-InstallerHash $installer (Get-InstallerConfig).sha256
        Invoke-StudioInstaller $installer $InstallDir ([bool]$IncludeAI)
        $executable = Get-StudioExecutable $InstallDir
        if (-not $executable) { throw 'Installer returned success but the Studio launcher is missing. Setup is incomplete.' }
        $installedNow = $true
    }
    $running = @(Get-Process -Name 'AugeLab AI Studio' -ErrorAction SilentlyContinue)
    if ($running.Count -eq 0) { Start-InstalledStudio $executable }
    $deadline = [DateTime]::UtcNow.AddSeconds($McpWaitSeconds)
    do {
        $ready = Test-StudioMcp
        if ($ready -or [DateTime]::UtcNow -ge $deadline) { break }
        Start-Sleep -Seconds 2
    } while ($true)
    $status = if ($ready) { 'mcp-ready' } else { 'needs-activation-or-mcp' }
    [pscustomobject]@{ status = $status; executable = $executable; installedNow = $installedNow; mcpReady = $ready }
}

if ($MyInvocation.InvocationName -ne '.') {
    Invoke-AugeLabSetup -CheckOnly:$CheckOnly -DownloadOnly:$DownloadOnly -IncludeAI:$IncludeAI `
        -InstallDir $InstallDir -McpWaitSeconds $McpWaitSeconds | ConvertTo-Json -Compress
}
