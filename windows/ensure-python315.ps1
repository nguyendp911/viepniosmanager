# ViePN Python 3.15 bootstrap; Windows PowerShell 5.1 and 7, ASCII-only.
param([switch]$UpgradePip)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $Root '.venv'
$Exe = Join-Path $Venv 'Scripts\python.exe'
$Requirements = Join-Path $Root 'backend\requirements.txt'
$check = 'import sys; sys.exit(0 if sys.version_info[:2] == (3,15) and sys.maxsize > 2**32 else 1)'
$cmd = $null
$argsPrefix = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    try {
        & py -3.15 -c $check 2>$null
        if ($LASTEXITCODE -eq 0) { $cmd = 'py'; $argsPrefix = @('-3.15') }
    } catch {}
}
if (-not $cmd -and (Get-Command python -ErrorAction SilentlyContinue)) {
    try {
        & python -c $check 2>$null
        if ($LASTEXITCODE -eq 0) { $cmd = 'python' }
    } catch {}
}
if (-not $cmd) {
    throw 'Python 3.15 64-bit was not found. Install Python 3.15 from https://www.python.org/downloads/windows/ and run: py -3.15 --version'
}
Write-Host 'ViePN: Python 3.15 detected:' -ForegroundColor Cyan
& $cmd @argsPrefix --version

$valid = $false
if (Test-Path -LiteralPath $Exe -PathType Leaf) {
    try {
        & $Exe -c $check 2>$null
        $valid = ($LASTEXITCODE -eq 0)
    } catch {}
}
$Backup = $null
$created = $false
if (-not $valid) {
    if (Test-Path -LiteralPath $Venv) {
        $Backup = Join-Path $Root ('.venv-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
        Write-Host "Backing up existing .venv to $Backup" -ForegroundColor Yellow
        Move-Item -LiteralPath $Venv -Destination $Backup -ErrorAction Stop
    }
    try {
        Write-Host 'Creating Python 3.15 environment...' -ForegroundColor Cyan
        & $cmd @argsPrefix -m venv $Venv
        if ($LASTEXITCODE -ne 0) { throw 'python -m venv failed.' }
        if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) { throw 'Virtual environment Python is missing.' }
        & $Exe -c $check
        if ($LASTEXITCODE -ne 0) { throw 'New virtual environment is not Python 3.15 64-bit.' }
        $created = $true
    } catch {
        if (Test-Path -LiteralPath $Venv) { Remove-Item -LiteralPath $Venv -Recurse -Force }
        if ($Backup -and (Test-Path -LiteralPath $Backup)) { Move-Item -LiteralPath $Backup -Destination $Venv }
        throw
    }
}
try {
    if ($created -or $UpgradePip) {
        & $Exe -m pip install --upgrade pip
        if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
    }
    $probe = 'import fastapi, uvicorn, httpx, requests, multipart, pymobiledevice3, cryptography, srp'
    if (-not $created -and -not $UpgradePip) {
        & $Exe -c $probe 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host 'ViePN Python 3.15 environment ready.' -ForegroundColor Green
            exit 0
        }
    }
    & $Exe -m pip install -r $Requirements
    if ($LASTEXITCODE -ne 0) { throw 'ViePN dependency installation failed on Python 3.15. Review pip output.' }
    & $Exe -c $probe
    if ($LASTEXITCODE -ne 0) { throw 'ViePN dependency import validation failed.' }
    Write-Host 'ViePN Python 3.15 environment ready.' -ForegroundColor Green
} catch {
    if ($created -and $Backup) {
        Write-Warning 'Dependency setup failed; restoring the previous .venv.'
        if (Test-Path -LiteralPath $Venv) { Remove-Item -LiteralPath $Venv -Recurse -Force }
        Move-Item -LiteralPath $Backup -Destination $Venv
    }
    throw
}
