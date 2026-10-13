#!/bin/sh
# PC-Tools für Linux – Installation für den aktuellen Benutzer (ohne root).
# Installiert nach ~/.local/share/pc-tools, legt ~/.local/bin/pc-tools, einen
# Startmenü-Eintrag und das Symbol an. Entfernen mit ./uninstall.sh
set -eu

SRC=$(dirname "$(readlink -f "$0")")
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
DEST="$DATA/pc-tools"
BIN="$HOME/.local/bin"
APPS="$DATA/applications"
ICONS="$DATA/icons/hicolor"

if [ "$(id -u)" = "0" ] && [ "${PCTOOLS_TEST_ALLOW_ROOT:-}" != "1" ]; then
    echo "Bitte NICHT als root/mit sudo installieren – PC-Tools wird pro Benutzer installiert." >&2
    exit 1
fi
if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)'; then
    echo "PC-Tools braucht Python 3.8 oder neuer (Paket python3)." >&2
    exit 1
fi
if [ ! -f "$SRC/pctools/__init__.py" ]; then
    echo "Programmdateien nicht gefunden (pctools/). Bitte install.sh aus dem entpackten Ordner starten." >&2
    exit 1
fi

echo "Installiere PC-Tools nach $DEST ..."
rm -rf "$DEST"
mkdir -p "$DEST" "$BIN" "$APPS" "$ICONS/256x256/apps" "$ICONS/64x64/apps"
cp -r "$SRC/pctools" "$SRC/lang" "$DEST/"
cp "$SRC/pc-tools" "$DEST/pc-tools"
if [ -f "$SRC/uninstall.sh" ]; then
    cp "$SRC/uninstall.sh" "$DEST/uninstall.sh"
    chmod 755 "$DEST/uninstall.sh"
fi
find "$DEST" -name __pycache__ -type d -prune -exec rm -rf {} +
chmod 755 "$DEST/pc-tools"
chmod 644 "$DEST/pctools/helper.py"

ln -sf "$DEST/pc-tools" "$BIN/pc-tools"
cp "$SRC/pctools/web/icon-256.png" "$ICONS/256x256/apps/pc-tools.png"
cp "$SRC/pctools/web/icon-64.png" "$ICONS/64x64/apps/pc-tools.png"

cat > "$APPS/pc-tools.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=PC-Tools
GenericName=System-Pflege
GenericName[en]=System maintenance
Comment=Updates, Aufräumen, Sicherheit und Netzwerk-Diagnose
Comment[en]=Updates, cleanup, security and network diagnostics
Exec="$DEST/pc-tools"
Icon=pc-tools
Terminal=false
Categories=System;Settings;Utility;
Keywords=update;clean;security;network;wartung;pflege;aufräumen;
StartupNotify=false
DESKTOP
chmod 644 "$APPS/pc-tools.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then update-desktop-database "$APPS" >/dev/null 2>&1 || true; fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then gtk-update-icon-cache -q -f -t "$ICONS" >/dev/null 2>&1 || true; fi

echo "Fertig. Start über das Startmenü (PC-Tools) oder mit: pc-tools"
case ":$PATH:" in
    *":$BIN:"*) ;;
    *) echo "Hinweis: $BIN ist nicht im PATH. Start dann mit: $DEST/pc-tools" ;;
esac
if ! command -v pkexec >/dev/null 2>&1; then
    echo "Hinweis: pkexec (polkit) fehlt. Für Updates und Systempflege bitte das Paket 'pkexec' bzw. 'polkit' installieren."
fi
