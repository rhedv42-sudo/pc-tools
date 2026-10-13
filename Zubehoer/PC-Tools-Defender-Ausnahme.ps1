<#
    PC-Tools - Defender-Ausnahme einrichten
    ----------------------------------------
    Sagt Microsoft Defender, dass er die PC-Tools-Ordner in Ruhe lassen soll
    (nicht scannen, nicht loeschen). Nur bei Bedarf ausfuehren.
    Aendert ausschliesslich die Ausnahmeliste von Defender - sonst nichts.

    Ausfuehren: Rechtsklick auf diese Datei > "Mit PowerShell ausfuehren"
    (oder in einer Administrator-PowerShell starten). Fragt selbst nach Adminrechten.

    Rueckgaengig: Remove-MpPreference -ExclusionPath "<Ordner>"
#>

# --- Adminrechte pruefen (KEIN automatischer Neustart - bitte in einer Administrator-PowerShell ausfuehren) ---
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host ''
    Write-Host '  Bitte in einer PowerShell MIT Administratorrechten ausfuehren.' -ForegroundColor Yellow
    Write-Host '  Startmenue > "PowerShell" > Rechtsklick > "Als Administrator ausfuehren", dann dieses Skript erneut starten.' -ForegroundColor Gray
    Write-Host ''
    Read-Host '  Enter zum Beenden'
    return
}

$ErrorActionPreference = 'Stop'
try { $Host.UI.RawUI.WindowTitle = 'PC-Tools Defender-Ausnahme' } catch { }
Write-Host ''
Write-Host '  PC-TOOLS  -  DEFENDER-AUSNAHME' -ForegroundColor White -BackgroundColor DarkCyan
Write-Host ''

# Ordner bestimmen: Standard-Installationsordner, Datenordner und - falls dieses Skript
# neben einer PCPflege.ps1 liegt (z.B. USB-Stick) - auch dieser Ordner.
$paths = New-Object System.Collections.Generic.List[string]
$paths.Add((Join-Path $env:ProgramData 'PCPflege'))
$here = Split-Path -Parent $PSCommandPath
if ($here -and (Test-Path (Join-Path $here 'PCPflege.ps1'))) { $paths.Add($here) }

$ok = 0
foreach ($p in ($paths | Select-Object -Unique)) {
    try {
        Add-MpPreference -ExclusionPath $p -ErrorAction Stop
        Write-Host ('  Ausnahme hinzugefuegt: {0}' -f $p) -ForegroundColor Green
        $ok++
    } catch {
        Write-Host ('  {0}: {1}' -f $p, $_.Exception.Message) -ForegroundColor Yellow
    }
}

Write-Host ''
Write-Host '  Aktuelle Defender-Ordner-Ausnahmen:' -ForegroundColor Gray
try { foreach ($x in @((Get-MpPreference).ExclusionPath)) { Write-Host ('    ' + $x) -ForegroundColor DarkGray } } catch { Write-Host '    (nicht lesbar)' -ForegroundColor DarkGray }

Write-Host ''
Write-Host ('  Fertig - {0} Ordner ausgenommen. Defender laesst PC-Tools jetzt in Ruhe.' -f $ok) -ForegroundColor Cyan
Write-Host '  Rueckgaengig: Remove-MpPreference -ExclusionPath "<Ordner>"' -ForegroundColor DarkGray
Write-Host ''
Read-Host '  Enter zum Beenden'
