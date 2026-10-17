"""Small color toolkit: parsing, formatting and blending of 8-bit RGB."""

from __future__ import annotations

import colorsys
from typing import Iterable, Sequence, Tuple, Union

RGB = Tuple[int, int, int]
ColorLike = Union[str, Sequence[int]]

BLACK: RGB = (0, 0, 0)
WHITE: RGB = (255, 255, 255)

NAMED: dict[str, RGB] = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "yellow": (255, 220, 0),
    "orange": (255, 110, 0),
    "amber": (255, 170, 0),
    "purple": (140, 40, 255),
    "violet": (124, 92, 255),
    "pink": (255, 60, 160),
    "teal": (0, 200, 170),
    "lime": (140, 255, 0),
    "warm": (255, 160, 80),
    "cool": (200, 230, 255),
}

# Palette offered by the UIs as one-click swatches.
SWATCHES: list[str] = [
    "#ffffff", "#ffd7a8", "#ff3b30", "#ff9500", "#ffcc00", "#34c759",
    "#00c7be", "#30b0ff", "#007aff", "#5856d6", "#af52de", "#ff2d92",
]


def clamp8(v: float) -> int:
    return 0 if v <= 0 else 255 if v >= 255 else int(round(v))


def parse(value: ColorLike) -> RGB:
    """Parse '#rrggbb', 'rrggbb', '#rgb', 'r,g,b', a color name or a 3-sequence."""
    if isinstance(value, (tuple, list)):
        if len(value) != 3:
            raise ValueError(f"expected 3 components, got {value!r}")
        return (clamp8(value[0]), clamp8(value[1]), clamp8(value[2]))
    if not isinstance(value, str):
        raise ValueError(f"not a color: {value!r}")
    text = value.strip().lower()
    if text in NAMED:
        return NAMED[text]
    if "," in text:
        parts = [p.strip() for p in text.split(",")]
        if len(parts) == 3:
            return (clamp8(int(parts[0])), clamp8(int(parts[1])), clamp8(int(parts[2])))
        raise ValueError(f"not a color: {value!r}")
    if text.startswith("#"):
        text = text[1:]
    elif text.startswith("0x"):
        text = text[2:]
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        raise ValueError(f"not a color: {value!r}")
    try:
        n = int(text, 16)
    except ValueError:
        raise ValueError(f"not a color: {value!r}") from None
    return ((n >> 16) & 0xFF, (n >> 8) & 0xFF, n & 0xFF)


def is_color(value: object) -> bool:
    try:
        parse(value)  # type: ignore[arg-type]
        return True
    except (ValueError, TypeError):
        return False


def to_hex(c: RGB) -> str:
    return "#%02x%02x%02x" % (clamp8(c[0]), clamp8(c[1]), clamp8(c[2]))


def normalize(value: ColorLike) -> str:
    """Return the canonical '#rrggbb' form of any accepted color value."""
    return to_hex(parse(value))


def scale(c: RGB, factor: float) -> RGB:
    return (clamp8(c[0] * factor), clamp8(c[1] * factor), clamp8(c[2] * factor))


def lerp(a: RGB, b: RGB, t: float) -> RGB:
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return (
        clamp8(a[0] + (b[0] - a[0]) * t),
        clamp8(a[1] + (b[1] - a[1]) * t),
        clamp8(a[2] + (b[2] - a[2]) * t),
    )


def gradient(stops: Sequence[RGB], t: float) -> RGB:
    """Sample a multi-stop gradient at t in [0, 1]."""
    if not stops:
        return BLACK
    if len(stops) == 1:
        return stops[0]
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    pos = t * (len(stops) - 1)
    i = min(int(pos), len(stops) - 2)
    return lerp(stops[i], stops[i + 1], pos - i)


def hsv(h: float, s: float = 1.0, v: float = 1.0) -> RGB:
    """HSV to RGB; hue wraps around [0, 1)."""
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (clamp8(r * 255), clamp8(g * 255), clamp8(b * 255))


def to_hsv(c: RGB) -> tuple[float, float, float]:
    return colorsys.rgb_to_hsv(c[0] / 255.0, c[1] / 255.0, c[2] / 255.0)


def luminance(c: RGB) -> float:
    """Approximate perceived brightness in [0, 1]."""
    return (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255.0


def average(colors: Iterable[RGB]) -> RGB:
    colors = list(colors)
    if not colors:
        return BLACK
    n = len(colors)
    return (
        clamp8(sum(c[0] for c in colors) / n),
        clamp8(sum(c[1] for c in colors) / n),
        clamp8(sum(c[2] for c in colors) / n),
    )
