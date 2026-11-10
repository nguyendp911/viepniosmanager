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
echo.
echo =============================================================
echo  ViePN iOS Manager - Update
echo  Default: latest Windows source from GitHub main
echo  Optional: --release for verified Windows + unsigned iOS IPA
echo =============================================================
echo.
set "UPDATER=%~dp0windows\update-main.ps1"
if /I "%~1"=="--release" set "UPDATER=%~dp0windows\update-viepn.ps1"
if not exist "%UPDATER%" (
  echo [ERROR] Missing updater: %UPDATER%
  echo Download the latest source ZIP from your official GitHub repository.
  pause
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%UPDATER%" -Destination "C:\ViePN-iOS-Manager"
set "CODE=%errorlevel%"
if not "%CODE%"=="0" (
  echo.
  echo [ERROR] Update was not completed. See details above.
  pause
  exit /b %CODE%
)
echo.
echo [OK] Update completed.
echo Open C:\ViePN-iOS-Manager\Start-ViePN.bat to run.
pause
endlocal
