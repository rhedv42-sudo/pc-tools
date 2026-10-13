# Zweck und Abgrenzung / Purpose and scope

**PC-Tools ist ein Wartungs- und Absicherungswerkzeug – kein Angriffswerkzeug.**

Die Sicherheits- und Netzwerkfunktionen dienen ausschließlich dazu, **Schwachstellen im eigenen Netz bzw. auf den
eigenen Geräten zu finden und zu beheben** (Härtung):

- Es werden **keine Schwachstellen ausgenutzt**, keine Kennwörter ausprobiert, keine Schutzmaßnahmen umgangen und
  keine Geräte geschaltet oder verändert.
- Geprüft wird nur, ob Dienste ohne Anmeldung erreichbar sind oder veraltet/unsicher eingestellt sind – zu jedem
  Befund nennt PC-Tools die **Behebung** (z.B. „Kennwort setzen“, „Telnet abschalten“, „Firmware aktualisieren“).
- Die Netzwerk-Prüfungen sind auf das **lokale eigene Netz** des PCs beschränkt (höchstens das eigene /24-Netz).
  Die Oberfläche weist darauf hin, sie nur in Netzen zu verwenden, die einem gehören oder die man prüfen darf.
- Die Prüfung der Erreichbarkeit von außen schlägt nur die **eigene öffentliche IP** in einer öffentlichen
  Datenbank nach (passiv, abschaltbar) – es wird nichts im Internet gescannt.
- Ergebnis ist eine Dokumentation mit Maßnahmenplan für Administratoren, Firmen und Privatanwender.

---

**PC-Tools is a maintenance and hardening tool – not an offensive security tool.**

Its security and network features exist solely to **find and fix weaknesses on the user's own devices and own local
network**. It does not exploit vulnerabilities, does not try passwords, does not bypass security measures and does not
control or modify other devices. Checks are limited to the PC's own local subnet; the external exposure check only
looks up the user's own public IP in a public database (passive, optional). Every finding comes with remediation
guidance. The output is a documentation report with an action plan.
