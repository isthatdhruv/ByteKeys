"""Lenovo Legion / LOQ / IdeaPad Gaming 4-zone RGB keyboards (ITE, 048d:c9xx).

A single 33-byte feature report (ID 0xCC, usage page 0xFF89 / usage 0xCC)
carries the complete lighting state: effect, speed, brightness and the four
zone colors. There is no init, commit or save command, and the controller is
streamed at high rates by other tools without trouble, so software effects
are fine. Protocol as documented by L5P-Keyboard-RGB, LegionAura, OpenRGB and
Lenovo Legion Toolkit.
"""

from __future__ import annotations

from ..base import ColorMode, DeviceError, EffectInfo, Frame, Param, ZoneInfo
from ..hid import HidKeyboard

REPORT_ID = 0xCC
REPORT_LEN = 33
USAGE = (0xFF89, 0x00CC)

EFFECT_STATIC = 0x01
HW_EFFECTS = {"breath": 0x03, "wave": 0x04, "smooth": 0x06}

SPEED = Param("speed", "Speed", "choice", default="2",
              choices=[["1", "Slowest"], ["2", "Slow"], ["3", "Fast"], ["4", "Fastest"]])
DIRECTION = Param("direction", "Direction", "choice", default="right",
                  choices=[["right", "Left to right"], ["left", "Right to left"]])


class Lenovo4Zone(HidKeyboard):
    DRIVER = "lenovo-4zone"
    VENDOR = "Lenovo"
    PRODUCTS = {
        (0x048D, 0xC955): "Legion 4-Zone Keyboard (2020)",
        (0x048D, 0xC963): "IdeaPad Gaming Keyboard (2021)",
        (0x048D, 0xC965): "Legion 4-Zone Keyboard (2021)",
        (0x048D, 0xC973): "IdeaPad Gaming Keyboard (2022)",
        (0x048D, 0xC975): "Legion 4-Zone Keyboard (2022)",
        (0x048D, 0xC983): "LOQ Keyboard (2023)",
        (0x048D, 0xC984): "Legion 4-Zone Keyboard (2023)",
        (0x048D, 0xC985): "Legion Pro 4-Zone Keyboard (2023)",
        (0x048D, 0xC993): "LOQ Keyboard (2024)",
        (0x048D, 0xC994): "Legion 4-Zone Keyboard (2024)",
        (0x048D, 0xC995): "Legion Pro 4-Zone Keyboard (2024)",
    }

    @classmethod
    def score(cls, info) -> int:
        if info.vid != 0x048D or info.pid & 0xFF00 != 0xC900:
            return 0
        rep = info.reports
        if USAGE in rep.applications and rep.feature.get(REPORT_ID) == REPORT_LEN:
            return 3
        # Unknown descriptor (unreadable): trust the product list only.
        if not rep.applications and (info.vid, info.pid) in cls.PRODUCTS:
            return 1
        return 0

    def __init__(self, info, transport_factory=None):
        super().__init__(info, transport_factory)
        if (info.vid, info.pid) not in self.PRODUCTS:
            self.name = "Lenovo 4-Zone Keyboard"
            self.experimental = True
            self.notes.append("Unlisted model detected by its report layout; please report whether it works.")
        self.color_mode = ColorMode.ZONES
        self.zones = [ZoneInfo(i, n) for i, n in enumerate(["Left", "Left center", "Right center", "Right"])]
        self.layout = "zones"
        self.brightness_max = 2          # off / low / high
        self.readable = True
        self.max_fps = 30
        self.hw_effects = [
            EffectInfo("breath", "Breathing", True, [SPEED],
                       description="The keyboard breathes in the zone colors"),
            EffectInfo("smooth", "Color cycle", True, [SPEED],
                       description="The keyboard cycles smoothly through all colors"),
            EffectInfo("wave", "Rainbow wave", True, [SPEED, DIRECTION],
                       description="A rainbow travels across the four zones"),
        ]
        self._last_report: bytes | None = None
        self._read_failures = 0

    def report(self, frame: Frame) -> bytes:
        buf = bytearray(REPORT_LEN)
        buf[0], buf[1] = REPORT_ID, 0x16
        if not frame.on or frame.level <= 0:
            return bytes(buf)                    # effect 0, brightness 0: off
        effect, speed = EFFECT_STATIC, 1
        if frame.effect in HW_EFFECTS:
            effect = HW_EFFECTS[frame.effect]
            try:
                speed = max(1, min(4, int(frame.params.get("speed", 2))))
            except (TypeError, ValueError):
                speed = 2
        buf[2], buf[3], buf[4] = effect, speed, max(1, min(2, frame.level))
        if effect in (EFFECT_STATIC, HW_EFFECTS["breath"]):
            colors = frame.colors or [(255, 255, 255)]
            for zone in range(4):
                r, g, b = colors[min(zone, len(colors) - 1)]
                buf[5 + 3 * zone:8 + 3 * zone] = bytes((r, g, b))
        if effect == HW_EFFECTS["wave"]:
            buf[19 if frame.params.get("direction") == "left" else 18] = 1
        return bytes(buf)

    def _show(self, frame: Frame, prev: Frame | None) -> None:
        data = self.report(frame)
        if prev is None or data != self._last_report:
            self._feature(data)
            self._last_report = data

    def read_level(self) -> int | None:
        if self._read_failures >= 3:
            return None
        try:
            data = self._io(self.transport.get_feature, REPORT_ID, REPORT_LEN)
        except DeviceError:
            self._read_failures += 1
            return None
        if len(data) < 5 or data[1] != 0x16:
            return None
        return 0 if data[2] == 0 else max(0, min(2, data[4]))   # Fn+Space changes this
