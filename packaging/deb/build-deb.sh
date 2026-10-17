#!/usr/bin/env bash
# Build dist/bytekeys_<version>_all.deb (pure Python, works on every architecture).
#
# Environment:
#   MAINTAINER   "Name <email>" written to the package control file
#   OUT          output directory (default: dist)
set -euo pipefail
umask 022

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
VERSION=$(PYTHONPATH="$ROOT" python3 -c "import bytekeys; print(bytekeys.__version__)")
MAINTAINER=${MAINTAINER:-"ByteKeys Developers <maintainers@bytekeys.invalid>"}
OUT=${OUT:-$ROOT/dist}
PKG=$ROOT/build/deb/bytekeys_${VERSION}_all

rm -rf "$PKG"
mkdir -p "$PKG/DEBIAN" "$OUT"
"$ROOT/packaging/stage.sh" "$PKG" /usr

DOC=$PKG/usr/share/doc/bytekeys
install -d "$DOC"
install -m 0644 "$ROOT/packaging/deb/copyright" "$DOC/copyright"
gzip -9n -c "$ROOT/packaging/deb/changelog" > "$DOC/changelog.gz"
install -m 0644 "$ROOT/README.md" "$DOC/README.md"

SIZE=$(du -sk --exclude=DEBIAN "$PKG" | cut -f1)
sed -e "s|@VERSION@|$VERSION|" -e "s|@MAINTAINER@|$MAINTAINER|" -e "s|@SIZE@|$SIZE|" \
    "$ROOT/packaging/deb/control" > "$PKG/DEBIAN/control"
for script in postinst prerm postrm; do
    install -m 0755 "$ROOT/packaging/deb/$script" "$PKG/DEBIAN/$script"
done
(cd "$PKG" && find usr -type f -exec md5sum {} + | sort -k2) > "$PKG/DEBIAN/md5sums"

DEB=$OUT/bytekeys_${VERSION}_all.deb
dpkg-deb --root-owner-group -Zxz --build "$PKG" "$DEB" >/dev/null
echo "built $DEB"
if command -v lintian >/dev/null 2>&1; then
    lintian --no-tag-display-limit "$DEB" || true
fi
