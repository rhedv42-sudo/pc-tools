@echo off
title PC-Tools Netzwerk-Notfall
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0PCPflege.ps1" -NetDiag
