"""Übersetzungen und Einstellungen.

Alle Texte im Quellcode sind Deutsch und laufen durch die Funktion t(). Die Sprachdateien
liegen in lang/<code>.json im Format {"meta": {...}, "strings": {"Deutsch": "Übersetzung"}}.
Fehlt eine Übersetzung (oder ist sie leer), wird der deutsche Text gezeigt.
"""
import re
import threading
from pathlib import Path

from .util import CONFIG_DIR, load_json, save_json

# Sprachen mit ihrem Namen in der eigenen Sprache (für die Sprachauswahl)
LANGUAGES = [
    ("de-DE", "Deutsch"), ("en-US", "English"), ("zh-CN", "简体中文"),
    ("ru-RU", "Русский"), ("es-ES", "Español"), ("pt-BR", "Português (Brasil)"),
    ("fr-FR", "Français"), ("ja-JP", "日本語"), ("pl-PL", "Polski"),
    ("ko-KR", "한국어"), ("tr-TR", "Türkçe"), ("it-IT", "Italiano"),
]
LANG_CODES = {c for c, _ in LANGUAGES}

SETTINGS_FILE = CONFIG_DIR / "settings.json"
DEFAULT_SETTINGS = {"lang": "", "theme": "auto", "ai_provider": "ollama", "ai_models": {},
                    "ai_custom_url": "", "ai_context": True}

_lock = threading.Lock()
_strings = {}
_current = "de-DE"


def lang_dir():
    """Sprachordner: neben dem Paket (Quellbaum/Installation) oder im Paket."""
    here = Path(__file__).resolve().parent
    for cand in (here.parent / "lang", here / "lang"):
        if cand.is_dir():
            return cand
    return here.parent / "lang"


def load_lang_file(code):
    if code not in LANG_CODES:
        return {}
    data = load_json(lang_dir() / ("%s.json" % code), {})
    strings = data.get("strings", {}) if isinstance(data, dict) else {}
    return {k: v for k, v in strings.items() if isinstance(v, str) and v}


def set_language(code):
    global _strings, _current
    with _lock:
        _current = code if code in LANG_CODES else "de-DE"
        _strings = load_lang_file(_current) if _current != "de-DE" else {}


def current_language():
    return _current


def N_(text):
    """Markiert einen Text zur Übersetzung, ohne ihn sofort zu übersetzen (für Tabellen)."""
    return text


def t(text, *args):
    """Übersetzt einen deutschen Text; {0}, {1} ... werden durch args ersetzt."""
    s = _strings.get(text) or text
    if args:
        s = re.sub(r"\{(\d+)\}", lambda m: str(args[int(m.group(1))]) if int(m.group(1)) < len(args) else m.group(0), s)
    return s


# ---------------------------------------------------------------- Einstellungen
def get_settings():
    s = dict(DEFAULT_SETTINGS)
    data = load_json(SETTINGS_FILE, {})
    if isinstance(data, dict):
        s.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
    return s


def update_settings(changes):
    """Übernimmt nur bekannte Schlüssel mit passendem Typ."""
    s = get_settings()
    for k, v in (changes or {}).items():
        if k not in DEFAULT_SETTINGS:
            continue
        if not isinstance(v, type(DEFAULT_SETTINGS[k])):
            continue
        if k == "lang" and v and v not in LANG_CODES:
            continue
        if k == "theme" and v not in ("auto", "light", "dark"):
            continue
        s[k] = v
    save_json(SETTINGS_FILE, s)
    if "lang" in (changes or {}):
        set_language(s["lang"] or "de-DE")
    return s


def init():
    set_language(get_settings().get("lang") or "de-DE")
