@echo off
setlocal
title ViePN iOS Manager Launcher
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [ERROR] Python environment has not been set up.
    echo Open PowerShell here and run:
    echo   powershell -ExecutionPolicy Bypass -File .\windows\setup.ps1
    echo.
    pause
    exit /b 1
)

rem Reuse the existing local backend when the dashboard is already running.
powershell.exe -NoProfile -Command "try { $r=Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/health' -TimeoutSec 2; if ($r.ok -eq $true) { exit 0 } } catch {} ; exit 1" >nul 2>&1
if errorlevel 1 (
    echo [ViePN] Starting local API server...
    start "ViePN iOS Manager - Server" powershell.exe -NoProfile -ExecutionPolicy Bypass -NoExit -File "%~dp0windows\start.ps1"
    timeout /t 4 /nobreak >nul
) else (
    echo [ViePN] Server already running. Opening dashboard...
)

start "" "http://127.0.0.1:8765"
endlocal
