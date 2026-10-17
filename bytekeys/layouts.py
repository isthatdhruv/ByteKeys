"""Keyboard geometry used to draw keyboards and to map zones to keys.

Units are key widths; one row is one unit high. Two generic laptop layouts
are provided: ``full`` (with numpad, 19.5 units wide) and ``compact``
(15 units wide).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Key:
    label: str
    x: float
    y: float
    w: float = 1.0
    h: float = 1.0
    numpad: bool = False

    @property
    def cx(self) -> float:
        return self.x + self.w / 2


def _row(y: int, start: float, keys: list) -> list[Key]:
    out, x = [], start
    for item in keys:
        label, w = (item, 1.0) if isinstance(item, str) else item
        if label:
            out.append(Key(label, x, y, w))
        x += w
    return out


def _main_block() -> list[Key]:
    keys: list[Key] = []
    keys += _row(0, 0, ["Esc"] + [f"F{i}" for i in range(1, 13)] + ["PrtSc", "Del"])
    keys += _row(1, 0, ["`", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=", ("Backspace", 2)])
    keys += _row(2, 0, [("Tab", 1.5), "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "[", "]", ("\\", 1.5)])
    keys += _row(3, 0, [("Caps", 1.75), "A", "S", "D", "F", "G", "H", "J", "K", "L", ";", "'", ("Enter", 2.25)])
    keys += _row(4, 0, [("Shift", 2), "Z", "X", "C", "V", "B", "N", "M", ",", ".", "/", ("Shift ", 1), "Up"])
    keys += _row(5, 0, [("Ctrl", 1.25), "Fn", "Win", ("Alt", 1.25), ("Space", 4.5), "AltGr", "Menu",
                        "Ctrl ", "Left", "Down", "Right"])
    return keys


def _numpad(x: float) -> list[Key]:
    def k(label, col, row, w=1.0, h=1.0):
        return Key(label, x + col, row, w, h, numpad=True)
    return [
        k("Home", 0, 0), k("PgUp", 1, 0), k("PgDn", 2, 0), k("End", 3, 0),
        k("Num", 0, 1), k("/ ", 1, 1), k("*", 2, 1), k("- ", 3, 1),
        k("7 ", 0, 2), k("8 ", 1, 2), k("9 ", 2, 2), k("+", 3, 2, h=2),
        k("4 ", 0, 3), k("5 ", 1, 3), k("6 ", 2, 3),
        k("1 ", 0, 4), k("2 ", 1, 4), k("3 ", 2, 4), k("Enter ", 3, 4, h=2),
        k("0 ", 0, 5, w=2), k(". ", 2, 5),
    ]


LAYOUTS: dict[str, list[Key]] = {
    "compact": _main_block(),
    "full": _main_block() + _numpad(15.5),
}


def get(name: str) -> list[Key]:
    return LAYOUTS.get(name, LAYOUTS["compact"])


def width(keys: list[Key]) -> float:
    return max(k.x + k.w for k in keys)


def height(keys: list[Key]) -> float:
    return max(k.y + k.h for k in keys)


def zone_of(key: Key, zones: int, keys: list[Key]) -> int:
    """Which of *zones* left-to-right zones a key belongs to."""
    if zones <= 1:
        return 0
    has_numpad = any(k.numpad for k in keys)
    if zones == 4 and has_numpad:
        if key.numpad:
            return 3
        return min(2, int(key.cx / 5.0))
    return min(zones - 1, int(key.cx / width(keys) * zones))


def matrix_of(keys: list[Key]) -> list[tuple[int, int]]:
    """(row, column) of each key when the keys are packed into a matrix."""
    positions = []
    cols: dict[int, int] = {}
    for key in sorted(keys, key=lambda k: (k.y, k.x)):
        row = int(key.y)
        positions.append((key, row, cols.get(row, 0)))
        cols[row] = cols.get(row, 0) + 1
    order = {id(k): (r, c) for k, r, c in positions}
    return [order[id(k)] for k in keys]
