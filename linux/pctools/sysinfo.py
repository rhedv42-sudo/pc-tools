"""Systeminformationen: Distribution, Paketverwaltung, CPU, RAM, Datenträger."""
import json
import os
import platform
import shlex
import time

from .i18n import t
from .util import read_text, run, which

# Pseudo-Dateisysteme, die in der Übersicht nichts zu suchen haben
SKIP_FS = {"tmpfs", "devtmpfs", "squashfs", "overlay", "efivarfs", "proc", "sysfs",
           "devpts", "cgroup", "cgroup2", "ramfs", "fuse.portal", "fuse.gvfsd-fuse", "nsfs"}


# ------------------------------------------------------------------ Parser
def parse_os_release(text):
    """Liest /etc/os-release (KEY="Wert") in ein Dict."""
    info = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        try:
            parts = shlex.split(val)
            val = parts[0] if parts else ""
        except ValueError:
            val = val.strip("\"'")
        info[key.strip()] = val
    return info


def distro_family(osr):
    """Grobe Familie aus ID und ID_LIKE: debian, fedora, suse, arch oder unknown."""
    ids = [osr.get("ID", "").lower()] + osr.get("ID_LIKE", "").lower().split()
    for fam, keys in (("debian", ("debian", "ubuntu")), ("fedora", ("fedora", "rhel", "centos")),
                      ("suse", ("suse", "opensuse", "opensuse-leap", "opensuse-tumbleweed", "sles")),
                      ("arch", ("arch", "archlinux", "manjaro", "endeavouros"))):
        if any(i in keys for i in ids):
            return fam
    return "unknown"


def detect_package_manager(osr=None):
    """Bevorzugt die Paketverwaltung der Distribution, sonst die erste vorhandene."""
    osr = osr or parse_os_release(read_text("/etc/os-release"))
    pref = {"debian": "apt", "fedora": "dnf", "suse": "zypper", "arch": "pacman"}.get(distro_family(osr))
    if pref and which(pref if pref != "apt" else "apt-get"):
        return pref
    for pm, exe in (("apt", "apt-get"), ("dnf", "dnf"), ("zypper", "zypper"), ("pacman", "pacman")):
        if which(exe):
            return pm
    return None


def parse_df(text):
    """Ausgabe von 'df -P -B1 -T' -> Liste von Dicts (Bytes)."""
    rows = []
    lines = (text or "").splitlines()
    for line in lines[1:]:
        parts = line.split(None, 6)
        if len(parts) < 7:
            continue
        dev, fstype, size, used, avail, pct, mount = parts
        try:
            size, used, avail = int(size), int(used), int(avail)
        except ValueError:
            continue
        if fstype in SKIP_FS or size == 0:
            continue
        try:
            percent = int(pct.rstrip("%"))
        except ValueError:
            percent = round(used * 100.0 / size) if size else 0
        rows.append({"device": dev, "fstype": fstype, "size": size, "used": used,
                     "avail": avail, "percent": percent, "mount": mount})
    return rows


def parse_lsblk_json(text):
    """lsblk -J -> flache Liste aller Geräte mit 'parent' und 'depth'."""
    try:
        data = json.loads(text or "{}")
    except ValueError:
        return []
    out = []

    def walk(devs, parent, depth):
        for d in devs or []:
            item = {k: v for k, v in d.items() if k != "children"}
            item["parent"] = parent
            item["depth"] = depth
            out.append(item)
            walk(d.get("children"), d.get("name"), depth + 1)

    walk(data.get("blockdevices"), None, 0)
    return out


def parse_meminfo(text):
    mem = {}
    for line in (text or "").splitlines():
        k, _, v = line.partition(":")
        parts = v.split()
        if parts and parts[0].isdigit():
            mem[k.strip()] = int(parts[0]) * 1024
    return mem


# ------------------------------------------------------------------ Erhebung
def os_release():
    return parse_os_release(read_text("/etc/os-release") or read_text("/usr/lib/os-release"))


def cpu_info():
    model = ""
    for line in read_text("/proc/cpuinfo").splitlines():
        if line.lower().startswith(("model name", "hardware", "processor\t: arm")):
            model = line.split(":", 1)[1].strip()
            if model:
                break
    return {"model": model or platform.processor() or platform.machine(),
            "cores": os.cpu_count() or 0, "arch": platform.machine(),
            "load": list(os.getloadavg()) if hasattr(os, "getloadavg") else []}


def uptime_seconds():
    try:
        return int(float(read_text("/proc/uptime").split()[0]))
    except (IndexError, ValueError):
        return 0


def desktop_name():
    d = os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("DESKTOP_SESSION") or ""
    session = os.environ.get("XDG_SESSION_TYPE", "")
    if not d:
        return t("nicht erkannt")
    return d.replace(":", " / ") + (" (%s)" % session if session else "")


def disks():
    r = run(["df", "-P", "-B1", "-T"], timeout=15)
    if not r.out:
        return []
    seen = set()
    rows = []
    ro = set()
    for line in read_text("/proc/mounts").splitlines():
        parts = line.split()
        if len(parts) >= 4 and "ro" in parts[3].split(","):
            ro.add(parts[1].replace("\\040", " "))
    for row in parse_df(r.out):
        row["readonly"] = row["mount"] in ro
        # Gleiches Gerät mehrfach eingehängt (z. B. btrfs-Subvolumes): nur einmal zeigen
        key = (row["device"], row["size"])
        if key in seen or row["mount"].startswith(("/snap/", "/var/lib/docker", "/run/")):
            continue
        seen.add(key)
        rows.append(row)
    return rows


def lsblk():
    cols = "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL,ROTA,TRAN,RM"
    r = run(["lsblk", "-J", "-b", "-o", cols], timeout=15)
    if not r.ok:
        return None
    return parse_lsblk_json(r.out)


def overview():
    """Alles für die Übersichtsseite (schnell, ohne Netzwerkzugriffe)."""
    osr = os_release()
    mem = parse_meminfo(read_text("/proc/meminfo"))
    return {
        "distro": osr.get("PRETTY_NAME") or osr.get("NAME") or t("unbekannt"),
        "distro_id": osr.get("ID", ""),
        "family": distro_family(osr),
        "kernel": platform.release(),
        "cpu": cpu_info(),
        "mem_total": mem.get("MemTotal", 0),
        "mem_available": mem.get("MemAvailable", mem.get("MemFree", 0)),
        "swap_total": mem.get("SwapTotal", 0),
        "swap_free": mem.get("SwapFree", 0),
        "uptime": uptime_seconds(),
        "desktop": desktop_name(),
        "package_manager": detect_package_manager(osr) or t("nicht verfügbar"),
        "flatpak": bool(which("flatpak")),
        "snap": bool(which("snap")),
        "disks": disks(),
        "time": int(time.time()),
    }
