# PC-Tools – Sicherheit & Transparenz

Dieses Dokument erklärt offen, **warum ein Virenschutz bei PC-Tools gelegentlich Alarm schlägt**,
warum das ein **Fehlalarm** ist, und was wir dagegen tun. Es ist gedacht zum Weitergeben an
Kollegen und Bekannte, die PC-Tools einsetzen.

## Kurzfassung

PC-Tools ist ein **offenes PowerShell-/WPF-Wartungswerkzeug** für Windows 11. Der komplette
Quellcode liegt in diesem Repository – es ist nichts verschleiert, nichts verschlüsselt, nichts
nachgeladen, was man nicht lesen kann. Manche Virenscanner (vor allem die **KI-Heuristik** von
Microsoft Defender, Erkennungsname `Trojan:Win32/Powbr.A!MTB`) melden es trotzdem als verdächtig.
Das ist ein **Fehlalarm (false positive)**.

## Warum kommt der Fehlalarm?

PC-Tools tut viele Dinge, die ein normales Programm **nicht** tut, ein Administrator-Werkzeug aber
sehr wohl – und genau diese Muster lösen die Heuristik aus:

1. **Desktop-Symbole anordnen.** Um Namen und Positionen der Desktop-Symbole zu lesen und zu setzen,
   muss man der Symbol-Liste (`SysListView32`) Nachrichten schicken. Diese Liste gehört zum
   **Explorer-Prozess**. Windows verlangt dafür zwingend die API-Aufrufe
   `OpenProcess`, `VirtualAllocEx`, `WriteProcessMemory` und `ReadProcessMemory`.
   **Dieselben Aufrufe nutzt auch Schadsoftware zum Code-Einschleusen** – deshalb reagiert die
   Heuristik, obwohl PC-Tools damit nur Symbol-Texte und -Koordinaten liest/setzt.
   (Siehe `DesktopIcons`-Klasse in `PCPflege.ps1`.)
2. **Viele Systemeingriffe.** Dienste auf Standard setzen, Registry, `netsh`, `bcdedit`, `pnputil`,
   Prozesse beenden, geplante Aufgaben – alles legitime Wartung, in Summe aber „auffällig".
3. **Versteckte PowerShell-Starts** (Hintergrundläufe ohne Fenster) und **dynamisch geladener
   Programmcode** (die Engine wird als Textblock ausgeführt). Beides ist bei großen PowerShell-Tools
   üblich, triggert die KI-Modelle aber zusätzlich.

**Was PC-Tools NICHT tut** (und was man im Quellcode nachprüfen kann):
kein Nachladen und Ausführen fremden Codes aus dem Internet, keine verschlüsselten/verschleierten
Befehle, kein Abgreifen von Kennwörtern, kein Deaktivieren von Defender/AMSI, keine Persistenz-Tricks.

## Was wir dagegen tun

1. **Fehlalarm bei Microsoft melden** (kostenlos, wirkt für alle):
   Datei auf <https://www.microsoft.com/en-us/wdsi/filesubmission> einreichen
   (Kategorie *Software developer* → *Incorrectly detected as malware/PUA*).
   Microsoft prüft und nimmt die Datei aus der Erkennung. Begründung siehe unten.
2. **Code-Signierung** mit einem Zertifikat (baut über die Zeit Hersteller-Reputation auf,
   sodass Defender und SmartScreen dem Herausgeber vertrauen).
3. **Transparenz**: offener Quellcode + dieses Dokument.

## Soforthilfe auf dem eigenen PC

- **Aus der Quarantäne wiederherstellen**: Windows-Sicherheit → *Schutzverlauf* → den Fund öffnen →
  *Aktionen* → **Zulassen**.
- **Ordner-Ausnahme setzen** (für die eigenen PCs): Skript
  `Zubehoer/PC-Tools-Defender-Ausnahme.ps1` als Administrator ausführen.
  Das nimmt `C:\ProgramData\PCPflege` von Defender aus.
  (Für die Weitergabe an andere ist die **Microsoft-Meldung** der richtige Weg, nicht die Ausnahme.)

## Begründungstext für die Microsoft-Meldung (zum Kopieren)

> PC-Tools (file: PCPflege.ps1) is an open-source Windows 11 maintenance utility (PowerShell/WPF).
> The full source is available and not obfuscated. The detection
> `Trojan:Win32/Powbr.A!MTB` is a false positive triggered by a legitimate "arrange desktop icons"
> feature that reads/sets Explorer's SysListView32 items via the documented
> OpenProcess/VirtualAllocEx/WriteProcessMemory/ReadProcessMemory sequence, combined with routine
> administrative operations (service/registry/network maintenance) and hidden background PowerShell
> launches. The tool does not download or execute remote code, does not obfuscate commands, does not
> touch credentials, and does not tamper with Defender/AMSI. Please reclassify as clean.

Datei-Prüfsumme (SHA-256) der Version 11.0:
`BF48C0CD8D65C071ADA81005646E205F44CF5DB87DE6AD52222A99AF03508E9A`

> Hinweis: Die Prüfsumme ändert sich mit jeder Version und bei jedem Selbst-Update. Dauerhaft hilft
> deshalb vor allem die **signierte Verteilung** (Hersteller-Reputation), nicht die Freigabe einer
> einzelnen Datei-Prüfsumme.
