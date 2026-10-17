"""ASUS ROG laptop keyboards with USB Aura lighting (0b05:1854/1866/1869/19b6/1a30).

The Aura collection (usage page 0xFF31, usage 0x79) takes 64-byte reports
with ID 0x5D. A mode is described with 0xB3 and activated with 0xB5; 0xB4
additionally stores it in the keyboard, so it is only sent for an explicit
save. Brightness belongs to the kernel's ``asus::kbd_backlight`` LED when it
exists (it also tracks the Fn keys); otherwise the 0x5A brightness report is
used. Protocol per asusctl (rog-aura) and OpenRGB. TUF laptops are not
USB Aura; they use asus-wmi (see sysfs_leds.AsusWmiKeyboard).
"""

from __future__ import annotations

from ... import fsroot
from ..base import ColorMode, DeviceError, EffectInfo, Frame, Param
from ..hid import HidKeyboard

USAGE = (0xFF31, 0x0079)
REPORT_ID = 0x5D
REPORT_LEN = 64
HANDSHAKE = b"ASUS Tech.Inc.\x00"

MODES = {"breathe": 1, "cycle": 2, "wave": 3, "pulse": 10}
SPEEDS = {"0": 0xE1, "1": 0xEB, "2": 0xF5}
SPEED = Param("speed", "Speed", "choice", default="1",
              choices=[["0", "Slow"], ["1", "Medium"], ["2", "Fast"]])
DIRECTION = Param("direction", "Direction", "choice", default="right",
                  choices=[["right", "To the right"], ["left", "To the left"]])


def asusd_running() -> bool:
    for pid in fsroot.listdir("/proc"):
        if pid.isdigit() and fsroot.read(f"/proc/{pid}/comm") == "asusd":
            return True
    return False


class AsusAura(HidKeyboard):
    DRIVER = "asus-aura"
    VENDOR = "ASUS"
    PRODUCTS = {
        (0x0B05, 0x1854): "ASUS ROG Keyboard",
        (0x0B05, 0x1866): "ASUS ROG N-KEY Keyboard",
        (0x0B05, 0x1869): "ASUS ROG Keyboard",
        (0x0B05, 0x19B6): "ASUS ROG N-KEY Keyboard",
        (0x0B05, 0x1A30): "ASUS ROG Z13 Folio Keyboard",
    }

    @classmethod
    def score(cls, info) -> int:
        if (info.vid, info.pid) not in cls.PRODUCTS:
            return 0
        if USAGE in info.reports.applications:
            return 3
        if REPORT_ID in info.reports.feature or REPORT_ID in info.reports.output:
            return 2
        return 0

    def __init__(self, info, transport_factory=None):
        super().__init__(info, transport_factory)
        self.experimental = True
        self.color_mode = ColorMode.SINGLE
        self.brightness_max = 3
        self.max_fps = 15
        self.can_persist = True
        self.companion = None          # SysfsKeyboard for asus::kbd_backlight, set by the registry
        self._ready = False
        self._use_output = False
        self.hw_effects = [
            EffectInfo("breathe", "Breathing", True, [SPEED], colors=2,
                       description="Breathes between two colors"),
            EffectInfo("cycle", "Color cycle", True, [SPEED]),
            EffectInfo("wave", "Rainbow wave", True, [SPEED, DIRECTION]),
            EffectInfo("pulse", "Pulse", True, [SPEED], colors=1),
        ]
        if asusd_running():
            self.notes.append("asusd (asusctl) is running and may also change the keyboard lighting.")

    def attach_companion(self, led_device) -> None:
        self.companion = led_device
        self.readable = True

    # -------------------------------------------------------------- transport
    def _send(self, *payload: int) -> None:
        buf = bytes((REPORT_ID,) + payload)
        buf += bytes(REPORT_LEN - len(buf))
        if not self._use_output:
            try:
                self._feature(buf)
                return
            except DeviceError:
                self._use_output = True     # some firmware only honors output reports
        self._output(buf)

    def _send_brightness(self, level: int) -> None:
        """Keyboard brightness 0-3: report 0x5A (kernel, older keyboards) or 0x5D (newer)."""
        level = max(0, min(3, level))
        for report_id in (0x5A, REPORT_ID):
            try:
                self._feature(bytes((report_id, 0xBA, 0xC5, 0xC4, level)) + bytes(REPORT_LEN - 5))
                return
            except DeviceError:
                continue
        raise DeviceError("the keyboard rejected the brightness report")

    def _init(self) -> None:
        if self._ready:
            return
        try:
            self._feature(bytes((REPORT_ID,)) + HANDSHAKE + bytes(REPORT_LEN - 1 - len(HANDSHAKE)))
        except DeviceError:
            pass        # hid-asus already did it, or the firmware does not need it
        self._ready = True

    def mode_packet(self, frame: Frame) -> tuple[int, ...]:
        mode, speed, direction = 0, 0xE1, 0
        c1 = frame.colors[0] if frame.colors else (255, 255, 255)
        c2 = (0, 0, 0)
        if frame.effect in MODES:
            mode = MODES[frame.effect]
            speed = SPEEDS.get(str(frame.params.get("speed", "1")), 0xEB)
            direction = 1 if frame.params.get("direction") == "left" else 0
            if frame.effect_colors:
                c1 = frame.effect_colors[0]
                if len(frame.effect_colors) > 1:
                    c2 = frame.effect_colors[1]
        return (0xB3, 0x00, mode, *c1, speed, direction, 0x00, *c2)

    def _show(self, frame: Frame, prev: Frame | None) -> None:
        self._init()
        level = frame.level if frame.on else 0
        prev_level = (prev.level if prev.on else 0) if prev else None
        if level != prev_level:
            if self.companion is not None:
                self.companion._write_level(level)
            else:
                self._send_brightness(level)
        packet = self.mode_packet(frame)
        persist = frame.persist and not frame.transient
        if prev is None or packet != self.mode_packet(prev) or persist:
            self._send(*packet)
            self._send(0xB5)
            if persist:
                self._send(0xB4)

    def read_level(self) -> int | None:
        if self.companion is not None:
            return self.companion.read_level()
        return None

    def access_problem(self) -> str | None:
        problem = super().access_problem()
        if problem is None and self.companion is not None:
            return self.companion.access_problem()
        return problem

