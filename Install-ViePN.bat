@echo off
setlocal EnableExtensions DisableDelayedExpansion
title ViePN - Install Windows Portable
cd /d "%~dp0"
if /I "%~1"=="--self-test" (
    if not exist "%~dp0windows\install-portable.ps1" exit /b 1
    echo [OK] ViePN Portable installer launcher ready.
    exit /b 0
)
echo =======================================================
echo  ViePN Windows Portable Installer
echo  Checks every packaged file before installing.
echo  Does NOT delete user data in LOCALAPPDATA.
echo =======================================================
echo.
set "VIEPN_INSTALL_DEST=C:\ViePN-iOS-Manager"
if defined VIEPN_TEST_INSTALL_DEST set "VIEPN_INSTALL_DEST=%VIEPN_TEST_INSTALL_DEST%"
rem IMPORTANT: Never pass -Source "%%~dp0" with a trailing backslash:
rem Windows argument quoting may escape the closing double quote and merge
rem -Source with -Destination. The PowerShell script resolves its own source.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\install-portable.ps1" -Destination "%VIEPN_INSTALL_DEST%"
if errorlevel 1 (
    echo.
    echo [ERROR] Installation aborted. See the error above.
    if /I not "%~1"=="--ci-test" pause
    exit /b 1
)
echo.
echo [OK] Installation complete: %VIEPN_INSTALL_DEST%
if /I not "%~1"=="--ci-test" pause
endlocal
exit /b 0
