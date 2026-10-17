"""MSI SteelSeries "KLM" 3-zone keyboards (1770:ff00, MSI GE/GS/GT ~2014-2018).

8-byte feature reports with report ID 1 and a 0xEC terminator: set each
region's RGB, then select "normal" mode, which applies the colors. Nothing
is stored; the keyboard resets on reboot and resume, so the engine simply
re-applies the state. Protocol per MSIKLM, msi-keyboard and OpenRGB.
The controller has no brightness control: ByteKeys dims the colors itself.
"""

from __future__ import annotations

from ...color import scale
from ..base import ColorMode, Frame, ZoneInfo
from ..hid import HidKeyboard

REGIONS = [(1, "Left"), (2, "Middle"), (3, "Right")]
MODE_NORMAL = 0x01


class MsiKlm(HidKeyboard):
    DRIVER = "msi-klm"
    VENDOR = "MSI"
    PRODUCTS = {(0x1770, 0xFF00): "MSI SteelSeries 3-Zone Keyboard"}

    def __init__(self, info, transport_factory=None):
        super().__init__(info, transport_factory)
        self.color_mode = ColorMode.ZONES
        self.zones = [ZoneInfo(i, name) for i, (_region, name) in enumerate(REGIONS)]
        self.layout = "zones"
        self.brightness_hw = False
        self.brightness_max = 100
        self.max_fps = 20

    @staticmethod
    def packet(cmd: int, a: int = 0, b: int = 0, c: int = 0, d: int = 0) -> bytes:
        return bytes((0x01, 0x02, cmd, a, b, c, d, 0xEC))

    def _show(self, frame: Frame, prev: Frame | None) -> None:
        factor = frame.level / 100.0 if frame.on else 0.0
        colors = frame.colors or [(255, 255, 255)] * 3
        out = [scale(colors[min(i, len(colors) - 1)], factor) for i in range(3)]
        prev_out = None
        if prev is not None:
            pf = prev.level / 100.0 if prev.on else 0.0
            pc = prev.colors or [(255, 255, 255)] * 3
            prev_out = [scale(pc[min(i, len(pc) - 1)], pf) for i in range(3)]
        if out == prev_out:
            return
        for (region, _name), (r, g, b) in zip(REGIONS, out):
            self._feature(self.packet(0x40, region, r, g, b))
        self._feature(self.packet(0x41, MODE_NORMAL))
