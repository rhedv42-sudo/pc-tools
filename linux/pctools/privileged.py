"""Startet den Root-Helfer (helper.py) über pkexec bzw. sudo -n.

Die App selbst läuft nie als root. Nur der kleine Helfer mit fester Aktionsliste
bekommt Administratorrechte – nach Kennwortabfrage durch das System (polkit).
"""
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from .i18n import t
from .util import which

HELPER = Path(__file__).resolve().parent / "helper.py"


def _python():
    exe = os.path.realpath(sys.executable or "")
    if exe and os.path.isabs(exe) and os.path.exists(exe):
        return exe
    return which("python3") or "/usr/bin/python3"


def method():
    """Welcher Weg zu Root-Rechten ist verfügbar? 'pkexec', 'sudo' oder None."""
    if which("pkexec"):
        return "pkexec"
    if which("sudo"):
        return "sudo"
    return None


def build_command(action, params):
    m = method()
    base = [_python(), str(HELPER), action] + list(params)
    if m == "pkexec":
        return [which("pkexec")] + base
    if m == "sudo":
        return [which("sudo"), "-n"] + base
    return None


def step_text(line):
    """Übersetzt Statuszeilen des Helfers in lesbare Meldungen."""
    parts = line.split()
    key = parts[1] if len(parts) > 1 else ""
    arg = " ".join(parts[2:])
    texts = {
        "refresh": t("Paketlisten werden aktualisiert ({0}) …", arg),
        "upgrade-system": t("Systempakete werden aktualisiert ({0}) …", arg),
        "upgrade-flatpak": t("Flatpak-Apps werden aktualisiert …"),
        "upgrade-snap": t("Snap-Pakete werden aktualisiert …"),
        "clean-pkgcache": t("Paket-Cache wird geleert ({0}) …", arg),
        "autoremove": t("Nicht mehr benötigte Pakete werden entfernt …"),
        "journal": t("Systemprotokoll (Journal) wird auf 14 Tage gekürzt …"),
        "snap-old": t("Alte Snap-Versionen werden entfernt …"),
        "flatpak-unused": t("Ungenutzte Flatpak-Laufzeiten werden entfernt …"),
        "restart-unit": t("Dienst {0} wird neu gestartet …", arg),
        "smart": t("SMART-Werte von {0} werden gelesen …", arg),
        "enable-unit": t("{0} wird aktiviert …", arg),
        "missing": t("Programm nicht verfügbar: {0}", arg),
        "unsupported": t("Für diese Distribution nicht unterstützt: {0}", arg),
        "timeout": t("Zeitlimit überschritten: {0}", arg),
        "rejected": t("Aktion vom Helfer abgelehnt (nicht erlaubt)."),
        "not-root": t("Der Helfer hat keine Administratorrechte bekommen."),
    }
    if key == "done":
        return None
    return texts.get(key, line)


def run_helper(job, action, params=(), timeout=7200):
    """Führt eine Helfer-Aktion aus, schreibt die Ausgabe ins Job-Protokoll.

    Rückgabe: (rc, ergebnis_dict_oder_None)
    """
    cmd = build_command(action, params)
    if not cmd:
        job.log(t("Weder pkexec noch sudo gefunden – Administratoraktionen sind nicht möglich."))
        return 127, None
    job.log(t("Administratorrechte werden angefordert (Kennwortabfrage des Systems) …"))
    result = None
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, text=True, errors="replace")
    except OSError as e:
        job.log(t("Start fehlgeschlagen: {0}", e))
        return 126, None
    timer = threading.Timer(timeout, p.kill)
    timer.start()
    try:
        for raw in p.stdout:
            line = raw.rstrip("\n")
            if line.startswith("PCT-RESULT "):
                try:
                    result = json.loads(line[11:])
                except ValueError:
                    pass
                continue
            if line.startswith("PCT-STEP "):
                line = step_text(line)
                if line is None:
                    continue
            job.log(line)
        p.wait()
    finally:
        timer.cancel()
    rc = p.returncode
    if cmd[0].endswith("pkexec") and rc in (126, 127):
        job.log(t("Abgebrochen: Die Anmeldung als Administrator wurde abgelehnt oder abgebrochen."))
    elif cmd[0].endswith("sudo") and rc == 1 and result is None and len(job.lines) < 3:
        job.log(t("sudo verlangt ein Kennwort. Bitte pkexec (polkit) installieren oder den Befehl im Terminal ausführen."))
    elif rc == 0:
        job.log(t("Fertig."))
    else:
        job.log(t("Beendet mit Fehlercode {0}.", rc))
    return rc, result
