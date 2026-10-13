#!/usr/bin/env python3
"""Sammelt alle deutschen Quelltexte für die Übersetzung.

Durchsucht pctools/**/*.py (t('...'), N_('...')), pctools/web/*.js (t('...'))
und pctools/web/*.html (data-t="...") und schreibt lang/keys.json
(sortierte Liste). Mit --sync werden fehlende Schlüssel zusätzlich als ""
in alle lang/<code>.json eingetragen (vorhandene Übersetzungen bleiben).

Aufruf:  python3 tools/extract_strings.py [--sync]
"""
import ast
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "pctools"
LANG = ROOT / "lang"

STR_LIT = r"(?:\"(?:[^\"\\\n]|\\.)*\"|'(?:[^'\\\n]|\\.)*')"
# t( oder N_( gefolgt von einem oder mehreren direkt aneinandergereihten String-Literalen
CALL_RX = re.compile(r"(?<![\w.$])(?:t|N_)\(\s*((?:" + STR_LIT + r"\s*)+)\s*[,)]")
LIT_RX = re.compile(STR_LIT)
DATA_T_RX = re.compile(r'data-t="([^"]+)"')


def literals(src):
    """Alle übersetzbaren Texte aus Python- oder JS-Quelltext."""
    found = set()
    for m in CALL_RX.finditer(src):
        parts = []
        for lit in LIT_RX.findall(m.group(1)):
            try:
                parts.append(ast.literal_eval(lit))
            except (ValueError, SyntaxError):
                parts = []
                break
        text = "".join(parts)
        if text.strip():
            found.add(text)
    return found


def collect():
    keys = set()
    for f in sorted(PKG.rglob("*.py")):
        keys |= literals(f.read_text(encoding="utf-8"))
    for f in sorted((PKG / "web").glob("*.js")):
        keys |= literals(f.read_text(encoding="utf-8"))
    for f in sorted((PKG / "web").glob("*.html")):
        keys |= {html.unescape(k) for k in DATA_T_RX.findall(f.read_text(encoding="utf-8"))}
    return sorted(keys)


def sync(keys):
    for f in sorted(LANG.glob("*.json")):
        if f.name == "keys.json":
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        strings = data.setdefault("strings", {})
        added = 0
        for k in keys:
            if k not in strings:
                strings[k] = ""
                added += 1
        data["strings"] = dict(sorted(strings.items()))
        f.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("%s: %d neue Schlüssel" % (f.name, added))


def main(argv):
    keys = collect()
    LANG.mkdir(exist_ok=True)
    (LANG / "keys.json").write_text(json.dumps(keys, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("%d Texte -> %s" % (len(keys), LANG / "keys.json"))
    if "--sync" in argv:
        sync(keys)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
