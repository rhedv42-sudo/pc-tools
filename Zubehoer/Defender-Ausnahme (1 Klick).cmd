@echo off
title PC-Tools - Defender-Ausnahme (1 Klick)
rem Holt Adminrechte, entsperrt die Skripte und startet die Defender-Ausnahme - ohne Sicherheitswarnung.
net session >nul 2>&1
if %errorlevel% neq 0 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem '%~dp0PC-Tools-*.ps1' | Unblock-File"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0PC-Tools-Defender-Ausnahme.ps1"
