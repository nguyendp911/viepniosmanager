# ViePN 2.1 portable installer. Windows PowerShell 5.1 / 7.
# Run from an extracted official CI artifact, NOT directly from untrusted ZIP.
# It does not touch %%LOCALAPPDATA%%/ViePN-iOS-Manager user data.
param(
    [string]$Source = (Split-Path -Parent $PSScriptRoot),
    [string]$Destination = 'C:\ViePN-iOS-Manager'
)
$ErrorActionPreference = 'Stop'
$Source = (Resolve-Path -LiteralPath $Source).Path
$ManifestPath = Join-Path $Source 'manifest.json'
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    throw 'manifest.json is missing. Extract the official ViePN-Windows-Portable.zip first.'
}
if (Test-Path -LiteralPath $Destination) {
    $destinationResolved = (Resolve-Path -LiteralPath $Destination).Path
    if ($destinationResolved.TrimEnd('\') -ieq $Source.TrimEnd('\')) {
        throw 'Extract the portable package into a different folder, not the existing ViePN installation.'
    }
}
foreach ($port in @(8765,8766)) {
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
    if ($listeners.Count -gt 0) {
        throw "ViePN service is still listening on port $port. Close the API and gateway windows before installing."
    }
}
$Manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($Manifest.schema -ne 1 -or $Manifest.version -ne '2.1.1') {
    throw 'Unsupported or unexpected ViePN package manifest.'
}
$Entries = @($Manifest.files.PSObject.Properties)
if ($Entries.Count -lt 15) { throw 'Package is incomplete.' }
$approved = @('backend','web','windows','ios','docs')
foreach ($entry in $Entries) {
    $rel = [string]$entry.Name
    if ($rel -match '(^/|\\|(^|/)\.\.(/|$)|:|\x00)' -or $rel -notmatch '^[A-Za-z0-9._/-]+$') {
        throw "Unsafe package path: $rel"
    }
    $part = $rel.Split('/')[0]
    if ($part -notin $approved -and $rel -notin @('README.md','Start-ViePN.bat','Install-ViePN.bat')) {
        throw "Unapproved package path: $rel"
    }
    $file = Join-Path $Source ($rel.Replace('/', '\'))
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Missing file: $rel" }
    $actual = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne ([string]$entry.Value).ToLowerInvariant()) {
        throw "Checksum mismatch: $rel"
    }
}
# Fail closed if there are unexpectedly added executable files.
$all = Get-ChildItem -LiteralPath $Source -Recurse -File | Where-Object { $_.FullName -notmatch '[\\/]\.git[\\/]' }
foreach ($file in $all) {
    $rel = $file.FullName.Substring($Source.Length).TrimStart('\', '/').Replace('\','/')
    if ($rel -ne 'manifest.json' -and $rel -notin @($Entries | ForEach-Object { $_.Name })) {
        throw "Unlisted file detected in package: $rel"
    }
}
$destinationParent = Split-Path -Parent $Destination
if (-not (Test-Path -LiteralPath $destinationParent)) {
    New-Item -ItemType Directory -Force -Path $destinationParent | Out-Null
}
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$backupRoot = Join-Path $Destination 'code-backups'
$backupPath = Join-Path $backupRoot (Get-Date -Format 'yyyyMMdd-HHmmss')
New-Item -ItemType Directory -Force -Path $backupPath | Out-Null
$installed = @()
try {
    foreach ($entry in $Entries) {
        $rel = [string]$entry.Name
        $relativeWindows = $rel.Replace('/', '\')
        $target = Join-Path $Destination $relativeWindows
        $src = Join-Path $Source $relativeWindows
        $parent = Split-Path -Parent $target
        if (-not (Test-Path -LiteralPath $parent)) {
            New-Item -ItemType Directory -Force -Path $parent | Out-Null
        }
        if (Test-Path -LiteralPath $target -PathType Leaf) {
            $backupFile = Join-Path $backupPath $relativeWindows
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backupFile) | Out-Null
            Copy-Item -LiteralPath $target -Destination $backupFile -Force
        }
        Copy-Item -LiteralPath $src -Destination $target -Force
        $installed += $target
        $actual = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne ([string]$entry.Value).ToLowerInvariant()) {
            throw "Installed file checksum mismatch: $rel"
        }
    }
} catch {
    Write-Warning "Install failed. Restoring previous source files from $backupPath"
    foreach ($target in $installed) {
        $rel = $target.Substring($Destination.Length).TrimStart('\','/')
        $saved = Join-Path $backupPath $rel
        if (Test-Path -LiteralPath $saved -PathType Leaf) {
            Copy-Item -LiteralPath $saved -Destination $target -Force
        } elseif (Test-Path -LiteralPath $target -PathType Leaf) {
            Remove-Item -LiteralPath $target -Force
        }
    }
    throw
}
Write-Host ''
Write-Host "ViePN 2.1 source installed at $Destination" -ForegroundColor Green
Write-Host "Previous code backup: $backupPath"
Write-Host 'Your %%LOCALAPPDATA%% ViePN data, IPA files, sessions and token were not overwritten.'
Write-Host 'Start ViePN by double-clicking Start-ViePN.bat after setup.'
