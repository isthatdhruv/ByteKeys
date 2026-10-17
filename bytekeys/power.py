"""Performance profiles, fans, firmware fan curves and battery charge limits.

Only firmware-managed controls are used: the platform profile (the same
thing Fn+F5 / Armoury Crate / Vantage switch), fan curves that the embedded
controller executes itself, fan boost and the battery charge threshold.
ByteKeys never drives fan PWM directly, so a crash can never leave a fan
stopped.
"""

from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import time

from . import fsroot
from .hw.base import AccessError, DeviceError

PROFILE_FILE = "/sys/firmware/acpi/platform_profile"
PROFILE_CHOICES = "/sys/firmware/acpi/platform_profile_choices"
HWMON = "/sys/class/hwmon"
PSU = "/sys/class/power_supply"
PCI = "/sys/bus/pci/devices"

ROOT_HINT = "Install the ByteKeys service to change fan and power settings."

# Canonical order and the names people know from the vendor apps.
PROFILE_ORDER = ["low-power", "cool", "quiet", "balanced", "balanced-performance", "performance", "max-power",
                 "custom"]
PROFILE_INFO = {
    "low-power": ("Power saver", "leaf", "Longest battery life"),
    "cool": ("Cool", "leaf", "Keeps the chassis cool"),
    "quiet": ("Silent", "leaf", "Quiet fans, lower power"),
    "balanced": ("Balanced", "gauge", "Everyday use"),
    "balanced-performance": ("Enhanced", "gauge", "A bit more power"),
    "performance": ("Performance", "rocket", "Full power, louder fans"),
    "max-power": ("Max power", "flame", "Everything the firmware allows"),
    "custom": ("Custom", "gear", "Vendor custom mode"),
}
PPD_FOR_PROFILE = {"low-power": "power-saver", "quiet": "power-saver", "cool": "power-saver",
                   "balanced": "balanced", "balanced-performance": "balanced", "performance": "performance",
                   "max-power": "performance"}


def _write(path: str, value: str) -> None:
    try:
        fsroot.write(path, value)
    except PermissionError:
        raise AccessError(f"no permission to write {path}", ROOT_HINT) from None
    except OSError as e:
        raise DeviceError(f"writing {path} failed: {e.strerror or e}") from None


def _busctl(*args: str, timeout: float = 3.0) -> str | None:
    if not shutil.which("busctl"):
        return None
    try:
        out = subprocess.run(["busctl", "--system", *args], capture_output=True, text=True,
                             timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


class PowerControl:
    def __init__(self, sensors=None):
        if sensors is None:
            from .engine.sensors import Sensors   # imported late: the engine imports this module
            sensors = Sensors()
        self.sensors = sensors
        self._gpu_cache: tuple[float, float | None] = (0.0, None)
        self.refresh()

    # ------------------------------------------------------------ discovery
    def refresh(self) -> None:
        self.hwmons = {h: (fsroot.read(f"{HWMON}/{h}/name") or "") for h in fsroot.listdir(HWMON)}
        self.curve_hwmon = next((f"{HWMON}/{h}" for h, n in self.hwmons.items()
                                 if n == "asus_custom_fan_curve"), None)
        self.asus_hwmon = next((f"{HWMON}/{h}" for h, n in self.hwmons.items() if n == "asus"), None)
        self.battery = next((f"{PSU}/{b}" for b in fsroot.listdir(PSU)
                             if fsroot.read(f"{PSU}/{b}/type") == "Battery"
                             and fsroot.read(f"{PSU}/{b}/scope") != "Device"), None)
        self.conservation = next((p for p in (
            "/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/conservation_mode",
            "/sys/bus/platform/drivers/ideapad_acpi/VPC2004:01/conservation_mode") if fsroot.exists(p)), None)
        # Never talk to the real daemon when pointed at a fake tree (tests, fixtures).
        self.ppd = not fsroot.get_root() and _busctl("status", "net.hadess.PowerProfiles", timeout=2) is not None

    # -------------------------------------------------------------- profiles
    def profiles(self) -> tuple[list[str], str | None]:
        choices = (fsroot.read(PROFILE_CHOICES) or "").split()
        current = fsroot.read(PROFILE_FILE)
        ordered = [p for p in PROFILE_ORDER if p in choices] + [p for p in choices if p not in PROFILE_ORDER]
        return ordered, current

    def set_profile(self, name: str) -> None:
        choices, _current = self.profiles()
        if name not in choices:
            raise ValueError(f"profile {name!r} is not offered by this laptop")
        # Prefer power-profiles-daemon so desktop quick settings stay in sync.
        ppd = PPD_FOR_PROFILE.get(name)
        if self.ppd and ppd and self._ppd_maps_to(name):
            out = _busctl("set-property", "net.hadess.PowerProfiles", "/net/hadess/PowerProfiles",
                          "net.hadess.PowerProfiles", "ActiveProfile", "s", ppd)
            if out is not None:
                deadline = time.monotonic() + 1.5
                while time.monotonic() < deadline and fsroot.read(PROFILE_FILE) != name:
                    time.sleep(0.05)
                if fsroot.read(PROFILE_FILE) == name:
                    return
        _write(PROFILE_FILE, name)

    def _ppd_maps_to(self, name: str) -> bool:
        """power-profiles-daemon only has three profiles; use it when it lands on *name*."""
        choices, _ = self.profiles()
        low = next((p for p in ("low-power", "quiet", "cool") if p in choices), None)
        return name in (low, "balanced", "performance")

    # ------------------------------------------------------------------ fans
    def fans(self) -> list[dict]:
        out = []
        for h, name in sorted(self.hwmons.items()):
            if name == "asus_custom_fan_curve":
                continue
            base = f"{HWMON}/{h}"
            for f in fsroot.listdir(base):
                m = re.fullmatch(r"fan(\d+)_input", f)
                if not m:
                    continue
                rpm = fsroot.read_int(f"{base}/{f}")
                label = fsroot.read(f"{base}/fan{m[1]}_label") or f"Fan {m[1]}"
                out.append({"id": f"{name}:{m[1]}", "label": _pretty_fan(label), "rpm": rpm, "index": int(m[1])})
        return out

    def boost(self) -> dict | None:
        """ASUS: pwm1_enable on the 'asus' hwmon (0 = full speed, 2 = automatic).

        Only "SPEC83" fans have a full-speed switch; older "AGFN" fans expose a
        manual pwm1 instead (and reject 0), so they get no boost control.
        """
        if not self.asus_hwmon or not fsroot.exists(f"{self.asus_hwmon}/pwm1_enable"):
            return None
        if fsroot.exists(f"{self.asus_hwmon}/pwm1"):
            return None
        value = fsroot.read_int(f"{self.asus_hwmon}/pwm1_enable")
        return {"on": value == 0}

    def set_boost(self, on: bool) -> None:
        """Note: the kernel disables custom fan curves whenever this changes."""
        if self.boost() is None:
            raise KeyError("full fan speed is not available on this laptop")
        _write(f"{self.asus_hwmon}/pwm1_enable", "0" if on else "2")

    # ------------------------------------------------------------ fan curves
    def curve_fans(self) -> list[str]:
        if not self.curve_hwmon:
            return []
        return sorted({m[1] for f in fsroot.listdir(self.curve_hwmon)
                       if (m := re.fullmatch(r"pwm(\d+)_auto_point1_temp", f))})

    def curve(self, fan: str) -> dict:
        base = self.curve_hwmon
        points = []
        for i in range(1, 9):
            t = fsroot.read_int(f"{base}/pwm{fan}_auto_point{i}_temp")
            pwm = fsroot.read_int(f"{base}/pwm{fan}_auto_point{i}_pwm")
            if t is None or pwm is None:
                break
            points.append([t, round(pwm * 100 / 255)])
        enabled = fsroot.read_int(f"{base}/pwm{fan}_enable") == 1
        return {"fan": fan, "label": {"1": "CPU fan", "2": "GPU fan", "3": "Mid fan"}.get(fan, f"Fan {fan}"),
                "enabled": enabled, "points": points}

    def set_curve(self, fan: str, points: list[list[int]] | None, enabled: bool) -> None:
        if fan not in self.curve_fans():
            raise KeyError(f"no fan curve {fan!r}")
        base = self.curve_hwmon
        if points is not None:
            points = validate_curve(points)
            for i, (t, pct) in enumerate(points, start=1):
                _write(f"{base}/pwm{fan}_auto_point{i}_temp", str(t))
                _write(f"{base}/pwm{fan}_auto_point{i}_pwm", str(round(pct * 255 / 100)))
        # Writing points disables the curve in the kernel; "1" sends all 8 points to the firmware.
        _write(f"{base}/pwm{fan}_enable", "1" if enabled else "2")

    def reset_curve(self, fan: str) -> None:
        """Back to the firmware's own curve: 3 reloads the factory points of the active profile.

        Like switching any curve off, this makes the firmware reset every fan.
        """
        if fan not in self.curve_fans():
            raise KeyError(f"no fan curve {fan!r}")
        _write(f"{self.curve_hwmon}/pwm{fan}_enable", "3")

    def curve_enabled(self, fan: str) -> bool:
        return fsroot.read_int(f"{self.curve_hwmon}/pwm{fan}_enable") == 1

    def load_points(self, fan: str, points: list[list[int]]) -> None:
        """Put points into the kernel's copy of a curve without enabling it (shown, not run)."""
        if fan not in self.curve_fans() or len(points) != 8:
            raise KeyError(f"no fan curve {fan!r}")
        for i, (t, pct) in enumerate(points, start=1):
            _write(f"{self.curve_hwmon}/pwm{fan}_auto_point{i}_temp", str(max(0, min(255, int(t)))))
            _write(f"{self.curve_hwmon}/pwm{fan}_auto_point{i}_pwm", str(round(max(0, min(100, int(pct))) * 255 / 100)))

    # --------------------------------------------------------------- battery
    def _charge_types(self) -> tuple[list[str], str | None]:
        """Options and active value of charge_types ("Fast [Standard] Long_Life")."""
        text = fsroot.read(f"{self.battery}/charge_types") if self.battery else None
        if not text:
            return [], None
        options, current = [], None
        for word in text.split():
            name = word.strip("[]")
            options.append(name)
            if word.startswith("["):
                current = name
        return options, current

    def charge(self) -> dict | None:
        if self.battery and fsroot.exists(f"{self.battery}/charge_control_end_threshold"):
            presets = [80, 100] if fsroot.exists("/sys/devices/platform/lg-laptop") else [60, 80, 100]
            return {"kind": "threshold", "limit": fsroot.read_int(f"{self.battery}/charge_control_end_threshold"),
                    "presets": presets}
        if self.conservation:
            return {"kind": "conservation", "limit": 60 if fsroot.read(self.conservation) == "1" else 100,
                    "presets": [60, 100]}
        options, current = self._charge_types()
        if "Long_Life" in options:      # newer ideapad-laptop, samsung-laptop: a fixed firmware level
            return {"kind": "conservation", "limit": 60 if current == "Long_Life" else 100, "presets": [60, 100]}
        return None

    def set_charge_limit(self, limit: int) -> None:
        info = self.charge()
        if info is None:
            raise KeyError("this laptop has no battery charge limit")
        if info["kind"] == "conservation":
            if self.conservation:
                _write(self.conservation, "1" if limit < 100 else "0")
            else:
                _write(f"{self.battery}/charge_types", "Long_Life" if limit < 100 else "Standard")
            return
        limit = max(20, min(100, int(limit)))
        end = f"{self.battery}/charge_control_end_threshold"
        start = f"{self.battery}/charge_control_start_threshold"
        low = fsroot.read_int(start) if fsroot.exists(start) else None
        if low is not None and limit < 100 and low > limit - 5:
            _write(start, str(max(0, limit - 5)))   # keep start below end (ThinkPad, Dell, Chromebooks)
        _write(end, str(limit))
        options, current = self._charge_types()
        if "Custom" in options:                     # Dell: thresholds only count in Custom mode
            if limit < 100 and current != "Custom":
                _write(f"{self.battery}/charge_types", "Custom")
            elif limit >= 100 and current == "Custom" and "Standard" in options:
                _write(f"{self.battery}/charge_types", "Standard")

    # ------------------------------------------------------------ monitoring
    def gpu_temperature(self) -> tuple[float | None, str]:
        """(°C, note). Never wakes a sleeping discrete GPU just to read it."""
        for h, name in self.hwmons.items():
            if name in ("amdgpu", "nouveau", "radeon"):
                milli = fsroot.read_int(f"{HWMON}/{h}/temp1_input")
                if milli is not None:
                    return milli / 1000.0, ""
        for dev in fsroot.listdir(PCI):
            base = f"{PCI}/{dev}"
            if fsroot.read(f"{base}/vendor") != "0x10de" or not (fsroot.read(f"{base}/class") or "").startswith("0x03"):
                continue
            if fsroot.read(f"{base}/power/runtime_status") not in (None, "active"):
                return None, "sleeping"
            if not shutil.which("nvidia-smi"):
                return None, ""
            now = time.monotonic()
            if now - self._gpu_cache[0] < 3:
                return self._gpu_cache[1], ""
            try:
                out = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                                     capture_output=True, text=True, timeout=3, check=False).stdout
                value = float(out.split()[0]) if out.strip() else None
            except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
                value = None
            self._gpu_cache = (now, value)
            return value, ""
        return None, ""

    def monitor(self) -> dict:
        snap = self.sensors.read({"temperature", "cpu", "power", "battery"})
        gpu, gpu_note = self.gpu_temperature()
        choices, current = self.profiles()
        return {
            "cpu_temp": snap.temperature, "gpu_temp": gpu, "gpu_note": gpu_note, "cpu_load": snap.cpu,
            "fans": self.fans(), "battery": snap.battery, "charging": snap.charging, "ac": snap.ac_online,
            "profile": current,
        }

    def info(self) -> dict:
        choices, current = self.profiles()
        writable = os.geteuid() == 0 or fsroot.writable(PROFILE_FILE)
        return {
            "profiles": [{"id": p, "name": PROFILE_INFO.get(p, (p.title(),))[0],
                          "icon": PROFILE_INFO.get(p, ("", "gauge"))[1],
                          "description": PROFILE_INFO.get(p, ("", "", ""))[2]} for p in choices],
            "profile": current,
            "profile_via": "power-profiles-daemon" if self.ppd else ("sysfs" if choices else None),
            "fans": self.fans(),
            "curves": [self.curve(f) for f in self.curve_fans()],
            "boost": self.boost(),
            "charge": self.charge(),
            "access": None if writable or self.ppd else ROOT_HINT,
            "write_access": writable,
        }


def _pretty_fan(label: str) -> str:
    text = label.replace("_", " ").strip()
    return {"cpu fan": "CPU fan", "gpu fan": "GPU fan", "mid fan": "Mid fan"}.get(text.lower(), text.capitalize())


def validate_curve(points) -> list[list[int]]:
    """8 points, temperatures rising, duty never falling, and enough cooling when hot."""
    if not isinstance(points, list) or len(points) != 8:
        raise ValueError("a fan curve has exactly 8 points")
    out: list[list[int]] = []
    for item in points:
        try:
            t, pct = int(item[0]), int(item[1])
        except (TypeError, ValueError, IndexError):
            raise ValueError("fan curve points are [temperature, percent] pairs") from None
        if not 20 <= t <= 100 or not 0 <= pct <= 100:
            raise ValueError("fan curve values out of range (20-100 °C, 0-100 %)")
        if out and (t <= out[-1][0] or pct < out[-1][1]):
            raise ValueError("fan curve temperatures must rise and fan speeds must not drop")
        out.append([t, pct])
    for t, pct in out:
        if t >= 80 and pct < 50:
            raise ValueError("for safety the fans must run at 50 % or more from 80 °C")
    if out[-1][1] < 70:
        raise ValueError("for safety the last point must be at least 70 %")
    return out


class DemoPower(PowerControl):
    """Simulated performance controls for --demo: nothing touches the hardware."""

    PROFILES = ["quiet", "balanced", "performance"]
    LABELS = {"1": "CPU fan", "2": "GPU fan"}

    def __init__(self, sensors=None):
        self.sensors = sensors
        self.ppd = False
        self._t0 = time.monotonic()
        self._profile = "balanced"
        self._boost = False
        self._limit = 80
        self._curves = {fan: {"enabled": False, "points": self._factory()} for fan in self.LABELS}

    def refresh(self) -> None:
        pass

    def _wave(self, period: float, phase: float = 0.0) -> float:
        return math.sin((time.monotonic() - self._t0) / period * 2 * math.pi + phase)

    def profiles(self) -> tuple[list[str], str | None]:
        return list(self.PROFILES), self._profile

    def set_profile(self, name: str) -> None:
        if name not in self.PROFILES:
            raise ValueError(f"profile {name!r} is not offered by this laptop")
        self._profile = name
        for curve in self._curves.values():     # like asus-wmi: a profile change drops custom curves
            curve["enabled"] = False

    def _factory(self) -> list[list[int]]:
        shift = {"quiet": -12, "balanced": 0, "performance": 12}[self._profile]
        base = [[45, 10], [55, 20], [62, 30], [68, 40], [74, 55], [80, 65], [88, 85], [95, 100]]
        return [[t, max(0, min(100, pct + shift if t < 90 else pct))] for t, pct in base]

    def _heat(self) -> float:
        return {"quiet": 0.0, "balanced": 0.5, "performance": 1.0}[self._profile]

    def fans(self) -> list[dict]:
        out = []
        for i, (fan, label) in enumerate(self.LABELS.items()):
            if self._boost:
                rpm = 6100 - 150 * i
            else:
                rpm = 2300 + 1500 * self._heat() + 260 * self._wave(9, i) - 200 * i
            out.append({"id": f"demo:{fan}", "label": label, "rpm": int(rpm), "index": int(fan)})
        return out

    def boost(self) -> dict | None:
        return {"on": self._boost}

    def set_boost(self, on: bool) -> None:
        self._boost = bool(on)
        for curve in self._curves.values():
            curve["enabled"] = False

    def curve_fans(self) -> list[str]:
        return list(self.LABELS)

    def curve(self, fan: str) -> dict:
        c = self._curves[fan]
        return {"fan": fan, "label": self.LABELS[fan], "enabled": c["enabled"], "points": [list(p) for p in c["points"]]}

    def set_curve(self, fan: str, points, enabled: bool) -> None:
        if fan not in self._curves:
            raise KeyError(f"no fan curve {fan!r}")
        if points is not None:
            self._curves[fan]["points"] = validate_curve(points)
        if enabled:
            self._curves[fan]["enabled"] = True
        else:                                    # back to firmware control resets every fan
            for curve in self._curves.values():
                curve["enabled"] = False

    def reset_curve(self, fan: str) -> None:
        if fan not in self._curves:
            raise KeyError(f"no fan curve {fan!r}")
        self._curves[fan]["points"] = self._factory()
        for curve in self._curves.values():
            curve["enabled"] = False

    def curve_enabled(self, fan: str) -> bool:
        return self._curves[fan]["enabled"]

    def load_points(self, fan: str, points: list[list[int]]) -> None:
        self._curves[fan]["points"] = [list(p) for p in points]
        self._curves[fan]["enabled"] = False

    def charge(self) -> dict | None:
        return {"kind": "threshold", "limit": self._limit, "presets": [60, 80, 100]}

    def set_charge_limit(self, limit: int) -> None:
        self._limit = max(20, min(100, int(limit)))

    def gpu_temperature(self) -> tuple[float | None, str]:
        return round(48 + 14 * self._heat() + 2 * self._wave(13, 1.0), 1), ""

    def monitor(self) -> dict:
        cpu = round(52 + 16 * self._heat() + 3 * self._wave(7), 1)
        gpu, note = self.gpu_temperature()
        return {"cpu_temp": cpu, "gpu_temp": gpu, "gpu_note": note,
                "cpu_load": round(18 + 30 * self._heat() + 6 * self._wave(5, 2.0)), "fans": self.fans(),
                "battery": 78, "charging": False, "ac": True, "profile": self._profile}

    def info(self) -> dict:
        info = {
            "profiles": [{"id": p, "name": PROFILE_INFO[p][0], "icon": PROFILE_INFO[p][1],
                          "description": PROFILE_INFO[p][2]} for p in self.PROFILES],
            "profile": self._profile, "profile_via": "sysfs", "fans": self.fans(),
            "curves": [self.curve(f) for f in self.curve_fans()], "boost": self.boost(),
            "charge": self.charge(), "access": None, "write_access": True,
        }
        return info
