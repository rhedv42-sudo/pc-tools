"""Verfügbare Updates je Quelle (Systempakete, Flatpak, Snap) ermitteln."""
import re
import threading
import time

from .i18n import t
from .sysinfo import detect_package_manager
from .util import run, which

_cache = {"time": 0, "data": None}
_cache_lock = threading.Lock()


# ------------------------------------------------------------------ Parser
def parse_apt_upgradable(text):
    """'apt list --upgradable' -> [{name, new, old, security}]"""
    pkgs = []
    rx = re.compile(r"^([^/\s]+)/(\S+)\s+(\S+)\s+(\S+)(?:\s+\[upgradable from:\s*([^\]]+)\])?")
    for line in (text or "").splitlines():
        m = rx.match(line.strip())
        if not m:
            continue
        pkgs.append({"name": m.group(1), "new": m.group(3), "old": (m.group(5) or "").strip(),
                     "repo": m.group(2), "security": "-security" in m.group(2)})
    return pkgs


def parse_dnf_check_update(text):
    """'dnf check-update' (dnf4/dnf5) -> [{name, new, repo}]"""
    pkgs = []
    carry = ""
    for line in (text or "").splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith(("Obsoleting", "Security:")):
            break
        if s.startswith(("Last metadata", "Updating and loading", "Repositories loaded",
                         "Metadata cache", "Upgrades", "Available upgrades")):
            continue
        parts = (carry + " " + s).split() if carry else s.split()
        carry = ""
        if len(parts) == 1 and "." in parts[0]:
            carry = parts[0]          # dnf4 bricht lange Namen in die nächste Zeile um
            continue
        if len(parts) != 3 or "." not in parts[0]:
            continue
        name = parts[0].rsplit(".", 1)[0]
        if not re.match(r"^[\w.+-]+$", name):
            continue
        pkgs.append({"name": name, "new": parts[1], "old": "", "repo": parts[2],
                     "security": False})
    return pkgs


def parse_zypper_table(text):
    """Tabellen von zypper (lu, lp, packages) -> Liste von Dicts nach Kopfzeile."""
    rows = []
    header = None
    for line in (text or "").splitlines():
        if "|" not in line:
            continue
        cols = [c.strip() for c in line.split("|")]
        if set(line.replace("|", "").replace("+", "").strip()) <= {"-"}:
            continue
        if header is None:
            header = [c.lower() for c in cols]
            continue
        rows.append(dict(zip(header, cols)))
    return rows


def parse_zypper_lu(text):
    pkgs = []
    for r in parse_zypper_table(text):
        name = r.get("name")
        if not name:
            continue
        pkgs.append({"name": name, "new": r.get("available version", ""),
                     "old": r.get("current version", ""), "repo": r.get("repository", ""),
                     "security": False})
    return pkgs


def parse_pacman_updates(text):
    """'checkupdates' / 'pacman -Qu': 'name alt -> neu'"""
    pkgs = []
    for line in (text or "").splitlines():
        m = re.match(r"^(\S+)\s+(\S+)\s+->\s+(\S+)", line.strip())
        if m:
            pkgs.append({"name": m.group(1), "old": m.group(2), "new": m.group(3),
                         "repo": "", "security": False})
    return pkgs


def parse_flatpak_updates(text):
    pkgs = []
    for line in (text or "").splitlines():
        parts = line.split("\t")
        if not parts[0].strip() or parts[0].strip().lower() in ("application id", "application"):
            continue
        pkgs.append({"name": parts[0].strip(), "new": parts[1].strip() if len(parts) > 1 else "",
                     "old": "", "repo": parts[2].strip() if len(parts) > 2 else "",
                     "security": False})
    return pkgs


def parse_snap_refresh_list(text):
    pkgs = []
    lines = (text or "").splitlines()
    if not lines or not lines[0].startswith("Name"):
        return pkgs
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 2:
            pkgs.append({"name": parts[0], "new": parts[1], "old": "", "repo": "snap",
                         "security": False})
    return pkgs


# ------------------------------------------------------------------ Abfragen
def system_updates(pm, online=False):
    """Liefert (pakete, fehlertext). online=False nutzt nur vorhandene Paketlisten."""
    if pm == "apt":
        r = run(["apt", "list", "--upgradable"], timeout=60)
        if r.missing:
            return [], t("nicht verfügbar")
        return parse_apt_upgradable(r.out), ""
    if pm == "dnf":
        argv = ["dnf", "check-update", "-q"] + ([] if online else ["-C"])
        r = run(argv, timeout=180)
        if r.missing or r.timeout:
            return [], t("nicht verfügbar")
        if r.rc not in (0, 100):
            return [], (r.err.strip().splitlines() or [t("Fehler bei der Abfrage")])[-1]
        return parse_dnf_check_update(r.out), ""
    if pm == "zypper":
        argv = ["zypper", "-q", "--non-interactive"] + ([] if online else ["--no-refresh"]) + ["lu"]
        r = run(argv, timeout=180)
        if r.missing or r.timeout:
            return [], t("nicht verfügbar")
        return parse_zypper_lu(r.out), ""
    if pm == "pacman":
        if online and which("checkupdates"):
            r = run(["checkupdates"], timeout=120)
            # rc 2 = keine Updates
            return parse_pacman_updates(r.out), ""
        r = run(["pacman", "-Qu"], timeout=30)
        note = "" if which("checkupdates") else t("Hinweis: Ohne 'checkupdates' (Paket pacman-contrib) ist die Liste evtl. veraltet.")
        return parse_pacman_updates(r.out), note
    return [], t("Keine unterstützte Paketverwaltung gefunden.")


def flatpak_updates():
    if not which("flatpak"):
        return None
    r = run(["flatpak", "remote-ls", "--updates", "--columns=application,version,origin"], timeout=90)
    return parse_flatpak_updates(r.out) if r.ok else []


def snap_updates():
    if not which("snap"):
        return None
    r = run(["snap", "refresh", "--list"], timeout=90)
    return parse_snap_refresh_list(r.out)


def security_count(pm, sys_pkgs):
    """Anzahl ausstehender Sicherheitsupdates (None = nicht ermittelbar)."""
    if pm == "apt":
        return sum(1 for p in sys_pkgs if p.get("security"))
    if pm == "dnf":
        r = run(["dnf", "-C", "-q", "updateinfo", "list", "--security"], timeout=120)
        if not r.ok:
            return None
        return len({ln.split()[-1] for ln in r.out.splitlines()
                    if len(ln.split()) >= 3 and "/Sec" in ln})
    if pm == "zypper":
        r = run(["zypper", "-q", "--non-interactive", "--no-refresh", "lp", "-g", "security"], timeout=120)
        if r.missing:
            return None
        return sum(1 for row in parse_zypper_table(r.out) if "needed" in (row.get("status", "") + row.get("state", "")).lower())
    return None


def collect(online=False, include_apps=True):
    pm = detect_package_manager()
    sys_pkgs, note = system_updates(pm, online) if pm else ([], t("Keine unterstützte Paketverwaltung gefunden."))
    data = {
        "package_manager": pm,
        "system": sys_pkgs,
        "system_note": note,
        "flatpak": flatpak_updates() if include_apps else None,
        "snap": snap_updates() if include_apps else None,
        "security": security_count(pm, sys_pkgs),
        "reboot_required": reboot_required(),
        "apps_checked": include_apps,
        "time": int(time.time()),
    }
    with _cache_lock:
        _cache["time"] = time.time()
        _cache["data"] = data
    return data


def cached(max_age=900):
    """Letztes Ergebnis, falls jünger als max_age Sekunden."""
    with _cache_lock:
        if _cache["data"] and time.time() - _cache["time"] < max_age:
            return _cache["data"]
    return None


def invalidate():
    with _cache_lock:
        _cache["data"] = None


def reboot_required():
    """Neustart nötig? Debian/Ubuntu-Marker oder fehlende Module des laufenden Kernels."""
    import os
    import platform
    if os.path.exists("/var/run/reboot-required") or os.path.exists("/run/reboot-required"):
        return True
    rel = platform.release()
    if os.path.isdir("/usr/lib/modules") and os.listdir("/usr/lib/modules"):
        if not os.path.isdir("/usr/lib/modules/" + rel) and not os.path.isdir("/lib/modules/" + rel):
            return True       # Kernel wurde aktualisiert und das alte Modulverzeichnis entfernt (Arch u. a.)
    if which("needs-restarting"):
        r = run(["needs-restarting", "-r"], timeout=30)
        if r.rc == 1:
            return True
    return False
