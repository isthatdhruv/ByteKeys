import unittest

from bytekeys.hw import registry, sysfs_leds, wmi_zones
from bytekeys.hw.base import Frame

from .fakesys import FakeSys


class WmiZonesTest(unittest.TestCase):
    def setUp(self):
        self.fs = FakeSys()
        sysfs_leds.CLAIMED.clear()

    def tearDown(self):
        sysfs_leds.CLAIMED.clear()
        self.fs.close()

    def test_omen_rgb_keyboard_claims_its_led(self):
        base = wmi_zones.OMEN_RGB
        for z in range(4):
            self.fs.write(f"{base}/zone0{z}", "FFFFFF\n")
        self.fs.write(f"{base}/brightness", "100\n")
        self.fs.write(f"{base}/animation_mode", "static\n")
        self.fs.write(f"{base}/animation_speed", "5\n")
        self.fs.led("omen::kbd_backlight", 100, 100)
        devices = registry.discover(registry.Options(hid=False, openrgb=False))
        self.assertEqual([d.id for d in devices], ["sysfs:omen-rgb-keyboard"])
        dev = devices[0]
        dev.show(Frame(on=True, level=60, colors=[(255, 0, 0)] * 4))
        self.assertEqual(self.fs.read(f"{base}/zone00"), "FF0000")
        self.assertEqual(self.fs.read(f"{base}/brightness"), "60")
        dev.show(Frame(on=True, level=60, colors=[(255, 0, 0)] * 4, effect="wave", params={"speed": 8}))
        self.assertEqual(self.fs.read(f"{base}/animation_mode"), "wave")
        self.assertEqual(self.fs.read(f"{base}/animation_speed"), "8")

    def test_alienware_four_bit_colors(self):
        base = wmi_zones.ALIENWARE_ZONES
        for z in range(3):
            self.fs.write(f"{base}/zone0{z}", "red: 0, green: 0, blue: 0\n")
        self.fs.write(f"{base}/lighting_control_state", "booting [running] suspend\n")
        (dev,) = wmi_zones.discover()
        self.assertEqual(len(dev.zones), 3)
        dev.show(Frame(on=True, level=100, colors=[(255, 128, 0)] * 3))
        self.assertEqual(self.fs.read(f"{base}/zone00"), "0F0800")

    def test_acer_packets(self):
        self.fs.write(wmi_zones.ACER_DYNAMIC, b"")
        self.fs.write(wmi_zones.ACER_STATIC, b"")
        (dev,) = wmi_zones.discover()
        dev.show(Frame(on=True, level=80, colors=[(1, 2, 3), (4, 5, 6), (7, 8, 9), (10, 11, 12)]))
        # Files are overwritten by each write; the last static packet is zone 4.
        with open(self.fs.root + wmi_zones.ACER_STATIC, "rb") as f:
            self.assertEqual(f.read(), bytes((8, 10, 11, 12)))
        with open(self.fs.root + wmi_zones.ACER_DYNAMIC, "rb") as f:
            packet = f.read()
        self.assertEqual(len(packet), 16)
        self.assertEqual((packet[0], packet[2], packet[9]), (0, 80, 1))


if __name__ == "__main__":
    unittest.main()
