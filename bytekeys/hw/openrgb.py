"""Bridge to an OpenRGB SDK server (TCP, default port 6742).

OpenRGB supports hundreds of RGB controllers, including many laptop
keyboards ByteKeys has no native driver for. When an OpenRGB server is
running, its keyboards show up as ByteKeys devices and get the same effects,
rules and profiles as everything else.

The wire format is little endian: a 16 byte header (b"ORGB", device index,
packet id, payload size) followed by the payload. We speak protocol
version 3 and parse controller descriptions accordingly.
"""

from __future__ import annotations

import re
import socket
import struct
import threading

from ..color import RGB, scale
from .base import (
    ColorMode,
    Device,
    DeviceError,
    EffectInfo,
    Frame,
    Param,
    ZoneInfo,
)

MAGIC = b"ORGB"
HEADER = struct.Struct("<4sIII")
CLIENT_PROTOCOL = 3

REQUEST_CONTROLLER_COUNT = 0
REQUEST_CONTROLLER_DATA = 1
REQUEST_PROTOCOL_VERSION = 40
SET_CLIENT_NAME = 50
DEVICE_LIST_UPDATED = 100
UPDATELEDS = 1050
UPDATEZONELEDS = 1051
SETCUSTOMMODE = 1100
UPDATEMODE = 1101

MODE_FLAG_HAS_SPEED = 1 << 0
MODE_FLAG_HAS_DIRECTION_LR = 1 << 1
MODE_FLAG_HAS_DIRECTION_UD = 1 << 2
MODE_FLAG_HAS_DIRECTION_HV = 1 << 3
MODE_FLAG_HAS_BRIGHTNESS = 1 << 4
MODE_FLAG_HAS_PER_LED_COLOR = 1 << 5
MODE_FLAG_HAS_MODE_SPECIFIC_COLOR = 1 << 6

MODE_COLORS_MODE_SPECIFIC = 2

ZONE_TYPE_MATRIX = 2
NO_LED = 0xFFFFFFFF

DEVICE_TYPES = {
    0: "motherboard", 1: "dram", 2: "gpu", 3: "cooler", 4: "ledstrip",
    5: "keyboard", 6: "mouse", 7: "mousemat", 8: "headset", 9: "headset_stand",
    10: "gamepad", 11: "light", 12: "speaker", 13: "virtual", 14: "storage",
    15: "case", 16: "microphone", 17: "accessory", 18: "keypad", 19: "laptop",
}
KEYBOARD_TYPES = {5, 18}
LAPTOP_TYPE = 19   # "laptop" only on servers speaking protocol 6+; "unknown" on older ones

DIRECT_MODE_NAMES = ("direct", "custom", "static")


class ProtocolError(DeviceError):
    pass


class _Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def _unpack(self, fmt: str):
        try:
            values = struct.unpack_from(fmt, self.data, self.pos)
        except struct.error:
            raise ProtocolError("truncated OpenRGB controller description") from None
        self.pos += struct.calcsize(fmt)
        return values

    def u16(self) -> int:
        return self._unpack("<H")[0]

    def u32(self) -> int:
        return self._unpack("<I")[0]

    def i32(self) -> int:
        return self._unpack("<i")[0]

    def string(self) -> str:
        n = self.u16()
        raw = self.data[self.pos:self.pos + n]
        if len(raw) != n:
            raise ProtocolError("truncated string in OpenRGB data")
        self.pos += n
        return raw.split(b"\0", 1)[0].decode("utf-8", "replace")

    def color(self) -> RGB:
        r, g, b, _ = self._unpack("<4B")
        return (r, g, b)


def _pack_string(text: str) -> bytes:
    raw = text.encode("utf-8") + b"\0"
    return struct.pack("<H", len(raw)) + raw


def _pack_color(c: RGB) -> bytes:
    return struct.pack("<4B", c[0], c[1], c[2], 0)


def parse_controller(data: bytes, version: int) -> dict:
    r = _Reader(data)
    r.u32()  # total size
    ctrl: dict = {"type": r.i32(), "name": r.string()}
    ctrl["vendor"] = r.string() if version >= 1 else ""
    ctrl["description"] = r.string()
    ctrl["version"] = r.string()
    ctrl["serial"] = r.string()
    ctrl["location"] = r.string()
    num_modes = r.u16()
    ctrl["active_mode"] = r.i32()
    modes = []
    for i in range(num_modes):
        m: dict = {"index": i, "name": r.string(), "value": r.i32(), "flags": r.u32(),
                   "speed_min": r.u32(), "speed_max": r.u32()}
        if version >= 3:
            m["brightness_min"] = r.u32()
            m["brightness_max"] = r.u32()
        m["colors_min"] = r.u32()
        m["colors_max"] = r.u32()
        m["speed"] = r.u32()
        if version >= 3:
            m["brightness"] = r.u32()
        m["direction"] = r.u32()
        m["color_mode"] = r.u32()
        m["colors"] = [r.color() for _ in range(r.u16())]
        modes.append(m)
    ctrl["modes"] = modes
    zones = []
    for i in range(r.u16()):
        z: dict = {"index": i, "name": r.string(), "type": r.i32(), "leds_min": r.u32(),
                   "leds_max": r.u32(), "leds_count": r.u32(), "matrix": None}
        if r.u16() > 0:
            height, width = r.u32(), r.u32()
            z["matrix"] = (height, width, [r.u32() for _ in range(height * width)])
        zones.append(z)
    ctrl["zones"] = zones
    ctrl["leds"] = [{"name": r.string(), "value": r.u32()} for _ in range(r.u16())]
    ctrl["colors"] = [r.color() for _ in range(r.u16())]
    return ctrl


def pack_mode(mode: dict, version: int) -> bytes:
    body = _pack_string(mode["name"])
    body += struct.pack("<iIII", mode["value"], mode["flags"], mode["speed_min"], mode["speed_max"])
    if version >= 3:
        body += struct.pack("<II", mode.get("brightness_min", 0), mode.get("brightness_max", 0))
    body += struct.pack("<III", mode["colors_min"], mode["colors_max"], mode["speed"])
    if version >= 3:
        body += struct.pack("<I", mode.get("brightness", 0))
    body += struct.pack("<II", mode["direction"], mode["color_mode"])
    body += struct.pack("<H", len(mode["colors"])) + b"".join(_pack_color(c) for c in mode["colors"])
    payload = struct.pack("<i", mode["index"]) + body
    return struct.pack("<I", len(payload) + 4) + payload


class OpenRGBClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 6742, timeout: float = 1.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: socket.socket | None = None
        self.version = 0
        self.server_version = 0
        self.list_changed = False
        self.lock = threading.RLock()

    def connect(self) -> None:
        with self.lock:
            self.close()
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            sock.settimeout(self.timeout)
            self.sock = sock
            # Negotiate first (the server answers with its own maximum), then name ourselves.
            self._send(0, REQUEST_PROTOCOL_VERSION, struct.pack("<I", CLIENT_PROTOCOL))
            try:
                server = struct.unpack("<I", self._recv(REQUEST_PROTOCOL_VERSION, 1.0)[:4])[0]
            except (socket.timeout, struct.error):
                server = 0  # protocol 0 servers do not answer
            self.server_version = server
            self.version = min(CLIENT_PROTOCOL, server)
            self._send(0, SET_CLIENT_NAME, b"ByteKeys\0")

    def close(self) -> None:
        with self.lock:
            if self.sock is not None:
                try:
                    self.sock.close()
                finally:
                    self.sock = None

    def _send(self, device: int, packet: int, payload: bytes = b"") -> None:
        if self.sock is None:
            raise ProtocolError("not connected to OpenRGB")
        try:
            self.sock.sendall(HEADER.pack(MAGIC, device, packet, len(payload)) + payload)
        except OSError as e:
            self.close()
            raise ProtocolError(f"OpenRGB connection lost: {e}") from None

    def _recv_exact(self, n: int) -> bytes:
        assert self.sock is not None
        chunks = b""
        while len(chunks) < n:
            chunk = self.sock.recv(n - len(chunks))
            if not chunk:
                self.close()
                raise ProtocolError("OpenRGB closed the connection")
            chunks += chunk
        return chunks

    def _recv(self, packet: int, timeout: float | None = None) -> bytes:
        assert self.sock is not None
        if timeout is not None:
            self.sock.settimeout(timeout)
        try:
            while True:
                magic, _dev, pkt, size = HEADER.unpack(self._recv_exact(HEADER.size))
                if magic != MAGIC:
                    self.close()
                    raise ProtocolError("bad OpenRGB packet magic")
                data = self._recv_exact(size) if size else b""
                if pkt == packet:
                    return data
                if pkt == DEVICE_LIST_UPDATED:
                    self.list_changed = True
        finally:
            if timeout is not None and self.sock is not None:
                self.sock.settimeout(self.timeout)

    def controller_count(self) -> int:
        with self.lock:
            self._send(0, REQUEST_CONTROLLER_COUNT)
            return struct.unpack("<I", self._recv(REQUEST_CONTROLLER_COUNT)[:4])[0]

    def controller(self, index: int) -> dict:
        with self.lock:
            payload = struct.pack("<I", self.version) if self.version >= 1 else b""
            self._send(index, REQUEST_CONTROLLER_DATA, payload)
            return parse_controller(self._recv(REQUEST_CONTROLLER_DATA), self.version)

    def set_custom_mode(self, index: int) -> None:
        with self.lock:
            self._send(index, SETCUSTOMMODE)

    def update_leds(self, index: int, colors: list[RGB]) -> None:
        payload = struct.pack("<H", len(colors)) + b"".join(_pack_color(c) for c in colors)
        with self.lock:
            self._send(index, UPDATELEDS, struct.pack("<I", len(payload) + 4) + payload)

    def update_mode(self, index: int, mode: dict) -> None:
        with self.lock:
            self._send(index, UPDATEMODE, pack_mode(mode, self.version))


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "device"


def _key_label(led_name: str) -> str:
    name = led_name.split(":", 1)[1].strip() if ":" in led_name else led_name
    return name


class OpenRGBKeyboard(Device):
    backend = "openrgb"

    def __init__(self, client: OpenRGBClient, index: int, ctrl: dict):
        super().__init__(f"openrgb:{_slug(ctrl['name'])}", ctrl["name"])
        self.client = client
        self.index = index
        self.ctrl = ctrl
        self.vendor = ctrl.get("vendor", "")
        self.path = f"OpenRGB #{index} ({ctrl.get('location', '')})"
        self.brightness_hw = False
        self.brightness_max = 100
        self.max_fps = 30
        self._custom_mode_set = False
        leds = ctrl["leds"]
        n = len(leds)
        matrix_zone = max(
            (z for z in ctrl["zones"] if z["type"] == ZONE_TYPE_MATRIX and z["matrix"]),
            key=lambda z: z["leds_count"], default=None,
        )
        if n <= 1:
            self.color_mode = ColorMode.SINGLE
        elif n <= 8 and matrix_zone is None:
            self.color_mode = ColorMode.ZONES
            self.zones = [ZoneInfo(i, _key_label(led["name"])) for i, led in enumerate(leds)]
            self.layout = "zones"
        else:
            self.color_mode = ColorMode.PERKEY
            positions: dict[int, tuple[int, int]] = {}
            if matrix_zone is not None:
                height, width, cells = matrix_zone["matrix"]
                offset = sum(z["leds_count"] for z in ctrl["zones"][:matrix_zone["index"]])
                for cell, led in enumerate(cells):
                    if led != NO_LED:
                        positions[offset + led] = (cell // width, cell % width)
                self.matrix = (height, width)
                self.layout = "perkey-matrix"
            else:
                self.layout = "perkey-list"
            self.zones = [
                ZoneInfo(i, _key_label(led["name"]), *positions.get(i, (None, None)),
                         key=_key_label(led["name"]))
                for i, led in enumerate(leds)
            ]
        self._modes = {}
        for mode in ctrl["modes"]:
            if mode["name"].lower() in DIRECT_MODE_NAMES or mode["name"].lower() == "off":
                continue
            eid = "mode-" + _slug(mode["name"])
            self._modes[eid] = mode
            self.hw_effects.append(self._effect_info(eid, mode))

    def _effect_info(self, eid: str, mode: dict) -> EffectInfo:
        params: list[Param] = []
        flags = mode["flags"]
        if flags & MODE_FLAG_HAS_SPEED:
            lo, hi = sorted((mode["speed_min"], mode["speed_max"]))
            params.append(Param("speed", "Speed", "range", default=mode["speed"], min=lo, max=hi))
        if flags & MODE_FLAG_HAS_DIRECTION_LR:
            params.append(Param("direction", "Direction", "choice", default="0",
                                choices=[["0", "Left"], ["1", "Right"]]))
        elif flags & MODE_FLAG_HAS_DIRECTION_UD:
            params.append(Param("direction", "Direction", "choice", default="2",
                                choices=[["2", "Up"], ["3", "Down"]]))
        if flags & MODE_FLAG_HAS_BRIGHTNESS and mode.get("brightness_max", 0) > 0:
            params.append(Param("hw_brightness", "Brightness", "range",
                                default=mode.get("brightness", mode["brightness_max"]),
                                min=mode.get("brightness_min", 0), max=mode["brightness_max"]))
        colors = mode["colors_max"] if mode["color_mode"] == MODE_COLORS_MODE_SPECIFIC else 0
        return EffectInfo(eid, mode["name"], True, params, colors=min(colors, 4))

    def _show(self, frame: Frame, prev: Frame | None) -> None:
        try:
            if frame.effect and frame.effect in self._modes:
                if prev is None or prev.effect != frame.effect or prev.params != frame.params \
                        or prev.effect_colors != frame.effect_colors:
                    mode = dict(self._modes[frame.effect])
                    p = frame.params
                    if "speed" in p:
                        mode["speed"] = int(p["speed"])
                    if "direction" in p:
                        mode["direction"] = int(p["direction"])
                    if "hw_brightness" in p:
                        mode["brightness"] = int(p["hw_brightness"])
                    if frame.effect_colors and mode["colors_max"]:
                        mode["colors"] = list(frame.effect_colors[:mode["colors_max"]])
                    self.client.update_mode(self.index, mode)
                    self._custom_mode_set = False
                return
            if not self._custom_mode_set:
                self.client.set_custom_mode(self.index)
                self._custom_mode_set = True
            n = max(1, len(self.ctrl["leds"]))
            if not frame.on or not frame.colors:
                colors = [(0, 0, 0)] * n
            else:
                factor = frame.level / 100.0
                base = frame.colors
                colors = [scale(base[i] if i < len(base) else base[-1], factor) for i in range(n)]
            self.client.update_leds(self.index, colors)
        except ProtocolError:
            self._custom_mode_set = False
            raise

    def diagnostics(self) -> dict:
        info = super().diagnostics()
        info.update({
            "openrgb_type": DEVICE_TYPES.get(self.ctrl["type"], self.ctrl["type"]),
            "leds": len(self.ctrl["leds"]),
            "zones": [(z["name"], z["leds_count"]) for z in self.ctrl["zones"]],
            "modes": [m["name"] for m in self.ctrl["modes"]],
            "protocol": self.client.version,
        })
        return info


def discover(host: str = "127.0.0.1", port: int = 6742, all_devices: bool = False) -> list[Device]:
    client = OpenRGBClient(host, port, timeout=0.6)
    try:
        client.connect()
        count = client.controller_count()
        devices: list[Device] = []
        for i in range(count):
            ctrl = client.controller(i)
            laptop = ctrl["type"] == LAPTOP_TYPE and client.server_version >= 6
            if all_devices or laptop or ctrl["type"] in KEYBOARD_TYPES or "keyboard" in ctrl["name"].lower():
                devices.append(OpenRGBKeyboard(client, i, ctrl))
        if not devices:
            client.close()
        return devices
    except (OSError, ProtocolError):
        client.close()
        return []
