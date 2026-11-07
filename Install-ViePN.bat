@echo off
setlocal
title ViePN 2.1 - Install Windows Portable
cd /d "%~dp0"
echo =======================================================
echo  ViePN Windows Portable Installer
echo  Checks every packaged file before installing.
echo  Does NOT delete user data in LOCALAPPDATA.
echo =======================================================
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\install-portable.ps1" -Source "%~dp0" -Destination "C:\ViePN-iOS-Manager"
if errorlevel 1 (
 echo.
 echo [ERROR] Installation aborted. See the error above.
 pause
 exit /b 1
)
echo.
echo [OK] Installation complete. Open C:\ViePN-iOS-Manager\Start-ViePN.bat
pause
endlocal
