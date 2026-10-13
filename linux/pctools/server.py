"""Lokaler Webserver (nur 127.0.0.1) mit Token-Schutz und JSON-API für die Oberfläche."""
import argparse
import hmac
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import (APP_NAME, GITHUB_URL, __version__, ai, autostart, cleanup, disks, health, i18n,
               jobs, network, privileged, security, services, sysinfo, updates)
from .i18n import t
from .util import run, which

WEB_DIR = Path(__file__).resolve().parent / "web"
STATIC = {"index.html": "text/html; charset=utf-8", "app.css": "text/css; charset=utf-8",
          "app.js": "application/javascript; charset=utf-8", "icon-256.png": "image/png",
          "icon-64.png": "image/png"}
IDLE_LIMIT = 2 * 3600          # Sekunden ohne Anfrage bis zum automatischen Beenden
BYE_GRACE = 20                 # Sekunden nach Schließen des Tabs (Neuladen kommt schneller zurück)
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")


class State:
    def __init__(self, token, port):
        self.token = token
        self.port = port
        self.last = time.time()
        self.bye = None
        self.last_scan = None
        self.httpd = None


STATE = None


# ------------------------------------------------------------------ Aufträge
def _job_updates_install(job, sources):
    sources = [s for s in sources if s in ("system", "flatpak", "snap")] or ["system"]
    if "flatpak" in sources and which("flatpak"):
        job.log(t("Flatpak-Apps des Benutzers werden aktualisiert …"))
        r = run(["flatpak", "update", "-y", "--noninteractive", "--user"], timeout=3600)
        for line in (r.out or "").strip().splitlines()[-15:]:
            job.log(line)
    rc, _ = privileged.run_helper(job, "upgrade", sources)
    updates.invalidate()
    return {"rc": rc, "error": rc != 0, "reboot": updates.reboot_required()}


def _job_updates_check(job, online):
    job.log(t("Suche nach Updates …"))
    data = updates.collect(online=online, include_apps=True)
    job.log(t("{0} Systempakete, {1} Flatpak, {2} Snap.", len(data["system"]),
              len(data["flatpak"] or []), len(data["snap"] or [])))
    return data


def _job_refresh(job):
    rc, _ = privileged.run_helper(job, "refresh")
    data = _job_updates_check(job, True) if rc == 0 else None
    return {"rc": rc, "error": rc != 0, "data": data}


def _job_maintain(job):
    job.log(t("Alles pflegen: Updates installieren und aufräumen."))
    if which("flatpak"):
        run(["flatpak", "update", "-y", "--noninteractive", "--user"], timeout=3600)
    cleanup.clean(job, ["thumbnails"])
    rc, _ = privileged.run_helper(job, "maintain")
    updates.invalidate()
    return {"rc": rc, "error": rc != 0, "reboot": updates.reboot_required()}


def _job_fix(job, action):
    if action not in ("enable-ufw", "enable-firewalld", "enable-fstrim"):
        job.log(t("Unbekannte Aktion."))
        return {"error": True}
    rc, _ = privileged.run_helper(job, action)
    return {"rc": rc, "error": rc != 0}


def _job_netscan(job):
    res = network.scan(job)
    if res and not res.get("error"):
        STATE.last_scan = res
    return res


def start_job(kind, params):
    p = params if isinstance(params, dict) else {}
    if kind == "updates-check":
        return jobs.start(kind, t("Updates suchen"), _job_updates_check, bool(p.get("online")))
    if kind == "updates-install":
        src = p.get("sources") if isinstance(p.get("sources"), list) else ["system"]
        return jobs.start(kind, t("Updates installieren"), _job_updates_install, [str(s) for s in src])
    if kind == "refresh":
        return jobs.start(kind, t("Paketquellen aktualisieren"), _job_refresh)
    if kind == "maintain":
        return jobs.start(kind, t("Alles pflegen"), _job_maintain)
    if kind == "clean":
        items = [str(i) for i in p.get("items", []) if isinstance(i, str)]
        return jobs.start(kind, t("Aufräumen"), cleanup.clean, items)
    if kind == "restart-unit":
        return jobs.start(kind, t("Dienst neu starten"), services.restart, str(p.get("unit", "")), bool(p.get("user")))
    if kind == "smart":
        return jobs.start(kind, t("SMART prüfen"), disks.smart_job)
    if kind == "fix":
        return jobs.start(kind, t("Problem beheben"), _job_fix, str(p.get("action", "")))
    if kind == "netscan":
        return jobs.start(kind, t("Netzwerk scannen"), _job_netscan)
    if kind == "ollama-pull":
        return jobs.start(kind, t("KI-Modell laden"), ai.ollama_pull, str(p.get("model", "")))
    return None


# ------------------------------------------------------------------ HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "PC-Tools"
    sys_version = ""

    def log_message(self, fmt, *args):  # keine Zugriffsprotokolle (Token in URL!)
        pass

    # --- Antworten
    def _headers(self, code, ctype, length):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)
        self.end_headers()

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._headers(code, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def send_error_json(self, code, msg):
        self.send_json({"error": msg}, code)

    # --- Prüfungen
    def host_ok(self):
        host = self.headers.get("Host", "")
        return host in ("127.0.0.1:%d" % STATE.port, "localhost:%d" % STATE.port)

    def origin_ok(self):
        origin = self.headers.get("Origin")
        return origin is None or origin in ("http://127.0.0.1:%d" % STATE.port, "http://localhost:%d" % STATE.port)

    def token_ok(self, value=None):
        value = value if value is not None else self.headers.get("X-PCT-Token", "")
        return bool(value) and hmac.compare_digest(value.encode(), STATE.token.encode())

    def read_body(self, limit=1024 * 1024):
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            n = 0
        if n <= 0 or n > limit:
            return b""
        return self.rfile.read(n)

    def read_json(self):
        try:
            data = json.loads(self.read_body().decode("utf-8") or "{}")
            return data if isinstance(data, dict) else {}
        except ValueError:
            return {}

    # --- Methoden
    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def dispatch(self, method):
        if not self.host_ok():
            return self.send_error_json(403, "host")
        url = urlparse(self.path)
        path = url.path
        STATE.last = time.time()
        STATE.bye = None
        if method == "GET" and not path.startswith("/api/"):
            return self.static(path)
        if path == "/api/bye" and method == "POST":
            if self.token_ok(self.read_body(256).decode("utf-8", "replace").strip()):
                STATE.bye = time.time()
                return self.send_json({"ok": True})
            return self.send_error_json(403, "token")
        if not self.origin_ok() or not self.token_ok():
            return self.send_error_json(403, "token")
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            if method == "GET":
                return self.api_get(path, query)
            return self.api_post(path, self.read_json())
        except Exception as e:  # Fehler der Oberfläche melden statt Verbindung abbrechen
            return self.send_error_json(500, t("Interner Fehler: {0}", e))

    def static(self, path):
        name = path.lstrip("/") or "index.html"
        if name.startswith("lang/") and name.endswith(".json"):
            code = name[5:-5]
            f = i18n.lang_dir() / ("%s.json" % code)
            if code in i18n.LANG_CODES and f.is_file():
                body = f.read_bytes()
                self._headers(200, "application/json; charset=utf-8", len(body))
                return self.wfile.write(body)
            return self.send_error_json(404, "not found")
        if name not in STATIC:
            return self.send_error_json(404, "not found")
        body = (WEB_DIR / name).read_bytes()
        self._headers(200, STATIC[name], len(body))
        self.wfile.write(body)

    def api_get(self, path, q):
        if path == "/api/ping":
            return self.send_json({"ok": True})
        if path == "/api/init":
            s = i18n.get_settings()
            return self.send_json({
                "version": __version__, "app": APP_NAME, "github": GITHUB_URL,
                "settings": s, "first_run": not s.get("lang"), "lang": i18n.current_language(),
                "languages": [{"code": c, "name": n} for c, n in i18n.LANGUAGES],
                "root_method": privileged.method(), "config_dir": str(i18n.SETTINGS_FILE.parent),
                "jobs": jobs.running()})
        if path == "/api/overview":
            info = sysinfo.overview()
            return self.send_json({"info": info, "health": health.gather(info)})
        if path == "/api/updates/cached":
            return self.send_json({"data": updates.cached()})
        if path == "/api/cleanup":
            return self.send_json(cleanup.analyze())
        if path == "/api/autostart":
            return self.send_json(autostart.overview())
        if path == "/api/services":
            return self.send_json(services.overview())
        if path == "/api/services/journal":
            return self.send_json(services.journal(q.get("unit", ""), q.get("user") == "1"))
        if path == "/api/disks":
            return self.send_json(disks.overview())
        if path == "/api/security":
            return self.send_json(security.check())
        if path == "/api/netdiag":
            return self.send_json(network.diagnose())
        if path == "/api/netscan/info":
            return self.send_json({"network": network.local_network(), "last": STATE.last_scan})
        if path == "/api/netscan/report":
            if not STATE.last_scan:
                return self.send_error_json(404, t("Noch kein Scan vorhanden."))
            return self.send_json({"html": network.report_html(STATE.last_scan)})
        if path == "/api/ai/providers":
            return self.send_json(ai.providers_public())
        if path == "/api/ai/ollama":
            return self.send_json(ai.ollama_status())
        if path == "/api/ai/context":
            return self.send_json({"text": ai.build_context()})
        if path == "/api/jobs":
            return self.send_json({"jobs": jobs.running()})
        if path.startswith("/api/jobs/"):
            job = jobs.get(path.rsplit("/", 1)[-1])
            if not job:
                return self.send_error_json(404, t("Auftrag nicht gefunden."))
            try:
                since = int(q.get("since", "0"))
            except ValueError:
                since = 0
            return self.send_json(job.to_dict(since))
        return self.send_error_json(404, "not found")

    def api_post(self, path, body):
        if path == "/api/settings":
            return self.send_json({"settings": i18n.update_settings(body), "lang": i18n.current_language()})
        if path == "/api/autostart/toggle":
            return self.send_json(autostart.toggle(str(body.get("file", "")), bool(body.get("enabled"))))
        if path == "/api/jobs/start":
            job = start_job(str(body.get("kind", "")), body.get("params"))
            if not job:
                return self.send_error_json(400, t("Unbekannter Auftrag."))
            return self.send_json({"id": job.id})
        if path == "/api/ai/key":
            return self.send_json(ai.set_key(str(body.get("provider", "")), str(body.get("key", ""))))
        if path == "/api/ai/settings":
            s = i18n.get_settings()
            models = dict(s.get("ai_models") or {})
            pid = str(body.get("provider", ""))
            if ai.provider(pid):
                if body.get("model") and ai.MODEL_RX.fullmatch(str(body["model"])):
                    models[pid] = str(body["model"])
                changes = {"ai_provider": pid, "ai_models": models}
                if "custom_url" in body:
                    changes["ai_custom_url"] = str(body["custom_url"])[:500]
                if "context" in body:
                    changes["ai_context"] = bool(body["context"])
                i18n.update_settings(changes)
            return self.send_json(ai.providers_public())
        if path == "/api/ai/chat":
            return self.send_json(ai.chat(str(body.get("provider", "")), str(body.get("model", "")),
                                          body.get("messages") or [], bool(body.get("context")),
                                          i18n.get_settings().get("ai_custom_url", "")))
        if path == "/api/shutdown":
            self.send_json({"ok": True})
            threading.Thread(target=STATE.httpd.shutdown, daemon=True).start()
            return None
        return self.send_error_json(404, "not found")


def watchdog():
    while True:
        time.sleep(5)
        now = time.time()
        if now - STATE.last > IDLE_LIMIT or (STATE.bye and now - STATE.bye > BYE_GRACE and not jobs.running()):
            STATE.httpd.shutdown()
            return


def open_browser(url):
    """Öffnet den Standardbrowser des Benutzers (xdg-open, sonst Python-webbrowser)."""
    exe = which("xdg-open")
    if exe:
        try:
            subprocess.Popen([exe, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             stdin=subprocess.DEVNULL, start_new_session=True)
            return True
        except OSError:
            pass
    try:
        return webbrowser.open(url)
    except Exception:
        return False


def main(argv=None):
    global STATE
    ap = argparse.ArgumentParser(prog="pc-tools", description=APP_NAME)
    ap.add_argument("--no-browser", action="store_true", help="Browser nicht öffnen, nur die Adresse ausgeben")
    ap.add_argument("--port", type=int, default=0, help="fester Port (Standard: zufällig)")
    ap.add_argument("--version", action="version", version="%s %s" % (APP_NAME, __version__))
    args = ap.parse_args(argv)
    # PCTOOLS_TEST_ALLOW_ROOT=1 nur für automatische Tests in Containern, in denen alles als root läuft
    if hasattr(os, "geteuid") and os.geteuid() == 0 and os.environ.get("PCTOOLS_TEST_ALLOW_ROOT") != "1":
        print("PC-Tools bitte NICHT als root starten. Administratorrechte werden bei Bedarf "
              "einzeln über pkexec angefragt.", file=sys.stderr)
        return 1
    if sys.version_info < (3, 8):
        print("PC-Tools braucht Python 3.8 oder neuer.", file=sys.stderr)
        return 1
    i18n.init()
    token = secrets.token_urlsafe(32)
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    httpd.daemon_threads = True
    STATE = State(token, httpd.server_address[1])
    STATE.httpd = httpd
    url = "http://127.0.0.1:%d/?t=%s" % (STATE.port, token)
    threading.Thread(target=watchdog, daemon=True).start()
    if args.no_browser:
        print(url, flush=True)
    else:
        print("%s %s – %s" % (APP_NAME, __version__, url), flush=True)
        if not open_browser(url):
            print("Bitte die Adresse im Browser öffnen.", flush=True)
    try:
        httpd.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0
