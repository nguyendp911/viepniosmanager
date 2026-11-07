# Windows PowerShell 5.1 / PowerShell 7 compatible; ASCII-only source.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Exe = Join-Path $Root '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) {
    throw 'Python venv missing. Run: powershell -ExecutionPolicy Bypass -File .\windows\setup.ps1'
}

Set-Location -LiteralPath $Root
Write-Host 'ViePN dashboard: http://127.0.0.1:8765' -ForegroundColor Cyan
& $Exe (Join-Path $Root 'backend\run.py')
if ($LASTEXITCODE -ne 0) {
    throw "Backend exited with code $LASTEXITCODE. Check the error messages above."
}
