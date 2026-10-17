"""Notice keyboard/mouse activity for idle timeouts, the Reactive effect and
the vendor "launch" key (Armoury Crate, NitroSense, Omen... keys).

Only timestamps are kept. The single key code that is ever compared is the
configured launch key (and, while the user asks ByteKeys to detect it, the
next vendor/special key). Nothing typed is stored or logged. Reading
/dev/input requires root, so this runs inside the service.
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

# Keys vendors use for their control-center apps. Only these can be learned as the
# launch key, so detection can never capture letters, digits or passwords.
# F20-F23 are left out: desktops use them for mic mute and the touchpad (and F23 for the Copilot key).
SPECIAL_KEYS: dict[int, str] = {
    148: "KEY_PROG1", 149: "KEY_PROG2", 202: "KEY_PROG3", 203: "KEY_PROG4", 171: "KEY_CONFIG",
    360: "KEY_VENDOR", 364: "KEY_FAVORITES", 156: "KEY_BOOKMARKS", 140: "KEY_CALC", 425: "KEY_PRESENTATION",
    138: "KEY_HELP", 141: "KEY_SETUP", 226: "KEY_MEDIA", 358: "KEY_INFO", 444: "KEY_NOTIFICATION_CENTER",
    579: "KEY_CONTROLPANEL", 701: "KEY_PERFORMANCE",
    **{656 + i: f"KEY_MACRO{1 + i}" for i in range(5)},
    **{183 + i: f"KEY_F{13 + i}" for i in range(7)}, 194: "KEY_F24",
}


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
    hotkeys = any(keys >> code & 1 for code in SPECIAL_KEYS)   # e.g. "Asus WMI hotkeys"
    return keyboard or pointer or hotkeys, keyboard


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
        self._halt = threading.Event()   # not "_stop": that shadows Thread._stop on Python <= 3.12
        self.launch_code = 0
        self.on_launch: Callable[[], None] | None = None
        self._learning: threading.Event | None = None
        self._learned: int | None = None

    def learn(self, timeout: float = 10.0) -> int | None:
        """Wait for the next vendor/special key press and return its code."""
        self._learned = None
        self._learning = threading.Event()
        try:
            self._learning.wait(timeout)
            return self._learned
        finally:
            self._learning = None

    def idle_seconds(self) -> float:
        return time.monotonic() - self.last_activity

    def available(self) -> bool:
        self._rescan()
        return bool(self.devices)

    def stop(self) -> None:
        self._halt.set()

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
        while not self._halt.is_set():
            now = time.monotonic()
            if now - last_scan > 10:
                self._rescan()
                last_scan = now
            if not self.devices:
                self._halt.wait(5)
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
                if not data:      # end of file: the device went away
                    self._close(node)
                    continue
                self._handle(data, keyboard)
        for node in list(self.devices):
            self._close(node)

    def _handle(self, data: bytes, keyboard: bool) -> None:
        pressed = active = False
        for off in range(0, len(data) - EVENT.size + 1, EVENT.size):
            _s, _us, etype, code, value = EVENT.unpack_from(data, off)
            if etype == EV_KEY:
                active = True
                if value == 1:
                    if keyboard:
                        pressed = True
                    if self._learning is not None and code in SPECIAL_KEYS:
                        self._learned = code
                        self._learning.set()
                    elif code == self.launch_code and self.on_launch:
                        self.on_launch()
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
