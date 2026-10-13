@echo off
title PC-Tools Komplett-Reparatur
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0PCPflege.ps1" -FullRepair
