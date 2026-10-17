"""Base class and discovery for USB HID lighting controllers."""

from __future__ import annotations

import os
from typing import Callable

from .. import fsroot
from .base import AccessError, Device, DeviceError
from .hidraw import HidInfo, HidrawTransport, enumerate_hidraw

ROOT_HINT = "Install the ByteKeys service: lighting controllers are only accessible to root."


class HidKeyboard(Device):
    """A keyboard lighting controller reached through /dev/hidrawN."""

    backend = "hid"
    DRIVER = "hid"
    VENDOR = ""
    # (vid, pid) -> model description
    PRODUCTS: dict[tuple[int, int], str] = {}

    @classmethod
    def score(cls, info: HidInfo) -> int:
        """How well *info* fits this driver: 0 = not ours, higher = better interface."""
        return 1 if (info.vid, info.pid) in cls.PRODUCTS else 0

    def __init__(self, info: HidInfo, transport_factory: Callable | None = None):
        model = self.PRODUCTS.get((info.vid, info.pid), "")
        super().__init__(f"hid:{info.vid:04x}:{info.pid:04x}", model or f"{self.VENDOR} Keyboard")
        self.info = info
        self.vendor = self.VENDOR
        self.path = info.devnode
        self._factory = transport_factory or HidrawTransport
        self._transport = None

    @property
    def transport(self):
        if self._transport is None:
            self._transport = self._factory(self.info.devnode)
        return self._transport

    def access_problem(self) -> str | None:
        if self._factory is not HidrawTransport:
            return None
        if os.access(fsroot.path(self.info.devnode), os.R_OK | os.W_OK):
            return None
        return f"No permission to use {self.info.devnode}. {ROOT_HINT}"

    def _feature(self, data: bytes | list[int]) -> None:
        self._io(self.transport.send_feature, bytes(data))

    def _output(self, data: bytes | list[int]) -> None:
        self._io(self.transport.write, bytes(data))

    def _io(self, fn, *args):
        try:
            return fn(*args)
        except AccessError:
            raise
        except DeviceError:
            self.close()  # reopen on the next attempt (device may have reset)
            raise

    def close(self) -> None:
        if self._transport is not None:
            try:
                self._transport.close()
            finally:
                self._transport = None

    def diagnostics(self) -> dict:
        info = super().diagnostics()
        info.update({
            "driver": self.DRIVER,
            "hidraw": self.info.label(),
            "name": self.info.name,
            "applications": [f"{p:04x}:{u:04x}" for p, u in self.info.reports.applications],
            "feature_reports": {f"{k:#04x}": v for k, v in self.info.reports.feature.items()},
            "output_reports": {f"{k:#04x}": v for k, v in self.info.reports.output.items()},
        })
        return info


def discover(drivers: list[type[HidKeyboard]], infos: list[HidInfo] | None = None) -> list[Device]:
    """Instantiate one driver per physical controller, on its best interface."""
    infos = enumerate_hidraw() if infos is None else infos
    best: dict[tuple, tuple[int, type[HidKeyboard], HidInfo]] = {}
    for info in infos:
        for driver in drivers:
            score = driver.score(info)
            if score <= 0:
                continue
            key = (info.vid, info.pid, info.parent or info.phys.split("/")[0])
            if key not in best or score > best[key][0]:
                best[key] = (score, driver, info)
    devices: list[Device] = []
    for _score, driver, info in best.values():
        try:
            devices.append(driver(info))
        except DeviceError:
            continue
    return devices
