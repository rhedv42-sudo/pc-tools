#!/bin/sh
# PC-Tools für Linux – Deinstallation (entfernt alles, was install.sh angelegt hat).
# Einstellungen und API-Schlüssel in ~/.config/pc-tools bleiben erhalten,
# außer mit: ./uninstall.sh --purge
set -eu

DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
DEST="$DATA/pc-tools"
BIN="$HOME/.local/bin/pc-tools"
CONF="${XDG_CONFIG_HOME:-$HOME/.config}/pc-tools"

if [ -L "$BIN" ] && [ "$(readlink "$BIN")" = "$DEST/pc-tools" ]; then
    rm -f "$BIN"
fi
rm -f "$DATA/applications/pc-tools.desktop"
rm -f "$DATA/icons/hicolor/256x256/apps/pc-tools.png" "$DATA/icons/hicolor/64x64/apps/pc-tools.png"
rm -rf "$DEST"
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DATA/applications" >/dev/null 2>&1 || true
fi

if [ "${1:-}" = "--purge" ]; then
    rm -rf "$CONF"
    echo "PC-Tools samt Einstellungen und API-Schlüsseln entfernt."
else
    echo "PC-Tools entfernt. Einstellungen/API-Schlüssel liegen noch in $CONF (löschen mit: uninstall.sh --purge)."
fi
