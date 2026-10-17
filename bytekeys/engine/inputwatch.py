"""Notice keyboard/mouse activity for idle timeouts and the Reactive effect.

Only timestamps are kept: which keys were pressed is never looked at,
stored or logged. Reading /dev/input requires root, so this runs inside the
service.
"""

from __future__ import annotations

import logging
import os
import selectors
import struct
import threading
import time
from typing import Callable

from .. import fsroot

log = logging.getLogger(__name__)

EVENT = struct.Struct("llHHi")   # struct input_event on 64-bit Linux
EV_KEY, EV_REL, EV_ABS = 0x01, 0x02, 0x03
KEY_A, KEY_SPACE, BTN_LEFT, BTN_TOUCH = 30, 57, 0x110, 0x14A


def _bits(text: str | None) -> int:
    """Parse a sysfs capability bitmap (space separated hex words, most significant first)."""
    if not text:
        return 0
    value = 0
    for word in text.split():
        value = (value << 64) | int(word, 16)
    return value


def _interesting(event_node: str) -> tuple[bool, bool]:
    """(watch it, is a keyboard) for /dev/input/<event_node>."""
    caps = f"/sys/class/input/{event_node}/device/capabilities"
    ev = _bits(fsroot.read(f"{caps}/ev"))
    if not ev & (1 << EV_KEY):
        return False, False
    keys = _bits(fsroot.read(f"{caps}/key"))
    keyboard = bool(keys >> KEY_A & 1 and keys >> KEY_SPACE & 1)
    pointer = bool(keys >> BTN_LEFT & 1 or keys >> BTN_TOUCH & 1)
    return keyboard or pointer, keyboard


class InputWatcher(threading.Thread):
    def __init__(self, on_key: Callable[[], None] | None = None,
                 on_wake: Callable[[], None] | None = None, idle_wake_after: float = 5.0):
        super().__init__(name="bytekeys-input", daemon=True)
        self.on_key = on_key
        self.on_wake = on_wake
        self.idle_wake_after = idle_wake_after
        self.last_activity = time.monotonic()
        self.last_key: float | None = None
        self.devices: dict[str, int] = {}
        self._sel = selectors.DefaultSelector()
        self._stop = threading.Event()

    def idle_seconds(self) -> float:
        return time.monotonic() - self.last_activity

    def available(self) -> bool:
        self._rescan()
        return bool(self.devices)

    def stop(self) -> None:
        self._stop.set()

    def _rescan(self) -> None:
        present = {n for n in fsroot.listdir("/dev/input") if n.startswith("event")}
        for node in list(self.devices):
            if node not in present:
                self._close(node)
        for node in sorted(present - set(self.devices)):
            watch, keyboard = _interesting(node)
            if not watch:
                continue
            try:
                fd = os.open(fsroot.path(f"/dev/input/{node}"), os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
            except OSError:
                continue
            self.devices[node] = fd
            self._sel.register(fd, selectors.EVENT_READ, (node, keyboard))

    def _close(self, node: str) -> None:
        fd = self.devices.pop(node, None)
        if fd is None:
            return
        try:
            self._sel.unregister(fd)
        except (KeyError, ValueError):
            pass
        os.close(fd)

    def run(self) -> None:
        last_scan = 0.0
        while not self._stop.is_set():
            now = time.monotonic()
            if now - last_scan > 10:
                self._rescan()
                last_scan = now
            if not self.devices:
                self._stop.wait(5)
                continue
            for key, _ in self._sel.select(timeout=2.0):
                node, keyboard = key.data
                try:
                    data = os.read(key.fd, EVENT.size * 64)
                except BlockingIOError:
                    continue
                except OSError:
                    self._close(node)
                    continue
                self._handle(data, keyboard)
        for node in list(self.devices):
            self._close(node)

    def _handle(self, data: bytes, keyboard: bool) -> None:
        pressed = active = False
        for off in range(0, len(data) - EVENT.size + 1, EVENT.size):
            _s, _us, etype, _code, value = EVENT.unpack_from(data, off)
            if etype == EV_KEY:
                active = True
                if keyboard and value == 1:
                    pressed = True
            elif etype in (EV_REL, EV_ABS):
                active = True
        if not active:
            return
        now = time.monotonic()
        was_idle = now - self.last_activity >= self.idle_wake_after
        self.last_activity = now
        if pressed:
            self.last_key = now
            if self.on_key:
                self.on_key()
        if was_idle and self.on_wake:
            self.on_wake()
