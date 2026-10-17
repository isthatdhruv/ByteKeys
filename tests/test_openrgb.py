"""OpenRGB SDK client against a small fake server."""

import socket
import struct
import threading
import unittest

from bytekeys.hw import openrgb
from bytekeys.hw.base import ColorMode, Frame


def s16(text: str) -> bytes:
    raw = text.encode() + b"\0"
    return struct.pack("<H", len(raw)) + raw


def controller_blob(version: int) -> bytes:
    """A 4-LED laptop keyboard with Direct and Breathing modes, serialized like OpenRGB."""
    body = struct.pack("<i", 5) + s16("Legion 4-Zone Keyboard")
    if version >= 1:
        body += s16("Lenovo")
    body += s16("desc") + s16("1.0") + s16("") + s16("HID: /dev/hidraw7")
    modes = [("Direct", 0, 1 << 5, 0, 0, 0, 1), ("Breathing", 3, 1 | 1 << 6, 1, 4, 1, 2)]
    body += struct.pack("<Hi", len(modes), 0)
    for name, value, flags, smin, smax, cmin, cmode in modes:
        body += s16(name) + struct.pack("<iIII", value, flags, smin, smax)
        if version >= 3:
            body += struct.pack("<II", 0, 0)
        body += struct.pack("<III", cmin, cmin, smin)
        if version >= 3:
            body += struct.pack("<I", 0)
        body += struct.pack("<II", 0, cmode)
        body += struct.pack("<H", cmin) + b"\xff\x00\x00\x00" * cmin
    body += struct.pack("<H", 1) + s16("Keyboard") + struct.pack("<iIII", 1, 4, 4, 4) + struct.pack("<H", 0)
    body += struct.pack("<H", 4) + b"".join(s16(f"Zone {i}") + struct.pack("<I", i) for i in range(4))
    body += struct.pack("<H", 4) + bytes(16)
    return struct.pack("<I", len(body) + 4) + body


class FakeServer(threading.Thread):
    def __init__(self, server_version=4):
        super().__init__(daemon=True)
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.server_version = server_version
        self.negotiated = 0
        self.packets = []
        self.done = threading.Event()

    def run(self):
        conn, _ = self.sock.accept()
        with conn:
            buf = b""
            while True:
                try:
                    chunk = conn.recv(65536)
                except OSError:
                    break
                if not chunk:
                    break
                buf += chunk
                while len(buf) >= 16:
                    magic, dev, pkt, size = struct.unpack("<4sIII", buf[:16])
                    if len(buf) < 16 + size:
                        break
                    data, buf = buf[16:16 + size], buf[16 + size:]
                    self.packets.append((pkt, dev, data))
                    reply = None
                    if pkt == openrgb.REQUEST_PROTOCOL_VERSION:
                        self.negotiated = min(struct.unpack("<I", data)[0], self.server_version)
                        reply = struct.pack("<I", self.server_version)
                    elif pkt == openrgb.REQUEST_CONTROLLER_COUNT:
                        reply = struct.pack("<I", 1)
                    elif pkt == openrgb.REQUEST_CONTROLLER_DATA:
                        reply = controller_blob(self.negotiated)
                    if reply is not None:
                        conn.sendall(struct.pack("<4sIII", b"ORGB", dev, pkt, len(reply)) + reply)
        self.done.set()


class OpenRGBTest(unittest.TestCase):
    def test_discover_and_drive(self):
        server = FakeServer()
        server.start()
        (dev,) = openrgb.discover("127.0.0.1", server.port)
        self.assertEqual(dev.client.version, 3)
        self.assertEqual(dev.name, "Legion 4-Zone Keyboard")
        self.assertEqual(dev.color_mode, ColorMode.ZONES)
        self.assertEqual([e.id for e in dev.hw_effects], ["mode-breathing"])
        self.assertEqual(server.packets[0][0], openrgb.REQUEST_PROTOCOL_VERSION)   # negotiate first
        dev.show(Frame(on=True, level=50, colors=[(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]))
        dev.show(Frame(on=True, level=100, colors=[(0, 0, 0)] * 4, effect="mode-breathing",
                       params={"speed": 2}, effect_colors=[(0, 255, 0)]))
        dev.client.close()
        server.done.wait(2)
        kinds = [p for p, _, _ in server.packets]
        self.assertIn(openrgb.SETCUSTOMMODE, kinds)
        leds = next(d for p, _, d in server.packets if p == openrgb.UPDATELEDS)
        size, count = struct.unpack_from("<IH", leds)
        self.assertEqual((size, count), (len(leds), 4))
        self.assertEqual(leds[6:10], bytes((128, 0, 0, 0)))          # software dimming to 50 %
        mode = next(d for p, _, d in server.packets if p == openrgb.UPDATEMODE)
        self.assertEqual(struct.unpack_from("<I", mode)[0], len(mode))
        self.assertEqual(struct.unpack_from("<i", mode, 4)[0], 1)    # mode index
        self.assertIn(b"Breathing\0", mode)

    def test_no_server(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        self.assertEqual(openrgb.discover("127.0.0.1", port), [])

    def tearDown(self):
        import gc
        gc.collect()


if __name__ == "__main__":
    unittest.main()
