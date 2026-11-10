@echo off
setlocal EnableExtensions DisableDelayedExpansion
title ViePN - Auto Update
cd /d "%~dp0"
if /I "%~1"=="--self-test" (
  if not exist "%~dp0windows\update-main.ps1" exit /b 1
  if not exist "%~dp0windows\update-viepn.ps1" exit /b 1
  echo [OK] ViePN updater scripts found.
  exit /b 0
)
set "UPDATER=%~dp0windows\update-main.ps1"
if /I "%~1"=="--release" set "UPDATER=%~dp0windows\update-viepn.ps1"
if not exist "%UPDATER%" (
  echo [ERROR] Missing updater: %UPDATER%
  pause
  exit /b 1
)
echo.
echo =============================================================
echo  ViePN iOS Manager - Update
echo  Default: latest Windows source from GitHub main
echo  Optional: --release for verified Windows + unsigned iOS IPA
echo =============================================================
echo.
echo [ViePN] Opening standalone updater window...
rem CRITICAL: exit this BAT before the updater overwrites Update-ViePN.bat.
rem Running PowerShell in a separate console avoids cmd batch offset corruption.
start "ViePN Updater" powershell.exe -NoLogo -NoProfile -NoExit -ExecutionPolicy Bypass -File "%UPDATER%" -Destination "C:\ViePN-iOS-Manager"
if errorlevel 1 (
  echo [ERROR] Could not launch updater.
  pause
  exit /b 1
)
exit /b 0
