#!/usr/bin/env python3
"""Regenerate every ByteKeys logo asset from data/icons/io.github.bytekeys.ByteKeys.svg.

Two steps, because they need different toolkits:

  1. wordmark (needs PySide6): turns "ByteKeys" into vector outlines and
     writes the logo/banner SVGs in data/branding/ (no font needed to view them).
  2. raster (needs PyGObject + GdkPixbuf with librsvg): renders all PNG sizes,
     favicons and the social preview image.

    python3 tools/make_icons.py raster
    <python with PySide6> tools/make_icons.py wordmark
"""

from __future__ import annotations

import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON = os.path.join(ROOT, "data/icons/io.github.bytekeys.ByteKeys.svg")
BRAND = os.path.join(ROOT, "data/branding")
WEB = os.path.join(BRAND, "web")

FONT_FAMILY, FONT_WEIGHT = "Lato", 800
TEXT_LIGHT, TEXT_DARK = "#f4f6ff", "#141a2e"
KEYS_GRADIENT = ("#3fa2ff", "#a26bff")


# ------------------------------------------------------------------ wordmark
def _svg_path(path) -> str:
    """QPainterPath -> SVG path data."""
    out, i, n = [], 0, path.elementCount()
    while i < n:
        e = path.elementAt(i)
        if e.isMoveTo():
            out.append(f"M{e.x:.2f} {e.y:.2f}")
            i += 1
        elif e.isLineTo():
            out.append(f"L{e.x:.2f} {e.y:.2f}")
            i += 1
        else:  # curveTo followed by two curveToData elements
            c1, c2 = path.elementAt(i + 1), path.elementAt(i + 2)
            out.append(f"C{e.x:.2f} {e.y:.2f} {c1.x:.2f} {c1.y:.2f} {c2.x:.2f} {c2.y:.2f}")
            i += 3
    return "".join(out) + "Z"


def _icon_body() -> tuple[str, str]:
    """(defs, drawing) of the icon SVG, ids prefixed so several copies can coexist."""
    svg = open(ICON, encoding="utf-8").read()
    defs = re.search(r"<defs>(.*?)</defs>", svg, re.S).group(1)
    body = svg.split("</defs>", 1)[1].rsplit("</svg>", 1)[0]
    return defs, body


def wordmark() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtCore, QtGui

    app = QtGui.QGuiApplication([])  # noqa: F841  (fonts need an application)
    font = QtGui.QFont(FONT_FAMILY)
    font.setPixelSize(100)
    font.setWeight(QtGui.QFont.Weight(FONT_WEIGHT))
    if QtGui.QFontInfo(font).family() != FONT_FAMILY:
        sys.exit(f"font {FONT_FAMILY!r} is not installed")
    metrics = QtGui.QFontMetricsF(font)
    byte, keys = QtGui.QPainterPath(), QtGui.QPainterPath()
    byte.addText(QtCore.QPointF(0, 0), font, "Byte")
    keys.addText(QtCore.QPointF(metrics.horizontalAdvance("Byte") - 1.5, 0), font, "Keys")
    both = byte.boundingRect().united(keys.boundingRect())
    text_w, text_h, text_top = both.width(), both.height(), both.top()
    defs, body = _icon_body()
    os.makedirs(BRAND, exist_ok=True)

    def write(name: str, width: float, height: float, icon_xform: str, text_xform: str, byte_color: str) -> None:
        grad = (f'<linearGradient id="wk" gradientUnits="userSpaceOnUse" x1="{keys.boundingRect().left():.1f}" '
                f'y1="0" x2="{keys.boundingRect().right():.1f}" y2="0">'
                f'<stop offset="0" stop-color="{KEYS_GRADIENT[0]}"/><stop offset="1" stop-color="{KEYS_GRADIENT[1]}"/>'
                f"</linearGradient>")
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
               f'viewBox="0 0 {width:.1f} {height:.1f}">\n<title>ByteKeys</title>\n'
               f"<defs>{defs}{grad}</defs>\n"
               f'<g transform="{icon_xform}">{body}</g>\n'
               f'<g transform="{text_xform}">'
               f'<path fill="{byte_color}" d="{_svg_path(byte)}"/>'
               f'<path fill="url(#wk)" d="{_svg_path(keys)}"/></g>\n</svg>\n')
        with open(os.path.join(BRAND, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print("wrote", name)

    # Stacked logo (icon above the wordmark), like the original artwork.
    scale = 0.62
    w = max(256, text_w * scale + 40)
    h = 256 + 16 + text_h * scale + 24
    tx = (w - text_w * scale) / 2
    ty = 256 + 16 - text_top * scale
    for name, color in (("bytekeys-logo.svg", TEXT_LIGHT), ("bytekeys-logo-light.svg", TEXT_DARK)):
        write(name, w, h, f"translate({(w - 256) / 2:.1f} 0)", f"translate({tx:.1f} {ty:.1f}) scale({scale})", color)

    # Horizontal banner: icon left, wordmark right.
    icon = 160
    scale = 0.95
    w = icon + 28 + text_w * scale + 20
    h = icon
    ty = (h - text_h * scale) / 2 - text_top * scale
    for name, color in (("bytekeys-banner.svg", TEXT_LIGHT), ("bytekeys-banner-light.svg", TEXT_DARK)):
        write(name, w, h, f"scale({icon / 256:.4f})", f"translate({icon + 28} {ty:.1f}) scale({scale})", color)


# -------------------------------------------------------------------- raster
def _render(src: str, width: int, height: int | None = None):
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    return GdkPixbuf.Pixbuf.new_from_file_at_scale(src, width, height or width, True)


def _save(pixbuf, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pixbuf.savev(path, "png", [], [])
    print("wrote", os.path.relpath(path, ROOT))


def _ico(paths: list[str], dest: str) -> None:
    """Windows .ico holding PNG images (supported by every current browser)."""
    blobs = [open(p, "rb").read() for p in paths]
    sizes = [struct.unpack(">II", b[16:24]) for b in blobs]
    header = struct.pack("<HHH", 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    entries = b""
    for (w, h), blob in zip(sizes, blobs):
        entries += struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    with open(dest, "wb") as f:
        f.write(header + entries + b"".join(blobs))
    print("wrote", os.path.relpath(dest, ROOT))


def raster() -> None:
    for size in (16, 24, 32, 48, 64, 128, 256, 512):
        _save(_render(ICON, size), os.path.join(ROOT, f"data/icons/png/{size}.png"))
    for size in (32, 64, 128, 256):
        _save(_render(ICON, size), os.path.join(ROOT, f"bytekeys/gui/assets/bytekeys-{size}.png"))
    # Web: favicons and app icons.
    for size, name in ((16, "favicon-16.png"), (32, "favicon-32.png"), (48, "favicon-48.png"),
                       (180, "apple-touch-icon.png"), (192, "icon-192.png"), (512, "icon-512.png")):
        _save(_render(ICON, size), os.path.join(WEB, name))
    _ico([os.path.join(WEB, f"favicon-{s}.png") for s in (16, 32, 48)], os.path.join(WEB, "favicon.ico"))
    with open(ICON, encoding="utf-8") as src, open(os.path.join(WEB, "favicon.svg"), "w", encoding="utf-8") as dst:
        dst.write(src.read())
    print("wrote data/branding/web/favicon.svg")
    # Logos.
    for name in ("bytekeys-logo", "bytekeys-banner"):
        svg = os.path.join(BRAND, f"{name}.svg")
        if os.path.exists(svg):
            _save(_render(svg, 1024 if name.endswith("logo") else 1280, 2000), os.path.join(BRAND, f"{name}.png"))
    _social_preview()


def _social_preview() -> None:
    """1280x640 image for the GitHub repository's social preview."""
    banner = os.path.join(BRAND, "bytekeys-banner.svg")
    if not os.path.exists(banner):
        return
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    canvas = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 1280, 640)
    canvas.fill(0x0E1220FF)
    logo = _render(banner, 900, 300)
    x = (1280 - logo.get_width()) // 2
    y = (640 - logo.get_height()) // 2
    logo.composite(canvas, x, y, logo.get_width(), logo.get_height(), x, y, 1, 1,
                   GdkPixbuf.InterpType.BILINEAR, 255)
    _save(canvas, os.path.join(BRAND, "social-preview.png"))


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "raster"
    {"wordmark": wordmark, "raster": raster}[step]()
