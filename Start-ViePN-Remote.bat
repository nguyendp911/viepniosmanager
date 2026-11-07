@echo off
setlocal
title ViePN iOS Manager - Private Remote Access
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -NoExit -File "%~dp0windows\start-remote.ps1"
endlocal
