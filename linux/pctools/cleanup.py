"""Aufräumen: erst analysieren (Größen), dann ausgewählte Punkte bereinigen."""
import os
import re
import shutil
from pathlib import Path

from . import privileged
from .i18n import t
from .sysinfo import detect_package_manager
from .updates import parse_zypper_table
from .util import dir_size, human_size, parse_size, run, which

HOME = Path.home()
TRASH = Path(os.environ.get("XDG_DATA_HOME") or HOME / ".local/share") / "Trash"
CACHE = Path(os.environ.get("XDG_CACHE_HOME") or HOME / ".cache")
THUMBS = CACHE / "thumbnails"
PKG_CACHE_DIRS = {"apt": ["/var/cache/apt/archives"], "dnf": ["/var/cache/dnf", "/var/cache/libdnf5"],
                  "zypper": ["/var/cache/zypp/packages"], "pacman": ["/var/cache/pacman/pkg"]}
ROOT_ITEMS = ("pkgcache", "autoremove", "journal", "snap-old", "flatpak-unused")
USER_ITEMS = ("trash", "thumbnails")


# ------------------------------------------------------------------ Parser
def parse_apt_autoremove(text):
    """'apt-get -s autoremove' -> Paketnamen aus den 'Remv'-Zeilen."""
    return [m.group(1) for m in re.finditer(r"^Remv\s+(\S+)", text or "", re.M)]


def parse_snap_disabled(text):
    """'snap list --all' -> [(name, revision)] der deaktivierten (alten) Versionen."""
    res = []
    for line in (text or "").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 4 and "disabled" in parts[-1] and parts[2].isdigit():
            res.append((parts[0], parts[2]))
    return res


def unused_packages(pm):
    """Liste nicht mehr benötigter Pakete (nur Anzeige)."""
    if pm == "apt":
        r = run(["apt-get", "-s", "autoremove"], timeout=60)
        return parse_apt_autoremove(r.out) if r.ok else None
    if pm == "dnf":
        r = run(["dnf", "-C", "-q", "repoquery", "--unneeded"], timeout=120)
        return [l.strip() for l in r.out.splitlines() if l.strip()] if r.ok else None
    if pm == "pacman":
        r = run(["pacman", "-Qdtq"], timeout=30)
        return r.out.split() if not r.missing else None
    if pm == "zypper":
        r = run(["zypper", "-q", "--non-interactive", "--no-refresh", "packages", "--unneeded"], timeout=120)
        return [row.get("name") for row in parse_zypper_table(r.out) if row.get("name")] if r.ok else None
    return None


def cache_folders(limit=12):
    """Größte Unterordner von ~/.cache (wird nie automatisch gelöscht)."""
    if not CACHE.is_dir():
        return []
    res = []
    try:
        for entry in os.scandir(CACHE):
            if entry.is_dir(follow_symlinks=False):
                res.append({"name": entry.name, "size": dir_size(entry.path)})
    except OSError:
        return []
    res.sort(key=lambda x: -x["size"])
    return res[:limit]


def analyze():
    pm = detect_package_manager()
    items = []

    size = sum(dir_size(d) for d in PKG_CACHE_DIRS.get(pm, []) if os.path.isdir(d))
    note = ""
    if pm == "pacman" and not which("paccache"):
        note = t("Für Arch wird 'paccache' (Paket pacman-contrib) benötigt.")
    items.append({"id": "pkgcache", "title": t("Paket-Cache"), "root": True, "size": size,
                  "available": bool(pm), "default": True,
                  "desc": t("Heruntergeladene Installationspakete. Werden nach der Installation nicht mehr gebraucht."),
                  "note": note})

    pkgs = unused_packages(pm) if pm else None
    items.append({"id": "autoremove", "title": t("Nicht mehr benötigte Pakete"), "root": True,
                  "size": None, "count": len(pkgs or []), "details": (pkgs or [])[:200],
                  "available": pkgs is not None and pm != "zypper" and bool(pkgs), "default": False,
                  "confirm": True,
                  "desc": t("Abhängigkeiten, die kein installiertes Programm mehr braucht. Bitte die Liste vor dem Entfernen prüfen."),
                  "note": t("Unter openSUSE nur Anzeige – bitte selbst mit zypper entfernen.") if pm == "zypper" else ""})

    jsize = None
    if which("journalctl"):
        r = run(["journalctl", "--disk-usage"], timeout=30)
        jsize = parse_size(r.out.split("take up")[-1]) if r.ok else None
    items.append({"id": "journal", "title": t("Systemprotokoll (Journal)"), "root": True, "size": jsize,
                  "available": bool(which("journalctl")), "default": True,
                  "desc": t("Einträge älter als 14 Tage werden gelöscht. Neuere bleiben für die Fehlersuche.")})

    items.append({"id": "trash", "title": t("Papierkorb"), "root": False,
                  "size": dir_size(TRASH) if TRASH.is_dir() else 0, "available": TRASH.is_dir(),
                  "default": False, "confirm": True,
                  "desc": t("Dateien im Papierkorb werden endgültig gelöscht.")})

    items.append({"id": "thumbnails", "title": t("Vorschaubilder-Cache"), "root": False,
                  "size": dir_size(THUMBS) if THUMBS.is_dir() else 0, "available": THUMBS.is_dir(),
                  "default": True, "desc": t("Vorschaubilder werden bei Bedarf neu erzeugt.")})

    if which("snap"):
        r = run(["snap", "list", "--all"], timeout=30)
        old = parse_snap_disabled(r.out)
        ssize = 0
        for name, rev in old:
            try:
                ssize += os.path.getsize("/var/lib/snapd/snaps/%s_%s.snap" % (name, rev))
            except OSError:
                pass
        items.append({"id": "snap-old", "title": t("Alte Snap-Versionen"), "root": True, "size": ssize,
                      "count": len(old), "details": ["%s (rev %s)" % o for o in old],
                      "available": bool(old), "default": True,
                      "desc": t("Snap behält ältere Versionen jedes Pakets. Die deaktivierten werden entfernt.")})
    if which("flatpak"):
        items.append({"id": "flatpak-unused", "title": t("Ungenutzte Flatpak-Laufzeiten"), "root": True,
                      "size": None, "available": True, "default": True,
                      "desc": t("Laufzeiten, die keine installierte Flatpak-App mehr braucht.")})

    return {"package_manager": pm, "items": items, "cache_folders": cache_folders(),
            "cache_total": dir_size(CACHE) if CACHE.is_dir() else 0}


def _empty_dir(path, job):
    """Löscht den Inhalt eines Ordners (ohne Symlinks zu folgen). Gibt freigegebene Bytes zurück."""
    freed = 0
    if not os.path.isdir(path) or os.path.islink(path):
        return 0
    for entry in os.scandir(path):
        try:
            if entry.is_dir(follow_symlinks=False):
                freed += dir_size(entry.path)
                shutil.rmtree(entry.path, ignore_errors=True)
            else:
                freed += entry.stat(follow_symlinks=False).st_size
                os.unlink(entry.path)
        except OSError as e:
            job.log(t("Konnte nicht löschen: {0} ({1})", entry.name, e.strerror))
    return freed


def clean(job, items):
    """Bereinigt die ausgewählten Punkte. Root-Punkte laufen gesammelt in EINEM Helferaufruf."""
    items = [i for i in items if i in ROOT_ITEMS + USER_ITEMS]
    freed = 0
    if "trash" in items:
        job.log(t("Papierkorb wird geleert …"))
        for sub in ("files", "info", "expunged"):
            freed += _empty_dir(str(TRASH / sub), job)
    if "thumbnails" in items:
        job.log(t("Vorschaubilder-Cache wird geleert …"))
        freed += _empty_dir(str(THUMBS), job)
    if "flatpak-unused" in items and which("flatpak"):
        # Benutzer-Installation braucht keine Root-Rechte
        r = run(["flatpak", "uninstall", "--unused", "-y", "--noninteractive", "--user"], timeout=600)
        if r.out.strip():
            job.log(r.out.strip())
    if freed:
        job.log(t("Freigegeben (ohne Systembereiche): {0}", human_size(freed)))
    root = [i for i in items if i in ROOT_ITEMS]
    rc = 0
    if root:
        rc, _ = privileged.run_helper(job, "clean", root)
    return {"freed_user": freed, "rc": rc, "error": rc != 0}
