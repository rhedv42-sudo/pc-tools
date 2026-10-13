"""Netzwerk-Diagnose und Netzwerk-Dokumentation (Scan nur im eigenen Subnetz)."""
import concurrent.futures as cf
import html
import ipaddress
import json
import re
import socket
import struct
import time

from . import __version__, oui
from .i18n import t
from .util import read_text, run, which

SCAN_PORTS = [21, 22, 23, 25, 53, 80, 139, 143, 443, 445, 515, 548, 554, 631, 1883, 3306, 3389, 5000,
              5001, 5432, 5900, 6379, 8000, 8008, 8009, 8080, 8123, 8443, 9100, 27017, 32400, 62078]
PORT_LABELS = {21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 80: "HTTP", 139: "NetBIOS",
               143: "IMAP", 443: "HTTPS", 445: "SMB", 515: "LPD", 548: "AFP", 554: "RTSP", 631: "IPP",
               1883: "MQTT", 3306: "MySQL", 3389: "RDP", 5000: "UPnP/NAS", 5001: "NAS-HTTPS",
               5432: "PostgreSQL", 5900: "VNC", 6379: "Redis", 8000: "HTTP-Alt", 8008: "Cast",
               8009: "Cast", 8080: "HTTP-Alt", 8123: "Home Assistant", 8443: "HTTPS-Alt",
               9100: "RAW-Druck", 27017: "MongoDB", 32400: "Plex", 62078: "iOS-Sync"}
NETWORK_VENDORS = ("AVM", "TP-Link", "Ubiquiti", "Netgear", "MikroTik", "Zyxel", "D-Link", "Linksys",
                   "Cisco", "Aruba", "Ruckus", "Fortinet", "Arcadyan", "Sagemcom", "Tenda", "Huawei")


# ------------------------------------------------------------------ Parser
def parse_ping(text):
    """'ping'-Ausgabe -> {received, sent, avg_ms}"""
    res = {"sent": 0, "received": 0, "avg_ms": None}
    m = re.search(r"(\d+) packets transmitted, (\d+) (?:packets )?received", text or "")
    if m:
        res["sent"], res["received"] = int(m.group(1)), int(m.group(2))
    m = re.search(r"= [\d.]+/([\d.]+)/", text or "")
    if m:
        res["avg_ms"] = float(m.group(1))
    return res


def parse_ip_neigh_json(text):
    """'ip -j neigh' -> {ip: mac} (nur Einträge mit MAC, ohne FAILED/INCOMPLETE)."""
    try:
        data = json.loads(text or "[]")
    except ValueError:
        return {}
    res = {}
    for e in data:
        state = e.get("state") or []
        if e.get("lladdr") and not set(state) & {"FAILED", "INCOMPLETE"}:
            res[e.get("dst")] = e["lladdr"].lower()
    return res


def parse_proc_arp(text):
    """/proc/net/arp -> {ip: mac}"""
    res = {}
    for line in (text or "").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 4 and parts[3] != "00:00:00:00:00:00" and parts[2] != "0x0":
            res[parts[0]] = parts[3].lower()
    return res


def split_nmcli(line):
    """nmcli -t trennt mit ':' und maskiert ':' im Inhalt als '\\:'."""
    return [p.replace("\\:", ":") for p in re.split(r"(?<!\\):", line)]


# ------------------------------------------------------------------ Schnittstellen
def interfaces():
    r = run(["ip", "-j", "addr", "show"], timeout=10)
    res = []
    if r.ok and r.out.strip().startswith("["):
        try:
            for i in json.loads(r.out):
                if i.get("ifname") == "lo":
                    continue
                addrs = [{"family": a.get("family"), "addr": a.get("local"), "prefix": a.get("prefixlen")}
                         for a in i.get("addr_info", []) if a.get("local")]
                res.append({"name": i.get("ifname"), "state": i.get("operstate", ""),
                            "mac": i.get("address", ""), "addrs": addrs})
            return res
        except ValueError:
            pass
    return interfaces_fallback()


def _ioctl_addr(ifname, request):
    """IPv4-Adresse/Netzmaske per ioctl (wenn 'ip' fehlt)."""
    import fcntl
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        data = fcntl.ioctl(s.fileno(), request, struct.pack("256s", ifname[:15].encode()))
        return socket.inet_ntoa(data[20:24])
    except OSError:
        return None
    finally:
        s.close()


def interfaces_fallback():
    """Schnittstellen aus /sys/class/net (ohne iproute2)."""
    import os
    res = []
    base = "/sys/class/net"
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if name == "lo":
            continue
        addrs = []
        ip = _ioctl_addr(name, 0x8915)          # SIOCGIFADDR
        mask = _ioctl_addr(name, 0x891B)        # SIOCGIFNETMASK
        if ip and mask:
            prefix = ipaddress.ip_network("0.0.0.0/%s" % mask).prefixlen
            addrs.append({"family": "inet", "addr": ip, "prefix": prefix})
        res.append({"name": name, "state": read_text("%s/%s/operstate" % (base, name)).strip().upper(),
                    "mac": read_text("%s/%s/address" % (base, name)).strip(), "addrs": addrs})
    return res


def default_route():
    r = run(["ip", "-j", "route", "show", "default"], timeout=10)
    if r.ok:
        try:
            routes = json.loads(r.out)
            if routes:
                return {"gateway": routes[0].get("gateway"), "dev": routes[0].get("dev")}
        except ValueError:
            pass
    # Fallback: /proc/net/route (Gateway hexadezimal, little endian)
    for line in read_text("/proc/net/route").splitlines()[1:]:
        p = line.split()
        if len(p) > 2 and p[1] == "00000000":
            gw = socket.inet_ntoa(struct.pack("<L", int(p[2], 16)))
            return {"gateway": gw, "dev": p[0]}
    return {"gateway": None, "dev": None}


def local_network():
    """IPv4-Adresse und Netz der Schnittstelle mit der Standardroute."""
    route = default_route()
    for i in interfaces():
        if route["dev"] and i["name"] != route["dev"]:
            continue
        for a in i["addrs"]:
            if a["family"] == "inet":
                iface = ipaddress.ip_interface("%s/%s" % (a["addr"], a["prefix"]))
                return {"ip": a["addr"], "prefix": a["prefix"], "iface": i["name"], "mac": i["mac"],
                        "network": str(iface.network), "gateway": route["gateway"]}
    return None


def ping(host, count=1, timeout=3):
    if not which("ping"):
        return None
    r = run(["ping", "-n", "-c", str(count), "-W", "1", host], timeout=timeout + count)
    return parse_ping(r.out)


def tcp_check(host, port, timeout=3.0):
    start = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return round((time.time() - start) * 1000)
    except OSError:
        return None


def dns_test(names=("example.org", "wikipedia.org")):
    res = []
    with cf.ThreadPoolExecutor(max_workers=len(names)) as ex:
        futs = {ex.submit(socket.getaddrinfo, n, 443, 0, socket.SOCK_STREAM): n for n in names}
        for f, n in futs.items():
            start = time.time()
            try:
                info = f.result(timeout=6)
                res.append({"name": n, "ok": True, "addr": info[0][4][0], "ms": round((time.time() - start) * 1000)})
            except Exception:
                res.append({"name": n, "ok": False, "addr": "", "ms": None})
    return res


def dns_servers():
    servers = re.findall(r"^\s*nameserver\s+(\S+)", read_text("/etc/resolv.conf"), re.M)
    if servers == ["127.0.0.53"] and which("resolvectl"):
        r = run(["resolvectl", "dns"], timeout=10)
        real = re.findall(r"([0-9a-fA-F:.]{7,})", r.out)
        if real:
            return ["127.0.0.53 (systemd-resolved)"] + sorted(set(real))
    return servers


def wifi():
    if not which("nmcli"):
        return None
    r = run(["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,CHAN,RATE,SECURITY", "dev", "wifi"], timeout=15)
    for line in r.out.splitlines():
        p = split_nmcli(line)
        if p and p[0] == "yes" and len(p) >= 6:
            return {"ssid": p[1], "signal": int(p[2]) if p[2].isdigit() else None, "channel": p[3],
                    "rate": p[4], "security": p[5] or t("offen")}
    return {}


def diagnose():
    route = default_route()
    gw = route.get("gateway")
    checks = []
    gw_ping = ping(gw, count=3, timeout=5) if gw else None
    checks.append({"id": "gateway", "title": t("Router erreichbar ({0})", gw or "-"),
                   "ok": bool(gw_ping and gw_ping["received"]),
                   "detail": (t("{0} von {1} Antworten, Ø {2} ms", gw_ping["received"], gw_ping["sent"], gw_ping["avg_ms"])
                              if gw_ping else (t("Kein Standard-Gateway") if not gw else t("ping nicht verfügbar")))})
    dns = dns_test()
    checks.append({"id": "dns", "title": t("Namensauflösung (DNS)"), "ok": all(d["ok"] for d in dns),
                   "detail": ", ".join("%s: %s" % (d["name"], ("%s ms" % d["ms"]) if d["ok"] else t("Fehler")) for d in dns)})
    for host in ("1.1.1.1", "9.9.9.9"):
        ms = tcp_check(host, 443)
        checks.append({"id": "inet-" + host, "title": t("Internet: {0} (TCP 443)", host), "ok": ms is not None,
                       "detail": ("%d ms" % ms) if ms is not None else t("keine Verbindung")})
    return {"interfaces": interfaces(), "route": route, "dns_servers": dns_servers(), "checks": checks,
            "wifi": wifi()}


# ------------------------------------------------------------------ Scan
def neighbours():
    r = run(["ip", "-j", "neigh"], timeout=10)
    if r.ok:
        res = parse_ip_neigh_json(r.out)
        if res:
            return res
    return parse_proc_arp(read_text("/proc/net/arp"))


def smb1_enabled(host, timeout=2.0):
    """Schickt eine SMB1-Negotiate-Anfrage (nur Dialekt 'NT LM 0.12'). True = SMB1 aktiv."""
    hdr = (b"\xffSMB" + b"\x72" + b"\x00" * 4 + b"\x18" + b"\x53\xc8" + b"\x00" * 2 + b"\x00" * 8 +
           b"\x00" * 2 + b"\xff\xff" + b"\xfe\xff" + b"\x00" * 2 + b"\x00" * 2)
    dialects = b"\x02NT LM 0.12\x00"
    payload = hdr + b"\x00" + struct.pack("<H", len(dialects)) + dialects
    packet = b"\x00" + struct.pack(">I", len(payload))[1:] + payload
    try:
        with socket.create_connection((host, 445), timeout=timeout) as s:
            s.settimeout(timeout)
            s.sendall(packet)
            resp = s.recv(256)
    except OSError:
        return False
    return len(resp) >= 13 and resp[4:8] == b"\xffSMB" and resp[8] == 0x72 and resp[9:13] == b"\x00" * 4


def probe(host, port, timeout=0.6):
    """'open', 'closed' (Gerät antwortet mit RST) oder None (keine Antwort)."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return "open"
    except ConnectionRefusedError:
        return "closed"
    except OSError:
        return None


def guess_type(ports, vendor, is_gateway=False, is_self=False, random_mac=False):
    p = set(ports)
    v = vendor or ""
    if is_self:
        return t("Dieser Computer")
    if is_gateway:
        return t("Router / Gateway")
    if "virtuell" in v:
        return t("Virtuelle Maschine")
    if p & {9100, 631, 515} or any(x in v for x in ("Brother", "Canon", "Epson", "Lexmark", "Kyocera", "Xerox", "Ricoh")):
        return t("Drucker")
    if 554 in p or any(x in v for x in ("Hikvision", "Dahua", "Reolink")):
        return t("Kamera")
    if any(x in v for x in ("Yealink", "snom", "Polycom", "Grandstream")):
        return t("IP-Telefon")
    if any(x in v for x in ("Synology", "QNAP", "Western Digital", "Buffalo")) or p & {5000, 5001} and p & {139, 445}:
        return t("NAS / Netzwerkspeicher")
    if 8123 in p:
        return t("Home Assistant")
    if p & {8008, 8009} or "Roku" in v:
        return t("Smart-TV / Streaming")
    if "Sonos" in v or "Denon" in v or "Yamaha" in v:
        return t("Lautsprecher / Audio")
    if "Nintendo" in v or "PlayStation" in v:
        return t("Spielkonsole")
    if 62078 in p or v == "Apple":
        return t("Apple-Gerät (iPhone, iPad oder Mac)")
    if "Raspberry" in v:
        return "Raspberry Pi"
    if "Espressif" in v or "Hue" in v or "Homematic" in v or "Netatmo" in v or 1883 in p:
        return t("Smart-Home-Gerät (IoT)")
    if any(x in v for x in NETWORK_VENDORS):
        return t("Netzwerkgerät (Router, WLAN, Switch)")
    if 3389 in p:
        return t("Windows-PC")
    if p & {139, 445}:
        return t("Windows-PC oder Dateiserver")
    if 22 in p:
        return t("Linux/Unix-Gerät")
    if random_mac:
        return t("vermutlich Smartphone/Tablet (zufällige MAC)")
    return t("Unbekannt")


def host_findings(h):
    p = set(h["ports"])
    f = []
    if 23 in p:
        f.append({"severity": "crit", "text": t("Telnet offen – überträgt Kennwörter unverschlüsselt. Abschalten oder durch SSH ersetzen.")})
    if 21 in p:
        f.append({"severity": "warn", "text": t("FTP offen – unverschlüsselt. Besser SFTP/FTPS verwenden.")})
    if h.get("smb1"):
        f.append({"severity": "crit", "text": t("SMB1 aktiv – veraltet und unsicher (WannaCry). SMB1 am Gerät abschalten.")})
    if 5900 in p:
        f.append({"severity": "warn", "text": t("VNC offen – Fernsteuerung oft ohne starke Verschlüsselung.")})
    if 3389 in p:
        f.append({"severity": "info", "text": t("Remotedesktop (RDP) offen – nur im eigenen Netz nutzen, nie ins Internet freigeben.")})
    for port in (3306, 5432, 6379, 27017):
        if port in p:
            f.append({"severity": "warn", "text": t("Datenbank-Port {0} ({1}) im Netz erreichbar.", port, PORT_LABELS[port])})
    if 1883 in p:
        f.append({"severity": "info", "text": t("MQTT ohne Verschlüsselung (1883) – Zugangsdaten prüfen.")})
    if 80 in p and 443 not in p and (h.get("is_gateway") or "Netzwerk" in h.get("type", "")):
        f.append({"severity": "info", "text": t("Verwaltungsoberfläche nur über HTTP (unverschlüsselt).")})
    return f


def scan(job):
    """Scannt das eigene Subnetz (max. /24) mit begrenzter Parallelität."""
    net = local_network()
    if not net:
        job.log(t("Keine aktive IPv4-Verbindung gefunden."))
        return {"error": True}
    network = ipaddress.ip_network(net["network"], strict=False)
    if network.prefixlen < 24:
        network = ipaddress.ip_network("%s/24" % net["ip"], strict=False)
    if not network.is_private:
        job.log(t("Das Netz {0} ist kein privates Netz – Scan abgebrochen.", network))
        return {"error": True}
    hosts = [str(h) for h in network.hosts()][:254]
    job.log(t("Scanne {0} ({1} Adressen) über {2} …", network, len(hosts), net["iface"]))
    started = time.time()
    alive = set()

    # 1) Ping-Durchlauf (füllt nebenbei den ARP-Cache)
    if which("ping"):
        done = 0
        with cf.ThreadPoolExecutor(max_workers=64) as ex:
            for host, res in zip(hosts, ex.map(lambda h: ping(h, 1, 2), hosts)):
                done += 1
                if res and res["received"]:
                    alive.add(host)
                if done % 32 == 0:
                    job.progress = int(done * 30 / len(hosts))
        job.log(t("Ping: {0} Geräte antworten.", len(alive)))
    else:
        job.log(t("ping nicht verfügbar – nutze nur TCP-Prüfung."))

    # 2) Schnelle TCP-Prüfung auf typischen Ports (findet Geräte, die Ping blocken)
    quick = [80, 443, 445, 22, 62078]
    with cf.ThreadPoolExecutor(max_workers=128) as ex:
        pairs = [(h, p) for h in hosts if h not in alive for p in quick]
        for (h, p), res in zip(pairs, ex.map(lambda hp: probe(hp[0], hp[1], 0.4), pairs)):
            if res:
                alive.add(h)
    job.progress = 45

    # 3) ARP/Nachbarn
    neigh = neighbours()
    for ip in neigh:
        try:
            if ipaddress.ip_address(ip) in network:
                alive.add(ip)
        except ValueError:
            pass
    alive.add(net["ip"])
    if net["gateway"]:
        alive.add(net["gateway"])
    job.log(t("{0} Geräte gefunden, prüfe Dienste …", len(alive)))

    # 4) Portscan nur auf gefundenen Geräten
    ports = {h: [] for h in alive}
    pairs = [(h, p) for h in sorted(alive) for p in SCAN_PORTS]
    with cf.ThreadPoolExecutor(max_workers=100) as ex:
        for i, ((h, p), res) in enumerate(zip(pairs, ex.map(lambda hp: probe(hp[0], hp[1], 0.6), pairs))):
            if res == "open":
                ports[h].append(p)
            if i % 100 == 0:
                job.progress = 45 + int(i * 40 / max(1, len(pairs)))

    # 5) Namen (Reverse-DNS) und SMB1
    def rdns(ip):
        try:
            return socket.gethostbyaddr(ip)[0]
        except OSError:
            return ""
    names = {}
    with cf.ThreadPoolExecutor(max_workers=32) as ex:
        futs = {ex.submit(rdns, h): h for h in alive}
        try:
            for f in cf.as_completed(futs, timeout=20):
                names[futs[f]] = f.result()
        except cf.TimeoutError:
            pass
        smb_hosts = [h for h in alive if 445 in ports[h]]
        smb = dict(zip(smb_hosts, ex.map(smb1_enabled, smb_hosts)))
    job.progress = 95

    devices = []
    for h in sorted(alive, key=lambda x: ipaddress.ip_address(x)):
        mac = net["mac"] if h == net["ip"] else neigh.get(h, "")
        vendor = oui.lookup(mac) if mac else ""
        rnd = oui.is_random(mac) if mac else False
        d = {"ip": h, "mac": mac, "vendor": vendor or (t("zufällige oder lokal vergebene MAC") if rnd else ""),
             "hostname": names.get(h, ""), "ports": sorted(ports.get(h, [])), "smb1": smb.get(h, False),
             "is_gateway": h == net["gateway"], "is_self": h == net["ip"]}
        d["type"] = guess_type(d["ports"], vendor, d["is_gateway"], d["is_self"], rnd)
        d["findings"] = host_findings(d)
        devices.append(d)
    dur = round(time.time() - started)
    job.log(t("Fertig: {0} Geräte in {1} Sekunden.", len(devices), dur))
    return {"network": str(network), "iface": net["iface"], "gateway": net["gateway"], "own_ip": net["ip"],
            "devices": devices, "time": int(time.time()), "duration": dur}


def report_html(result):
    """Eigenständige, druckbare HTML-Seite (als PDF speichern über den Druckdialog)."""
    e = lambda s: html.escape(str(s if s is not None else ""))
    rows = []
    for d in result.get("devices", []):
        ports = ", ".join("%d %s" % (p, PORT_LABELS.get(p, "")) for p in d["ports"]) or "–"
        finds = "".join('<li class="%s">%s</li>' % (e(f["severity"]), e(f["text"])) for f in d["findings"])
        rows.append("<tr><td>%s</td><td>%s<br><small>%s</small></td><td>%s<br><small>%s</small></td><td>%s</td><td>%s</td><td><ul>%s</ul></td></tr>" % (
            e(d["ip"]), e(d["hostname"] or "–"), e(d["type"]), e(d["mac"] or "–"), e(d["vendor"]), e(ports),
            e(t("Ja") if d["smb1"] else ""), finds))
    n_crit = sum(1 for d in result.get("devices", []) for f in d["findings"] if f["severity"] == "crit")
    n_warn = sum(1 for d in result.get("devices", []) for f in d["findings"] if f["severity"] == "warn")
    ts = time.strftime("%d.%m.%Y %H:%M", time.localtime(result.get("time", time.time())))
    return """<!doctype html><html lang="de"><head><meta charset="utf-8">
<title>%(title)s</title><style>
body{font:13px/1.45 system-ui,sans-serif;color:#1b1f24;margin:24px;background:#fff}
h1{font-size:20px;margin:0 0 4px;color:#2D7FF9}.meta{color:#555;margin-bottom:16px}
table{border-collapse:collapse;width:100%%}th,td{border-bottom:1px solid #ddd;padding:6px;text-align:left;vertical-align:top}
th{background:#f0f4fa}small{color:#666}ul{margin:0;padding-left:16px}li.crit{color:#b00020;font-weight:600}
li.warn{color:#9a5b00}.sum{display:flex;gap:16px;margin:12px 0}.sum div{border:1px solid #ddd;border-radius:8px;padding:8px 12px}
.btn{background:#2D7FF9;color:#fff;border:0;border-radius:6px;padding:8px 14px;cursor:pointer;font-size:13px}
@media print{.btn{display:none}body{margin:0}tr{page-break-inside:avoid}}
</style></head><body>
<button class="btn" onclick="window.print()">%(print)s</button>
<h1>%(title)s</h1><div class="meta">%(net)s &middot; %(date)s &middot; PC-Tools für Linux %(ver)s</div>
<div class="sum"><div><b>%(ndev)d</b> %(devices)s</div><div><b>%(ncrit)d</b> %(crit)s</div><div><b>%(nwarn)d</b> %(warn)s</div></div>
<table><thead><tr><th>IP</th><th>%(h_name)s</th><th>MAC / %(h_vendor)s</th><th>%(h_ports)s</th><th>SMB1</th><th>%(h_find)s</th></tr></thead>
<tbody>%(rows)s</tbody></table>
<p class="meta">%(note)s</p></body></html>""" % {
        "title": e(t("Netzwerk-Dokumentation")), "print": e(t("Drucken / als PDF speichern")),
        "net": e(t("Netz {0}, Gateway {1}", result.get("network"), result.get("gateway") or "–")),
        "date": e(ts), "ver": e(__version__), "ndev": len(result.get("devices", [])),
        "devices": e(t("Geräte")), "ncrit": n_crit, "crit": e(t("kritisch")), "nwarn": n_warn,
        "warn": e(t("Warnungen")), "h_name": e(t("Name / Typ")), "h_vendor": e(t("Hersteller")),
        "h_ports": e(t("Offene Ports")), "h_find": e(t("Hinweise")), "rows": "".join(rows),
        "note": e(t("Erstellt mit PC-Tools. Nur im eigenen Netzwerk verwenden. Gerätetypen sind geschätzt."))}
