"""HID LampArray: descriptor-driven report layouts and the update flow."""

import struct
import unittest

from bytekeys.hw.base import ColorMode, Frame
from bytekeys.hw.drivers import lamparray as la
from bytekeys.hw.hidraw import HidInfo, parse_report_descriptor


def item(prefix: int, value: int | None = None, size: int = 1) -> bytes:
    if value is None:
        return bytes([prefix])
    code = {1: 1, 2: 2, 4: 3}[size]
    return bytes([prefix | code]) + value.to_bytes(size, "little")


def field(usages, bits, count=1, maximum=255) -> bytes:
    out = b"".join(item(0x08, u) for u in usages)                      # Usage
    out += item(0x14, 0) + item(0x24, maximum, 4)                      # Logical min / max
    out += item(0x74, bits) + item(0x94, count) + item(0xB0, 0x02)     # Size, Count, Feature
    return out


def collection(usage, report_id, body) -> bytes:
    return item(0x08, usage) + item(0xA0, 0x02) + item(0x84, report_id) + body + item(0xC0)


def lamparray_descriptor(per_report=8) -> bytes:
    d = item(0x04, 0x59) + item(0x08, 0x01) + item(0xA0, 0x01)         # Usage page, LampArray, Application
    d += collection(0x02, 1, field([0x03], 16) + field([0x04, 0x05, 0x06, 0x07, 0x08], 32, 5))
    d += collection(0x20, 2, field([0x21], 16))
    d += collection(0x22, 3, field([0x21], 16) + field([0x23, 0x24, 0x25, 0x27, 0x26], 32, 5)
                    + field([0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D], 8, 6))
    d += collection(0x50, 4, field([0x03, 0x55], 8, 2) + field([0x21] * per_report, 16, per_report)
                    + field([0x51, 0x52, 0x53, 0x54] * per_report, 8, 4 * per_report))
    d += collection(0x60, 5, field([0x55], 8) + field([0x61, 0x62], 16, 2) + field([0x51, 0x52, 0x53, 0x54], 8, 4))
    d += collection(0x70, 6, field([0x71], 8))
    return d + item(0xC0)


class FakeLamps:
    """Answers feature reads like a 10-key LampArray keyboard."""

    def __init__(self, lamps=10):
        self.lamps = lamps
        self.next_lamp = 0
        self.sent = []

    def __call__(self, devnode):
        return self

    def get_feature(self, report_id, length):
        if report_id == 1:
            body = struct.pack("<HIIIII", self.lamps, 300000, 120000, 1000, 1, 10000)
        elif report_id == 3:
            lamp = self.next_lamp
            self.next_lamp += 1
            row, col = divmod(lamp, 5)
            body = struct.pack("<HIIIII", lamp, col * 19000, row * 19000, 0, 0, 1) + bytes((255, 255, 255, 1, 1, 0x04 + lamp))
        else:
            body = b""
        data = bytes([report_id]) + body
        return (data + bytes(length))[:length]

    def send_feature(self, data):
        self.sent.append(bytes(data))
        if data[0] == 2:
            self.next_lamp = int.from_bytes(data[1:3], "little")

    def write(self, data):
        self.sent.append(bytes(data))

    def close(self):
        pass


class LampArrayTest(unittest.TestCase):
    def setUp(self):
        desc = lamparray_descriptor()
        reps = parse_report_descriptor(desc)
        self.info = HidInfo(node="hidraw9", devnode="/dev/hidraw9", bus=0x18, vid=0x1234, pid=0x5678,
                            name="Test Keyboard", descriptor=desc, reports=reps)

    def test_descriptor_layouts(self):
        reps = self.info.reports
        self.assertIn((0x59, 0x01), reps.applications)
        self.assertEqual(reps.report_for("feature", la.MULTI_UPDATE_REPORT), 4)
        self.assertEqual(reps.feature[4], 1 + 2 + 16 + 32)
        packed = reps.pack("feature", 5, {la.LAMP_ID_START: [2], la.LAMP_ID_END: [9], la.RED: [7]})
        self.assertEqual(packed[:7].hex(), "05" "00" "0200" "0900" "07")
        self.assertEqual(la.LampArray.score(self.info), 2)

    def test_probe_and_updates(self):
        fake = FakeLamps()
        dev = la.LampArray(self.info, fake)
        self.assertEqual(dev.color_mode, ColorMode.PERKEY)
        self.assertEqual(len(dev.zones), 10)
        self.assertEqual(dev.zones[0].key, "A")              # usage 0x04
        self.assertEqual((dev.zones[7].row, dev.zones[7].col), (1, 2))
        self.assertEqual(dev.max_fps, 60)                    # 10 ms minimum update interval
        fake.sent.clear()
        dev.show(Frame(on=True, level=100, colors=[(1, 2, 3)] * 10))
        self.assertEqual(fake.sent[0], bytes((6, 0)))       # host takes control
        rng = fake.sent[1]
        self.assertEqual(rng[0], 5)
        self.assertEqual(rng[1:].hex()[:22], "01" "0000" "0900" "010203ff")
        fake.sent.clear()
        colors = [(i, 0, 0) for i in range(10)]
        dev.show(Frame(on=True, level=100, colors=colors))
        multi = [p for p in fake.sent if p[0] == 4]
        self.assertEqual(len(multi), 2)                      # 8 lamps per report
        first, last = multi
        self.assertEqual((first[1], first[2]), (8, 0))       # count, flags (not complete yet)
        self.assertEqual((last[1], last[2]), (2, 1))         # last report completes the frame
        self.assertEqual(int.from_bytes(last[3:5], "little"), 8)


if __name__ == "__main__":
    unittest.main()
