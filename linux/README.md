# PC-Tools für Linux

Kostenloses Open-Source-Wartungswerkzeug (Apache-2.0) – die Linux-Ausgabe von PC-Tools.
Es zeigt auf einen Blick, wie es um den Rechner steht, und erledigt die übliche Pflege mit wenigen Klicks.
Die Oberfläche ist Deutsch (weitere Sprachen folgen).

## Was es kann

| Seite | Inhalt |
|---|---|
| **Übersicht** | Systeminfo (Distribution, Kernel, CPU, RAM, Datenträger, Laufzeit, Desktop), Zustand 0–100 mit Ampel und konkreten Befunden, „Alles pflegen“ (Updates + Aufräumen) mit einer Bestätigung |
| **Updates** | verfügbare Updates je Quelle (Systempakete, Flatpak, Snap), alles installieren mit Fortschritt und Protokoll, Hinweis „Neustart erforderlich“ |
| **Aufräumen** | erst analysieren (Größen), dann Auswahl bereinigen: Paket-Cache, nicht mehr benötigte Pakete (nur nach Bestätigung), Journal (> 14 Tage), Papierkorb, Vorschaubilder, alte Snap-Versionen, ungenutzte Flatpak-Laufzeiten. Große Ordner in `~/.cache` werden nur angezeigt |
| **Autostart** | Einträge aus `~/.config/autostart` und `/etc/xdg/autostart` ein-/ausschalten (über eine Benutzerkopie mit `Hidden=true`), aktivierte `systemd --user`-Dienste |
| **Dienste** | fehlgeschlagene systemd-Dienste (System und Benutzer) mit „Neu starten“ und Protokollauszug, Startzeit und die 10 langsamsten Dienste |
| **Datenträger** | Dateisysteme mit Belegung, Geräte (lsblk), SMART-Zustand (smartctl, nur lesend), TRIM-Status |
| **Sicherheit** | Firewall (ufw/firewalld/nftables), automatische Sicherheitsupdates, SSH-Einstellungen, offene Ports, ausstehende Sicherheitsupdates, Secure Boot, Verschlüsselung – jeweils mit Erklärung und Lösung |
| **Netzwerk-Diagnose** | Schnittstellen, Router-Ping, DNS-Test, Internet (TCP 443 zu 1.1.1.1 und 9.9.9.9), WLAN-Infos (nmcli) |
| **Netzwerk dokumentieren** | Scan des eigenen /24-Netzes (Ping, ARP, ~30 typische Ports), Hersteller, geschätzter Gerätetyp, Hinweise (Telnet, FTP, SMB1, offene Admin-Ports), druckbarer Bericht (als PDF speichern) |
| **KI-Assistent** | Fragen in einfacher Sprache stellen – lokal und kostenlos mit Ollama oder online mit Groq, OpenRouter, Mistral, Claude, ChatGPT, Gemini oder einem eigenen OpenAI-kompatiblen Server. Die KI führt nichts selbst aus |

## Installation

Voraussetzung: Python 3.8 oder neuer (ist auf praktisch jeder Distribution vorinstalliert).
Für Updates und Systempflege wird `pkexec` (polkit) empfohlen – auf Desktop-Systemen meist vorhanden.

Im Terminal (als normaler Benutzer, **nicht** mit sudo):

```sh
curl -fsSL https://github.com/rhedv42-sudo/pc-tools/releases/latest/download/pc-tools-linux-14.0.0.tar.gz | tar xz && cd pc-tools-linux-14.0.0 && ./install.sh
```

Danach startet PC-Tools über das Startmenü oder mit `pc-tools`.
Für Debian, Ubuntu und Mint gibt es zusätzlich ein `.deb`-Paket im Release (`sudo apt install ./pc-tools_14.0.0_all.deb`).

Ohne Installation ausprobieren: Archiv entpacken und `./pc-tools` starten.
`pc-tools --no-browser` zeigt nur die Adresse an, statt den Browser zu öffnen.

## Deinstallation

```sh
~/.local/share/pc-tools/uninstall.sh            # Programm entfernen
~/.local/share/pc-tools/uninstall.sh --purge    # zusätzlich Einstellungen und API-Schlüssel löschen
```

Beim `.deb`: `sudo apt remove pc-tools`.

## So funktioniert es

- PC-Tools startet einen kleinen Webserver **nur auf 127.0.0.1** mit zufälligem Port und öffnet den Standardbrowser.
  Jede Anfrage braucht einen zufälligen Schlüssel (32 Byte), der nur in dieser Adresse steckt. Andere Webseiten
  und andere Rechner im Netz können nicht zugreifen. Das Programm beendet sich über „Beenden“, kurz nach dem
  Schließen des Tabs oder nach 2 Stunden ohne Nutzung.
- Das Programm läuft **nie als root**. Aktionen mit Administratorrechten (Updates, Paket-Cache, Journal,
  Dienst neu starten, SMART lesen, Firewall/TRIM einschalten) laufen über einen kleinen Helfer
  (`pctools/helper.py`) mit fester Liste erlaubter Aktionen. Das System fragt dafür jedes Mal nach dem Kennwort
  (pkexec). Fehlt ein Werkzeug, zeigt PC-Tools „nicht verfügbar“ statt eines Fehlers.

## Datenschutz

- Keine Telemetrie, keine Werbung, kein Konto. Die Oberfläche lädt nichts aus dem Internet.
- Internetzugriffe nur auf deinen Wunsch: Updates (über die Paketquellen deiner Distribution), Verbindungstest
  (1.1.1.1, 9.9.9.9, example.org, wikipedia.org) und der KI-Assistent.
- KI-Assistent: Mit **Ollama** bleibt alles auf dem eigenen Rechner. Bei Online-Anbietern gehen deine Frage und –
  nur wenn angehakt – eine kurze Systemübersicht (ohne Rechner- und Benutzernamen) an den gewählten Anbieter.
  „Vorschau“ zeigt vorher genau, was mitgesendet würde.
- API-Schlüssel liegen in `~/.config/pc-tools/keys.json` mit Rechten 600 (nur für dich lesbar) und werden nie protokolliert.
- Der Netzwerk-Scan bleibt im eigenen Subnetz, der Bericht wird nur lokal erzeugt.
  **Nur im eigenen Netzwerk verwenden** – das Scannen fremder Netze ist ohne Erlaubnis verboten.

## Unterstützte Distributionen

Gedacht für alle gängigen Distributionen mit systemd: Ubuntu/Debian/Mint (apt), Fedora (dnf),
openSUSE (zypper), Arch/Manjaro/EndeavourOS (pacman), jeweils mit Flatpak und Snap.

**Ehrlicher Stand:** Version 14.0.0 wurde bisher nur in einem Ubuntu-24.04-Container ohne Desktop getestet
(Unit-Tests, Server-Test und die Oberfläche in Headless-Chrome). Die Befehle für dnf, zypper und pacman sind
nach deren Dokumentation umgesetzt und mit Beispielausgaben getestet, aber noch nicht auf echten Systemen.
Rückmeldungen und Fehlerberichte bitte über GitHub-Issues.

## Für Entwickler

```sh
cd linux
python3 -m unittest discover -s tests -v     # Tests
python3 tools/extract_strings.py --sync      # Texte für Übersetzungen sammeln (lang/keys.json)
sh build/build-packages.sh                   # dist/pc-tools-linux-<version>.tar.gz und .deb bauen
```

Übersetzungen: `lang/<code>.json` im Format `{"meta": {...}, "strings": {"Deutscher Text": "Übersetzung"}}`.
Leere oder fehlende Übersetzungen zeigen den deutschen Text.

Lizenz: Apache-2.0 · https://github.com/rhedv42-sudo/pc-tools
