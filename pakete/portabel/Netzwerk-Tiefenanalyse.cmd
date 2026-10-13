@echo off
title PC-Pflege Netzwerk-Tiefenanalyse
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0PCPflege.ps1" -NetDeep
