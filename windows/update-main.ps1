# ViePN main-branch updater for Windows, using the official GitHub Git repository.
# PowerShell 5.1 / 7; does not touch user IPA, certificates, tokens or sessions.
[CmdletBinding()]
param([string]$Destination = 'C:\ViePN-iOS-Manager', [switch]$SelfTest)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Remote = 'https://github.com/nguyendp911/viepniosmanager.git'
$Root = [System.IO.Path]::GetFullPath($Destination).TrimEnd('\')
$Staging = $null
$Backup = $null
$installed = New-Object 'System.Collections.Generic.List[string]'
$approvedFolders = @('backend','web','windows','ios','docs')
$top = @('Start-ViePN.bat','Install-ViePN.bat','Update-ViePN.bat','Import-ViePN-Certificate.bat','README.md','VERSION')
$allowedExtensions = @('.py','.txt','.md','.ps1','.bat','.html','.swift','.plist','.json','.yml','.yaml','.sh','.png','.jpg','.jpeg','.svg','.pem','.xcconfig','.entitlements')
function Allowed-Path([string]$rel) {
    if ($rel -notmatch '^[A-Za-z0-9._/-]+$' -or $rel -match '(^|/)\.\.(/|$)|(^|/)\.git(/|$)') { return $false }
    $parts = $rel.Split('/')
    if ($parts.Count -eq 1) { return $top -contains $rel }
    if ($approvedFolders -notcontains $parts[0]) { return $false }
    foreach ($part in $parts) {
        if ($part -in @('.venv','__pycache__','build','artifacts','dist','session','incoming','node_modules')) { return $false }
        if ($part.StartsWith('.env')) { return $false }
    }
    return $allowedExtensions -contains [System.IO.Path]::GetExtension($rel).ToLowerInvariant()
}
function Assert-Ports-Free {
    foreach ($port in @(8765,8766)) {
        $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
        if ($listeners.Count -gt 0) {
            throw "Port $port is in use. Close ViePN API and Gateway windows, then run Update-ViePN.bat again. No files changed."
        }
    }
}
if ($SelfTest) {
    if (-not (Allowed-Path 'windows/ensure-python315.ps1')) { throw 'Allowlist test failed.' }
    if (Allowed-Path 'IPA/private.ipa') { throw 'User data would be overwritten.' }
    if (Allowed-Path '../secret.txt') { throw 'Unsafe path accepted.' }
    Write-Host '[OK] ViePN main updater self-test passed.'
    exit 0
}
try {
    if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
        throw 'Git for Windows is required for direct main updates. Install from https://git-scm.com/downloads/win, then reopen Update-ViePN.bat.'
    }
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        throw "ViePN installation not found: $Root"
    }
    Assert-Ports-Free
    $Staging = Join-Path $env:TEMP ('ViePN-Main-' + [guid]::NewGuid().ToString('N'))
    $checkout = Join-Path $Staging 'repo'
    New-Item -Path $Staging -ItemType Directory -Force | Out-Null
    Write-Host '[ViePN] Fetching current main branch from official GitHub repository...' -ForegroundColor Cyan
    & git.exe clone --quiet --depth 1 --single-branch --branch main -- $Remote $checkout
    if ($LASTEXITCODE -ne 0) { throw 'Could not fetch official GitHub main branch. No files changed.' }
    $sha = (& git.exe -C $checkout rev-parse HEAD | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $sha -notmatch '^[a-f0-9]{40}$') { throw 'Cannot verify downloaded commit.' }
    $marker = Join-Path $Root '.viepn-main-commit'
    if ((Test-Path -LiteralPath $marker) -and (Get-Content -LiteralPath $marker -Raw).Trim() -eq $sha) {
        Write-Host '[OK] ViePN main source is already up to date.' -ForegroundColor Green
        $iosDownloader = Join-Path $checkout 'windows\download-ios-main.ps1'
        if (Test-Path -LiteralPath $iosDownloader -PathType Leaf) {
            & $iosDownloader -Commit $sha -Destination $Root
        }
        exit 0
    }
    $files = @(& git.exe -C $checkout ls-files)
    if ($LASTEXITCODE -ne 0) { throw 'Cannot enumerate tracked source files.' }
    $files = @($files | Where-Object { Allowed-Path ([string]$_) })
    if ($files.Count -lt 20) { throw 'Downloaded source inventory is unexpectedly small.' }
    # Avoid overwriting source that is in use; back up changed source before applying.
    Assert-Ports-Free
    $backupRoot = Join-Path $Root 'code-backups'
    $Backup = Join-Path $backupRoot ('main-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + $sha.Substring(0,7))
    New-Item -Path $Backup -ItemType Directory -Force | Out-Null
    Write-Host "[ViePN] Backing up existing code: $Backup"
    foreach ($rel in $files) {
        $rel = [string]$rel
        $src = Join-Path $checkout ($rel.Replace('/','\'))
        $target = Join-Path $Root ($rel.Replace('/','\'))
        if (-not (Test-Path -LiteralPath $src -PathType Leaf)) { throw "Source file missing or not regular: $rel" }
        if ((Get-Item -LiteralPath $src).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Symlink not permitted: $rel" }
        $parent = Split-Path -Parent $target
        if (-not (Test-Path -LiteralPath $parent)) { New-Item -Path $parent -ItemType Directory -Force | Out-Null }
        if (Test-Path -LiteralPath $target -PathType Leaf) {
            $saved = Join-Path $Backup ($rel.Replace('/','\'))
            $savedParent = Split-Path -Parent $saved
            if (-not (Test-Path -LiteralPath $savedParent)) { New-Item -Path $savedParent -ItemType Directory -Force | Out-Null }
            Copy-Item -LiteralPath $target -Destination $saved -Force
        }
        # Record before copy so a partially copied file is restored on failure.
        $installed.Add($rel)
        Copy-Item -LiteralPath $src -Destination $target -Force
    }
    Set-Content -LiteralPath $marker -Value $sha -Encoding Ascii
    Write-Host "[OK] ViePN Windows source updated to main commit $($sha.Substring(0,12))." -ForegroundColor Green
    Write-Host '[OK] User IPA, certificates, access token, sessions and .venv were preserved.'
    Write-Host '[ViePN] Checking for matching unsigned iOS IPA from GitHub Actions...'
    $iosDownloader = Join-Path $checkout 'windows\download-ios-main.ps1'
    if (Test-Path -LiteralPath $iosDownloader -PathType Leaf) {
        & $iosDownloader -Commit $sha -Destination $Root
    } else {
        Write-Warning 'iOS downloader not found in the downloaded source.'
    }
    Write-Host "[NEXT] Start $Root\Start-ViePN.bat"
} catch {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    if ($Backup -and (Test-Path -LiteralPath $Backup) -and $installed.Count -gt 0) {
        Write-Warning 'Restoring installed source files from backup...'
        foreach ($rel in $installed) {
            $target = Join-Path $Root ($rel.Replace('/','\'))
            $saved = Join-Path $Backup ($rel.Replace('/','\'))
            if (Test-Path -LiteralPath $saved -PathType Leaf) {
                Copy-Item -LiteralPath $saved -Destination $target -Force
            } elseif (Test-Path -LiteralPath $target -PathType Leaf) {
                Remove-Item -LiteralPath $target -Force
            }
        }
    }
    exit 1
} finally {
    if ($Staging -and (Test-Path -LiteralPath $Staging)) {
        Remove-Item -LiteralPath $Staging -Recurse -Force -ErrorAction SilentlyContinue
    }
}
