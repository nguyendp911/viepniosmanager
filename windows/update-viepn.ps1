# ViePN official release updater (Windows PowerShell 5.1+).
# Downloads only approved assets from nguyendp911/viepniosmanager latest stable
# GitHub Release. No arbitrary URL or shell code from a remote server is run.
# This script executes from the local installed, reviewed ViePN source.
[CmdletBinding()]
param(
    [string]$Destination = 'C:\ViePN-iOS-Manager',
    [switch]$SelfTest
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Repo = 'nguyendp911/viepniosmanager'
$Api = "https://api.github.com/repos/$Repo/releases/latest"
$Root = [System.IO.Path]::GetFullPath($Destination).TrimEnd('\')
$IPAFolder = Join-Path $Root 'IPA'
$Stage = $null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Assert-ReleaseTag([string]$Tag) {
    if ($Tag -notmatch '^v[0-9]+\.[0-9]+\.[0-9]+$') {
        throw 'Release tag is not a valid stable semantic version.'
    }
}
function Assert-ReleaseAsset($Release, [string]$Name) {
    # Exact expected GitHub Release asset URL, not a caller-controlled domain.
    $expected = "https://github.com/$Repo/releases/download/$($Release.tag_name)/$Name"
    $found = @($Release.assets | Where-Object {
        $_.name -ceq $Name -and $_.browser_download_url -ceq $expected
    })
    if ($found.Count -ne 1) { throw "Missing or untrusted release asset: $Name" }
    return $found[0].browser_download_url
}
function Expected-Hash([string]$Text, [string]$Name) {
    $rx = '(?im)^([a-f0-9]{64})\s+\*?' + [regex]::Escape($Name) + '\s*$'
    $match = [regex]::Match($Text, $rx)
    if (-not $match.Success) { throw "Invalid checksum file for $Name" }
    return $match.Groups[1].Value.ToLowerInvariant()
}
function Assert-SHA256([string]$Path, [string]$Expected) {
    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $Expected) { throw "Checksum mismatch for $(Split-Path -Leaf $Path); update aborted." }
}
function Download-Asset($Release, [string]$Name, [string]$Folder) {
    $url = Assert-ReleaseAsset $Release $Name
    $path = Join-Path $Folder $Name
    Write-Host "  Downloading: $Name"
    Invoke-WebRequest -Uri $url -Headers @{'User-Agent'='ViePN-Official-Updater'} -MaximumRedirection 5 -UseBasicParsing -OutFile $path -TimeoutSec 240
    if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or
        (Get-Item -LiteralPath $path).Length -le 0) {
        throw "Download is incomplete: $Name"
    }
    return $path
}
function Validate-IPA([string]$Path) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($Path)
    try {
        if (-not @($archive.Entries | Where-Object {
            $_.FullName -match '^Payload/[^/]+\.app/Info\.plist$'
        }).Count) {
            throw 'Downloaded IPA does not contain an iOS .app/Info.plist.'
        }
    } finally { $archive.Dispose() }
}
function Stop-OwnViePN {
    # Only stop processes whose executable is under OUR installation and
    # command line launches the known ViePN entrypoints.
    $busy = @()
    foreach ($port in @(8765, 8766)) {
        $connections = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
        foreach ($socket in $connections) {
            $processId = [int]$socket.OwningProcess
            if ($processId -le 0) { continue }
            $info = Get-CimInstance Win32_Process -Filter "ProcessId=$processId" -ErrorAction SilentlyContinue
            if (-not $info) {
                throw "Port $port is occupied. Close ViePN manually before updating."
            }
            $exe = [string]$info.ExecutablePath
            $cmd = [string]$info.CommandLine
            $venv = (Join-Path $Root '.venv\').ToLowerInvariant()
            $trusted = $exe.ToLowerInvariant().StartsWith($venv) -and
                ($cmd -match 'backend[\\/](run|remote_run)\.py')
            if (-not $trusted) {
                throw "Port $port is held by a process not recognized as ViePN. Close it manually; updater will not terminate it."
            }
            if ($busy -notcontains $processId) { $busy += $processId }
        }
    }
    if ($busy.Count -eq 0) { return }
    # Avoid interrupting active signing/installation/renewal operations.
    $tokenFile = Join-Path $env:LOCALAPPDATA 'ViePN-iOS-Manager\access_token.txt'
    if (-not (Test-Path $tokenFile)) {
        throw 'ViePN processes are running but token file is unavailable. Stop the service manually first.'
    }
    $token = (Get-Content -LiteralPath $tokenFile -Raw -Encoding UTF8).Trim()
    try {
        $overview = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/overview' -Headers @{
            Authorization = "Bearer $token"
        } -TimeoutSec 8
    } catch {
        throw 'Could not verify ViePN job state. Stop the backend and gateway manually and retry.'
    }
    $active = @($overview.jobs | Where-Object { $_.state -in @('queued','running') })
    if ($active.Count -gt 0) {
        throw 'ViePN has active signing/install/renewal jobs. Update cancelled to protect operations.'
    }
    Write-Host '[ViePN] Stopping verified ViePN API/gateway processes...'
    foreach ($id in $busy) {
        Stop-Process -Id $id -ErrorAction Stop
    }
    Start-Sleep -Seconds 2
    foreach ($port in @(8765,8766)) {
        if (@(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue).Count -gt 0) {
            throw "Port $port remains in use; update aborted."
        }
    }
}

if ($SelfTest) {
    Assert-ReleaseTag 'v2.1.2'
    if ((Expected-Hash ("{0}  file.zip" -f ('a' * 64)) 'file.zip') -ne ('a' * 64)) {
        throw 'SHA256 checksum parser self-test failed.'
    }
    try { Assert-ReleaseTag 'v2.1.2-preview'; throw 'Tag validator accepted prerelease' } catch {
        if ($_.Exception.Message -eq 'Tag validator accepted prerelease') { throw }
    }
    Write-Host '[OK] ViePN updater validation checks passed.'
    exit 0
}

try {
    Write-Host '[ViePN] Checking latest stable release from official GitHub...'
    $release = Invoke-RestMethod -Uri $Api -Headers @{
        Accept = 'application/vnd.github+json'
        'User-Agent' = 'ViePN-Official-Updater'
    } -TimeoutSec 45
    Assert-ReleaseTag ([string]$release.tag_name)
    if ($release.draft -or $release.prerelease) {
        throw 'GitHub returned a draft or prerelease; no changes were made.'
    }
    $version = $release.tag_name.Substring(1)
    $winName = "ViePN-Windows-Portable-$version.zip"
    $winHash = "ViePN-Windows-Portable-$version.sha256"
    $ipaName = "ViePNMobile-$version-UNSIGNED.ipa"
    $ipaHash = "$ipaName.sha256"
    # Verify full inventory before downloading anything.
    foreach ($name in @($winName, $winHash, $ipaName, $ipaHash)) {
        $null = Assert-ReleaseAsset $release $name
    }
    Write-Host "[ViePN] Latest official stable: $($release.tag_name)"
    $Stage = Join-Path $env:TEMP ('ViePN-Update-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $Stage | Out-Null
    $winZip = Download-Asset $release $winName $Stage
    $winHashFile = Download-Asset $release $winHash $Stage
    $ipa = Download-Asset $release $ipaName $Stage
    $ipaHashFile = Download-Asset $release $ipaHash $Stage
    Assert-SHA256 $winZip (Expected-Hash (Get-Content -LiteralPath $winHashFile -Raw) $winName)
    Assert-SHA256 $ipa (Expected-Hash (Get-Content -LiteralPath $ipaHashFile -Raw) $ipaName)
    Validate-IPA $ipa
    Write-Host '[ViePN] Both archives passed SHA256 checks.'
    $source = Join-Path $Stage 'source'
    Expand-Archive -LiteralPath $winZip -DestinationPath $source -Force
    $manifestFile = Join-Path $source 'manifest.json'
    if (-not (Test-Path -LiteralPath $manifestFile)) {
        throw 'Missing Windows release manifest.'
    }
    $manifest = Get-Content -LiteralPath $manifestFile -Raw | ConvertFrom-Json
    if ($manifest.version -cne $version) {
        throw 'Windows package version does not match GitHub Release tag.'
    }
    if (-not (Test-Path (Join-Path $source 'windows\install-portable.ps1'))) {
        throw 'Windows installer missing from verified release package.'
    }
    # Never stop an unrelated process; abort if a ViePN signing job is active.
    Stop-OwnViePN
    Write-Host "[ViePN] Installing verified Windows source into: $Root"
    & (Join-Path $source 'windows\install-portable.ps1') -Source $source -Destination $Root
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw 'Windows installation failed.'
    }
    if (-not (Test-Path $IPAFolder)) {
        New-Item -ItemType Directory -Force -Path $IPAFolder | Out-Null
    }
    $destinationIPA = Join-Path $IPAFolder $ipaName
    $tmpIPA = Join-Path $IPAFolder ('.download-' + [guid]::NewGuid().ToString('N') + '.ipa')
    try {
        Copy-Item -LiteralPath $ipa -Destination $tmpIPA -Force
        Assert-SHA256 $tmpIPA (Expected-Hash (Get-Content -LiteralPath $ipaHashFile -Raw) $ipaName)
        Move-Item -LiteralPath $tmpIPA -Destination $destinationIPA -Force
    } finally {
        if (Test-Path $tmpIPA) { Remove-Item -LiteralPath $tmpIPA -Force }
    }
    Write-Host ''
    Write-Host "[OK] Updated ViePN Windows to $version" -ForegroundColor Green
    Write-Host "[OK] Downloaded iOS IPA to: $destinationIPA" -ForegroundColor Green
    Write-Host '[NOTE] iOS IPA is unsigned and MUST be signed before installing on an iPhone.'
    Write-Host '[NOTE] Existing user IPA, token, Apple sessions and other files were not deleted.'
    Write-Host "[NEXT] Double-click $(Join-Path $Root 'Start-ViePN.bat')"
} catch {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    if ($Stage -and (Test-Path $Stage)) {
        Remove-Item -LiteralPath $Stage -Force -Recurse -ErrorAction SilentlyContinue
    }
}
