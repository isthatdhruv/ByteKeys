"""ITE 8291 rev 0.03 per-key RGB keyboards (Clevo / Tongfang / Uniwill / XMG / TUXEDO).

Interface 1 of the controller (usage page 0xFF03) takes 8-byte control
feature reports and 64-byte row data written to the interrupt OUT endpoint.
The matrix is 6 rows x 21 columns with row 0 at the *bottom*; a row is sent
as 21 blue, then 21 green, then 21 red bytes. Byte 7 of the effect command
asks the controller to store the state permanently, so it stays 0 except for
an explicit save. Protocol per ite8291r3-ctl, tuxedo-drivers and OpenRGB.

When TUXEDO's ``ite_8291`` kernel driver owns the device it shows up as LED
class devices instead (rgb:kbd_backlight...), handled by the sysfs backend.
"""

from __future__ import annotations

from ...color import RGB
from ..base import ColorMode, EffectInfo, Feature, Frame, Param, ZoneInfo
from ..hid import HidKeyboard

ROWS, COLS = 6, 21
USAGE = (0xFF03, 0x0001)

# Effect ids: (name, uses color, uses direction, uses reactive)
EFFECTS = {
    "breathing": (0x02, "Breathing", True, False, False),
    "wave": (0x03, "Wave", False, True, False),
    "random": (0x04, "Random", True, False, True),
    "rainbow": (0x05, "Rainbow", False, False, False),
    "ripple": (0x06, "Ripple", True, False, True),
    "marquee": (0x09, "Marquee", False, False, False),
    "raindrop": (0x0A, "Raindrop", True, False, False),
    "aurora": (0x0E, "Aurora", True, False, True),
    "fireworks": (0x11, "Fireworks", True, False, True),
}
USER_MODE = 0x33

# Key labels by (hardware row, column), after OpenRGB's map of the 048d:600b ISO
# keyboard with numpad. The arrow cluster differs between models.
KEYMAP: dict[tuple[int, int], str] = {}
for _col, _key in enumerate(["Esc"] + [f"F{i}" for i in range(1, 13)]
                            + ["PrtSc", "Ins", "Del", "Home", "PgUp", "PgDn", "End"]):
    KEYMAP[(5, _col)] = _key
for _col, _key in {0: "`", 1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9",
                   10: "0", 11: "-", 12: "=", 14: "Bksp", 15: "Num", 16: "/", 17: "*", 18: "-"}.items():
    KEYMAP[(4, _col)] = _key
for _col, _key in {0: "Tab", 2: "Q", 3: "W", 4: "E", 5: "R", 6: "T", 7: "Y", 8: "U", 9: "I", 10: "O",
                   11: "P", 12: "[", 13: "]", 14: "\\", 15: "7", 16: "8", 17: "9", 18: "+"}.items():
    KEYMAP[(3, _col)] = _key
for _col, _key in {0: "Caps", 2: "A", 3: "S", 4: "D", 5: "F", 6: "G", 7: "H", 8: "J", 9: "K", 10: "L",
                   11: ";", 12: "'", 13: "#", 14: "Enter", 15: "4", 16: "5", 17: "6"}.items():
    KEYMAP[(2, _col)] = _key
for _col, _key in {0: "Shift", 3: "Z", 4: "X", 5: "C", 6: "V", 7: "B", 8: "N", 9: "M", 10: ",",
                   11: ".", 12: "/", 14: "Shift", 15: "1", 16: "2", 17: "3", 18: "Ent"}.items():
    KEYMAP[(1, _col)] = _key
for _col, _key in {0: "Ctrl", 2: "Fn", 3: "Win", 4: "Alt", 7: "Space", 10: "AltGr", 12: "Ctrl",
                   13: "←", 14: "↑", 15: "→", 16: "0", 17: ".", 18: "↓"}.items():
    KEYMAP[(0, _col)] = _key

SPEED = Param("speed", "Speed", "range", default=6, min=1, max=10)
DIRECTION = Param("direction", "Direction", "choice", default="1",
                  choices=[["1", "Left to right"], ["2", "Right to left"], ["3", "Upwards"], ["4", "Downwards"]])
REACTIVE = Param("reactive", "React to key presses", "bool", default=False)
RANDOM = Param("random", "Random colors", "bool", default=False)


class Ite8291(HidKeyboard):
    DRIVER = "ite8291"
    VENDOR = "ITE"
    PRODUCTS = {
        (0x048D, 0x6004): "ITE 8291 Per-Key Keyboard",
        (0x048D, 0x6006): "ITE 8291 Per-Key Keyboard",
        (0x048D, 0x600A): "ITE 8291 Per-Key Keyboard",
        (0x048D, 0x600B): "ITE 8291 Per-Key Keyboard",
        (0x048D, 0xCE00): "ITE 8291 Per-Key Keyboard",
    }

    @classmethod
    def score(cls, info) -> int:
        if (info.vid, info.pid) not in cls.PRODUCTS:
            return 0
        if info.pid == 0xCE00 and info.bcd_device != 0x0003:
            return 0          # rev 0.02 is a 4-zone variant with another protocol
        if info.driver.startswith("ite_8291"):
            return 0          # tuxedo-drivers owns it; the sysfs backend takes over
        if USAGE in info.reports.applications:
            return 3
        if not info.reports.applications and info.interface == 1:
            return 1
        return 0

    def __init__(self, info, transport_factory=None):
        super().__init__(info, transport_factory)
        self.vendor = "Clevo/Tongfang"
        self.experimental = True
        self.color_mode = ColorMode.PERKEY
        self.matrix = (ROWS, COLS)
        self.layout = "perkey-matrix"
        self.zones = []
        for hw_row in range(ROWS):
            for col in range(COLS):
                key = KEYMAP.get((hw_row, col))
                self.zones.append(ZoneInfo(hw_row * COLS + col, key or f"R{ROWS - hw_row}C{col + 1}",
                                           ROWS - 1 - hw_row, col, key))
        self.brightness_max = 50
        self.max_fps = 20             # 13 USB transfers per full frame
        self.calibrate = True
        self.hw_effects = []
        for eid, (_code, name, color, direction, reactive) in EFFECTS.items():
            params = [SPEED] if eid != "rainbow" else []
            if direction:
                params.append(DIRECTION)
            if reactive:
                params.append(REACTIVE)
            if color:
                params.append(RANDOM)
            self.hw_effects.append(EffectInfo(eid, name, True, params, colors=1 if color else 0))
        self.notes.append("The key map is based on a typical ISO layout; some keys (arrows) sit "
                          "elsewhere on certain models.")

    # ---------------------------------------------------------------- frames
    def _ctrl(self, *payload: int) -> None:
        data = bytes(payload) + bytes(8 - len(payload))
        self._feature(b"\x00" + data)       # report ID 0 + 8 bytes, like ite8291r3-ctl

    def _correct(self, c: RGB) -> RGB:
        if not self.calibrate:
            return c
        # The LEDs are unbalanced; tuxedo-drivers' default correction for these controllers.
        return (c[0], c[1] * 126 // 255, c[2] * 120 // 255)

    def _row_packet(self, colors: list[RGB]) -> bytes:
        blue = bytes(c[2] for c in colors)
        green = bytes(c[1] for c in colors)
        red = bytes(c[0] for c in colors)
        return b"\x00\x00" + blue + green + red      # report ID (stripped) + 64 bytes

    def _show(self, frame: Frame, prev: Frame | None) -> None:
        if not frame.on or frame.level <= 0:
            if prev is None or (prev.on and prev.level > 0):
                self._ctrl(0x08, 0x01)
            return
        level = max(0, min(50, frame.level))
        save = 1 if frame.persist and not frame.transient else 0
        if frame.effect in EFFECTS:
            changed = prev is None or (prev.effect, prev.params, prev.effect_colors, prev.level, prev.on) != \
                (frame.effect, frame.params, frame.effect_colors, frame.level, frame.on)
            if not changed and not save:
                return
            code, _name, uses_color, uses_dir, uses_reactive = EFFECTS[frame.effect]
            p = frame.params
            try:
                speed = 11 - max(1, min(10, int(p.get("speed", 6))))     # device: 1 fastest .. 10 slowest
            except (TypeError, ValueError):
                speed = 5
            color = 0
            if uses_color:
                if p.get("random"):
                    color = 0x08
                else:
                    r, g, b = self._correct(frame.effect_colors[0] if frame.effect_colors else (255, 255, 255))
                    self._ctrl(0x14, 0x00, 0x01, r, g, b)
                    color = 0x01
            extra = 0
            if uses_dir:
                extra = int(p.get("direction", 1)) if str(p.get("direction", "1")).isdigit() else 1
            elif uses_reactive:
                extra = 0x00 if p.get("reactive") else 0x01
            self._ctrl(0x08, 0x02, code, speed if code != 0x05 else 0, level, color, extra, save)
            return
        switching = prev is None or prev.effect is not None or not prev.on or prev.level <= 0
        if switching or prev.level != level or save:
            self._ctrl(0x08, 0x02, USER_MODE, 0x00, level, 0x00, 0x00, save)
        colors = frame.colors or [(255, 255, 255)]
        colors = (list(colors) + [colors[-1]] * (ROWS * COLS))[:ROWS * COLS]
        prev_colors = None if switching or prev is None else prev.colors
        for row in range(ROWS):
            part = colors[row * COLS:(row + 1) * COLS]
            if prev_colors and prev_colors[row * COLS:(row + 1) * COLS] == part:
                continue
            self._ctrl(0x16, 0x00, row)
            self._output(self._row_packet([self._correct(c) for c in part]))

    def features(self) -> list[Feature]:
        return [Feature("calibrate", "Color calibration", "bool", value=self.calibrate, default=True,
                        description="Compensate for the brighter green and blue LEDs")]

    def set_feature(self, feature_id: str, value) -> None:
        if feature_id != "calibrate":
            raise KeyError(feature_id)
        self.calibrate = bool(value)
        self.last = None   # repaint with the new correction
