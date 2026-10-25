# Datenschutz

PC-Tools hat **keine Telemetrie** und sammelt keine Nutzungsdaten. Es gibt kein Konto, keine Werbung,
keinen Server des Projekts. Alle Daten (Einstellungen, Protokolle, Berichte) bleiben auf dem PC
(`C:\ProgramData\PCPflege`, Dokumente) bzw. bei der portablen Version auf dem Stick.

Verbindungen ins Internet entstehen nur durch Funktionen, die der Benutzer startet oder selbst einschaltet:

| Funktion | Ziel | Was wird gesendet | Abschalten |
|---|---|---|---|
| Selbstupdate | api.github.com (dieses Repository) | Abruf von version.json / Programmdatei | Einstellungen > „Beim Start nach neuer Version suchen“ |
| Programm-, Treiber-, Windows-Updates | Microsoft (Windows Update, Store, winget-Quellen), Chocolatey, Hersteller (Intel, NVIDIA, HP, Dell, Lenovo, Surface …) | übliche Update-Abfragen dieser Dienste | Einstellungen > Updates |
| Werkzeuge/Installationen auf Knopfdruck | Hersteller-Downloadseiten (z.B. Sysinternals, TeamViewer, AnyDesk, RustDesk, Ninite) | Download-Anfrage | nur auf Knopfdruck |
| Speedtest, DNS-Vergleich | speed.cloudflare.com, öffentliche DNS-Server | Mess-Anfragen | nur auf Knopfdruck |
| Netzwerk dokumentieren | api.ipify.org (öffentliche IP), optional internetdb.shodan.io (nur die eigene öffentliche IP) | eigene öffentliche IP-Adresse | Häkchen „Erreichbarkeit von außen prüfen“ |
| KI-Assistent (optional) | der gewählte Anbieter: localhost:11434 (Ollama, bleibt auf dem PC), api.groq.com, openrouter.ai, api.mistral.ai, api.anthropic.com, api.openai.com, generativelanguage.googleapis.com oder eine selbst eingetragene Adresse | Frage und die dazu gewählten PC-Infos | nur auf Knopfdruck; bei Ollama verlässt nichts den PC |
| KI-Assistent: Ollama einrichten (optional) | winget (Microsoft/GitHub), ollama.com | keine persönlichen Daten (Programm- und Modell-Download) | nur nach Bestätigung |
| Benachrichtigungen (optional) | vom Benutzer eingetragene Ziele (ntfy, Home Assistant, Teams/Slack-Webhook) | Kurzmeldung zum PC-Zustand | Einstellungen > Benachrichtigungen |
| Garantie-Abfrage, ISO-Download | Herstellerseiten, Microsoft, uupdump.net | Seriennummer/Modell bzw. Build | nur auf Knopfdruck |
| Passwort-Check (optional) | api.pwnedpasswords.com (Have I Been Pwned) | nur die ersten 5 Zeichen des SHA-1-Fingerabdrucks jedes Passworts (k-Anonymität) – nie das Passwort selbst, nie Seite oder Benutzername | nur auf Knopfdruck |
| Hilfe holen (optional) | der eigene „Meine PCs“-Ordner, die eingetragenen Benachrichtigungs-Ziele bzw. das eigene Mailprogramm | Bericht über den PC-Zustand (Score, Probleme, Fehler der letzten 3 Tage, letzte Protokollzeilen) – keine Passwörter, keine Dateien | nur auf Knopfdruck |
| Netzwerk-Prüfungen | nur Geräte im eigenen Netz bzw. der eigene Router | Verbindungsversuche | nur auf Knopfdruck / Zeitplan, den der Benutzer einschaltet |

Zugangsdaten (FRITZ!Box-Kennwort, Home-Assistant-Token, API-Schlüssel, GitHub-Token) werden nie übertragen,
außer an das jeweilige Ziel selbst, und – wenn überhaupt gespeichert – mit Windows-Verschlüsselung (DPAPI) auf
diesem PC. WLAN-Kennwörter kommen nie in Berichte.

Für Dienste Dritter gelten deren Datenschutzbestimmungen (z.B. GitHub, Microsoft, Cloudflare, Shodan und der jeweils gewählte KI-Anbieter).
