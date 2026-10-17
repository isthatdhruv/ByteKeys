"""Find every controllable keyboard light on this machine."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from . import demo, hid, openrgb, sysfs_leds, wmi_zones
from .base import Device
from .drivers import ALL_DRIVERS
from .drivers.asus_aura import AsusAura

log = logging.getLogger(__name__)


@dataclass
class Options:
    sysfs: bool = True
    hid: bool = True
    openrgb: bool = True
    openrgb_host: str = "127.0.0.1"
    openrgb_port: int = 6742
    openrgb_all: bool = False
    demo: bool = False


def _merge_asus(devices: list[Device]) -> list[Device]:
    """A ROG keyboard shows up twice: brightness via asus-wmi, color via USB Aura. Make it one."""
    aura = next((d for d in devices if isinstance(d, AsusAura)), None)
    led = next((d for d in devices if d.id == "sysfs:asus::kbd_backlight"
                and isinstance(d, sysfs_leds.SysfsKeyboard) and not d.rgb), None)
    if aura is None or led is None:
        return devices
    aura.attach_companion(led)
    return [d for d in devices if d is not led]


def discover(opts: Options | None = None) -> list[Device]:
    opts = opts or Options()
    devices: list[Device] = []

    def collect(label: str, fn, *args, **kwargs):
        try:
            devices.extend(fn(*args, **kwargs))
        except Exception:  # one broken backend must not hide the others
            log.exception("%s discovery failed", label)

    if opts.sysfs:
        collect("wmi zones", wmi_zones.discover)      # first: claims LEDs it drives itself
        collect("sysfs", sysfs_leds.discover)
    if opts.hid:
        collect("hid", hid.discover, ALL_DRIVERS)
    devices = _merge_asus(devices)
    if opts.openrgb:
        native_nodes = {d.path for d in devices if d.backend == "hid"}
        found: list[Device] = []
        try:
            found = openrgb.discover(opts.openrgb_host, opts.openrgb_port, opts.openrgb_all)
        except Exception:
            log.exception("OpenRGB discovery failed")
        for dev in found:
            # Skip keyboards we already drive natively (OpenRGB reports "HID: /dev/hidrawN").
            location = getattr(dev, "ctrl", {}).get("location", "")
            if any(node and node in location for node in native_nodes):
                continue
            devices.append(dev)
    if opts.demo:
        collect("demo", demo.discover)

    seen: dict[str, int] = {}
    for dev in devices:
        if dev.id in seen:
            seen[dev.id] += 1
            dev.id = f"{dev.id}#{seen[dev.id]}"
        else:
            seen[dev.id] = 1
    return devices
