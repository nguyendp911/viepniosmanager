# Windows PowerShell 5.1 / PowerShell 7 compatible; ASCII-only source.
$ErrorActionPreference = 'Stop'
$Script = Join-Path $PSScriptRoot 'ensure-python315.ps1'
& $Script -UpgradePip
if ($LASTEXITCODE -ne 0) { throw 'Python 3.15 setup failed.' }
Write-Host 'Setup completed. Start with Start-ViePN.bat' -ForegroundColor Green
