"""Device model shared by every hardware backend.

A backend turns some piece of hardware (a sysfs LED, a USB HID controller, an
OpenRGB device...) into a :class:`Device`. Devices are deliberately dumb: the
engine decides *what* to show and hands the device a :class:`Frame`; the
device only knows *how* to put that frame on the hardware.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ..color import RGB


class ColorMode:
    NONE = "none"        # single-color backlight, brightness only
    SINGLE = "single"    # whole keyboard is one RGB zone
    ZONES = "zones"      # a handful of RGB zones (typically 3 or 4)
    PERKEY = "perkey"    # individually addressable keys


class DeviceError(Exception):
    """The hardware rejected or failed an operation."""


class AccessError(DeviceError):
    """The hardware exists but this process is not allowed to drive it."""

    def __init__(self, message: str, hint: str | None = None):
        super().__init__(message)
        self.hint = hint


@dataclass
class Param:
    """A tunable parameter of an effect (rendered as a control by the UIs)."""

    id: str
    name: str
    kind: str = "range"          # "range" | "choice" | "bool"
    default: Any = None
    min: int = 0
    max: int = 100
    choices: list = field(default_factory=list)   # [[value, label], ...]


SPEED = Param("speed", "Speed", "range", default=50, min=0, max=100)
DIRECTION = Param(
    "direction", "Direction", "choice", default="right",
    choices=[["right", "Left to right"], ["left", "Right to left"]],
)


@dataclass
class EffectInfo:
    id: str
    name: str
    hardware: bool = False
    params: list[Param] = field(default_factory=list)
    colors: int = 0               # how many user colors the effect consumes
    description: str = ""


@dataclass
class ZoneInfo:
    index: int
    name: str
    row: int | None = None        # matrix position for per-key devices
    col: int | None = None
    key: str | None = None        # key label, when known ("Esc", "A", ...)


@dataclass
class Feature:
    """A device specific setting outside of plain lighting (timeouts, power states...)."""

    id: str
    name: str
    kind: str = "bool"            # "bool" | "choice" | "range"
    value: Any = None             # None when the hardware cannot report it
    default: Any = None
    choices: list = field(default_factory=list)
    min: int = 0
    max: int = 100
    description: str = ""


@dataclass
class Frame:
    """What the engine wants the hardware to show right now."""

    on: bool = True
    level: int = 0                          # hardware brightness 0..brightness_max
    colors: list[RGB] | None = None         # one per zone, None for brightness-only devices
    effect: str | None = None               # hardware effect id; None means static colors
    params: dict = field(default_factory=dict)
    effect_colors: list[RGB] = field(default_factory=list)
    transient: bool = False                 # an animation step; never persist it
    persist: bool = False                   # a settled state the firmware may remember

    def same_lighting(self, other: "Frame | None") -> bool:
        if other is None:
            return False
        return (
            self.on == other.on
            and self.level == other.level
            and self.colors == other.colors
            and self.effect == other.effect
            and self.params == other.params
            and self.effect_colors == other.effect_colors
        )


def default_level_names(max_level: int) -> list[str] | None:
    return {
        1: ["Off", "On"],
        2: ["Off", "Low", "High"],
        3: ["Off", "Low", "Medium", "High"],
        4: ["Off", "1", "2", "3", "4"],
        5: ["Off", "1", "2", "3", "4", "5"],
    }.get(max_level)


class Device:
    """Base class for every controllable keyboard light."""

    backend = "base"

    def __init__(self, dev_id: str, name: str):
        self.id = dev_id
        self.name = name
        self.vendor = ""
        self.color_mode = ColorMode.NONE
        self.brightness_max = 1
        # False: the hardware has no brightness of its own and the engine
        # dims colors instead (brightness_max is then 100).
        self.brightness_hw = True
        self.zones: list[ZoneInfo] = []
        self.matrix: tuple[int, int] | None = None
        self.layout: str | None = None
        self.hw_effects: list[EffectInfo] = []
        self.max_fps = 30
        self.readable = False
        # Firmware keeps its state over reboots when told to (frame.persist).
        self.can_persist = False
        self.experimental = False
        self.notes: list[str] = []
        self.path = ""
        self.last: Frame | None = None
        self.error: str | None = None

    # ----------------------------------------------------------- capabilities
    @property
    def rgb(self) -> bool:
        return self.color_mode != ColorMode.NONE

    @property
    def zone_count(self) -> int:
        if self.color_mode == ColorMode.NONE:
            return 0
        if self.color_mode == ColorMode.SINGLE:
            return 1
        return len(self.zones)

    def level_names(self) -> list[str] | None:
        if not self.brightness_hw:
            return None
        return default_level_names(self.brightness_max)

    def zone_list(self) -> list[ZoneInfo]:
        if self.color_mode == ColorMode.SINGLE and not self.zones:
            return [ZoneInfo(0, "Keyboard")]
        return self.zones

    # --------------------------------------------------------------- hardware
    def access_problem(self) -> str | None:
        """None when the device can be driven, else a human-readable reason."""
        return None

    def read_level(self) -> int | None:
        """Current hardware brightness when the device can report it."""
        return None

    def show(self, frame: Frame, force: bool = False) -> None:
        """Push a frame to the hardware, skipping unchanged parts unless *force*."""
        prev = None if force else self.last
        self._show(frame, prev)
        self.last = frame
        self.error = None

    def _show(self, frame: Frame, prev: Frame | None) -> None:
        raise NotImplementedError

    def features(self) -> list[Feature]:
        return []

    def set_feature(self, feature_id: str, value: Any) -> None:
        raise KeyError(feature_id)

    def close(self) -> None:
        pass

    # ------------------------------------------------------------ description
    def describe(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "vendor": self.vendor,
            "backend": self.backend,
            "color_mode": self.color_mode,
            "brightness_max": self.brightness_max,
            "brightness_hw": self.brightness_hw,
            "levels": self.level_names(),
            "zones": [asdict(z) for z in self.zone_list()],
            "matrix": list(self.matrix) if self.matrix else None,
            "layout": self.layout,
            "hw_effects": [asdict(e) for e in self.hw_effects],
            "features": [asdict(f) for f in self.features()],
            "max_fps": self.max_fps,
            "readable": self.readable,
            "can_persist": self.can_persist,
            "experimental": self.experimental,
            "notes": list(self.notes),
            "path": self.path,
            "access": self.access_problem(),
            "error": self.error,
        }

    def diagnostics(self) -> dict:
        return {"id": self.id, "backend": self.backend, "path": self.path}

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.id!r}>"
