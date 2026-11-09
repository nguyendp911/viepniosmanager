@echo off
setlocal EnableExtensions DisableDelayedExpansion
title ViePN - Nhap chung chi Ad Hoc tren Windows
cd /d "%~dp0"
echo ========================================================
echo   ViePN Certificate Manager - Windows LOCAL ONLY
echo   Khong tai P12, profile hay mat khau len GitHub/Tailscale
echo ========================================================
echo.
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Chay Start-ViePN.bat de cai moi truong Python truoc.
  pause
  exit /b 1
)
set "P12_FILE=%~dp0cert.p12"
set "PROFILE_FILE=%~dp0cert.mobileprovision"
if not exist "%P12_FILE%" (
  set /p "P12_FILE=Nhap duong dan day du den cert.p12: "
)
if not exist "%PROFILE_FILE%" (
  set /p "PROFILE_FILE=Nhap duong dan day du den cert.mobileprovision: "
)
if not exist "%P12_FILE%" (
  echo [ERROR] Khong tim thay P12
  pause
  exit /b 1
)
if not exist "%PROFILE_FILE%" (
  echo [ERROR] Khong tim thay mobileprovision
  pause
  exit /b 1
)
".venv\Scripts\python.exe" backend\import_certificate.py --p12 "%P12_FILE%" --profile "%PROFILE_FILE%"
if errorlevel 1 (
  echo [ERROR] P12 va profile khong khop, sai mat khau hoac chung chi het han.
  pause
  exit /b 1
)
echo.
echo [OK] Da nhap chung chi an toan vao kho LOCALAPPDATA.
echo [IMPORTANT] Sau khi xac minh, chuyen ban P12 goc vao noi luu tru an toan.
pause
