"""Dienste: fehlgeschlagene systemd-Units, Journal-Auszug, Startzeit."""
import re

from . import privileged
from .i18n import t
from .util import home_short, run

UNIT_RX = re.compile(r"^\w[\w@.\-]*\.service$")
ANY_UNIT_RX = re.compile(r"^\w[\w@.\-]*\.(service|socket|timer|mount|path|target|scope|slice|device|swap|automount)$")


def parse_failed(text):
    """'systemctl --failed --no-legend --plain' -> [{unit, load, active, sub, description}]"""
    units = []
    for line in (text or "").splitlines():
        parts = line.replace("●", " ").split(None, 4)
        if len(parts) >= 4 and ANY_UNIT_RX.fullmatch(parts[0]):
            units.append({"unit": parts[0], "load": parts[1], "active": parts[2], "sub": parts[3],
                          "description": parts[4].strip() if len(parts) > 4 else ""})
    return units


def failed_units(user=False):
    argv = ["systemctl"] + (["--user"] if user else []) + ["--failed", "--no-legend", "--plain", "--no-pager"]
    r = run(argv, timeout=15)
    if r.missing:
        return None
    return parse_failed(r.out)


def parse_blame(text, top=10):
    res = []
    for line in (text or "").splitlines():
        parts = line.strip().split()
        if len(parts) >= 2:
            res.append({"time": " ".join(parts[:-1]), "unit": parts[-1]})
        if len(res) >= top:
            break
    return res


def boot_info():
    r = run(["systemd-analyze"], timeout=20)
    if r.missing:
        return {"available": False}
    if not r.ok:
        return {"available": False, "summary": t("Startzeit nicht ermittelbar (systemd läuft nicht als Init-System?)")}
    summary = r.out.strip().splitlines()[0] if r.out.strip() else t("nicht verfügbar")
    m = re.search(r"=\s*(.+)$", summary)
    b = run(["systemd-analyze", "blame", "--no-pager"], timeout=30)
    return {"available": True, "summary": summary, "total": m.group(1) if m else "",
            "blame": parse_blame(b.out) if b.ok else []}


def journal(unit, user=False, lines=40):
    if not ANY_UNIT_RX.fullmatch(unit or ""):
        return {"error": t("Ungültiger Dienstname.")}
    argv = ["journalctl"] + (["--user"] if user else []) + ["-u", unit, "-n", str(lines), "--no-pager", "-o", "short-iso"]
    r = run(argv, timeout=30)
    if r.missing:
        return {"text": t("nicht verfügbar")}
    text = r.out.strip() or r.err.strip()
    if not text or "No entries" in text:
        text = t("Keine Einträge sichtbar. Für Systemdienste braucht dein Benutzer evtl. die Gruppe 'systemd-journal' oder 'adm'.")
    return {"text": home_short(text)}


def overview():
    return {"system": failed_units(False), "user": failed_units(True), "boot": boot_info()}


def restart(job, unit, user=False):
    if not UNIT_RX.fullmatch(unit or "") or len(unit) > 200:
        job.log(t("Ungültiger Dienstname."))
        return {"error": True}
    if user:
        job.log(t("Dienst {0} wird neu gestartet …", unit))
        r = run(["systemctl", "--user", "restart", unit], timeout=120)
        s = run(["systemctl", "--user", "is-active", unit], timeout=10)
        job.log((r.err or r.out).strip() or t("Status: {0}", s.out.strip()))
        return {"state": s.out.strip(), "error": not r.ok}
    rc, res = privileged.run_helper(job, "restart-unit", [unit], timeout=300)
    if res:
        job.log(t("Status: {0}", res.get("state")))
    return {"state": (res or {}).get("state"), "error": rc != 0}
