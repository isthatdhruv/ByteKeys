#!/usr/bin/env bash
# Build dist/ByteKeys-<version>-<arch>.AppImage: a relocatable CPython
# (python-build-standalone), the PySide6 Qt binding and ByteKeys itself.
#
# Environment:
#   ARCH          x86_64 (default: uname -m) or aarch64
#   PY_VERSION    bundled Python minor version (default 3.12)
#   QT_PACKAGE    pip requirement for the Qt binding (default PySide6-Essentials)
#   PBS_URL       explicit python-build-standalone tarball URL (skips the GitHub lookup)
#   CACHE_DIR     where downloads are kept between builds (default build/cache)
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
ARCH=${ARCH:-$(uname -m)}
PY_VERSION=${PY_VERSION:-3.12}
QT_PACKAGE=${QT_PACKAGE:-PySide6-Essentials}
CACHE=${CACHE_DIR:-$ROOT/build/cache}
BUILD=$ROOT/build/appimage
APPDIR=$BUILD/AppDir
OUT=${OUT:-$ROOT/dist}
APP_ID=io.github.isthatdhruv.ByteKeys
VERSION=$(PYTHONPATH="$ROOT" python3 -c "import bytekeys; print(bytekeys.__version__)")

mkdir -p "$CACHE" "$OUT"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib/bytekeys" "$APPDIR/usr/share/metainfo"

# --- 1. Python ---------------------------------------------------------------
if [ -z "${PBS_URL:-}" ]; then
    echo "Looking up python-build-standalone $PY_VERSION for $ARCH..."
    AUTH=()
    [ -n "${GITHUB_TOKEN:-}" ] && AUTH=(-H "Authorization: Bearer $GITHUB_TOKEN")
    PBS_URL=$(curl -fsSL "${AUTH[@]}" https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest |
        python3 -c '
import json, re, sys
ver, arch = sys.argv[1], sys.argv[2]
pattern = re.compile(r"cpython-%s\.\d+\+\d+-%s-unknown-linux-gnu-install_only_stripped\.tar\.gz$" % (re.escape(ver), arch))
assets = json.load(sys.stdin)["assets"]
print(next(a["browser_download_url"] for a in assets if pattern.search(a["name"])))
' "$PY_VERSION" "$ARCH")
fi
TARBALL=$CACHE/$(basename "$PBS_URL")
[ -f "$TARBALL" ] || curl -fL --retry 3 -o "$TARBALL" "$PBS_URL"
tar -xzf "$TARBALL" -C "$APPDIR/usr"          # -> usr/python
PY=$APPDIR/usr/python/bin/python3
"$PY" --version

# --- 2. Qt binding -------------------------------------------------------------
PIP_CACHE=$CACHE/pip
"$PY" -m pip install --disable-pip-version-check --no-warn-script-location \
    --cache-dir "$PIP_CACHE" --no-compile "$QT_PACKAGE"
SITE=$("$PY" -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")
# Drop Qt parts ByteKeys never loads (QML/Quick, PDF, Designer tooling, examples, headers).
if [ -d "$SITE/PySide6" ]; then
    Q=$SITE/PySide6
    rm -rf "$Q/Qt/qml" "$Q/include" "$Q/typesystems" "$Q/glue" "$Q/examples" "$Q/scripts" \
           "$Q"/Qt/libexec "$Q"/Qt/translations/qtwebengine* "$Q"/assistant "$Q"/designer \
           "$Q"/linguist "$Q"/lrelease "$Q"/lupdate "$Q"/qmllint "$Q"/qmlformat "$Q"/qmlls \
           "$Q"/balsam* "$Q"/rcc "$Q"/uic "$Q"/qmlcachegen "$Q"/qmlimportscanner "$Q"/qmltyperegistrar \
           "$Q"/svgtoqml "$Q"/metaobjectdump.py "$Q"/project.py
    for lib in Quick Qml QmlModels QmlWorkerScript QmlMeta QuickControls2 QuickTemplates2 QuickWidgets \
               QuickShapes QuickTest QuickDialogs2 QuickLayouts Pdf PdfQuick Designer DesignerComponents \
               UiTools Help ShaderTools Test Sql; do
        rm -f "$Q"/Qt/lib/libQt6"$lib".so* "$Q"/Qt"$lib".*.so "$Q"/Qt"$lib".pyi
    done
    rm -rf "$Q"/Qt/plugins/{qmltooling,sqldrivers,designer,qmllint,scenegraph}
fi
find "$SITE" -name '__pycache__' -prune -exec rm -rf {} +

# --- 3. ByteKeys ----------------------------------------------------------------
(cd "$ROOT" && find bytekeys -name '__pycache__' -prune -o -type f \( -name '*.py' -o -name '*.png' \) -print) |
while read -r f; do
    install -D -m 0644 "$ROOT/$f" "$APPDIR/usr/lib/bytekeys/$f"
done
# The AppImage is read-only at run time, so compile everything now.
"$PY" -m compileall -q -j 0 "$APPDIR/usr/lib/bytekeys" "$SITE" >/dev/null || true

# Check the Qt platform plugins still find all their Qt libraries.
if command -v ldd >/dev/null; then
    missing=$(find "$SITE" -path '*plugins/platforms/*.so' -exec ldd {} \; 2>/dev/null | grep 'libQt6.*not found' || true)
    if [ -n "$missing" ]; then
        echo "error: trimmed too much, Qt plugins miss libraries:" >&2
        echo "$missing" >&2
        exit 1
    fi
fi

# --- 4. AppDir metadata ------------------------------------------------------
install -m 0755 "$ROOT/packaging/appimage/AppRun" "$APPDIR/AppRun"
sed 's/^Exec=.*/Exec=bytekeys-gui/' "$ROOT/data/desktop/$APP_ID.desktop" > "$APPDIR/$APP_ID.desktop"
install -m 0644 "$ROOT/data/icons/png/256.png" "$APPDIR/$APP_ID.png"
install -D -m 0644 "$ROOT/data/icons/$APP_ID.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg"
install -D -m 0644 "$ROOT/data/icons/png/256.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_ID.png"
ln -sf "$APP_ID.png" "$APPDIR/.DirIcon"
install -m 0644 "$ROOT/data/desktop/$APP_ID.metainfo.xml" "$APPDIR/usr/share/metainfo/$APP_ID.appdata.xml"

# --- 5. Pack ------------------------------------------------------------------------
TOOL=$CACHE/appimagetool-$ARCH.AppImage
if [ ! -x "$TOOL" ]; then
    curl -fL --retry 3 -o "$TOOL" \
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$ARCH.AppImage"
    chmod +x "$TOOL"
fi
TARGET=$OUT/ByteKeys-$VERSION-$ARCH.AppImage
rm -f "$TARGET"
ARCH=$ARCH APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$APPDIR" "$TARGET"
echo "built $TARGET ($(du -h "$TARGET" | cut -f1))"
