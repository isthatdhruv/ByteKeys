"""Minimal hidraw access without third-party libraries.

Enumeration only reads sysfs (world readable), so detection works without
privileges. I/O goes through /dev/hidrawN with the standard hidraw ioctls.
"""

from __future__ import annotations

import fcntl
import os
import select
from dataclasses import dataclass, field

from .. import fsroot
from .base import AccessError, DeviceError

HIDRAW_CLASS = "/sys/class/hidraw"

BUS_USB = 0x03
BUS_I2C = 0x18

_IOC_WRITE = 1
_IOC_READ = 2


def _ioc(direction: int, nr: int, size: int) -> int:
    # Generic Linux ioctl encoding (x86, ARM, RISC-V).
    return (direction << 30) | (size << 16) | (ord("H") << 8) | nr


def HIDIOCSFEATURE(size: int) -> int:
    return _ioc(_IOC_WRITE | _IOC_READ, 0x06, size)


def HIDIOCGFEATURE(size: int) -> int:
    return _ioc(_IOC_WRITE | _IOC_READ, 0x07, size)


def HIDIOCGINPUT(size: int) -> int:
    return _ioc(_IOC_WRITE | _IOC_READ, 0x0A, size)


@dataclass
class Element:
    """One data element of a report: its usage and where its bits live."""

    usage: int            # (usage page << 16) | usage id
    offset: int           # bit offset after the report ID byte
    size: int             # bits
    collection: int       # usage of the innermost enclosing collection


@dataclass
class ReportInfo:
    """What a HID report descriptor declares."""

    applications: list[tuple[int, int]] = field(default_factory=list)  # (usage page, usage)
    input: dict[int, int] = field(default_factory=dict)     # report id -> bytes incl. id byte
    output: dict[int, int] = field(default_factory=dict)
    feature: dict[int, int] = field(default_factory=dict)
    # (kind, report id) -> elements, kind being "input" | "output" | "feature"
    layouts: dict[tuple[str, int], list[Element]] = field(default_factory=dict)

    @property
    def usage_pages(self) -> set[int]:
        return {page for page, _ in self.applications}

    def report_for(self, kind: str, collection: int) -> int | None:
        """Report ID whose elements sit in a collection with the given usage."""
        for (k, rid), elements in self.layouts.items():
            if k == kind and any(e.collection == collection for e in elements):
                return rid
        return None

    def pack(self, kind: str, report_id: int, values: dict[int, list[int]]) -> bytes:
        """Build a report buffer (report ID first) from per-usage value lists."""
        size = getattr(self, kind)[report_id]
        buf = bytearray(size)
        body = 1 if report_id else 0
        buf[0] = report_id
        cursor: dict[int, int] = {}
        for e in self.layouts.get((kind, report_id), []):
            seq = values.get(e.usage)
            if not seq:
                continue
            n = cursor.get(e.usage, 0)
            if n >= len(seq):
                continue
            cursor[e.usage] = n + 1
            value = int(seq[n]) & ((1 << e.size) - 1)
            for bit in range(e.size):
                if value >> bit & 1:
                    pos = e.offset + bit
                    buf[body + pos // 8] |= 1 << (pos % 8)
        return bytes(buf)

    def unpack(self, kind: str, report_id: int, data: bytes) -> dict[int, list[int]]:
        out: dict[int, list[int]] = {}
        body = 1 if report_id else 0
        for e in self.layouts.get((kind, report_id), []):
            value = 0
            for bit in range(e.size):
                pos = e.offset + bit
                idx = body + pos // 8
                if idx < len(data) and data[idx] >> (pos % 8) & 1:
                    value |= 1 << bit
            out.setdefault(e.usage, []).append(value)
        return out


def parse_report_descriptor(desc: bytes) -> ReportInfo:
    """Walk a HID report descriptor: application usages, report sizes and element layouts."""
    info = ReportInfo()
    usage_page = report_size = report_id = report_count = 0
    stack: list[tuple[int, int, int, int]] = []
    usages: list[int] = []
    usage_min: int | None = None
    collections: list[int] = []
    bits: dict[str, dict[int, int]] = {"input": {}, "output": {}, "feature": {}}
    i = 0

    def full(data: int, size: int) -> int:
        return data if size == 4 else (usage_page << 16) | data

    while i < len(desc):
        prefix = desc[i]
        if prefix == 0xFE:  # long item: 0xFE, size, tag, data...
            if i + 1 >= len(desc):
                break
            i += 3 + desc[i + 1]
            continue
        size = (0, 1, 2, 4)[prefix & 0x3]
        kind = (prefix >> 2) & 0x3
        tag = (prefix >> 4) & 0xF
        data = int.from_bytes(desc[i + 1:i + 1 + size], "little") if size else 0
        i += 1 + size
        if kind == 1:  # global
            if tag == 0x0:
                usage_page = data
            elif tag == 0x7:
                report_size = data
            elif tag == 0x8:
                report_id = data
            elif tag == 0x9:
                report_count = data
            elif tag == 0xA:
                stack.append((usage_page, report_size, report_id, report_count))
            elif tag == 0xB and stack:
                usage_page, report_size, report_id, report_count = stack.pop()
        elif kind == 2:  # local
            if tag == 0x0:
                usages.append(full(data, size))
            elif tag == 0x1:
                usage_min = full(data, size)
            elif tag == 0x2 and usage_min is not None:
                last = full(data, size)
                usages.extend(range(usage_min, min(last, usage_min + 1024) + 1))
                usage_min = None
        elif kind == 0:  # main
            if tag == 0xA:  # collection
                usage = usages[0] if usages else 0
                if not collections and data == 0x01 and usages:
                    info.applications.append((usage >> 16, usage & 0xFFFF))
                collections.append(usage)
            elif tag == 0xC:
                if collections:
                    collections.pop()
            elif tag in (0x8, 0x9, 0xB):
                name = {0x8: "input", 0x9: "output", 0xB: "feature"}[tag]
                start = bits[name].get(report_id, 0)
                constant = bool(data & 0x01)
                layout = info.layouts.setdefault((name, report_id), [])
                if not constant:
                    for n in range(report_count):
                        usage = usages[min(n, len(usages) - 1)] if usages else 0
                        layout.append(Element(usage, start + n * report_size, report_size,
                                              collections[-1] if collections else 0))
                bits[name][report_id] = start + report_size * report_count
            usages = []
            usage_min = None
    for name, table in bits.items():
        sizes = {rid: (nbits + 7) // 8 + (1 if rid else 0) for rid, nbits in table.items()}
        setattr(info, name, sizes)
    return info


@dataclass
class HidInfo:
    node: str                 # "hidraw3"
    devnode: str              # "/dev/hidraw3"
    bus: int
    vid: int
    pid: int
    name: str
    phys: str = ""
    uniq: str = ""
    interface: int | None = None
    parent: str = ""          # sysfs path of the physical (USB) device
    descriptor: bytes = b""
    reports: ReportInfo = field(default_factory=ReportInfo)
    driver: str = ""          # kernel HID driver bound to the device ("hid-generic", "ite_8291"...)
    bcd_device: int | None = None

    @property
    def usb(self) -> bool:
        return self.bus == BUS_USB

    def label(self) -> str:
        iface = f" if{self.interface}" if self.interface is not None else ""
        return f"{self.vid:04x}:{self.pid:04x}{iface} ({self.node})"


def _parse_uevent(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def enumerate_hidraw() -> list[HidInfo]:
    devices: list[HidInfo] = []
    for node in fsroot.listdir(HIDRAW_CLASS):
        base = f"{HIDRAW_CLASS}/{node}/device"
        uevent = _parse_uevent(fsroot.read(f"{base}/uevent", "") or "")
        hid_id = uevent.get("HID_ID", "")
        try:
            bus_s, vid_s, pid_s = hid_id.split(":")
            bus, vid, pid = int(bus_s, 16), int(vid_s, 16), int(pid_s, 16)
        except ValueError:
            continue
        hid_dev = fsroot.realpath(base)              # .../3-7:1.1/0003:048D:C965.0001
        usb_iface = os.path.dirname(hid_dev)         # .../3-7:1.1
        iface_text = fsroot.read(f"{usb_iface}/bInterfaceNumber")  # hex, e.g. "01"
        try:
            iface = int(iface_text, 16) if iface_text else None
        except ValueError:
            iface = None
        descriptor = fsroot.read_bytes(f"{base}/report_descriptor", b"") or b""
        driver = os.path.basename(fsroot.realpath(f"{base}/driver")) if fsroot.exists(f"{base}/driver") else ""
        usb_dev = os.path.dirname(usb_iface) if iface is not None else ""
        bcd_text = fsroot.read(f"{usb_dev}/bcdDevice") if usb_dev else None
        try:
            bcd = int(bcd_text, 16) if bcd_text else None
        except ValueError:
            bcd = None
        devices.append(HidInfo(
            node=node,
            devnode=f"/dev/{node}",
            bus=bus,
            vid=vid,
            pid=pid,
            name=uevent.get("HID_NAME", ""),
            phys=uevent.get("HID_PHYS", ""),
            uniq=uevent.get("HID_UNIQ", ""),
            interface=iface,
            parent=os.path.dirname(usb_iface) if iface is not None else usb_iface,
            descriptor=descriptor,
            reports=parse_report_descriptor(descriptor),
            driver=driver,
            bcd_device=bcd,
        ))
    return devices


class HidrawTransport:
    """Feature/output report I/O on one /dev/hidrawN node."""

    def __init__(self, devnode: str):
        self.devnode = devnode
        try:
            self.fd = os.open(fsroot.path(devnode), os.O_RDWR | os.O_CLOEXEC)
        except PermissionError:
            raise AccessError(
                f"no permission to open {devnode}",
                "Install the ByteKeys service: lighting controllers are only accessible to root.",
            ) from None
        except OSError as e:
            raise DeviceError(f"cannot open {devnode}: {e.strerror or e}") from None

    def send_feature(self, data: bytes) -> None:
        buf = bytearray(data)
        try:
            fcntl.ioctl(self.fd, HIDIOCSFEATURE(len(buf)), buf)
        except OSError as e:
            raise DeviceError(f"{self.devnode}: set feature report failed: {e.strerror or e}") from None

    def get_feature(self, report_id: int, length: int) -> bytes:
        buf = bytearray(length)
        buf[0] = report_id
        try:
            fcntl.ioctl(self.fd, HIDIOCGFEATURE(length), buf)
        except OSError as e:
            raise DeviceError(f"{self.devnode}: get feature report failed: {e.strerror or e}") from None
        return bytes(buf)

    def write(self, data: bytes) -> None:
        try:
            os.write(self.fd, bytes(data))
        except OSError as e:
            raise DeviceError(f"{self.devnode}: write failed: {e.strerror or e}") from None

    def read(self, length: int, timeout: float = 0.2) -> bytes | None:
        ready, _, _ = select.select([self.fd], [], [], timeout)
        if not ready:
            return None
        try:
            return os.read(self.fd, length)
        except OSError as e:
            raise DeviceError(f"{self.devnode}: read failed: {e.strerror or e}") from None

    def close(self) -> None:
        if self.fd >= 0:
            try:
                os.close(self.fd)
            finally:
                self.fd = -1


class RecordingTransport:
    """Test double that records every report instead of touching hardware."""

    def __init__(self, devnode: str = "/dev/null", replies: dict[int, bytes] | None = None):
        self.devnode = devnode
        self.sent: list[tuple[str, bytes]] = []
        self.replies = replies or {}

    def send_feature(self, data: bytes) -> None:
        self.sent.append(("feature", bytes(data)))

    def get_feature(self, report_id: int, length: int) -> bytes:
        return self.replies.get(report_id, bytes([report_id]) + bytes(length - 1))

    def write(self, data: bytes) -> None:
        self.sent.append(("output", bytes(data)))

    def read(self, length: int, timeout: float = 0.2) -> bytes | None:
        return None

    def close(self) -> None:
        pass
