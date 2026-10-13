"""Autostart: XDG-Autostart-Einträge (.desktop) und aktivierte systemd --user Units."""
import os
import re
from pathlib import Path

from .i18n import t
from .util import read_text, run

USER_DIR = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "autostart"
NAME_RX = re.compile(r"^[\w.@+\-]+\.desktop$")


def system_dirs():
    dirs = os.environ.get("XDG_CONFIG_DIRS") or "/etc/xdg"
    return [Path(d) / "autostart" for d in dirs.split(":") if d]


def parse_desktop(text):
    """Liest die Gruppe [Desktop Entry] einer .desktop-Datei."""
    data = {}
    in_group = False
    for line in (text or "").splitlines():
        s = line.strip()
        if s.startswith("["):
            in_group = s == "[Desktop Entry]"
            continue
        if in_group and "=" in s and not s.startswith("#"):
            k, _, v = s.partition("=")
            data.setdefault(k.strip(), v.strip())
    return data


def is_enabled(entry):
    if entry.get("Hidden", "").lower() == "true":
        return False
    if entry.get("X-GNOME-Autostart-enabled", "").lower() == "false":
        return False
    return True


def shown_in_desktop(entry):
    """Prüft OnlyShowIn/NotShowIn gegen den aktuellen Desktop."""
    cur = [d.lower() for d in os.environ.get("XDG_CURRENT_DESKTOP", "").split(":") if d]
    only = [d.lower() for d in entry.get("OnlyShowIn", "").split(";") if d]
    nots = [d.lower() for d in entry.get("NotShowIn", "").split(";") if d]
    if only and cur and not set(only) & set(cur):
        return False
    if nots and set(nots) & set(cur):
        return False
    return True


def list_entries():
    entries = {}
    for d in reversed(system_dirs()):
        if d.is_dir():
            for f in sorted(d.glob("*.desktop")):
                entries[f.name] = {"file": f.name, "path": str(f), "source": "system",
                                   "entry": parse_desktop(read_text(f))}
    if USER_DIR.is_dir():
        for f in sorted(USER_DIR.glob("*.desktop")):
            src = "override" if f.name in entries else "user"
            entries[f.name] = {"file": f.name, "path": str(f), "source": src,
                               "entry": parse_desktop(read_text(f))}
    out = []
    for name, e in sorted(entries.items(), key=lambda kv: kv[1]["entry"].get("Name", kv[0]).lower()):
        ent = e["entry"]
        out.append({"file": name, "name": ent.get("Name", name), "comment": ent.get("Comment", ""),
                    "exec": ent.get("Exec", ""), "source": e["source"], "enabled": is_enabled(ent),
                    "relevant": shown_in_desktop(ent)})
    return out


def set_line(text, key, value):
    """Setzt key=value in der Gruppe [Desktop Entry] (ersetzt oder ergänzt)."""
    lines = text.splitlines()
    in_group = False
    insert_at = None
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("["):
            if in_group and insert_at is None:
                insert_at = i
            in_group = s == "[Desktop Entry]"
            continue
        if in_group and s.split("=", 1)[0].strip() == key:
            lines[i] = "%s=%s" % (key, value)
            return "\n".join(lines) + "\n"
    if insert_at is None:
        insert_at = len(lines)
    lines.insert(insert_at, "%s=%s" % (key, value))
    return "\n".join(lines) + "\n"


def toggle(filename, enabled):
    """Aktiviert/deaktiviert einen Eintrag über eine Kopie in ~/.config/autostart."""
    if not NAME_RX.fullmatch(filename or ""):
        return {"error": t("Ungültiger Dateiname.")}
    user_file = USER_DIR / filename
    if user_file.is_file():
        text = read_text(user_file)
    else:
        src = next((d / filename for d in system_dirs() if (d / filename).is_file()), None)
        if not src:
            return {"error": t("Eintrag nicht gefunden.")}
        text = read_text(src)
    text = set_line(text, "Hidden", "false" if enabled else "true")
    if "X-GNOME-Autostart-enabled" in text:
        text = set_line(text, "X-GNOME-Autostart-enabled", "true" if enabled else "false")
    USER_DIR.mkdir(parents=True, exist_ok=True)
    tmp = user_file.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, user_file)
    return {"ok": True}


def user_units():
    r = run(["systemctl", "--user", "list-unit-files", "--state=enabled", "--no-legend", "--no-pager"], timeout=15)
    if r.missing:
        return None
    units = []
    for line in r.out.splitlines():
        parts = line.split()
        if parts and not parts[0].endswith(".target"):
            units.append({"unit": parts[0], "state": parts[1] if len(parts) > 1 else ""})
    return units


def overview():
    return {"entries": list_entries(), "user_units": user_units(), "user_dir": str(USER_DIR)}
