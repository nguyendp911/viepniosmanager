@echo off
setlocal EnableExtensions DisableDelayedExpansion
title ViePN - Auto Update from Official GitHub Release
cd /d "%~dp0"
if /I "%~1"=="--self-test" (
  if not exist "%~dp0windows\update-viepn.ps1" (
    echo [ERROR] Missing windows\update-viepn.ps1
    exit /b 1
  )
  echo [OK] ViePN updater launcher found.
  exit /b 0
)
echo.
echo ==============================================================
echo  ViePN iOS Manager - UPDATE ALL (Windows source + iOS IPA)
echo  Latest official GitHub Release; verified SHA256 and manifest
echo ==============================================================
echo.
if not exist "%~dp0windows\update-viepn.ps1" (
  echo [ERROR] Missing windows\update-viepn.ps1
  echo Install ViePN Portable 2.1.2 or newer first.
  pause
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\update-viepn.ps1" -Destination "C:\ViePN-iOS-Manager"
set "CODE=%errorlevel%"
if not "%CODE%"=="0" (
  echo.
  echo [ERROR] Update was not completed. See details above.
  pause
  exit /b %CODE%
)
echo.
echo [OK] ViePN source and iOS IPA update completed.
echo Open C:\ViePN-iOS-Manager\Start-ViePN.bat to run.
pause
endlocal
