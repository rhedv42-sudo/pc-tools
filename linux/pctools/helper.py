#!/usr/bin/env python3
"""PC-Tools Root-Helfer.

Wird ausschließlich über pkexec (oder sudo -n) gestartet und führt NUR Aktionen
aus einer festen Liste aus. Parameter werden streng geprüft, Befehle laufen als
Argumentliste (nie über eine Shell) und immer mit Zeitlimit.

Aufruf:  helper.py <aktion> [parameter ...]
Ausgabe: Zeilen der Befehle; Statuszeilen beginnen mit "PCT-STEP ", ein
         strukturiertes Ergebnis steht in einer Zeile "PCT-RESULT {json}".
Eigenständig (nur Standardbibliothek, keine Importe aus dem Paket).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

SAFE_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
UNIT_RX = re.compile(r"^\w[\w@.\-]*\.service$")
PKG_RX = re.compile(r"^[A-Za-z0-9@_+][A-Za-z0-9@._+\-]*$")
CLEAN_ITEMS = ("pkgcache", "autoremove", "journal", "snap-old", "flatpak-unused")
UPGRADE_SOURCES = ("system", "flatpak", "snap")


def step(key, *args):
    print("PCT-STEP " + key + ((" " + " ".join(str(a) for a in args)) if args else ""), flush=True)


def which(name):
    return shutil.which(name, path=SAFE_PATH)


def env():
    return {"PATH": SAFE_PATH, "LC_ALL": "C", "LANG": "C",
            "DEBIAN_FRONTEND": "noninteractive", "HOME": "/root"}


def stream(argv, timeout):
    """Startet argv, gibt jede Ausgabezeile sofort weiter, beendet nach timeout Sekunden."""
    exe = which(argv[0])
    if not exe:
        step("missing", argv[0])
        return 127
    print("$ " + " ".join(argv), flush=True)
    p = subprocess.Popen([exe] + argv[1:], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, env=env(), text=True, errors="replace")
    timer = threading.Timer(timeout, p.kill)
    timer.start()
    try:
        for line in p.stdout:
            print(line.rstrip("\n"), flush=True)
        p.wait()
    finally:
        timer.cancel()
    if p.returncode < 0:
        step("timeout", argv[0])
    return p.returncode


def capture(argv, timeout=60):
    exe = which(argv[0])
    if not exe:
        return 127, ""
    try:
        p = subprocess.run([exe] + argv[1:], capture_output=True, text=True, timeout=timeout,
                           env=env(), errors="replace", stdin=subprocess.DEVNULL)
        return p.returncode, p.stdout
    except subprocess.TimeoutExpired:
        return 124, ""


def package_manager():
    # Zuerst die Paketverwaltung der Distribution laut os-release, dann die erste vorhandene
    osr = ""
    try:
        with open("/etc/os-release") as f:
            osr = f.read().lower()
    except OSError:
        pass
    ids = " ".join(l.split("=", 1)[1] for l in osr.splitlines() if l.startswith(("id=", "id_like=")))
    for key, cand, exe in (("debian", "apt", "apt-get"), ("ubuntu", "apt", "apt-get"),
                           ("fedora", "dnf", "dnf"), ("rhel", "dnf", "dnf"),
                           ("suse", "zypper", "zypper"), ("arch", "pacman", "pacman")):
        if key in ids and which(exe):
            return cand
    for pm, exe in (("apt", "apt-get"), ("dnf", "dnf"), ("zypper", "zypper"), ("pacman", "pacman")):
        if which(exe):
            return pm
    return None


# ------------------------------------------------------------------ Aktionen
def do_refresh():
    pm = package_manager()
    step("refresh", pm)
    cmd = {"apt": ["apt-get", "update"], "dnf": ["dnf", "-y", "makecache"],
           "zypper": ["zypper", "--non-interactive", "refresh"], "pacman": ["pacman", "-Sy"]}.get(pm)
    return stream(cmd, 900) if cmd else 2


def do_upgrade(sources):
    rc = 0
    pm = package_manager()
    if "system" in sources and pm:
        step("upgrade-system", pm)
        if pm == "apt":
            rc |= stream(["apt-get", "update"], 900)
            rc |= stream(["apt-get", "-y", "-o", "Dpkg::Options::=--force-confdef",
                          "-o", "Dpkg::Options::=--force-confold", "--with-new-pkgs", "upgrade"], 3600)
        elif pm == "dnf":
            rc |= stream(["dnf", "-y", "upgrade", "--refresh"], 3600)
        elif pm == "zypper":
            rc |= stream(["zypper", "--non-interactive", "refresh"], 900)
            rc |= stream(["zypper", "--non-interactive", "update"], 3600)
        elif pm == "pacman":
            rc |= stream(["pacman", "-Syu", "--noconfirm"], 3600)
    if "flatpak" in sources and which("flatpak"):
        step("upgrade-flatpak")
        rc |= stream(["flatpak", "update", "-y", "--noninteractive", "--system"], 3600)
    if "snap" in sources and which("snap"):
        step("upgrade-snap")
        rc |= stream(["snap", "refresh"], 3600)
    return 1 if rc else 0


def snap_disabled():
    rc, out = capture(["snap", "list", "--all"])
    res = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 4 and "disabled" in parts[-1] and PKG_RX.fullmatch(parts[0]) and parts[2].isdigit():
            res.append((parts[0], parts[2]))
    return res


def do_clean(items):
    rc = 0
    pm = package_manager()
    if "pkgcache" in items:
        step("clean-pkgcache", pm)
        if pm == "apt":
            rc |= stream(["apt-get", "clean"], 300)
        elif pm == "dnf":
            rc |= stream(["dnf", "clean", "all"], 300)
        elif pm == "zypper":
            rc |= stream(["zypper", "--non-interactive", "clean", "--all"], 300)
        elif pm == "pacman":
            if which("paccache"):
                rc |= stream(["paccache", "-rk2"], 300)
            else:
                step("missing", "paccache")
    if "autoremove" in items:
        step("autoremove", pm)
        if pm == "apt":
            rc |= stream(["apt-get", "-y", "autoremove"], 1800)
        elif pm == "dnf":
            rc |= stream(["dnf", "-y", "autoremove"], 1800)
        elif pm == "pacman":
            _, out = capture(["pacman", "-Qdtq"])
            names = [n for n in out.split() if PKG_RX.fullmatch(n)]
            if names:
                rc |= stream(["pacman", "-Rns", "--noconfirm"] + names, 1800)
        else:
            step("unsupported", "autoremove")
    if "journal" in items:
        step("journal")
        rc |= stream(["journalctl", "--vacuum-time=14d"], 300)
    if "snap-old" in items and which("snap"):
        step("snap-old")
        for name, rev in snap_disabled():
            rc |= stream(["snap", "remove", name, "--revision=" + rev], 600)
    if "flatpak-unused" in items and which("flatpak"):
        step("flatpak-unused")
        rc |= stream(["flatpak", "uninstall", "--unused", "-y", "--noninteractive", "--system"], 900)
    return 1 if rc else 0


def do_restart_unit(unit):
    step("restart-unit", unit)
    rc = stream(["systemctl", "restart", "--", unit], 120)
    _, state = capture(["systemctl", "is-active", unit])
    print("PCT-RESULT " + json.dumps({"unit": unit, "state": state.strip()}), flush=True)
    return rc


def smart_disks():
    rc, out = capture(["lsblk", "-J", "-d", "-o", "NAME,TYPE"])
    try:
        devs = json.loads(out).get("blockdevices", [])
    except ValueError:
        return []
    return ["/dev/" + d["name"] for d in devs
            if d.get("type") == "disk" and not d["name"].startswith(("zram", "loop", "ram", "sr"))
            and re.match(r"^[a-z0-9]+$", d["name"])]


def do_smart():
    if not which("smartctl"):
        step("missing", "smartctl")
        print("PCT-RESULT " + json.dumps({"available": False, "disks": []}), flush=True)
        return 0
    results = []
    for dev in smart_disks():
        step("smart", dev)
        rc, out = capture(["smartctl", "-H", "-A", "-i", "-j", dev], 60)
        entry = {"device": dev, "passed": None, "model": "", "temp": None, "warnings": []}
        try:
            data = json.loads(out)
            entry["model"] = data.get("model_name", "")
            st = data.get("smart_status")
            if isinstance(st, dict):
                entry["passed"] = bool(st.get("passed"))
            entry["temp"] = (data.get("temperature") or {}).get("current")
            for a in (data.get("ata_smart_attributes") or {}).get("table", []):
                raw = (a.get("raw") or {}).get("value", 0)
                if a.get("id") in (5, 187, 197, 198) and raw:
                    entry["warnings"].append("%s=%s" % (a.get("name"), raw))
            nv = data.get("nvme_smart_health_information_log") or {}
            if nv.get("media_errors"):
                entry["warnings"].append("media_errors=%s" % nv["media_errors"])
            if nv.get("percentage_used", 0) >= 90:
                entry["warnings"].append("percentage_used=%s" % nv["percentage_used"])
            if nv.get("critical_warning"):
                entry["warnings"].append("critical_warning=%s" % nv["critical_warning"])
            if entry["passed"] is None:
                entry["note"] = "unsupported"
        except ValueError:
            entry["passed"] = None
            entry["note"] = "unsupported"
        results.append(entry)
    print("PCT-RESULT " + json.dumps({"available": True, "disks": results}), flush=True)
    return 0


def do_enable_ufw():
    if not which("ufw"):
        step("missing", "ufw")
        return 127
    # Laufende SSH-Verbindungen nicht aussperren
    _, ss = capture(["ss", "-tlnH"])
    if re.search(r":22\s", ss):
        stream(["ufw", "allow", "22/tcp"], 60)
    return stream(["ufw", "--force", "enable"], 120)


def do_enable_unit(unit):
    step("enable-unit", unit)
    return stream(["systemctl", "enable", "--now", unit], 120)


def resolve(argv):
    """Prüft Aktion und Parameter gegen die Whitelist. Rückgabe: Funktion ohne Argumente oder None."""
    if not argv:
        return None
    action, params = argv[0], argv[1:]
    if action == "refresh" and not params:
        return do_refresh
    if action == "upgrade" and params and all(p in UPGRADE_SOURCES for p in params):
        return lambda: do_upgrade(set(params))
    if action == "clean" and params and all(p in CLEAN_ITEMS for p in params):
        return lambda: do_clean(set(params))
    if action == "maintain" and not params:
        return lambda: do_upgrade(set(UPGRADE_SOURCES)) | do_clean({"pkgcache", "journal"})
    if action == "restart-unit" and len(params) == 1 and UNIT_RX.fullmatch(params[0]) and len(params[0]) < 200:
        return lambda: do_restart_unit(params[0])
    if action == "smart" and not params:
        return do_smart
    if action == "enable-ufw" and not params:
        return do_enable_ufw
    if action == "enable-firewalld" and not params:
        return lambda: do_enable_unit("firewalld.service")
    if action == "enable-fstrim" and not params:
        return lambda: do_enable_unit("fstrim.timer")
    return None


def main(argv):
    func = resolve(argv)
    if func is None:
        print("PCT-STEP rejected", flush=True)
        return 2
    if os.geteuid() != 0:
        print("PCT-STEP not-root", flush=True)
        return 3
    os.environ.clear()
    os.environ.update(env())
    return func()


if __name__ == "__main__":
    start = time.time()
    code = main(sys.argv[1:])
    print("PCT-STEP done %d %.0f" % (code, time.time() - start), flush=True)
    sys.exit(code)
