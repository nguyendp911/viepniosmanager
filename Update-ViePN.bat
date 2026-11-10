@echo off
setlocal EnableExtensions DisableDelayedExpansion
title ViePN - Auto Update
rem Run update logic from a temporary BAT: the updater replaces its own
rem installed BAT file, which corrupts cmd.exe batch parsing mid-execution.
if /I "%~1"=="--self-test" (
  if not exist "%~dp0windows\update-main.ps1" exit /b 1
  if not exist "%~dp0windows\update-viepn.ps1" exit /b 1
  echo [OK] ViePN updater scripts found.
  exit /b 0
)
if /I not "%~1"=="--worker" (
  set "VIEPN_UPDATE_ROOT=%~dp0"
  set "WORKER=%TEMP%\viepn-update-%RANDOM%-%RANDOM%.bat"
  copy /Y "%~f0" "%WORKER%" >nul
  if errorlevel 1 (
    echo [ERROR] Cannot prepare temporary updater.
    pause
    exit /b 1
  )
  call "%WORKER%" --worker %*
  set "CODE=%errorlevel%"
  del /Q "%WORKER%" >nul 2>&1
  exit /b %CODE%
)
if not defined VIEPN_UPDATE_ROOT (
  echo [ERROR] Missing installation root.
  exit /b 1
)
cd /d "%VIEPN_UPDATE_ROOT%"
echo.
echo =============================================================
echo  ViePN iOS Manager - Update
echo  Default: latest Windows source from GitHub main
echo  Optional: --release for verified Windows + unsigned iOS IPA
echo =============================================================
echo.
set "UPDATER=%VIEPN_UPDATE_ROOT%windows\update-main.ps1"
if /I "%~2"=="--release" set "UPDATER=%VIEPN_UPDATE_ROOT%windows\update-viepn.ps1"
if not exist "%UPDATER%" (
  echo [ERROR] Missing updater: %UPDATER%
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
exit /b 0
