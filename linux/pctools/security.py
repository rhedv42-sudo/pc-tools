"""Sicherheit: Firewall, automatische Updates, SSH, offene Ports, Secure Boot, Verschlüsselung."""
import glob
import os
import re

from . import updates
from .i18n import t
from .sysinfo import detect_package_manager, parse_lsblk_json
from .util import read_text, run, which

PORT_NAMES = {21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 67: "DHCP", 80: "HTTP",
              111: "rpcbind", 139: "NetBIOS/SMB", 443: "HTTPS", 445: "SMB", 631: "CUPS (Drucken)",
              1716: "KDE Connect", 3306: "MySQL/MariaDB", 3389: "RDP", 5353: "mDNS (Avahi)",
              5432: "PostgreSQL", 5900: "VNC", 6379: "Redis", 8080: "HTTP-Alt", 27017: "MongoDB"}


# ------------------------------------------------------------------ Parser
def parse_ss(text):
    """'ss -tulpn' -> [{proto, addr, port, process, public}]"""
    res = []
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0] in ("Netid", "State"):
            continue
        proto, state = parts[0], parts[1]
        if proto not in ("tcp", "udp", "tcp6", "udp6"):
            continue
        if proto.startswith("tcp") and state != "LISTEN":
            continue
        if proto.startswith("udp") and state not in ("UNCONN", "LISTEN"):
            continue
        local = parts[4]
        addr, _, port = local.rpartition(":")
        if not port.isdigit():
            continue
        addr = addr.strip("[]").split("%")[0]
        proc = ""
        m = re.search(r'users:\(\("([^"]+)"', line)
        if m:
            proc = m.group(1)
        loopback = addr.startswith("127.") or addr == "::1"
        res.append({"proto": proto[:3], "addr": addr or "*", "port": int(port), "process": proc,
                    "public": not loopback, "name": PORT_NAMES.get(int(port), "")})
    # Doppelte (IPv4/IPv6) zusammenfassen
    seen, out = set(), []
    for r in res:
        key = (r["proto"], r["port"], r["public"], r["process"])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return sorted(out, key=lambda r: (not r["public"], r["port"]))


def parse_sshd_config(texts):
    """Erste Angabe gewinnt (wie bei sshd). Match-Blöcke werden ignoriert."""
    conf = {}
    for text in texts:
        for line in (text or "").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = s.split(None, 1)
            key = parts[0].lower()
            if key == "match":
                break
            if len(parts) == 2 and key not in conf:
                conf[key] = parts[1].strip().strip('"')
    return conf


def sshd_texts(path="/etc/ssh/sshd_config"):
    """Liest sshd_config samt Include-Dateien in der Reihenfolge, wie sshd sie liest."""
    texts = []
    main = read_text(path)
    for line in main.splitlines():
        s = line.strip()
        if s.lower().startswith("include "):
            for pat in s.split()[1:]:
                if not pat.startswith("/"):
                    pat = "/etc/ssh/" + pat
                for f in sorted(glob.glob(pat)):
                    texts.append(read_text(f))
    texts.append(main)
    return texts


def secure_boot():
    """Secure-Boot-Status: mokutil oder direkt die EFI-Variable."""
    if not os.path.isdir("/sys/firmware/efi"):
        return "legacy"
    if which("mokutil"):
        r = run(["mokutil", "--sb-state"], timeout=10)
        txt = (r.out + r.err).lower()
        if "enabled" in txt:
            return "on"
        if "disabled" in txt:
            return "off"
    for f in glob.glob("/sys/firmware/efi/efivars/SecureBoot-*"):
        try:
            with open(f, "rb") as fh:
                data = fh.read()
            return "on" if data and data[-1] == 1 else "off"
        except OSError:
            pass
    return "unknown"


def encryption():
    """Ist das Root-Dateisystem verschlüsselt (LUKS/dm-crypt)?"""
    r = run(["lsblk", "-J", "-o", "NAME,TYPE,FSTYPE,MOUNTPOINT"], timeout=15)
    if not r.ok:
        return {"available": False}
    devs = parse_lsblk_json(r.out)
    by_name = {d["name"]: d for d in devs}
    any_luks = any(d.get("fstype") == "crypto_LUKS" or d.get("type") == "crypt" for d in devs)
    root_enc = False
    for d in devs:
        if d.get("mountpoint") == "/":
            cur = d
            while cur:
                if cur.get("type") == "crypt" or cur.get("fstype") == "crypto_LUKS":
                    root_enc = True
                    break
                cur = by_name.get(cur.get("parent"))
    return {"available": True, "any": any_luks, "root": root_enc}


def firewall():
    def active(unit):
        return run(["systemctl", "is-active", unit], timeout=10).out.strip() == "active"
    res = {"ufw_installed": bool(which("ufw")), "firewalld_installed": bool(which("firewall-cmd")),
           "active": None}
    if res["ufw_installed"]:
        conf = read_text("/etc/ufw/ufw.conf")
        if re.search(r"^\s*ENABLED\s*=\s*yes", conf, re.M) and active("ufw"):
            res["active"] = "ufw"
    if not res["active"] and res["firewalld_installed"] and active("firewalld"):
        res["active"] = "firewalld"
    if not res["active"] and which("nft") and active("nftables"):
        res["active"] = "nftables"
    return res


def auto_updates(pm):
    if pm == "apt":
        installed = run(["dpkg-query", "-W", "-f=${Status}", "unattended-upgrades"], timeout=10).out
        conf = " ".join(read_text(f) for f in glob.glob("/etc/apt/apt.conf.d/*"))
        on = "install ok installed" in installed and re.search(r'Unattended-Upgrade\s+"1"', conf) is not None
        return {"tool": "unattended-upgrades", "enabled": on}
    if pm == "dnf":
        for timer in ("dnf-automatic-install.timer", "dnf-automatic.timer", "dnf5-automatic.timer"):
            if run(["systemctl", "is-enabled", timer], timeout=10).out.strip() == "enabled":
                return {"tool": "dnf-automatic", "enabled": True}
        return {"tool": "dnf-automatic", "enabled": False}
    if pm == "zypper":
        return {"tool": "zypper", "enabled": None}
    return {"tool": pm or "", "enabled": None}


def ssh_status():
    if not os.path.exists("/etc/ssh/sshd_config"):
        return None
    active = any(run(["systemctl", "is-active", u], timeout=10).out.strip() == "active"
                 for u in ("ssh", "sshd"))
    conf = parse_sshd_config(sshd_texts())
    return {"active": active, "permit_root": conf.get("permitrootlogin", "prohibit-password"),
            "password_auth": conf.get("passwordauthentication", "yes")}


def check():
    pm = detect_package_manager()
    findings = []

    def add(sev, title, detail, fix="", action=None):
        findings.append({"severity": sev, "title": title, "detail": detail, "fix": fix, "action": action})

    fw = firewall()
    if fw["active"]:
        add("ok", t("Firewall aktiv ({0})", fw["active"]), t("Eingehende Verbindungen werden gefiltert."))
    elif fw["ufw_installed"]:
        add("warn", t("Firewall ist ausgeschaltet"), t("ufw ist installiert, aber nicht aktiv. Ohne Firewall sind alle lauschenden Dienste aus dem Netzwerk erreichbar."),
            t("ufw einschalten (SSH bleibt erlaubt, falls aktiv)."), "enable-ufw")
    elif fw["firewalld_installed"]:
        add("warn", t("Firewall ist ausgeschaltet"), t("firewalld ist installiert, aber nicht aktiv."),
            t("firewalld einschalten."), "enable-firewalld")
    else:
        add("warn", t("Keine Firewall gefunden"), t("Weder ufw noch firewalld sind installiert."),
            t("Paket 'ufw' (Debian/Ubuntu/Arch) oder 'firewalld' (Fedora/openSUSE) installieren."))

    au = auto_updates(pm)
    if au["enabled"] is True:
        add("ok", t("Automatische Sicherheitsupdates aktiv"), au["tool"])
    elif au["enabled"] is False:
        fix = (t("Im Terminal: sudo apt install unattended-upgrades && sudo dpkg-reconfigure -plow unattended-upgrades")
               if pm == "apt" else t("Im Terminal: sudo dnf install dnf-automatic && sudo systemctl enable --now dnf-automatic-install.timer"))
        add("info", t("Automatische Sicherheitsupdates aus"), t("Sicherheitslücken werden nur geschlossen, wenn du selbst aktualisierst."), fix)
    else:
        add("info", t("Automatische Updates: nicht geprüft"), t("Für diese Distribution gibt es kein Standardwerkzeug. Bitte regelmäßig die Seite Updates nutzen."))

    data = updates.cached() or updates.collect(online=False, include_apps=False)
    sec = data.get("security")
    if sec:
        add("warn", t("{0} Sicherheitsupdates ausstehend", sec), t("Diese Updates schließen bekannte Sicherheitslücken."),
            t("Auf der Seite Updates installieren."))
    elif sec == 0:
        add("ok", t("Keine Sicherheitsupdates ausstehend"), "")

    ssh = ssh_status()
    if ssh and ssh["active"]:
        if ssh["permit_root"].lower() == "yes":
            add("warn", t("SSH: Anmeldung als root erlaubt"), t("PermitRootLogin yes – Angreifer können direkt das root-Konto angreifen."),
                t("In /etc/ssh/sshd_config 'PermitRootLogin no' setzen und sshd neu starten."))
        if ssh["password_auth"].lower() == "yes":
            add("info", t("SSH: Anmeldung mit Kennwort erlaubt"), t("Sicherer sind SSH-Schlüssel. Kennwörter können erraten werden."),
                t("Schlüssel einrichten, dann 'PasswordAuthentication no' setzen."))
        if ssh["permit_root"].lower() != "yes" and ssh["password_auth"].lower() != "yes":
            add("ok", t("SSH-Server sicher eingestellt"), "")
    elif ssh:
        add("ok", t("SSH-Server installiert, aber nicht aktiv"), "")

    sb = secure_boot()
    if sb == "on":
        add("ok", t("Secure Boot aktiv"), "")
    elif sb == "off":
        add("info", t("Secure Boot ist aus"), t("Secure Boot schützt den Startvorgang vor Manipulation. Einschalten im UEFI/BIOS – nur, wenn deine Distribution es unterstützt."))
    elif sb == "legacy":
        add("info", t("Klassischer BIOS-Start"), t("Das System startet ohne UEFI, Secure Boot ist nicht möglich."))

    enc = encryption()
    if enc.get("root"):
        add("ok", t("Systemlaufwerk verschlüsselt (LUKS)"), "")
    elif enc.get("available"):
        add("info", t("Systemlaufwerk nicht verschlüsselt"), t("Bei Diebstahl (v. a. Laptops) sind alle Daten lesbar. Verschlüsselung lässt sich meist nur bei einer Neuinstallation einschalten."))

    r = run(["ss", "-tulpn"], timeout=15)
    ports = parse_ss(r.out) if r.ok else None
    if ports:
        risky = [p for p in ports if p["public"] and p["port"] in (21, 23, 139, 445, 3306, 5432, 5900, 6379, 27017)]
        for p in risky:
            add("warn", t("Port {0} ({1}) ist aus dem Netzwerk erreichbar", p["port"], p["name"]),
                t("Dienst: {0}. Nur offen lassen, wenn du ihn wirklich im Netzwerk brauchst.", p["process"] or t("unbekannt")))
    return {"findings": findings, "ports": ports, "firewall": fw, "ssh": ssh,
            "secure_boot": sb, "encryption": enc, "auto_updates": au}
