$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Py = 'py'
try { & $Py -3.12 --version | Out-Null; if ($LASTEXITCODE -ne 0) { throw 'Python missing' } }
catch { throw 'Cần cài Python 3.12 từ python.org và bật Python Launcher (py.exe).' }
& $Py -3.12 -m venv '.venv'
if ($LASTEXITCODE -ne 0) { throw 'Không tạo được .venv' }
& '.\.venv\Scripts\python.exe' -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Không thể nâng pip' }
& '.\.venv\Scripts\python.exe' -m pip install -r 'backend\requirements.txt'
if ($LASTEXITCODE -ne 0) { throw 'Không thể cài dependencies' }
Write-Host 'Đã cài ViePN Windows Companion. Chạy windows\start.ps1.' -ForegroundColor Green
Write-Host 'Lưu ý: Cần iTunes/Apple Mobile Device Service và zsign để cài/ký IPA.'
