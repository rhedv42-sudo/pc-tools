<#
    PC-Tools - Code-Signierung einrichten (kostenlos, selbst signiert)
    ------------------------------------------------------------------
    Nur noetig, wenn du auf dem PC wirklich NUR signierte Skripte zulaesst
    (ExecutionPolicy AllSigned). PC-Tools selbst startet ohnehin mit
    -ExecutionPolicy Bypass und braucht die Signatur zum Laufen NICHT.

    Dieses Skript:
      1) erstellt EINMALIG ein eigenes Codesignatur-Zertifikat "PC-Tools (eigene Signatur)"
      2) richtet es als vertrauenswuerdig ein (Trusted Root + Trusted Publisher, LocalMachine)
      3) signiert die PCPflege.ps1 im selben Ordner

    WICHTIG - ehrlich:
      - Nur auf DEINEN eigenen PCs ausfuehren.
      - "Vertrauen einrichten" heisst: dieser PC vertraut ab dann ALLEM, was mit
        diesem Zertifikat signiert ist. Deshalb laeuft das bewusst NICHT automatisch
        und ist nicht in PC-Tools eingebaut, sondern nur dieses Skript auf Zuruf.
      - Im Firmennetz ist die Verteilung des Zertifikats per Gruppenrichtlinie/Intune
        der sauberere Weg als dieses Skript auf jedem PC.
      - Ein selbst signiertes Zertifikat stoppt WEDER Virenschutz-Loeschungen NOCH
        SmartScreen-Warnungen - dafuer braeuchte es ein kostenpflichtiges Zertifikat.

    Ausfuehren: Rechtsklick > "Mit PowerShell ausfuehren" (fragt selbst nach Adminrechten).
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
try { $Host.UI.RawUI.WindowTitle = 'PC-Tools Signierung einrichten' } catch { }
$subject = 'CN=PC-Tools (eigene Signatur)'
Write-Host ''
Write-Host '  PC-TOOLS  -  CODE-SIGNIERUNG EINRICHTEN' -ForegroundColor White -BackgroundColor DarkBlue
Write-Host ''

# 1) Zertifikat finden oder neu erstellen
$cert = @(Get-ChildItem Cert:\LocalMachine\My -CodeSigningCert -ErrorAction SilentlyContinue | Where-Object { $_.Subject -like 'CN=*PC-Tools*' -and $_.NotAfter -gt (Get-Date) } | Sort-Object NotAfter -Descending | Select-Object -First 1)
if ($cert.Count) {
    $cert = $cert[0]
    Write-Host ('  Vorhandenes Zertifikat genutzt: {0} (gueltig bis {1:dd.MM.yyyy})' -f $cert.Thumbprint, $cert.NotAfter) -ForegroundColor Green
} else {
    $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject $subject -CertStoreLocation Cert:\LocalMachine\My -KeyUsage DigitalSignature -KeyExportPolicy NonExportable -NotAfter (Get-Date).AddYears(3)
    Write-Host ('  Neues Zertifikat erstellt: {0} (gueltig bis {1:dd.MM.yyyy})' -f $cert.Subject, $cert.NotAfter) -ForegroundColor Green
}

# 2) Vertrauen einrichten (oeffentlicher Teil in Root + TrustedPublisher)
$tmp = Join-Path $env:TEMP 'pctools-codesign.cer'
Export-Certificate -Cert $cert -FilePath $tmp -Force | Out-Null
foreach ($store in 'Root', 'TrustedPublisher') {
    try { Import-Certificate -FilePath $tmp -CertStoreLocation ('Cert:\LocalMachine\{0}' -f $store) | Out-Null; Write-Host ('  Zertifikat in LocalMachine\{0} eingetragen.' -f $store) -ForegroundColor Green }
    catch { Write-Host ('  {0}: {1}' -f $store, $_.Exception.Message) -ForegroundColor Yellow }
}
Remove-Item $tmp -Force -ErrorAction SilentlyContinue

# 3) PCPflege.ps1 im selben Ordner signieren
$here = Split-Path -Parent $PSCommandPath
$target = if ($here) { Join-Path $here 'PCPflege.ps1' } else { '' }
if ($target -and (Test-Path $target)) {
    try {
        $r = Set-AuthenticodeSignature -FilePath $target -Certificate $cert -HashAlgorithm SHA256 -TimestampServer 'http://timestamp.digicert.com' -ErrorAction Stop
        Write-Host ('  PCPflege.ps1 signiert: {0}' -f $r.Status) -ForegroundColor $(if ([string]$r.Status -eq 'Valid') { 'Green' } else { 'Yellow' })
    } catch { Write-Host ('  Signieren fehlgeschlagen: {0}' -f $_.Exception.Message) -ForegroundColor Yellow }
} else {
    Write-Host '  Keine PCPflege.ps1 in diesem Ordner - nur Zertifikat und Vertrauen eingerichtet.' -ForegroundColor Yellow
    Write-Host '  (Lege dieses Skript neben PCPflege.ps1, um sie gleich mitzusignieren.)' -ForegroundColor DarkGray
}

Write-Host ''
Write-Host '  Hinweise:' -ForegroundColor Yellow
Write-Host '   - PC-Tools startet mit -ExecutionPolicy Bypass und braucht die Signatur zum Laufen NICHT.' -ForegroundColor Gray
Write-Host '   - Nach jedem Selbstupdate ist PCPflege.ps1 wieder unsigniert. Unter AllSigned dann erneut' -ForegroundColor Gray
Write-Host '     signieren (dieses Skript nochmal laufen lassen) oder die Datei vor dem Hochladen mit' -ForegroundColor Gray
Write-Host '     "PCPflege.ps1 -Sign" signieren.' -ForegroundColor Gray
Write-Host ''
Read-Host '  Enter zum Beenden'
