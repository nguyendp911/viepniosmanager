# ViePN Apple Account authentication, local console only. ASCII for PS 5.1.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Python venv is missing. Run windows\setup.ps1 first.'
}
Set-Location (Join-Path $Root 'backend')
Write-Host 'ViePN Apple ID - local sign-in. No browser password form.' -ForegroundColor Cyan
& $Python -m viepn.native_sign login
if ($LASTEXITCODE -ne 0) { throw 'Apple ID login failed. See error above.' }
Write-Host 'Apple ID session saved on this Windows user profile.' -ForegroundColor Green
