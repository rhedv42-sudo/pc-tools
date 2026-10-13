@echo off
title PC-Tools Windows-Reparatur
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0PCPflege.ps1" -WinRepair
