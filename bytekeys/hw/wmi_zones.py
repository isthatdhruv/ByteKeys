"""Zone lighting exposed by platform drivers outside the LED class.

* HP Omen / Victus four-zone keyboards:
  - omen-rgb-keyboard (alessandromrc, DKMS): rgb_zones/{zone00..03, brightness,
    animation_mode, animation_speed} plus its own ``omen::kbd_backlight`` LED;
  - hp-omen-linux-module (pelrun, older): /sys/devices/platform/hp-wmi/rgb_zones/zone0X.
* Legacy Alienware (alienware-wmi on older AlienFX machines): rgb_zones/zone0X
  with only 4 bits per channel, global brightness LED ``alienware::global_brightness``.
* Acer Predator / Nitro with the out-of-tree "facer" module: character
  devices /dev/acer-gkbbl-0 (effects, 16 bytes) and /dev/acer-gkbbl-static-0
  (static zone colors, 4 bytes).
"""

from __future__ import annotations

import os

from .. import fsroot
from ..color import RGB, scale
from . import sysfs_leds
from .base import (
    AccessError,
    ColorMode,
    Device,
    DeviceError,
    EffectInfo,
    Frame,
    Param,
    ZoneInfo,
)

ROOT_HINT = sysfs_leds.ROOT_HINT
FOUR_ZONES = ["Right", "Center", "Left", "WASD"]
LEFT_TO_RIGHT = ["Left", "Center", "Right", "Numpad"]

OMEN_RGB = "/sys/devices/platform/omen-rgb-keyboard/rgb_zones"
HP_WMI_ZONES = "/sys/devices/platform/hp-wmi/rgb_zones"
ALIENWARE_ZONES = "/sys/devices/platform/alienware-wmi/rgb_zones"
ACER_DYNAMIC = "/dev/acer-gkbbl-0"
ACER_STATIC = "/dev/acer-gkbbl-static-0"


def _write(path: str, value: str) -> None:
    try:
        fsroot.write(path, value)
    except PermissionError:
        raise AccessError(f"no permission to write {path}", ROOT_HINT) from None
    except OSError as e:
        raise DeviceError(f"writing {path} failed: {e.strerror or e}") from None


class ZoneFileKeyboard(Device):
    """Four (or fewer) zone files taking a hex color each."""

    backend = "sysfs"

    def __init__(self, dev_id: str, name: str, base: str, zone_files: list[str], zone_names: list[str]):
        super().__init__(dev_id, name)
        self.base = base
        self.zone_files = zone_files
        self.path = base
        self.color_mode = ColorMode.ZONES
        self.zones = [ZoneInfo(i, zone_names[i] if i < len(zone_names) else f"Zone {i + 1}")
                      for i in range(len(zone_files))]
        self.layout = "zones"
        self.brightness_hw = False
        self.brightness_max = 100
        self.max_fps = 10

    def access_problem(self) -> str | None:
        return None if fsroot.writable(f"{self.base}/{self.zone_files[0]}") else ROOT_HINT

    def encode(self, color: RGB) -> str:
        return "%02X%02X%02X" % color

    def _scaled(self, frame: Frame) -> list[RGB]:
        factor = frame.level / 100.0 if frame.on else 0.0
        colors = frame.colors or [(255, 255, 255)]
        return [scale(colors[min(i, len(colors) - 1)], factor) for i in range(len(self.zone_files))]

    def _show(self, frame: Frame, prev: Frame | None) -> None:
        now = self._scaled(frame)
        before = self._scaled(prev) if prev is not None else None
        for i, (zone_file, color) in enumerate(zip(self.zone_files, now)):
            if before and before[i] == color:
                continue
            _write(f"{self.base}/{zone_file}", self.encode(color))


class OmenRgbKeyboard(ZoneFileKeyboard):
    """omen-rgb-keyboard: zone colors, brightness 0-100 and kernel-side animations."""

    ANIMATIONS = ["breathing", "rainbow", "wave", "pulse", "chase", "sparkle", "candle", "aurora", "disco"]

    def __init__(self):
        zones = sorted(f for f in fsroot.listdir(OMEN_RGB) if f.startswith("zone"))
        super().__init__("sysfs:omen-rgb-keyboard", "HP Omen Keyboard", OMEN_RGB, zones, FOUR_ZONES)
        self.vendor = "HP"
        self.brightness_hw = fsroot.exists(f"{OMEN_RGB}/brightness")
        self.readable = self.brightness_hw
        speed = Param("speed", "Speed", "range", default=5, min=1, max=10)
        if fsroot.exists(f"{OMEN_RGB}/animation_mode"):
            self.hw_effects = [EffectInfo(a, "Color cycle" if a == "rainbow" else a.title(), True, [speed])
                               for a in self.ANIMATIONS]

    def read_level(self) -> int | None:
        return fsroot.read_int(f"{OMEN_RGB}/brightness") if self.brightness_hw else None

    def _scaled(self, frame: Frame) -> list[RGB]:
        if self.brightness_hw:   # the module dims by itself
            colors = frame.colors or [(255, 255, 255)]
            return [colors[min(i, len(colors) - 1)] for i in range(len(self.zone_files))]
        return super()._scaled(frame)

    def _show(self, frame: Frame, prev: Frame | None) -> None:
        if self.hw_effects:
            mode = frame.effect if frame.effect in self.ANIMATIONS else "static"
            prev_mode = (prev.effect if prev and prev.effect in self.ANIMATIONS else "static") if prev else None
            if mode != prev_mode:
                _write(f"{OMEN_RGB}/animation_mode", mode)
            if frame.effect and "speed" in frame.params and (prev is None or prev.params != frame.params):
                _write(f"{OMEN_RGB}/animation_speed", str(int(frame.params["speed"])))
        if self.brightness_hw:
            level = frame.level if frame.on else 0
            if prev is None or level != (prev.level if prev.on else 0):
                _write(f"{OMEN_RGB}/brightness", str(level))
        super()._show(frame, prev)


class AlienwareZones(ZoneFileKeyboard):
    """Legacy AlienFX zones: each channel keeps only its low 4 bits."""

    def __init__(self):
        zones = sorted(f for f in fsroot.listdir(ALIENWARE_ZONES) if f.startswith("zone"))
        super().__init__("sysfs:alienware-wmi", "Alienware Lighting", ALIENWARE_ZONES, zones, LEFT_TO_RIGHT)
        self.vendor = "Alienware"
        self.led = "alienware::global_brightness"
        if fsroot.exists(f"/sys/class/leds/{self.led}/brightness"):
            self.brightness_hw = True
            self.brightness_max = fsroot.read_int(f"/sys/class/leds/{self.led}/max_brightness", 15) or 15
            self.readable = True

    def encode(self, color: RGB) -> str:
        return "%02X%02X%02X" % tuple(round(c * 15 / 255) for c in color)   # "800000" would be black

    def read_level(self) -> int | None:
        return fsroot.read_int(f"/sys/class/leds/{self.led}/brightness") if self.brightness_hw else None

    def _scaled(self, frame: Frame) -> list[RGB]:
        if self.brightness_hw:
            colors = frame.colors or [(255, 255, 255)]
            return [colors[min(i, len(colors) - 1)] for i in range(len(self.zone_files))]
        return super()._scaled(frame)

    def _show(self, frame: Frame, prev: Frame | None) -> None:
        if fsroot.exists(f"{ALIENWARE_ZONES}/lighting_control_state"):
            state = fsroot.read(f"{ALIENWARE_ZONES}/lighting_control_state") or ""
            if "[running]" not in state:
                _write(f"{ALIENWARE_ZONES}/lighting_control_state", "running\n")
        if self.brightness_hw:
            level = frame.level if frame.on else 0
            if prev is None or level != (prev.level if prev.on else 0):
                _write(f"/sys/class/leds/{self.led}/brightness", str(level))
        super()._show(frame, prev)


class AcerGamingKeyboard(Device):
    """Acer Predator / Nitro four-zone keyboards through the 'facer' kernel module."""

    backend = "sysfs"
    EFFECTS = {"breathing": 1, "neon": 2, "wave": 3, "shifting": 4, "zoom": 5}

    def __init__(self):
        super().__init__("dev:acer-gkbbl", "Acer Gaming Keyboard")
        self.vendor = "Acer"
        self.path = ACER_DYNAMIC
        self.color_mode = ColorMode.ZONES
        self.zones = [ZoneInfo(i, n) for i, n in enumerate(LEFT_TO_RIGHT)]
        self.layout = "zones"
        self.brightness_max = 100
        self.max_fps = 10
        speed = Param("speed", "Speed", "range", default=5, min=1, max=9)
        direction = Param("direction", "Direction", "choice", default="2",
                          choices=[["2", "Left to right"], ["1", "Right to left"]])
        self.hw_effects = [
            EffectInfo("breathing", "Breathing", True, [speed], colors=1),
            EffectInfo("neon", "Color cycle", True, [speed]),
            EffectInfo("wave", "Wave", True, [speed, direction]),
            EffectInfo("shifting", "Shifting", True, [speed, direction], colors=1),
            EffectInfo("zoom", "Zoom", True, [speed], colors=1),
        ]

    def access_problem(self) -> str | None:
        ok = all(os.access(fsroot.path(p), os.W_OK) for p in (ACER_DYNAMIC, ACER_STATIC))
        return None if ok else "No permission for /dev/acer-gkbbl-*. " + ROOT_HINT

    def _send(self, path: str, payload: bytes) -> None:
        try:
            fd = os.open(fsroot.path(path), os.O_WRONLY | os.O_CLOEXEC)
        except PermissionError:
            raise AccessError(f"no permission to open {path}", ROOT_HINT) from None
        except OSError as e:
            raise DeviceError(f"cannot open {path}: {e.strerror or e}") from None
        try:
            written = os.write(fd, payload)
        except OSError as e:
            raise DeviceError(f"writing {path} failed: {e.strerror or e}") from None
        finally:
            os.close(fd)
        if written != len(payload):   # the module answers 0 to a wrong-sized write; never retry blindly
            raise DeviceError(f"{path} rejected the {len(payload)} byte command")

    def effect_packet(self, frame: Frame) -> bytes:
        buf = bytearray(16)
        effect = self.EFFECTS.get(frame.effect or "", 0)
        buf[0] = effect
        try:
            buf[1] = max(1, min(9, int(frame.params.get("speed", 5)))) if effect else 0
        except (TypeError, ValueError):
            buf[1] = 5
        buf[2] = max(0, min(100, frame.level if frame.on else 0))
        buf[3] = 8 if effect == self.EFFECTS["wave"] else 0
        buf[4] = int(frame.params.get("direction", 2)) if effect in (3, 4) else 1
        color = frame.effect_colors[0] if frame.effect_colors else (frame.colors or [(255, 255, 255)])[0]
        buf[5:8] = bytes(color)
        buf[9] = 1
        return bytes(buf)

    def _show(self, frame: Frame, prev: Frame | None) -> None:
        if not frame.effect:
            colors = frame.colors or [(255, 255, 255)]
            prev_colors = prev.colors if prev and not prev.effect else None
            for zone in range(4):
                color = colors[min(zone, len(colors) - 1)]
                if prev_colors and zone < len(prev_colors) and prev_colors[zone] == color:
                    continue
                self._send(ACER_STATIC, bytes((1 << zone, *color)))
        packet = self.effect_packet(frame)
        if prev is None or packet != self.effect_packet(prev):
            self._send(ACER_DYNAMIC, packet)


def discover() -> list[Device]:
    devices: list[Device] = []
    if fsroot.isdir(OMEN_RGB) and any(f.startswith("zone") for f in fsroot.listdir(OMEN_RGB)):
        devices.append(OmenRgbKeyboard())
        sysfs_leds.CLAIMED.add("omen::kbd_backlight")
    elif fsroot.isdir(HP_WMI_ZONES) and any(f.startswith("zone") for f in fsroot.listdir(HP_WMI_ZONES)):
        zones = sorted(f for f in fsroot.listdir(HP_WMI_ZONES) if f.startswith("zone"))
        dev = ZoneFileKeyboard("sysfs:hp-wmi-zones", "HP Omen Keyboard", HP_WMI_ZONES, zones, FOUR_ZONES)
        dev.vendor = "HP"
        devices.append(dev)
    if fsroot.isdir(ALIENWARE_ZONES) and any(f.startswith("zone") for f in fsroot.listdir(ALIENWARE_ZONES)):
        devices.append(AlienwareZones())
        sysfs_leds.CLAIMED.add("alienware::global_brightness")
    if fsroot.exists(ACER_DYNAMIC) and fsroot.exists(ACER_STATIC):
        devices.append(AcerGamingKeyboard())
    return devices
