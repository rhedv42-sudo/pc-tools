#!/bin/sh
# Baut die Release-Pakete von PC-Tools für Linux:
#   dist/pc-tools-linux-<version>.tar.gz   (für install.sh, jede Distribution)
#   dist/pc-tools_<version>_all.deb        (Debian/Ubuntu/Mint, nur wenn dpkg-deb vorhanden)
# Aufruf aus beliebigem Ordner: linux/build/build-packages.sh
set -eu

HERE=$(dirname "$(readlink -f "$0")")
LINUX=$(dirname "$HERE")
REPO=$(dirname "$LINUX")
VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$LINUX/pctools/__init__.py")
[ -n "$VERSION" ] || { echo "Version nicht gefunden." >&2; exit 1; }
DIST="$LINUX/dist"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$DIST"

copy_app() {   # $1 = Zielordner für pctools/, lang/, pc-tools
    mkdir -p "$1"
    cp -r "$LINUX/pctools" "$LINUX/lang" "$1/"
    cp "$LINUX/pc-tools" "$1/pc-tools"
    find "$1" -name __pycache__ -type d -prune -exec rm -rf {} +
    find "$1" -type d -exec chmod 755 {} +
    find "$1" -type f -exec chmod 644 {} +
    chmod 755 "$1/pc-tools"
}

# ---------------------------------------------------------------- tar.gz
NAME="pc-tools-linux-$VERSION"
copy_app "$WORK/$NAME"
cp "$LINUX/install.sh" "$LINUX/uninstall.sh" "$LINUX/README.md" "$WORK/$NAME/"
chmod 755 "$WORK/$NAME/install.sh" "$WORK/$NAME/uninstall.sh"
[ -f "$REPO/LICENSE" ] && cp "$REPO/LICENSE" "$WORK/$NAME/LICENSE" && chmod 644 "$WORK/$NAME/LICENSE"
tar -C "$WORK" --owner=0 --group=0 -czf "$DIST/$NAME.tar.gz" "$NAME"
echo "Gebaut: $DIST/$NAME.tar.gz"

# ---------------------------------------------------------------- .deb
if ! command -v dpkg-deb >/dev/null 2>&1; then
    echo "dpkg-deb nicht gefunden – .deb wird übersprungen."
    exit 0
fi
ROOT="$WORK/deb"
copy_app "$ROOT/usr/lib/pc-tools"
mkdir -p "$ROOT/usr/bin" "$ROOT/usr/share/applications" "$ROOT/usr/share/doc/pc-tools" \
         "$ROOT/usr/share/icons/hicolor/256x256/apps" "$ROOT/usr/share/icons/hicolor/64x64/apps" "$ROOT/DEBIAN"
ln -s ../lib/pc-tools/pc-tools "$ROOT/usr/bin/pc-tools"
cp "$LINUX/pctools/web/icon-256.png" "$ROOT/usr/share/icons/hicolor/256x256/apps/pc-tools.png"
cp "$LINUX/pctools/web/icon-64.png" "$ROOT/usr/share/icons/hicolor/64x64/apps/pc-tools.png"
[ -f "$REPO/LICENSE" ] && cp "$REPO/LICENSE" "$ROOT/usr/share/doc/pc-tools/copyright"
cat > "$ROOT/usr/share/applications/pc-tools.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=PC-Tools
GenericName=System-Pflege
GenericName[en]=System maintenance
Comment=Updates, Aufräumen, Sicherheit und Netzwerk-Diagnose
Comment[en]=Updates, cleanup, security and network diagnostics
Exec=/usr/bin/pc-tools
Icon=pc-tools
Terminal=false
Categories=System;Settings;Utility;
Keywords=update;clean;security;network;wartung;pflege;aufräumen;
StartupNotify=false
DESKTOP
SIZE=$(du -sk "$ROOT/usr" | cut -f1)
cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: pc-tools
Version: $VERSION
Section: admin
Priority: optional
Architecture: all
Depends: python3 (>= 3.8)
Recommends: pkexec | policykit-1, iproute2, smartmontools, xdg-utils
Installed-Size: $SIZE
Maintainer: PC-Tools (rhedv42-sudo) <rhedv42-sudo@users.noreply.github.com>
Homepage: https://github.com/rhedv42-sudo/pc-tools
Description: PC-Tools für Linux - Pflege, Updates, Sicherheit
 Kostenloses Open-Source-Wartungswerkzeug (Apache-2.0) mit lokaler
 Weboberfläche: Updates, Aufräumen, Autostart, Dienste, Datenträger,
 Sicherheitsprüfung, Netzwerk-Diagnose und -Dokumentation, KI-Assistent.
CONTROL
chmod 644 "$ROOT/DEBIAN/control" "$ROOT/usr/share/applications/pc-tools.desktop"
DEB="$DIST/pc-tools_${VERSION}_all.deb"
if dpkg-deb --help 2>/dev/null | grep -q -- --root-owner-group; then
    dpkg-deb --root-owner-group --build "$ROOT" "$DEB" >/dev/null
else
    dpkg-deb --build "$ROOT" "$DEB" >/dev/null
fi
echo "Gebaut: $DEB"
