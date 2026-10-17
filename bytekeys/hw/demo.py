"""Simulated keyboards for development, screenshots and tests.

Enable with ``--demo`` (GUI/CLI/daemon) or ``BYTEKEYS_DEMO=1``.
"""

from __future__ import annotations

from .. import layouts
from .base import (
    DIRECTION,
    SPEED,
    ColorMode,
    Device,
    EffectInfo,
    Feature,
    Frame,
    Param,
    ZoneInfo,
)


class DemoKeyboard(Device):
    backend = "demo"

    def __init__(self, dev_id: str, name: str):
        super().__init__(dev_id, name)
        self.vendor = "Demo"
        self.path = "(simulated)"
        self.readable = True
        self.frames: list[Frame] = []
        self.level = 0
        self.feature_values: dict = {}

    def read_level(self) -> int | None:
        return self.level

    def _show(self, frame: Frame, prev: Frame | None) -> None:
        self.level = frame.level if frame.on else 0
        self.frames.append(frame)
        del self.frames[:-50]

    def set_feature(self, feature_id: str, value) -> None:
        self.feature_values[feature_id] = value

    def features(self) -> list[Feature]:
        return [
            Feature(f.id, f.name, f.kind, self.feature_values.get(f.id, f.value), f.default,
                    f.choices, f.min, f.max, f.description)
            for f in self._features()
        ]

    def _features(self) -> list[Feature]:
        return []


def discover() -> list[Device]:
    white = DemoKeyboard("demo:white", "Demo White Backlight")
    white.brightness_max = 2
    white.level = 1
    white._features = lambda: [  # type: ignore[method-assign]
        Feature("timeout", "Firmware timeout", "choice", "30s", "30s",
                [["0", "Never"], ["10s", "10 seconds"], ["30s", "30 seconds"], ["1m", "1 minute"]]),
    ]

    single = DemoKeyboard("demo:rgb", "Demo RGB Keyboard")
    single.color_mode = ColorMode.SINGLE
    single.brightness_max = 3
    single.level = 3
    single.can_persist = True
    speed3 = Param("speed", "Speed", "choice", default="1",
                   choices=[["0", "Slow"], ["1", "Medium"], ["2", "Fast"]])
    single.hw_effects = [
        EffectInfo("breathing", "Breathing", True, [speed3], colors=1),
        EffectInfo("cycle", "Color cycle", True, [speed3]),
    ]
    single._features = lambda: [  # type: ignore[method-assign]
        Feature("boot", "Light up while booting", "bool", True, True),
        Feature("sleep", "Light up while sleeping", "bool", False, False),
    ]

    zones = DemoKeyboard("demo:4zone", "Demo 4-Zone Keyboard")
    zones.color_mode = ColorMode.ZONES
    zones.zones = [ZoneInfo(i, n) for i, n in enumerate(["Left", "Center", "Right", "Numpad"])]
    zones.layout = "zones"
    zones.brightness_max = 2
    zones.level = 2
    zones.hw_effects = [
        EffectInfo("breath", "Breathing", True, [SPEED], colors=0),
        EffectInfo("wave", "Rainbow wave", True, [SPEED, DIRECTION]),
        EffectInfo("smooth", "Color cycle", True, [SPEED]),
    ]

    keys = layouts.get("full")
    perkey = DemoKeyboard("demo:perkey", "Demo Per-Key Keyboard")
    perkey.color_mode = ColorMode.PERKEY
    perkey.brightness_max = 10
    perkey.level = 8
    perkey.layout = "perkey-full"
    perkey.matrix = (6, 21)
    perkey.zones = [
        ZoneInfo(i, k.label.strip(), r, c, k.label.strip())
        for i, (k, (r, c)) in enumerate(zip(keys, layouts.matrix_of(keys)))
    ]
    return [white, single, zones, perkey]
