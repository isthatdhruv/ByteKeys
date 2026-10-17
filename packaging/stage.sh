#!/usr/bin/env bash
# Lay out a ByteKeys installation tree.
#
#   packaging/stage.sh DESTDIR [PREFIX] [UNITDIR]
#
# Used by the .deb build (PREFIX=/usr) and by "make install" (PREFIX=/usr/local).
set -euo pipefail
umask 022

DEST=${1:?usage: stage.sh DESTDIR [PREFIX] [UNITDIR]}
PREFIX=${2:-/usr}
UNITDIR=${3:-$PREFIX/lib/systemd/system}
PYTHON=${PYTHON:-/usr/bin/python3}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
APP_ID=io.github.isthatdhruv.ByteKeys
LIB=$PREFIX/lib/bytekeys

install -d "$DEST$LIB" "$DEST$PREFIX/bin" "$DEST$PREFIX/sbin" "$DEST$UNITDIR"

# Python package (sources and assets only).
(cd "$ROOT" && find bytekeys -name '__pycache__' -prune -o -type f \( -name '*.py' -o -name '*.png' \) -print) |
while read -r f; do
    install -D -m 0644 "$ROOT/$f" "$DEST$LIB/$f"
done

launcher() {  # launcher NAME MODULE
    cat > "$DEST$2" <<EOF
#!$PYTHON
import sys
sys.path.insert(0, "$LIB")
from $3 import main
sys.exit(main())
EOF
    chmod 0755 "$DEST$2"
}
launcher bytekeys "$PREFIX/bin/bytekeys" bytekeys.cli
launcher bytekeys-gui "$PREFIX/bin/bytekeys-gui" bytekeys.gui.app
launcher bytekeysd "$PREFIX/sbin/bytekeysd" bytekeys.daemon

sed "s|/usr/sbin/bytekeysd|$PREFIX/sbin/bytekeysd|" "$ROOT/data/systemd/bytekeysd.service" \
    > "$DEST$UNITDIR/bytekeysd.service"
chmod 0644 "$DEST$UNITDIR/bytekeysd.service"

install -D -m 0644 "$ROOT/data/desktop/$APP_ID.desktop" "$DEST$PREFIX/share/applications/$APP_ID.desktop"
install -D -m 0644 "$ROOT/data/desktop/$APP_ID.metainfo.xml" "$DEST$PREFIX/share/metainfo/$APP_ID.metainfo.xml"
install -D -m 0644 "$ROOT/data/icons/$APP_ID.svg" "$DEST$PREFIX/share/icons/hicolor/scalable/apps/$APP_ID.svg"
for size in 16 24 32 48 64 128 256 512; do
    install -D -m 0644 "$ROOT/data/icons/png/$size.png" \
        "$DEST$PREFIX/share/icons/hicolor/${size}x${size}/apps/$APP_ID.png"
done
for page in bytekeys.1 bytekeys-gui.1 bytekeysd.8; do
    section=${page##*.}
    install -D -m 0644 "$ROOT/data/$page" "$DEST$PREFIX/share/man/man$section/$page"
    gzip -9nf "$DEST$PREFIX/share/man/man$section/$page"
done
