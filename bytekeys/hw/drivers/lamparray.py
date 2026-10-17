"""HID LampArray ("Dynamic Lighting"): the vendor-neutral lighting standard.

Usage page 0x59 (Lighting And Illumination). The device describes itself:
how many lamps it has, where each lamp sits and which key it lights. Colors
are sent with LampRangeUpdate (one color for a range of lamps) or
LampMultiUpdate (individual lamps). Report IDs and field sizes come from the
report descriptor, so nothing here is model specific. Used by TUXEDO NB04
laptops (mainline virtual device), some 2025 ASUS and Lenovo laptops, and
external keyboards.
"""

from __future__ import annotations

from ..base import ColorMode, DeviceError, Frame, ZoneInfo
from ..hid import HidKeyboard

PAGE = 0x59
U = lambda usage: (PAGE << 16) | usage  # noqa: E731

LAMP_ARRAY = 0x01
ATTRIBUTES_REPORT, LAMP_COUNT, KIND, MIN_INTERVAL = U(0x02), U(0x03), U(0x07), U(0x08)
ATTR_REQUEST_REPORT, LAMP_ID = U(0x20), U(0x21)
ATTR_RESPONSE_REPORT, POS_X, POS_Y = U(0x22), U(0x23), U(0x24)
INPUT_BINDING = U(0x2D)
MULTI_UPDATE_REPORT, RED, GREEN, BLUE, INTENSITY, UPDATE_FLAGS = U(0x50), U(0x51), U(0x52), U(0x53), U(0x54), U(0x55)
RANGE_UPDATE_REPORT, LAMP_ID_START, LAMP_ID_END = U(0x60), U(0x61), U(0x62)
CONTROL_REPORT, AUTONOMOUS_MODE = U(0x70), U(0x71)

KIND_KEYBOARD, KIND_CHASSIS = 1, 7
FLAG_UPDATE_COMPLETE = 0x01

# HID keyboard usages (page 0x07) for lamp labels.
_KEYS = {0x28: "Enter", 0x29: "Esc", 0x2A: "Bksp", 0x2B: "Tab", 0x2C: "Space", 0x2D: "-", 0x2E: "=",
         0x2F: "[", 0x30: "]", 0x31: "\\", 0x33: ";", 0x34: "'", 0x35: "`", 0x36: ",", 0x37: ".",
         0x38: "/", 0x39: "Caps", 0x46: "PrtSc", 0x49: "Ins", 0x4A: "Home", 0x4B: "PgUp", 0x4C: "Del",
         0x4D: "End", 0x4E: "PgDn", 0x4F: "→", 0x50: "←", 0x51: "↓", 0x52: "↑", 0x53: "Num",
         0xE0: "Ctrl", 0xE1: "Shift", 0xE2: "Alt", 0xE3: "Win", 0xE4: "Ctrl", 0xE5: "Shift",
         0xE6: "AltGr", 0xE7: "Win", 0x65: "Menu"}


def key_name(usage: int) -> str | None:
    if 0x04 <= usage <= 0x1D:
        return chr(ord("A") + usage - 0x04)
    if 0x1E <= usage <= 0x26:
        return str(usage - 0x1D)
    if usage == 0x27:
        return "0"
    if 0x3A <= usage <= 0x45:
        return f"F{usage - 0x39}"
    if 0x54 <= usage <= 0x63:
        return ["/", "*", "-", "+", "Ent", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "."][usage - 0x54]
    return _KEYS.get(usage)


def _rows(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Group lamps into rows by Y position and number the columns by X."""
    if not points:
        return []
    ys = sorted({y for _x, y in points})
    span = (ys[-1] - ys[0]) or 1
    gap = max(span / 12, 1)
    row_of_y: dict[int, int] = {}
    row, last = 0, ys[0]
    for y in ys:
        if y - last > gap:
            row += 1
        row_of_y[y] = row
        last = y
    rows = [row_of_y[y] for _x, y in points]
    out = [(0, 0)] * len(points)
    for r in set(rows):
        members = sorted((points[i][0], i) for i in range(len(points)) if rows[i] == r)
        for col, (_x, i) in enumerate(members):
            out[i] = (r, col)
    return out


class LampArray(HidKeyboard):
    DRIVER = "lamparray"
    VENDOR = "HID LampArray"
    PRODUCTS: dict = {}

    @classmethod
    def score(cls, info) -> int:
        reps = info.reports
        if (PAGE, LAMP_ARRAY) not in reps.applications:
            return 0
        needed = (ATTRIBUTES_REPORT, CONTROL_REPORT)
        if all(reps.report_for("feature", c) is not None for c in needed):
            return 2
        return 0

    def __init__(self, info, transport_factory=None):
        super().__init__(info, transport_factory)
        self.id = f"hid:{info.vid:04x}:{info.pid:04x}:lamparray"
        self.name = info.name or "LampArray Keyboard"
        self.vendor = ""
        self.experimental = True
        self.brightness_hw = False
        self.brightness_max = 100
        reps = info.reports
        self._r_attr = reps.report_for("feature", ATTRIBUTES_REPORT)
        self._r_req = reps.report_for("feature", ATTR_REQUEST_REPORT)
        self._r_resp = reps.report_for("feature", ATTR_RESPONSE_REPORT)
        self._r_multi = reps.report_for("feature", MULTI_UPDATE_REPORT)
        self._r_range = reps.report_for("feature", RANGE_UPDATE_REPORT)
        self._r_ctrl = reps.report_for("feature", CONTROL_REPORT)
        self._lamps = 0
        self._probed = False
        self._host_control = False
        # Until probed (needs device access), present a single-zone RGB device.
        self.color_mode = ColorMode.SINGLE
        if transport_factory is not None or self.access_problem() is None:
            try:
                self._probe()
            except DeviceError as e:
                self.error = str(e)

    # ---------------------------------------------------------------- helpers
    def _get(self, report_id: int) -> dict[int, list[int]]:
        size = self.info.reports.feature[report_id]
        data = self._io(self.transport.get_feature, report_id, size)
        return self.info.reports.unpack("feature", report_id, data)

    def _set(self, report_id: int, values: dict[int, list[int]]) -> None:
        self._feature(self.info.reports.pack("feature", report_id, values))

    def _probe(self) -> None:
        attrs = self._get(self._r_attr)
        self._lamps = (attrs.get(LAMP_COUNT) or [0])[0]
        kind = (attrs.get(KIND) or [0])[0]
        interval_us = (attrs.get(MIN_INTERVAL) or [0])[0]
        if interval_us:
            self.max_fps = max(1, min(60, int(1_000_000 / interval_us)))
        if kind not in (KIND_KEYBOARD, KIND_CHASSIS, 0):
            self.notes.append(f"LampArray kind {kind} (not a keyboard).")
        positions: list[tuple[int, int]] = []
        labels: list[str | None] = []
        if self._r_req is not None and self._r_resp is not None and self._lamps:
            self._set(self._r_req, {LAMP_ID: [0]})
            for _ in range(self._lamps):
                lamp = self._get(self._r_resp)
                positions.append(((lamp.get(POS_X) or [0])[0], (lamp.get(POS_Y) or [0])[0]))
                labels.append(key_name((lamp.get(INPUT_BINDING) or [0])[0]))
        if self._lamps > 1:
            self.color_mode = ColorMode.PERKEY if self._lamps > 8 else ColorMode.ZONES
            grid = _rows(positions) if positions else [(i // 16, i % 16) for i in range(self._lamps)]
            self.zones = [ZoneInfo(i, labels[i] if i < len(labels) and labels[i] else f"Lamp {i + 1}",
                                   grid[i][0], grid[i][1], labels[i] if i < len(labels) else None)
                          for i in range(self._lamps)]
            self.matrix = (max(r for r, _ in grid) + 1, max(c for _, c in grid) + 1)
            self.layout = "perkey-matrix" if self._lamps > 8 else "zones"
        self._probed = True

    def _take_control(self) -> None:
        if not self._host_control:
            self._set(self._r_ctrl, {AUTONOMOUS_MODE: [0]})
            self._host_control = True

    # ------------------------------------------------------------------ frames
    def _show(self, frame: Frame, prev: Frame | None) -> None:
        if not self._probed:
            self._probe()
        self._take_control()
        factor = frame.level / 100.0 if frame.on else 0.0
        n = max(1, self._lamps)
        base = frame.colors or [(255, 255, 255)]
        colors = [tuple(int(c * factor) for c in base[min(i, len(base) - 1)]) for i in range(n)]
        if len(set(colors)) == 1 and self._r_range is not None:
            r, g, b = colors[0]
            self._set(self._r_range, {UPDATE_FLAGS: [FLAG_UPDATE_COMPLETE], LAMP_ID_START: [0],
                                      LAMP_ID_END: [n - 1], RED: [r], GREEN: [g], BLUE: [b],
                                      INTENSITY: [255]})
            return
        if self._r_multi is None:
            raise DeviceError("this LampArray device has no per-lamp update report")
        per_report = sum(1 for e in self.info.reports.layouts[("feature", self._r_multi)] if e.usage == LAMP_ID)
        per_report = max(1, per_report)
        for start in range(0, n, per_report):
            ids = list(range(start, min(n, start + per_report)))
            chunk = [colors[i] for i in ids]
            last = start + per_report >= n
            self._set(self._r_multi, {
                LAMP_COUNT: [len(ids)], UPDATE_FLAGS: [FLAG_UPDATE_COMPLETE if last else 0],
                LAMP_ID: ids, RED: [c[0] for c in chunk], GREEN: [c[1] for c in chunk],
                BLUE: [c[2] for c in chunk], INTENSITY: [255] * len(ids),
            })
