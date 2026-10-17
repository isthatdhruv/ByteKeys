#!/usr/bin/env python3
"""Regenerate every ByteKeys logo asset from data/icons/io.github.isthatdhruv.ByteKeys.svg.

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
ICON = os.path.join(ROOT, "data/icons/io.github.isthatdhruv.ByteKeys.svg")
BRAND = os.path.join(ROOT, "data/branding")
WEB = os.path.join(BRAND, "web")

FONT_FAMILY, FONT_WEIGHT = "Lato", 700
TEXT_LIGHT, TEXT_DARK = "#f6f6f8", "#121215"
KEYS_GRADIENT = {"dark": ("#dcdce2", "#7f7f89"), "light": ("#55555f", "#9a9aa5")}
TAGLINE = "CONTROL YOUR KEYBOARD LIGHTING"
TAGLINE_COLOR = {"dark": "#b4b4bc", "light": "#6a6a75"}


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
    small = QtGui.QFont(FONT_FAMILY)
    small.setPixelSize(15)
    small.setWeight(QtGui.QFont.Weight(400))
    small.setLetterSpacing(QtGui.QFont.SpacingType.AbsoluteSpacing, 6)
    tagline = QtGui.QPainterPath()
    tagline.addText(QtCore.QPointF(0, 0), small, TAGLINE)
    tag_rect = tagline.boundingRect()
    defs, body = _icon_body()
    os.makedirs(BRAND, exist_ok=True)

    def write(name: str, width: float, height: float, icon_xform: str, text_xform: str, byte_color: str,
              tag_xform: str | None = None) -> None:
        variant = "light" if byte_color == TEXT_DARK else "dark"
        g0, g1 = KEYS_GRADIENT[variant]
        grad = (f'<linearGradient id="wk" gradientUnits="userSpaceOnUse" x1="{keys.boundingRect().left():.1f}" '
                f'y1="{keys.boundingRect().top():.1f}" x2="{keys.boundingRect().right():.1f}" '
                f'y2="{keys.boundingRect().bottom():.1f}">'
                f'<stop offset="0" stop-color="{g0}"/><stop offset="1" stop-color="{g1}"/>'
                f"</linearGradient>")
        tag = (f'<g transform="{tag_xform}"><path fill="{TAGLINE_COLOR[variant]}" d="{_svg_path(tagline)}"/></g>\n'
               if tag_xform else "")
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
               f'viewBox="0 0 {width:.1f} {height:.1f}">\n<title>ByteKeys</title>\n'
               f"<defs>{defs}{grad}</defs>\n"
               f'<g transform="{icon_xform}">{body}</g>\n'
               f'<g transform="{text_xform}">'
               f'<path fill="{byte_color}" d="{_svg_path(byte)}"/>'
               f'<path fill="url(#wk)" d="{_svg_path(keys)}"/></g>\n{tag}</svg>\n')
        with open(os.path.join(BRAND, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print("wrote", name)

    # Stacked logo: icon, wordmark, tagline (like the original artwork).
    scale = 0.62
    w = max(256, text_w * scale + 40, tag_rect.width() + 40)
    text_y = 256 + 14
    tag_y = text_y + text_h * scale + 26
    h = tag_y + tag_rect.height() + 10
    tx = (w - text_w * scale) / 2
    for name, color in (("bytekeys-logo.svg", TEXT_LIGHT), ("bytekeys-logo-light.svg", TEXT_DARK)):
        write(name, w, h, f"translate({(w - 256) / 2:.1f} 0)",
              f"translate({tx:.1f} {text_y - text_top * scale:.1f}) scale({scale})", color,
              f"translate({(w - tag_rect.width()) / 2 - tag_rect.left():.1f} {tag_y - tag_rect.top():.1f})")

    # Horizontal banner: icon left, wordmark and tagline right.
    icon = 160
    scale = 0.95
    w = icon + 24 + max(text_w * scale, tag_rect.width() * 0.9) + 20
    h = icon
    block = text_h * scale + 14 + tag_rect.height() * 0.9
    ty = (h - block) / 2 - text_top * scale
    tag_y = (h - block) / 2 + text_h * scale + 14 - tag_rect.top() * 0.9
    for name, color in (("bytekeys-banner.svg", TEXT_LIGHT), ("bytekeys-banner-light.svg", TEXT_DARK)):
        write(name, w, h, f"scale({icon / 256:.4f})", f"translate({icon + 24} {ty:.1f}) scale({scale})", color,
              f"translate({icon + 26} {tag_y:.1f}) scale(0.9)")


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


def _backdrop(width: int, height: int):
    """Near-black canvas with warm light in two corners, like the logo artwork."""
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
           '<defs><radialGradient id="a" cx="0" cy="0" r="0.75"><stop offset="0" stop-color="#6e604e" '
           'stop-opacity="0.65"/><stop offset="1" stop-color="#6e604e" stop-opacity="0"/></radialGradient>'
           '<radialGradient id="b" cx="1" cy="1" r="0.7"><stop offset="0" stop-color="#7a6c5a" '
           'stop-opacity="0.55"/><stop offset="1" stop-color="#7a6c5a" stop-opacity="0"/></radialGradient></defs>'
           f'<rect width="{width}" height="{height}" fill="#0b0b0d"/>'
           f'<rect width="{width}" height="{height}" fill="url(#a)"/><rect width="{width}" height="{height}" fill="url(#b)"/>'
           '</svg>')
    loader = GdkPixbuf.PixbufLoader.new_with_type("svg")
    loader.write(svg.encode())
    loader.close()
    return loader.get_pixbuf()


def _social_preview() -> None:
    """1280x640 image for the GitHub repository's social preview."""
    banner = os.path.join(BRAND, "bytekeys-banner.svg")
    if not os.path.exists(banner):
        return
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    canvas = _backdrop(1280, 640)
    logo = _render(banner, 900, 300)
    x = (1280 - logo.get_width()) // 2
    y = (640 - logo.get_height()) // 2
    logo.composite(canvas, x, y, logo.get_width(), logo.get_height(), x, y, 1, 1,
                   GdkPixbuf.InterpType.BILINEAR, 255)
    _save(canvas, os.path.join(BRAND, "social-preview.png"))


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "raster"
    {"wordmark": wordmark, "raster": raster}[step]()
