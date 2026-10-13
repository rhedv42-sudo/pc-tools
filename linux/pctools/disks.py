"""Datenträger: Übersicht, Dateisysteme, TRIM und SMART (über den Helfer, nur lesend)."""
import threading
import time

from . import privileged
from .i18n import t
from .sysinfo import disks as df_disks, lsblk
from .util import read_text, run, which

_smart = {"time": 0, "data": None}
_smart_lock = threading.Lock()


def mount_options():
    """Einhängeoptionen aus /proc/mounts je Einhängepunkt."""
    opts = {}
    for line in read_text("/proc/mounts").splitlines():
        parts = line.split()
        if len(parts) >= 4:
            mount = parts[1].replace("\\040", " ")
            opts[mount] = {"fstype": parts[2], "options": parts[3]}
    return opts


def fs_notes(fstype, options):
    notes = []
    o = options.split(",")
    if fstype == "btrfs":
        comp = [x for x in o if x.startswith(("compress=", "compress-force="))]
        notes.append(t("Btrfs: Komprimierung {0}", comp[0].split("=", 1)[1] if comp else t("aus")))
        if "ssd" in o:
            notes.append(t("SSD-Modus aktiv"))
    if fstype in ("ext4", "xfs", "btrfs"):
        if "discard" in o or any(x.startswith("discard=") for x in o):
            notes.append(t("Laufendes TRIM (discard) aktiv"))
        if "noatime" in o:
            notes.append("noatime")
    if "ro" in o:
        notes.append(t("nur lesbar eingehängt"))
    return notes


def trim_status():
    if not which("systemctl"):
        return {"available": False}
    en = run(["systemctl", "is-enabled", "fstrim.timer"], timeout=10)
    act = run(["systemctl", "is-active", "fstrim.timer"], timeout=10)
    return {"available": en.out.strip() not in ("", "not-found") or act.out.strip() == "active",
            "enabled": en.out.strip() == "enabled", "active": act.out.strip() == "active"}


def overview():
    opts = mount_options()
    rows = df_disks()
    for r in rows:
        o = opts.get(r["mount"], {})
        r["notes"] = fs_notes(r["fstype"], o.get("options", ""))
    devices = lsblk()
    return {"filesystems": rows,
            "devices": [d for d in (devices or []) if d.get("type") not in ("loop",)] if devices is not None else None,
            "trim": trim_status(), "smartctl": bool(which("smartctl")), "smart": smart_cached()}


def smart_cached():
    with _smart_lock:
        return _smart["data"]


def smart_job(job):
    """SMART-Status aller Laufwerke lesen (Root-Helfer, nur lesend)."""
    rc, res = privileged.run_helper(job, "smart", [], timeout=600)
    if res is not None:
        with _smart_lock:
            _smart["data"] = dict(res, time=int(time.time()))
        for d in res.get("disks", []):
            state = t("in Ordnung") if d.get("passed") else (t("WARNUNG") if d.get("passed") is False else t("nicht unterstützt"))
            job.log("%s %s: %s %s" % (d["device"], d.get("model", ""), state, ", ".join(d.get("warnings", []))))
    return {"smart": res, "error": rc != 0}
