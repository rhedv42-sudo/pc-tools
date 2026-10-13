"""KI-Assistent: Anbieter, API-Schlüssel (chmod 600) und Chat-Anfragen.

Die KI bekommt nur Text und kann nichts auf dem Rechner ausführen.
"""
import json
import re
import socket
import urllib.error
import urllib.request

from . import __version__
from .i18n import N_, current_language, get_settings, t
from .util import CONFIG_DIR, home_short, human_size, load_json, save_json, which

KEYS_FILE = CONFIG_DIR / "keys.json"
OLLAMA = "http://127.0.0.1:11434"
MODEL_RX = re.compile(r"^[\w.\-:/@]+$")

PROVIDERS = [
    {"id": "ollama", "label": N_("Kostenlos: Ollama – lokal auf diesem PC (ohne Konto)"), "kind": "openai",
     "url": OLLAMA + "/v1/chat/completions", "models": ["qwen3:4b", "qwen3:8b", "gpt-oss:20b", "llama3.1:8b"],
     "need_key": False, "local": True, "where": N_("nirgendwohin – die KI läuft auf diesem PC"),
     "key_url": "https://ollama.com/download"},
    {"id": "groq", "label": N_("Kostenlos: Groq (Gratis-Konto, sehr schnell)"), "kind": "openai",
     "url": "https://api.groq.com/openai/v1/chat/completions",
     "models": ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.3-70b-versatile"],
     "need_key": True, "where": N_("Groq (USA)"), "key_url": "https://console.groq.com/keys"},
    {"id": "openrouter", "label": N_("Kostenlos: OpenRouter (Gratis-Modelle, ca. 50 Fragen/Tag)"), "kind": "openai",
     "url": "https://openrouter.ai/api/v1/chat/completions",
     "models": ["openrouter/free", "openai/gpt-oss-120b:free", "meta-llama/llama-3.3-70b-instruct:free"],
     "need_key": True, "where": N_("OpenRouter (USA) und den jeweiligen Modellanbieter"),
     "key_url": "https://openrouter.ai/keys"},
    {"id": "mistral", "label": N_("Mistral (Server in der EU, Gratis-Testtarif oder bezahlt)"), "kind": "openai",
     "url": "https://api.mistral.ai/v1/chat/completions",
     "models": ["mistral-small-latest", "mistral-medium-latest", "mistral-large-latest"],
     "need_key": True, "where": N_("Mistral AI (Frankreich, EU)"), "key_url": "https://console.mistral.ai/api-keys"},
    {"id": "anthropic", "label": N_("Bezahlt: Claude (Anthropic)"), "kind": "anthropic",
     "url": "https://api.anthropic.com/v1/messages",
     "models": ["claude-haiku-4-5-20251001", "claude-sonnet-5", "claude-opus-5-5"],
     "need_key": True, "where": N_("Anthropic (USA)"), "key_url": "https://console.anthropic.com/settings/keys"},
    {"id": "openai", "label": N_("Bezahlt: ChatGPT (OpenAI)"), "kind": "openai",
     "url": "https://api.openai.com/v1/chat/completions", "models": ["gpt-5.4-mini", "gpt-5.4"],
     "need_key": True, "where": N_("OpenAI (USA)"), "key_url": "https://platform.openai.com/api-keys",
     "tok_field": "max_completion_tokens"},
    {"id": "gemini", "label": N_("Bezahlt: Gemini (Google)"), "kind": "openai",
     "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
     "models": ["gemini-2.5-flash", "gemini-2.5-pro"], "need_key": True, "where": N_("Google (USA)"),
     "key_url": "https://aistudio.google.com/apikey"},
    {"id": "custom", "label": N_("Andere KI / eigener Server (OpenAI-kompatibel)"), "kind": "openai", "url": "",
     "models": [], "need_key": False, "where": N_("den eingetragenen Server"), "key_url": ""},
]
LANG_NAMES = {"en-US": "Englisch", "zh-CN": "Chinesisch (vereinfacht)", "ru-RU": "Russisch",
              "es-ES": "Spanisch", "pt-BR": "Portugiesisch (Brasilien)", "fr-FR": "Französisch",
              "ja-JP": "Japanisch", "pl-PL": "Polnisch", "ko-KR": "Koreanisch", "tr-TR": "Türkisch",
              "it-IT": "Italienisch"}


def provider(pid):
    return next((p for p in PROVIDERS if p["id"] == pid), None)


# ------------------------------------------------------------------ Schlüssel
def _keys():
    data = load_json(KEYS_FILE, {})
    return data if isinstance(data, dict) else {}


def has_key(pid):
    return bool(_keys().get(pid))


def set_key(pid, key):
    if not provider(pid):
        return {"error": t("Unbekannter Anbieter.")}
    key = (key or "").strip()
    if key and (len(key) > 400 or not re.match(r"^[\x21-\x7e]+$", key)):
        return {"error": t("Der Schlüssel enthält ungültige Zeichen.")}
    keys = _keys()
    if key:
        keys[pid] = key
    else:
        keys.pop(pid, None)
    save_json(KEYS_FILE, keys, private=True)
    return {"ok": True}


def providers_public():
    """Anbieterliste für die Oberfläche – ohne Schlüssel, nur 'vorhanden ja/nein'."""
    s = get_settings()
    out = []
    for p in PROVIDERS:
        q = {k: v for k, v in p.items() if k != "tok_field"}
        q["label"] = t(p["label"])
        q["where"] = t(p["where"])
        q["has_key"] = has_key(p["id"])
        q["model"] = (s.get("ai_models") or {}).get(p["id"]) or (p["models"][0] if p["models"] else "")
        out.append(q)
    return {"providers": out, "selected": s.get("ai_provider") or "ollama",
            "custom_url": s.get("ai_custom_url", ""), "context": s.get("ai_context", True)}


# ------------------------------------------------------------------ Kontext
def system_prompt(context_text=""):
    lang = current_language()
    answer_lang = LANG_NAMES.get(lang, "Deutsch")
    p = ("Du bist der KI-Assistent in PC-Tools für Linux (Version %s), einem Werkzeug für Pflege, Updates, "
         "Sicherheit und Fehlersuche unter Linux. Antworte immer auf %s, freundlich und so einfach, dass es "
         "Menschen ohne IT-Wissen verstehen. Erkläre Fachbegriffe kurz. Erfinde nichts: Wenn die Daten etwas "
         "nicht hergeben, sag das. Nenne konkrete nächste Schritte, möglichst mit den Seiten von PC-Tools "
         "(Übersicht, Updates, Aufräumen, Autostart, Dienste, Datenträger, Sicherheit, Netzwerk-Diagnose, "
         "Netzwerk dokumentieren). Wenn ein Terminal-Befehl nötig ist, erkläre vorher, was er tut, und warne "
         "deutlich vor Befehlen, die Daten löschen können. Du kannst selbst nichts auf dem Rechner ausführen."
         % (__version__, answer_lang))
    if context_text:
        p += "\n\nAktuelle Daten dieses Rechners (vom Benutzer freigegeben):\n" + context_text
    return p


def build_context():
    """Kurze Systemübersicht + Befunde, ohne Rechnernamen und Benutzernamen."""
    from . import health, sysinfo
    info = sysinfo.overview()
    h = health.gather(info)
    lines = [
        "Distribution: %s, Kernel %s, Desktop %s" % (info["distro"], info["kernel"], info["desktop"]),
        "CPU: %s (%s Kerne), RAM: %s gesamt, %s frei" % (info["cpu"]["model"], info["cpu"]["cores"],
                                                        human_size(info["mem_total"]), human_size(info["mem_available"])),
        "Paketverwaltung: %s, Flatpak: %s, Snap: %s" % (info["package_manager"], info["flatpak"], info["snap"]),
    ]
    for d in info["disks"]:
        lines.append("Datenträger %s (%s): %s%% belegt, %s frei" % (d["mount"], d["fstype"], d["percent"], human_size(d["avail"])))
    lines.append("Zustand: %s/100" % h["score"])
    for f in h["findings"]:
        lines.append("- [%s] %s: %s" % (f["severity"], f["title"], f["detail"]))
    return home_short("\n".join(lines))


# ------------------------------------------------------------------ Anfrage
def _opener(local):
    if local:
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener()


def _post(url, body, headers, local=False, timeout=180):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers=dict(headers, **{"Content-Type": "application/json"}))
    with _opener(local).open(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def _error_text(code, body=""):
    m = {401: t("Schlüssel ungültig (401). Bitte prüfen."),
         403: t("Zugriff verweigert (403). Schlüssel oder Tarif prüfen."),
         404: t("Modell oder Adresse nicht gefunden (404)."),
         429: t("Zu viele Anfragen oder Limit erreicht (429). Kurz warten."),
         529: t("Der Dienst ist überlastet (529). Später erneut versuchen.")}
    msg = m.get(code) or t("Fehler {0} vom KI-Anbieter.", code)
    detail = ""
    try:
        detail = json.loads(body).get("error", {})
        detail = detail.get("message", "") if isinstance(detail, dict) else str(detail)
    except (ValueError, AttributeError):
        pass
    return msg + ((" " + detail[:300]) if detail else "")


def chat(pid, model, messages, attach_context=False, custom_url=""):
    p = provider(pid)
    if not p:
        return {"error": t("Unbekannter Anbieter.")}
    model = (model or (p["models"][0] if p["models"] else "")).strip()
    if not model or not MODEL_RX.fullmatch(model):
        return {"error": t("Bitte einen gültigen Modellnamen angeben.")}
    url = p["url"]
    if pid == "custom":
        url = (custom_url or "").strip()
        if not re.match(r"^https?://[^\s]+$", url):
            return {"error": t("Bitte eine gültige Adresse (http/https) bis /chat/completions eintragen.")}
    key = _keys().get(pid, "")
    if p["need_key"] and not key:
        return {"error": t("Für diesen Anbieter fehlt der API-Schlüssel.")}
    msgs = [{"role": m["role"], "content": str(m["content"])[:20000]} for m in (messages or [])[-20:]
            if isinstance(m, dict) and m.get("role") in ("user", "assistant") and m.get("content")]
    if not msgs:
        return {"error": t("Keine Frage angegeben.")}
    sysp = system_prompt(build_context() if attach_context else "")
    local = bool(p.get("local")) or url.startswith(("http://127.0.0.1", "http://localhost"))
    try:
        if p["kind"] == "anthropic":
            data = _post(url, {"model": model, "max_tokens": 2000, "system": sysp, "messages": msgs},
                         {"x-api-key": key, "anthropic-version": "2023-06-01"})
            text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        else:
            body = {"model": model, "messages": [{"role": "system", "content": sysp}] + msgs}
            body[p.get("tok_field", "max_tokens")] = 2000
            headers = {"Authorization": "Bearer " + key} if key else {}
            data = _post(url, body, headers, local=local)
            text = data["choices"][0]["message"].get("content") or ""
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()  # Denk-Ausgabe lokaler Modelle
        return {"text": text, "model": model}
    except urllib.error.HTTPError as e:
        return {"error": _error_text(e.code, e.read().decode("utf-8", "replace") if e.fp else "")}
    except urllib.error.URLError as e:
        if pid == "ollama":
            return {"error": t("Ollama ist nicht erreichbar. Läuft Ollama? Siehe 'Ollama einrichten'.")}
        return {"error": t("Keine Verbindung zum KI-Anbieter: {0}", e.reason)}
    except (socket.timeout, TimeoutError):
        return {"error": t("Zeitüberschreitung – die KI hat zu lange gebraucht.")}
    except (KeyError, IndexError, ValueError):
        return {"error": t("Unerwartete Antwort vom KI-Anbieter.")}


# ------------------------------------------------------------------ Ollama
def ollama_status():
    from .sysinfo import parse_meminfo
    from .util import read_text
    ram = parse_meminfo(read_text("/proc/meminfo")).get("MemTotal", 0)
    res = {"installed": bool(which("ollama")), "running": False, "models": [],
           "recommended": "qwen3:8b" if ram >= 24 * 1024 ** 3 else "qwen3:4b",
           "install_cmd": "curl -fsSL https://ollama.com/install.sh | sh"}
    try:
        with _opener(True).open(OLLAMA + "/api/tags", timeout=3) as r:
            data = json.loads(r.read().decode("utf-8"))
        res["running"] = True
        res["models"] = [m.get("name") for m in data.get("models", [])]
    except (OSError, ValueError):
        pass
    return res


def ollama_pull(job, model):
    if not MODEL_RX.fullmatch(model or ""):
        job.log(t("Ungültiger Modellname."))
        return {"error": True}
    job.log(t("Lade Modell {0} über Ollama …", model))
    req = urllib.request.Request(OLLAMA + "/api/pull", method="POST",
                                 data=json.dumps({"model": model, "stream": True}).encode(),
                                 headers={"Content-Type": "application/json"})
    last = ""
    try:
        with _opener(True).open(req, timeout=7200) as resp:
            for raw in resp:
                try:
                    ev = json.loads(raw.decode("utf-8"))
                except ValueError:
                    continue
                if ev.get("error"):
                    job.log(t("Fehler: {0}", ev["error"]))
                    return {"error": True}
                status = ev.get("status", "")
                if ev.get("total"):
                    job.progress = int(ev.get("completed", 0) * 100 / ev["total"])
                if status != last:
                    job.log(status)
                    last = status
    except urllib.error.URLError:
        job.log(t("Ollama ist nicht erreichbar. Bitte zuerst installieren und starten."))
        return {"error": True}
    job.log(t("Modell {0} ist bereit.", model))
    return {"ok": True}
