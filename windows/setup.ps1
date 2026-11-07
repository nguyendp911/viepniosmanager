# Windows PowerShell 5.1 / PowerShell 7 compatible; ASCII-only source.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

$PythonCmd = $null
$PythonArgs = @()
$VersionCheck = 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'

if (Get-Command py -ErrorAction SilentlyContinue) {
    try {
        & py -3 -c $VersionCheck 2>$null
        if ($LASTEXITCODE -eq 0) {
            $PythonCmd = 'py'
            $PythonArgs = @('-3')
        }
    } catch {}
}

if (-not $PythonCmd -and (Get-Command python -ErrorAction SilentlyContinue)) {
    try {
        & python -c $VersionCheck 2>$null
        if ($LASTEXITCODE -eq 0) {
            $PythonCmd = 'python'
            $PythonArgs = @()
        }
    } catch {}
}

if (-not $PythonCmd) {
    throw 'Python 3.10+ was not detected. Run: py --list-paths or python --version. Install Python from python.org if needed.'
}

Write-Host 'Using installed Python:' -ForegroundColor Cyan
& $PythonCmd @PythonArgs --version

$Exe = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) {
    Write-Host 'Creating .venv...' -ForegroundColor Cyan
    & $PythonCmd @PythonArgs -m venv (Join-Path $Root '.venv')
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to create .venv. Verify that the selected Python supports venv.'
    }
}

if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) {
    throw '.venv\Scripts\python.exe is missing. The virtual environment was not created.'
}

& $Exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }

& $Exe -m pip install -r (Join-Path $Root 'backend\requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Review the pip errors above.' }

Write-Host 'Setup completed. Start with:' -ForegroundColor Green
Write-Host 'powershell -ExecutionPolicy Bypass -File .\windows\start.ps1'
