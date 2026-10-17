"""Build fake /sys, /proc and /dev trees for tests (see bytekeys.fsroot)."""

from __future__ import annotations

import os
import shutil
import tempfile
import time

from bytekeys import fsroot


class FakeSys:
    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="bk-fsroot-")
        self._previous = fsroot.get_root()
        fsroot.set_root(self.root)

    def close(self) -> None:
        fsroot.set_root(self._previous)
        shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self) -> "FakeSys":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------- writing
    def write(self, path: str, content: str | bytes = "", mode: int = 0o644) -> None:
        full = self.root + path
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb" if isinstance(content, bytes) else "w") as f:
            f.write(content)
        os.chmod(full, mode)

    def read(self, path: str) -> str:
        full = self.root + path
        os.chmod(full, os.stat(full).st_mode | 0o400)   # write-only sysfs attributes
        with open(full) as f:
            return f.read()

    def mkdir(self, path: str) -> None:
        os.makedirs(self.root + path, exist_ok=True)

    def symlink(self, target: str, path: str) -> None:
        full = self.root + path
        os.makedirs(os.path.dirname(full), exist_ok=True)
        os.symlink(self.root + target, full)

    # ----------------------------------------------------------- hardware
    def dmi(self, **fields: str) -> None:
        for k, v in fields.items():
            self.write(f"/sys/class/dmi/id/{k}", v + "\n")

    def led(self, name: str, max_brightness: int = 255, brightness: int = 0, **attrs: str) -> str:
        base = f"/sys/class/leds/{name}"
        self.write(f"{base}/max_brightness", f"{max_brightness}\n", 0o444)
        self.write(f"{base}/brightness", f"{brightness}\n")
        self.write(f"{base}/trigger", "[none] kbd-capslock\n")
        for attr, value in attrs.items():
            mode = 0o200 if value is None else 0o644
            self.write(f"{base}/{attr}", "" if value is None else value, mode)
        return base

    def power(self, ac: bool = True, battery: int | None = 80, status: str = "Discharging") -> None:
        self.write("/sys/class/power_supply/AC/type", "Mains\n")
        self.write("/sys/class/power_supply/AC/online", "1\n" if ac else "0\n")
        if battery is not None:
            self.write("/sys/class/power_supply/BAT0/type", "Battery\n")
            self.write("/sys/class/power_supply/BAT0/capacity", f"{battery}\n")
            self.write("/sys/class/power_supply/BAT0/status", status + "\n")

    def cpu_temp(self, celsius: float) -> None:
        self.write("/sys/class/hwmon/hwmon3/name", "coretemp\n")
        self.write("/sys/class/hwmon/hwmon3/temp1_label", "Package id 0\n")
        self.write("/sys/class/hwmon/hwmon3/temp1_input", f"{int(celsius * 1000)}\n")

    def hidraw(self, node: str, vid: int, pid: int, interface: int = 0, descriptor: bytes = b"",
               name: str = "Test Device") -> None:
        dev = f"/sys/devices/pci0000:00/usb1/1-3/1-3:1.{interface}/0003:{vid:04X}:{pid:04X}.000{interface}"
        self.write(f"{dev}/uevent", f"HID_ID=0003:{vid:08X}:{pid:08X}\nHID_NAME={name}\nHID_PHYS=usb-1-3/input{interface}\n")
        self.write(f"{dev}/report_descriptor", descriptor)
        self.write(f"/sys/devices/pci0000:00/usb1/1-3/1-3:1.{interface}/bInterfaceNumber", f"{interface:02x}\n")
        self.symlink(dev, f"/sys/class/hidraw/{node}/device")
        self.write(f"/dev/{node}", "", 0o600)


def wait_for(predicate, timeout: float = 3.0, interval: float = 0.02) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()
