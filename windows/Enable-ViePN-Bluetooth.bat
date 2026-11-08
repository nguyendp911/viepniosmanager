@echo off
setlocal
title ViePN - Enable Bluetooth LE on Windows
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Chua co Python venv. Chay Start-ViePN.bat truoc.
  pause
  exit /b 1
)
echo.
echo ========================================================
echo  ViePN Bluetooth BLE - Cai thu vien quet Bluetooth
echo  Yeu cau may Windows co adapter Bluetooth LE
echo ========================================================
echo.
".venv\Scripts\python.exe" -m pip install "bleak>=0.22,<3"
if errorlevel 1 (
  echo [ERROR] Khong cai duoc Bleak. Kiem tra Python va Internet.
  pause
  exit /b 1
)
echo [OK] Da cai Bleak. Mo lai ViePN va quet BLE tu iPhone.
pause
