@echo off
rem PC-Tools - Erststart. Danach die Verknuepfung auf dem Desktop bzw. im Startmenue verwenden.
if exist "%SystemRoot%\System32\conhost.exe" (
  start "" "%SystemRoot%\System32\conhost.exe" --headless powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0PCPflege.ps1"
) else (
  start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0PCPflege.ps1"
)
