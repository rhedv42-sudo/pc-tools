"""Zustand: Punktzahl 0–100 mit Ampel und konkreten Befunden."""
from . import disks, security, services, sysinfo, updates
from .i18n import t
from .util import human_size

PENALTY = {"crit": 25, "warn": 10, "info": 3}


def compute_health(facts):
    """Reine Funktion (testbar): facts -> {score, light, findings}.

    facts: disks[], updates (int|None), security_updates (int|None), failed (int|None),
    firewall (bool|None), reboot (bool), smart (list|None), mem_total, mem_available,
    swap_total, swap_free
    """
    findings = []

    def add(sev, title, detail, page):
        findings.append({"severity": sev, "title": title, "detail": detail, "page": page})

    for d in facts.get("disks") or []:
        if d.get("readonly"):
            continue                      # schreibgeschützte Images (z. B. Snaps) sind immer "voll"
        if d.get("percent", 0) >= 95:
            add("crit", t("Datenträger {0} ist fast voll ({1}%)", d["mount"], d["percent"]),
                t("Nur noch {0} frei. Programme und Updates können fehlschlagen.", human_size(d.get("avail"))), "cleanup")
        elif d.get("percent", 0) >= 90:
            add("warn", t("Datenträger {0} ist zu {1}% belegt", d["mount"], d["percent"]),
                t("Noch {0} frei. Aufräumen schafft Platz.", human_size(d.get("avail"))), "cleanup")

    sec = facts.get("security_updates")
    upd = facts.get("updates")
    if sec:
        add("crit", t("{0} Sicherheitsupdates ausstehend", sec), t("Bitte bald installieren."), "updates")
    if upd:
        add("warn" if upd >= 10 else "info", t("{0} Updates verfügbar", upd), t("Updates bringen Fehlerkorrekturen und Sicherheit."), "updates")

    failed = facts.get("failed")
    if failed:
        add("warn", t("{0} Dienst(e) fehlgeschlagen", failed), t("Ein Systemdienst läuft nicht. Details auf der Seite Dienste."), "services")

    if facts.get("firewall") is False:
        add("warn", t("Keine aktive Firewall"), t("Dienste auf diesem Rechner sind aus dem Netzwerk erreichbar."), "security")

    if facts.get("reboot"):
        add("warn", t("Neustart erforderlich"), t("Updates (z. B. ein neuer Kernel) werden erst nach einem Neustart wirksam."), "updates")

    for s in facts.get("smart") or []:
        if s.get("passed") is False:
            add("crit", t("SMART-Warnung: {0}", s.get("device")), t("Das Laufwerk meldet einen Defekt. Sofort Daten sichern!"), "disks")
        elif s.get("warnings"):
            add("warn", t("SMART-Auffälligkeiten: {0}", s.get("device")), ", ".join(s["warnings"]), "disks")

    total, avail = facts.get("mem_total") or 0, facts.get("mem_available") or 0
    stotal, sfree = facts.get("swap_total") or 0, facts.get("swap_free") or 0
    if total and avail / total < 0.10 and stotal and (stotal - sfree) / stotal > 0.5:
        add("warn", t("Arbeitsspeicher knapp"), t("Weniger als 10% RAM frei und Auslagerung stark genutzt – das System wird langsam."), "overview")
    elif total and avail / total < 0.05:
        add("info", t("Arbeitsspeicher fast voll"), t("Programme schließen oder RAM aufrüsten."), "overview")

    score = 100
    for f in findings:
        score -= PENALTY.get(f["severity"], 0)
    score = max(0, min(100, score))
    light = "green" if score >= 80 else ("yellow" if score >= 50 else "red")
    order = {"crit": 0, "warn": 1, "info": 2}
    findings.sort(key=lambda f: order.get(f["severity"], 3))
    return {"score": score, "light": light, "findings": findings}


def gather(info=None):
    """Sammelt die Fakten (ohne Netzwerkzugriff und ohne Root) und berechnet den Zustand."""
    info = info or sysinfo.overview()
    upd = updates.cached() or updates.collect(online=False, include_apps=False)
    sys_failed = services.failed_units(False)
    usr_failed = services.failed_units(True)
    failed = None if sys_failed is None else len(sys_failed) + len(usr_failed or [])
    fw = security.firewall()
    smart = disks.smart_cached()
    facts = {
        "disks": info.get("disks"),
        "updates": len(upd["system"]) + len(upd.get("flatpak") or []) + len(upd.get("snap") or []),
        "security_updates": upd.get("security"),
        "failed": failed,
        "firewall": bool(fw["active"]),
        "reboot": upd.get("reboot_required"),
        "smart": smart.get("disks") if smart else None,
        "mem_total": info.get("mem_total"), "mem_available": info.get("mem_available"),
        "swap_total": info.get("swap_total"), "swap_free": info.get("swap_free"),
    }
    res = compute_health(facts)
    res["smart_checked"] = smart is not None
    return res
