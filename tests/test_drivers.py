"""Byte-exact checks of the USB HID drivers against their documented protocols."""

import unittest

from bytekeys.hw.base import Frame
from bytekeys.hw.drivers.asus_aura import AsusAura
from bytekeys.hw.drivers.dell import DellElc
from bytekeys.hw.drivers.ite8291 import Ite8291
from bytekeys.hw.drivers.lenovo import Lenovo4Zone
from bytekeys.hw.drivers.msi import MsiKlm
from bytekeys.hw.hid import discover
from bytekeys.hw.hidraw import HidInfo, RecordingTransport, parse_report_descriptor

LENOVO_DESC = bytes.fromhex("0689FF09CCA10185CC0900150026FF0075089520B102C0")
ITE_DESC = bytes.fromhex("0603FF0901A1010901150026FF0075089508B102090195409102C0")
ASUS_DESC = bytes.fromhex("0631FF0979A101855D0901150026FF007508953FB102C0")


def info(vid, pid, desc=b"", interface=0, bcd=None, driver="hid-generic", node="hidraw0"):
    return HidInfo(node=node, devnode=f"/dev/{node}", bus=3, vid=vid, pid=pid, name="test",
                   interface=interface, parent="/sys/devices/usb1/1-3", descriptor=desc,
                   reports=parse_report_descriptor(desc), driver=driver, bcd_device=bcd)


def recorder(transport):
    return lambda devnode: transport


class LenovoTest(unittest.TestCase):
    def test_matching(self):
        self.assertEqual(Lenovo4Zone.score(info(0x048D, 0xC965, LENOVO_DESC)), 3)
        self.assertEqual(Lenovo4Zone.score(info(0x048D, 0xC9AA, LENOVO_DESC)), 3)   # unlisted, right layout
        self.assertEqual(Lenovo4Zone.score(info(0x048D, 0xC195, LENOVO_DESC)), 0)   # 2025 per-key
        self.assertEqual(Lenovo4Zone.score(info(0x048D, 0x8051, b"")), 0)           # ASUS hotkeys (ITE5570)

    def test_reports(self):
        t = RecordingTransport()
        dev = Lenovo4Zone(info(0x048D, 0xC965, LENOVO_DESC), recorder(t))
        dev.show(Frame(on=True, level=2, colors=[(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]))
        self.assertEqual(t.sent[-1][1].hex(),
                         "cc160101" "02" "ff0000" "00ff00" "0000ff" "ffffff" + "00" * 16)
        dev.show(Frame(on=True, level=1, colors=[(0, 0, 0)] * 4, effect="wave",
                       params={"speed": "3", "direction": "right"}))
        report = t.sent[-1][1]
        self.assertEqual(report[:5].hex(), "cc16040301")
        self.assertEqual((report[18], report[19]), (1, 0))
        dev.show(Frame(on=False, level=0, colors=[(0, 0, 0)] * 4))
        self.assertEqual(t.sent[-1][1], bytes([0xCC, 0x16]) + bytes(31))
        n = len(t.sent)
        dev.show(Frame(on=False, level=0, colors=[(0, 0, 0)] * 4))
        self.assertEqual(len(t.sent), n, "unchanged state is not re-sent")


class Ite8291Test(unittest.TestCase):
    def test_matching(self):
        self.assertEqual(Ite8291.score(info(0x048D, 0x600B, ITE_DESC, interface=1)), 3)
        self.assertEqual(Ite8291.score(info(0x048D, 0xCE00, ITE_DESC, interface=1, bcd=0x0002)), 0)
        self.assertEqual(Ite8291.score(info(0x048D, 0xCE00, ITE_DESC, interface=1, bcd=0x0003)), 3)
        self.assertEqual(Ite8291.score(info(0x048D, 0x600B, ITE_DESC, interface=1, driver="ite_8291")), 0)

    def test_user_mode_frame(self):
        t = RecordingTransport()
        dev = Ite8291(info(0x048D, 0x600B, ITE_DESC, interface=1), recorder(t))
        dev.calibrate = False
        colors = [(0, 0, 0)] * 126
        colors[0] = (1, 2, 3)          # bottom-left key (hardware row 0, column 0)
        dev.show(Frame(on=True, level=40, colors=colors))
        kinds = [k for k, _ in t.sent]
        self.assertEqual(kinds.count("output"), 6)
        self.assertEqual(t.sent[0], ("feature", bytes.fromhex("00" "0802330028000000")))
        self.assertEqual(t.sent[1], ("feature", bytes.fromhex("00" "1600000000000000")))
        row0 = t.sent[2][1]
        self.assertEqual(len(row0), 65)
        self.assertEqual((row0[2], row0[2 + 21], row0[2 + 42]), (3, 2, 1))   # blue, green, red blocks
        t.sent.clear()
        colors = list(colors)
        colors[0] = (9, 9, 9)
        dev.show(Frame(on=True, level=40, colors=colors))
        self.assertEqual([k for k, _ in t.sent], ["feature", "output"], "only the changed row is sent")

    def test_hardware_effect_never_saves_by_default(self):
        t = RecordingTransport()
        dev = Ite8291(info(0x048D, 0x600B, ITE_DESC, interface=1), recorder(t))
        dev.show(Frame(on=True, level=50, effect="breathing", params={"speed": 10},
                       effect_colors=[(255, 0, 0)]))
        effect = t.sent[-1][1]
        self.assertEqual(effect[1:3].hex(), "0802")
        self.assertEqual(effect[3], 0x02)        # breathing
        self.assertEqual(effect[4], 1)           # fastest
        self.assertEqual(effect[8], 0)           # save flag off


class MsiTest(unittest.TestCase):
    def test_regions_then_commit(self):
        t = RecordingTransport()
        dev = MsiKlm(info(0x1770, 0xFF00), recorder(t))
        dev.show(Frame(on=True, level=100, colors=[(255, 0, 0), (0, 255, 0), (0, 0, 255)]))
        self.assertEqual([d.hex() for _, d in t.sent], [
            "01024001ff0000ec", "0102400200ff00ec", "010240030000ffec", "01024101000000ec"])
        t.sent.clear()
        dev.show(Frame(on=True, level=50, colors=[(255, 0, 0), (0, 255, 0), (0, 0, 255)]))
        self.assertEqual(t.sent[0][1].hex(), "01024001800000ec")   # software dimming


class AsusAuraTest(unittest.TestCase):
    def test_mode_apply_and_explicit_save(self):
        t = RecordingTransport()
        dev = AsusAura(info(0x0B05, 0x19B6, ASUS_DESC), recorder(t))
        dev.show(Frame(on=True, level=3, colors=[(255, 0, 0)]))
        payloads = [d for _, d in t.sent]
        self.assertTrue(payloads[0].startswith(b"\x5dASUS Tech.Inc."))
        self.assertTrue(any(p[:5] == bytes.fromhex("5abac5c403") for p in payloads))   # brightness
        mode = next(p for p in payloads if p[:2] == b"\x5d\xb3")
        self.assertEqual(mode[:9].hex(), "5db30000ff0000e100")
        self.assertIn(b"\x5d\xb5", [p[:2] for p in payloads])
        self.assertNotIn(b"\x5d\xb4", [p[:2] for p in payloads], "no flash write without a save")
        t.sent.clear()
        dev.show(Frame(on=True, level=3, colors=[(255, 0, 0)], persist=True))
        self.assertEqual([p[:2] for _, p in t.sent], [b"\x5d\xb3", b"\x5d\xb5", b"\x5d\xb4"])
        self.assertTrue(all(len(p) == 64 for _, p in t.sent))


class DellTest(unittest.TestCase):
    def test_static_zones_play_but_never_save(self):
        t = RecordingTransport(replies={0x00: bytes.fromhex("00032002" "0e07" "04") + bytes(27)})
        dev = DellElc(info(0x187C, 0x0550), recorder(t))
        dev.COMMAND_DELAY = dev.PLAY_DELAY = 0
        dev.show(Frame(on=True, level=75, colors=[(255, 0, 0)] * 4))
        cmds = [d[1:4].hex() for _, d in t.sent]
        self.assertTrue(all(len(d) == 34 and d[0] == 0 for _, d in t.sent))
        self.assertEqual(cmds[0], "032002")             # first: platform query
        sub = [d[4] for _, d in t.sent if d[1:3] == b"\x03\x21"]
        self.assertFalse({0x02, 0x06, 0x07} & set(sub), "never save, set default or set startup")
        self.assertEqual(sub, [0x04, 0x01, 0x03])       # remove, new, finish & play
        selects = [d[6] for _, d in t.sent if d[1:3] == b"\x03\x23"]
        self.assertEqual(selects, [0x10, 0x11, 0x12, 0x13])   # G15 5520 numbering from the platform id
        dim = t.sent[-1][1]
        self.assertEqual(dim[1:4].hex(), "032619")       # 25 % dim = 75 % brightness
        self.assertNotIn(0xFF, [d[2] for _, d in t.sent])
        self.assertNotIn(0x28, [d[2] for _, d in t.sent])


class DiscoveryTest(unittest.TestCase):
    def test_best_interface_wins(self):
        infos = [info(0x048D, 0x600B, b"", interface=0, node="hidraw1"),
                 info(0x048D, 0x600B, ITE_DESC, interface=1, node="hidraw2")]
        (dev,) = discover([Ite8291], infos)
        self.assertEqual(dev.path, "/dev/hidraw2")


if __name__ == "__main__":
    unittest.main()
