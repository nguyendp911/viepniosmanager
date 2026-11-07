$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Exe = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Exe)) { throw 'Chưa cài môi trường Python. Hãy chạy windows\setup.ps1' }
Write-Host 'Mở trình duyệt tại: http://127.0.0.1:8765' -ForegroundColor Cyan
& $Exe (Join-Path $Root 'backend\run.py')
