"""Readings that automation rules react to."""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from typing import Callable

from .. import fsroot

PSU = "/sys/class/power_supply"
HWMON = "/sys/class/hwmon"
THERMAL = "/sys/class/thermal"
IIO = "/sys/bus/iio/devices"
LEDS = "/sys/class/leds"

CPU_HWMON = ("coretemp", "k10temp", "zenpower", "cpu_thermal", "soc_thermal", "cpu")
CPU_LABELS = ("Package", "Tctl", "Tdie", "CPU")
CPU_ZONES = ("x86_pkg_temp", "TCPU", "cpu-thermal", "cpu_thermal", "soc_thermal", "soc-thermal", "acpitz")


@dataclass
class Snapshot:
    ac_online: bool | None = None
    battery: int | None = None
    charging: bool | None = None
    temperature: float | None = None
    cpu: float | None = None
    capslock: bool | None = None
    idle: float | None = None        # seconds since the last input
    lux: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class Sensors:
    def __init__(self, idle_source: Callable[[], float | None] | None = None):
        self.idle_source = idle_source
        self._temp_path: str | None | bool = False   # False = not searched yet
        self._lux_paths: tuple[str, float, float] | None | bool = False
        self._cpu_prev: tuple[int, int] | None = None

    # ------------------------------------------------------------ discovery
    def _supplies(self) -> list[tuple[str, str]]:
        out = []
        for name in fsroot.listdir(PSU):
            kind = fsroot.read(f"{PSU}/{name}/type") or ""
            out.append((name, kind))
        return out

    def _find_temp(self) -> str | None:
        for h in fsroot.listdir(HWMON):
            name = fsroot.read(f"{HWMON}/{h}/name") or ""
            if name not in CPU_HWMON:
                continue
            inputs = sorted(f for f in fsroot.listdir(f"{HWMON}/{h}")
                            if f.startswith("temp") and f.endswith("_input"))
            for f in inputs:
                label = fsroot.read(f"{HWMON}/{h}/{f[:-6]}_label") or ""
                if label.startswith(CPU_LABELS):
                    return f"{HWMON}/{h}/{f}"
            if inputs:
                return f"{HWMON}/{h}/{inputs[0]}"
        for kind in CPU_ZONES:
            for tz in fsroot.listdir(THERMAL):
                if tz.startswith("thermal_zone") and fsroot.read(f"{THERMAL}/{tz}/type") == kind:
                    return f"{THERMAL}/{tz}/temp"
        return None

    def _find_lux(self) -> tuple[str, float, float] | None:
        for dev in fsroot.listdir(IIO):
            base = f"{IIO}/{dev}"
            for attr in ("in_illuminance_input", "in_illuminance_raw", "in_illuminance0_input",
                         "in_illuminance0_raw"):
                if fsroot.exists(f"{base}/{attr}"):
                    stem = attr.rsplit("_", 1)[0]
                    scale = float(fsroot.read(f"{base}/{stem}_scale") or 1.0) if attr.endswith("raw") else 1.0
                    offset = float(fsroot.read(f"{base}/{stem}_offset") or 0.0) if attr.endswith("raw") else 0.0
                    return f"{base}/{attr}", scale, offset
        return None

    def _capslock_leds(self) -> list[str]:
        return [n for n in fsroot.listdir(LEDS) if n.startswith("input") and n.endswith("::capslock")]

    def available(self) -> dict[str, bool]:
        supplies = self._supplies()
        if self._temp_path is False:
            self._temp_path = self._find_temp()
        if self._lux_paths is False:
            self._lux_paths = self._find_lux()
        return {
            "power": any(k in ("Mains", "USB") for _, k in supplies),
            "battery": any(k == "Battery" for _, k in supplies),
            "temperature": bool(self._temp_path),
            "cpu": fsroot.exists("/proc/stat"),
            "capslock": bool(self._capslock_leds()),
            "idle": self.idle_source is not None,
            "ambient": bool(self._lux_paths),
        }

    # -------------------------------------------------------------- reading
    def read(self, needed: set[str] | None = None) -> Snapshot:
        everything = needed is None
        needed = needed or set()
        snap = Snapshot()
        if everything or needed & {"power", "battery"}:
            self._read_power(snap)
        if everything or "temperature" in needed:
            if self._temp_path is False:
                self._temp_path = self._find_temp()
            if self._temp_path:
                milli = fsroot.read_int(self._temp_path)  # type: ignore[arg-type]
                snap.temperature = milli / 1000.0 if milli is not None else None
        if everything or "cpu" in needed:
            snap.cpu = self._read_cpu()
            if snap.cpu is None and self._cpu_prev is not None:
                time.sleep(0.2)   # first reading: load needs two samples
                snap.cpu = self._read_cpu()
        if everything or "capslock" in needed:
            leds = self._capslock_leds()
            if leds:
                snap.capslock = any((fsroot.read_int(f"{LEDS}/{n}/brightness") or 0) > 0 for n in leds)
        if (everything or "idle" in needed) and self.idle_source is not None:
            snap.idle = self.idle_source()
        if everything or "ambient" in needed:
            if self._lux_paths is False:
                self._lux_paths = self._find_lux()
            if self._lux_paths:
                path, scale, offset = self._lux_paths  # type: ignore[misc]
                raw = fsroot.read(path)
                try:
                    snap.lux = (float(raw) + offset) * scale if raw is not None else None
                except ValueError:
                    snap.lux = None
        return snap

    def _read_power(self, snap: Snapshot) -> None:
        mains, usb = [], []
        for name, kind in self._supplies():
            base = f"{PSU}/{name}"
            if kind == "Mains":
                mains.append(fsroot.read(f"{base}/online") == "1")
            elif kind in ("USB", "USB_PD", "USB_C"):
                usb.append(fsroot.read(f"{base}/online") == "1")
            elif kind == "Battery" and fsroot.read(f"{base}/scope") != "Device":
                if snap.battery is None:
                    cap = fsroot.read_int(f"{base}/capacity")
                    if cap is None:
                        now = fsroot.read_int(f"{base}/energy_now") or fsroot.read_int(f"{base}/charge_now")
                        full = fsroot.read_int(f"{base}/energy_full") or fsroot.read_int(f"{base}/charge_full")
                        cap = int(100 * now / full) if now is not None and full else None
                    snap.battery = cap
                    status = fsroot.read(f"{base}/status") or ""
                    snap.charging = status in ("Charging", "Full")
        if mains:
            snap.ac_online = any(mains)
        elif usb:
            snap.ac_online = any(usb)
        elif snap.charging is not None:
            snap.ac_online = snap.charging

    def _read_cpu(self) -> float | None:
        text = fsroot.read("/proc/stat")
        if not text:
            return None
        fields = text.splitlines()[0].split()[1:]
        try:
            values = [int(v) for v in fields]
        except ValueError:
            return None
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        total = sum(values[:8])
        prev = self._cpu_prev
        self._cpu_prev = (idle, total)
        if prev is None or total <= prev[1]:
            return None
        return 100.0 * (1 - (idle - prev[0]) / (total - prev[1]))


class SessionIdle:
    """Idle time from the desktop session (GNOME/Mutter), for portable mode.

    The root service reads input devices directly; without it we can still
    ask the compositor how long the user has been idle.
    """

    def __init__(self):
        self.ok = shutil.which("gdbus") is not None

    def __call__(self) -> float | None:
        if not self.ok:
            return None
        try:
            out = subprocess.run(
                ["gdbus", "call", "--session", "--dest", "org.gnome.Mutter.IdleMonitor",
                 "--object-path", "/org/gnome/Mutter/IdleMonitor/Core",
                 "--method", "org.gnome.Mutter.IdleMonitor.GetIdletime"],
                capture_output=True, text=True, timeout=2, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            self.ok = False
            return None
        if out.returncode != 0:
            self.ok = False
            return None
        m = re.search(r"uint64\s+(\d+)", out.stdout)   # "(uint64 1027057,)" in milliseconds
        return int(m.group(1)) / 1000.0 if m else None
