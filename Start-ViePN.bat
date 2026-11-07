@echo off
setlocal EnableExtensions DisableDelayedExpansion
title ViePN iOS Manager - ALL IN ONE
cd /d "%~dp0"
if /i "%~1"=="--self-test" (
    echo ViePN ALL-IN-ONE launcher ready.
    exit /b 0
)
echo.
echo ========================================================
echo  ViePN iOS Manager - ALL IN ONE
echo  Windows API + Remote Gateway + Tailscale Serve + Alerts
echo ========================================================
echo.
set "VIEPN_HOST=127.0.0.1"
set "VIEPN_PORT=8765"
set "VIEPN_REMOTE_PORT=8766"
set "PY=.venv\Scripts\python.exe"

rem Set up only when the Python environment/dependencies are missing.
if not exist "%PY%" (
    where py >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python launcher not found. Install Python 3.10+.
        goto fail
    )
    echo [ViePN] Creating local Python environment...
    py -3 -m venv .venv
    if errorlevel 1 goto fail
)
"%PY%" -c "import fastapi, uvicorn, httpx, requests, multipart, pymobiledevice3" >nul 2>&1
if errorlevel 1 (
    echo [ViePN] Installing missing Python packages...
    "%PY%" -m pip install -r backend\requirements.txt
    if errorlevel 1 goto fail
)

rem The two ViePN ports must never listen on a public/LAN interface.
call :check_loopback 8765
if errorlevel 1 (
    echo [ERROR] Port 8765 is exposed beyond localhost. Stop the old LAN server.
    goto fail
)
call :check_loopback 8766
if errorlevel 1 (
    echo [ERROR] Port 8766 is exposed beyond localhost. Stop that process.
    goto fail
)

call :check_health 8765
if errorlevel 1 (
    echo [ViePN] Starting Windows API on 127.0.0.1:8765...
    start "ViePN - Windows API" /D "%CD%" cmd /k ".venv\Scripts\python.exe backend\run.py"
    call :wait_health 8765
    if errorlevel 1 goto fail
) else (
    echo [ViePN] Windows API is already running.
)
rem Prevent silently reusing a stale old-version service.
powershell.exe -NoProfile -Command "try {$r=Invoke-RestMethod 'http://127.0.0.1:8765/api/health' -TimeoutSec 2; if ($r.version -eq '1.4.0' -and $r.ok) {exit 0}}catch{}; exit 1" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Another ViePN version is running on 8765.
    echo Close its old PowerShell window, then double-click this BAT again.
    goto fail
)
call :check_loopback 8765
if errorlevel 1 goto fail

call :check_health 8766
if errorlevel 1 (
    echo [ViePN] Starting private gateway on 127.0.0.1:8766...
    start "ViePN - Private Gateway" /D "%CD%" cmd /k ".venv\Scripts\python.exe backend\remote_run.py"
    call :wait_health 8766
    if errorlevel 1 goto fail
) else (
    echo [ViePN] Private gateway is already running.
)
call :check_loopback 8766
if errorlevel 1 goto fail

echo [OK] ViePN API and gateway are working.
echo [ViePN] Local dashboard: http://127.0.0.1:8765
start "" "http://127.0.0.1:8765"

rem Remote mode is optional. Never switch to Tailscale Funnel or open router ports.
set "TAILSCALE="
if exist "%ProgramFiles%\Tailscale\tailscale.exe" set "TAILSCALE=%ProgramFiles%\Tailscale\tailscale.exe"
if not defined TAILSCALE (
    where tailscale.exe >nul 2>&1
    if not errorlevel 1 set "TAILSCALE=tailscale.exe"
)
if not defined TAILSCALE (
    echo [INFO] Tailscale not installed. Local ViePN remains available.
    echo Install Tailscale and rerun this BAT to enable private HTTPS.
    goto done
)

"%TAILSCALE%" status --json 2>nul | powershell.exe -NoProfile -Command "try {$s=($input | Out-String | ConvertFrom-Json);if($s.BackendState -eq 'Running'){exit 0}}catch{};exit 1" >nul
if errorlevel 1 (
    echo [INFO] Sign in / enable Tailscale for Windows, then rerun this BAT.
    goto done
)

set "STATUS_FILE=%TEMP%\viepn-serve-status-%RANDOM%-%RANDOM%.txt"
"%TAILSCALE%" serve status >"%STATUS_FILE%" 2>&1
findstr /C:"127.0.0.1:8766" "%STATUS_FILE%" >nul 2>&1
if not errorlevel 1 (
    echo [ViePN] Private HTTPS Serve is already configured.
    goto remote_ready
)
findstr /C:"No serve config" "%STATUS_FILE%" >nul 2>&1
if errorlevel 1 (
    echo [WARN] Existing Tailscale Serve configuration detected.
    echo ViePN will not overwrite an existing HTTPS service on port 443.
    echo Check using: tailscale serve status
    goto done
)
echo [ViePN] Enabling private Tailscale Serve HTTPS...
"%TAILSCALE%" serve --bg --https=443 http://127.0.0.1:8766
if errorlevel 1 (
    echo [WARN] Tailscale Serve was not enabled. Activate Serve in Tailscale admin.
    echo Then rerun this BAT; local ViePN is still running.
    goto done
)
:remote_ready
echo.
echo [OK] Tailscale private HTTPS status:
"%TAILSCALE%" serve status
echo.
echo On your iPhone, connect to the HTTPS address printed above.
echo Use the same Tailscale tailnet and your ViePN access token.
echo [ALERTS] Dashboard - Settings - iPhone Notifications:
echo          Opt in, copy the private topic, subscribe in the ntfy app.
:done
if defined STATUS_FILE if exist "%STATUS_FILE%" del /q "%STATUS_FILE%" >nul 2>&1
echo.
echo [ViePN] All available services started. Keep the API windows open.
pause
exit /b 0

:check_loopback
powershell.exe -NoProfile -Command "$items=Get-NetTCPConnection -State Listen -LocalPort %~1 -ErrorAction SilentlyContinue; if(@($items | Where-Object {$_.LocalAddress -notin @('127.0.0.1','::1')}).Count -gt 0){exit 1}else{exit 0}" >nul 2>&1
exit /b %errorlevel%

:check_health
powershell.exe -NoProfile -Command "try{$r=Invoke-RestMethod 'http://127.0.0.1:%~1/api/health' -TimeoutSec 2;if($r.ok -eq $true){exit 0}}catch{};exit 1" >nul 2>&1
exit /b %errorlevel%

:wait_health
powershell.exe -NoProfile -Command "$ok=$false;for($i=0;$i -lt 30;$i++){try{$r=Invoke-RestMethod 'http://127.0.0.1:%~1/api/health' -TimeoutSec 2;if($r.ok){$ok=$true;break}}catch{};Start-Sleep -Milliseconds 700};if($ok){exit 0}else{exit 1}" >nul 2>&1
if errorlevel 1 echo [ERROR] Port %~1 failed to start. Check the ViePN console.
exit /b %errorlevel%

:fail
echo.
echo [ERROR] ViePN could not finish startup. Check the message above.
pause
exit /b 1
