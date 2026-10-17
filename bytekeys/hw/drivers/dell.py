"""Dell G-series and Alienware 4-zone keyboards ("AW-ELC", 187c:0550/0551).

Every command is a 33-byte payload starting with 0x03 (hidraw buffer = 0x00
report ID + payload), sent as a feature report and followed by reading the
controller's reply. Colors are programmed as a temporary "running" animation
(ID 0xFFFF) that is *played*, never *saved*: the save, default and startup
commands write the controller's flash and are never used. The controller is
slow (about a second per change), so software animations are throttled hard.
Protocol per alienfx-tools, awelc-ctl and OpenRGB; command 0xFF erases flash
and 0x28 resets the controller, so neither exists in this file.
"""

from __future__ import annotations

import time

from ..base import ColorMode, DeviceError, EffectInfo, Feature, Frame, Param, ZoneInfo
from ..hid import HidKeyboard

ANIM_RUNNING = 0xFFFF
ACT_COLOR, ACT_PULSE = 0x00, 0x01
# Platform IDs whose keyboard zones are numbered 0x10-0x13 (OpenRGB's table).
HIGH_ZONE_PLATFORMS = {0x0E07, 0x0E0A}

SPEED = Param("speed", "Speed", "range", default=50, min=0, max=100)


class DellElc(HidKeyboard):
    DRIVER = "dell-elc"
    VENDOR = "Dell"
    PRODUCTS = {
        (0x187C, 0x0550): "Dell / Alienware 4-Zone Keyboard",
        (0x187C, 0x0551): "Alienware 4-Zone Keyboard",
    }
    COMMAND_DELAY = 0.06
    PLAY_DELAY = 1.0

    def __init__(self, info, transport_factory=None):
        super().__init__(info, transport_factory)
        self.experimental = True
        self.color_mode = ColorMode.ZONES
        self.zones = [ZoneInfo(i, n) for i, n in enumerate(["Left", "Center", "Right", "Numpad"])]
        self.layout = "zones"
        self.brightness_max = 100
        self.max_fps = 1
        self.zone_numbering = "auto"
        self._zone_base: int | None = None
        self.platform: int | None = None
        self.hw_effects = [EffectInfo("pulse", "Breathing", True, [SPEED],
                                      description="The controller pulses the zone colors")]
        self.notes.append("This controller needs about a second per change; animations run slowly.")

    # ------------------------------------------------------------ transport
    def _cmd(self, *payload: int, delay: float | None = None) -> bytes | None:
        body = bytes((0x03,) + payload)
        self._feature(b"\x00" + body + bytes(33 - len(body)))
        time.sleep(self.COMMAND_DELAY if delay is None else delay)
        try:
            return self._io(self.transport.get_feature, 0x00, 34)
        except DeviceError:
            return None

    def _zones(self) -> list[int]:
        if self.zone_numbering in ("0", "16"):
            base = int(self.zone_numbering)
        else:
            if self._zone_base is None:
                reply = self._cmd(0x20, 0x02)
                if reply and len(reply) >= 6 and reply[1] == 0x03:
                    self.platform = (reply[4] << 8) | reply[5]
                self._zone_base = 0x10 if self.platform in HIGH_ZONE_PLATFORMS else 0x00
            base = self._zone_base
        return [base + i for i in range(4)]

    # --------------------------------------------------------------- frames
    def _program(self, frame: Frame, zones: list[int]) -> None:
        colors = frame.colors or [(255, 255, 255)] * 4
        action, duration, tempo = ACT_COLOR, 0x07D0, 0x00FA
        if frame.effect == "pulse":
            speed = max(0, min(100, int(frame.params.get("speed", 50))))
            action, duration = ACT_PULSE, int(4000 - speed * 35)    # 4 s .. 0.5 s per pulse
        self._cmd(0x21, 0x00, 0x04, 0xFF, 0xFF)                  # remove the running animation
        self._cmd(0x21, 0x00, 0x01, 0xFF, 0xFF)                  # start a new running animation
        for i, zone in enumerate(zones):
            r, g, b = colors[min(i, len(colors) - 1)]
            self._cmd(0x23, 0x01, 0x00, 0x01, zone)               # select one zone
            self._cmd(0x24, action, duration >> 8, duration & 0xFF, tempo >> 8, tempo & 0xFF, r, g, b)
        self._cmd(0x21, 0x00, 0x03, 0xFF, 0xFF, delay=self.PLAY_DELAY)   # finish & play (not saved)

    def _dim(self, level: int, zones: list[int]) -> None:
        dim = 100 - max(0, min(100, level))
        self._cmd(0x26, dim, 0x00, len(zones), *zones)

    def _show(self, frame: Frame, prev: Frame | None) -> None:
        zones = self._zones()
        level = frame.level if frame.on else 0
        lighting = (frame.colors, frame.effect, frame.params)
        if prev is None or lighting != (prev.colors, prev.effect, prev.params):
            self._program(frame, zones)
            prev = None
        if prev is None or level != (prev.level if prev.on else 0):
            self._dim(level, zones)

    def features(self) -> list[Feature]:
        return [Feature("zones", "Zone numbering", "choice", value=self.zone_numbering, default="auto",
                        choices=[["auto", "Automatic"], ["0", "Zones 0-3"], ["16", "Zones 16-19"]],
                        description="Change this if colors do not reach the keyboard")]

    def set_feature(self, feature_id: str, value) -> None:
        if feature_id != "zones":
            raise KeyError(feature_id)
        self.zone_numbering = str(value)
        self.last = None
