# Starts the separate, restricted local remote gateway; never use 0.0.0.0.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'ViePN Python environment not found. Run windows\setup.ps1 first.'
}
Set-Location -LiteralPath $Root
& $Python (Join-Path $Root 'backend\remote_run.py')
if ($LASTEXITCODE -ne 0) { throw "Remote gateway stopped with error $LASTEXITCODE" }
