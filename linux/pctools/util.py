"""Gemeinsame Hilfsfunktionen: sichere Prozessaufrufe, Pfade, Größen."""
import json
import os
import shutil
import subprocess
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "pc-tools"


class Result:
    """Ergebnis eines externen Befehls. ok=False auch, wenn das Programm fehlt."""

    def __init__(self, rc, out="", err="", missing=False, timeout=False):
        self.rc = rc
        self.out = out
        self.err = err
        self.missing = missing
        self.timeout = timeout

    @property
    def ok(self):
        return self.rc == 0 and not self.missing and not self.timeout

    def __repr__(self):
        return "Result(rc=%r, missing=%r, timeout=%r)" % (self.rc, self.missing, self.timeout)


def which(name):
    """Pfad eines Programms oder None (sucht auch in /usr/sbin und /sbin)."""
    path = os.environ.get("PATH", "") + ":/usr/sbin:/sbin:/usr/local/sbin"
    return shutil.which(name, path=path)


def run(argv, timeout=20, env=None, input_text=None):
    """Führt einen Befehl als Argumentliste aus (nie über eine Shell).

    Fehlt das Programm, kommt Result(missing=True) zurück statt einer Ausnahme.
    """
    exe = which(argv[0]) if not os.path.isabs(argv[0]) else argv[0]
    if not exe or not os.path.exists(exe):
        return Result(127, missing=True)
    full_env = dict(os.environ)
    full_env.update({"LC_ALL": "C", "LANG": "C"})
    if env:
        full_env.update(env)
    try:
        p = subprocess.run([exe] + list(argv[1:]), capture_output=True, text=True,
                           timeout=timeout, env=full_env, input=input_text,
                           errors="replace")
        return Result(p.returncode, p.stdout, p.stderr)
    except subprocess.TimeoutExpired:
        return Result(124, timeout=True)
    except OSError as e:
        return Result(126, err=str(e), missing=True)


def read_text(path, default=""):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return default


def dir_size(path, limit_files=200000):
    """Größe eines Ordners in Bytes; nicht lesbare Teile werden übersprungen."""
    total = 0
    count = 0
    for root, dirs, files in os.walk(path, onerror=lambda e: None):
        for f in files:
            try:
                st = os.lstat(os.path.join(root, f))
                total += st.st_size
            except OSError:
                pass
            count += 1
            if count > limit_files:
                return total
    return total


def human_size(n):
    """Bytes als lesbare Größe (deutsche Schreibweise mit Komma)."""
    if n is None:
        return "?"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            if unit == "B":
                return "%d B" % n
            return ("%.1f %s" % (n, unit)).replace(".", ",")
        n /= 1024.0
    return "?"


def parse_size(text):
    """'1.2G', '512.0M', '24K' -> Bytes (für journalctl --disk-usage usw.)."""
    import re
    m = re.search(r"([\d.,]+)\s*([KMGTP]?)i?B?", text or "")
    if not m:
        return 0
    val = float(m.group(1).replace(",", "."))
    mult = {"": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3, "T": 1024 ** 4, "P": 1024 ** 5}
    return int(val * mult[m.group(2)])


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, data, private=False):
    """Schreibt JSON atomar; private=True -> Rechte 600 (nur der eigene Benutzer)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600 if private else 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if private:
        os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def home_short(text):
    """Ersetzt den Home-Pfad durch ~ (Datenschutz bei KI-Kontext)."""
    home = str(Path.home())
    return (text or "").replace(home, "~")
