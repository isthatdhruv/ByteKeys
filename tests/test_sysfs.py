import unittest

from bytekeys.hw import sysfs_leds
from bytekeys.hw.base import AccessError, ColorMode, Frame

from .fakesys import FakeSys


def by_id(devices):
    return {d.id: d for d in devices}


class SysfsDetectionTest(unittest.TestCase):
    def setUp(self):
        self.fs = FakeSys()

    def tearDown(self):
        self.fs.close()

    def test_ignores_non_keyboard_leds(self):
        self.fs.led("input3::capslock", 1)
        self.fs.led("phy0-led", 1)
        self.fs.led("enp4s0-0::lan", 1)
        self.assertEqual(sysfs_leds.discover(), [])

    def test_thinkpad_levels(self):
        self.fs.led("tpacpi::kbd_backlight", 2, 1)
        (dev,) = sysfs_leds.discover()
        self.assertEqual(dev.id, "sysfs:tpacpi::kbd_backlight")
        self.assertEqual(dev.vendor, "ThinkPad")
        self.assertEqual(dev.color_mode, ColorMode.NONE)
        self.assertEqual(dev.level_names(), ["Off", "Low", "High"])
        self.assertEqual(dev.read_level(), 1)
        dev.show(Frame(on=True, level=2))
        self.assertEqual(self.fs.read("/sys/class/leds/tpacpi::kbd_backlight/brightness"), "2")
        dev.show(Frame(on=False, level=2))
        self.assertEqual(self.fs.read("/sys/class/leds/tpacpi::kbd_backlight/brightness"), "0")

    def test_dell_timeout_feature(self):
        self.fs.led("dell::kbd_backlight", 2, 0, stop_timeout="10s\n", als_enabled="0\n")
        (dev,) = sysfs_leds.discover()
        feats = {f.id: f for f in dev.features()}
        self.assertEqual(feats["dell_timeout"].value, "10s")
        self.assertFalse(feats["dell_als"].value)
        dev.set_feature("dell_timeout", "1m")
        self.assertEqual(self.fs.read("/sys/class/leds/dell::kbd_backlight/stop_timeout").strip(), "1m")

    def test_asus_tuf_rgb(self):
        self.fs.led("asus::kbd_backlight", 3, 3, kbd_rgb_mode=None, kbd_rgb_state=None,
                    kbd_rgb_mode_index="cmd mode red green blue speed\n")
        (dev,) = sysfs_leds.discover()
        self.assertIsInstance(dev, sysfs_leds.AsusWmiKeyboard)
        self.assertEqual(dev.color_mode, ColorMode.SINGLE)
        self.assertTrue(dev.can_persist)
        self.assertEqual({e.id for e in dev.hw_effects}, {"breathing", "cycle", "strobe", "pulse"})
        dev.show(Frame(on=True, level=2, colors=[(255, 128, 0)]))
        self.assertEqual(self.fs.read("/sys/class/leds/asus::kbd_backlight/kbd_rgb_mode"), "0 0 255 128 0 1")
        self.assertEqual(self.fs.read("/sys/class/leds/asus::kbd_backlight/brightness"), "2")
        # A persistent write saves to firmware (cmd 1) even if nothing else changed.
        dev.show(Frame(on=True, level=2, colors=[(255, 128, 0)], persist=True))
        self.assertEqual(self.fs.read("/sys/class/leds/asus::kbd_backlight/kbd_rgb_mode"), "1 0 255 128 0 1")
        dev.show(Frame(on=True, level=2, colors=[(1, 2, 3)], effect="breathing",
                       params={"speed": "2"}, effect_colors=[(0, 0, 255)]))
        self.assertEqual(self.fs.read("/sys/class/leds/asus::kbd_backlight/kbd_rgb_mode"), "0 1 0 0 255 2")
        dev.set_feature("asus_sleep", {"asus_boot": True, "asus_awake": True, "asus_sleep": True,
                                       "asus_keyboard": True})
        self.assertEqual(self.fs.read("/sys/class/leds/asus::kbd_backlight/kbd_rgb_state"), "1 1 1 1 1")

    def test_system76_color(self):
        self.fs.led("system76_acpi::kbd_backlight", 255, 100, color="FFFFFF\n")
        (dev,) = sysfs_leds.discover()
        self.assertIsInstance(dev, sysfs_leds.System76Keyboard)
        self.assertEqual(dev.color_mode, ColorMode.SINGLE)
        dev.show(Frame(on=True, level=200, colors=[(0, 170, 255)]))
        self.assertEqual(self.fs.read("/sys/class/leds/system76_acpi::kbd_backlight/color"), "00AAFF")

    def test_tuxedo_three_zone_multicolor(self):
        for name in ("rgb:kbd_backlight", "rgb:kbd_backlight_1", "rgb:kbd_backlight_2"):
            self.fs.led(name, 255, 255, multi_index="red green blue\n", multi_intensity="255 255 255\n")
        (dev,) = sysfs_leds.discover()
        self.assertEqual(dev.id, "sysfs:rgb:kbd_backlight")
        self.assertEqual(dev.color_mode, ColorMode.ZONES)
        self.assertEqual([z.name for z in dev.zones], ["Left", "Center", "Right"])
        dev.show(Frame(on=True, level=128, colors=[(255, 0, 0), (0, 255, 0), (0, 0, 255)]))
        self.assertEqual(self.fs.read("/sys/class/leds/rgb:kbd_backlight/multi_intensity"), "255 0 0")
        self.assertEqual(self.fs.read("/sys/class/leds/rgb:kbd_backlight_2/multi_intensity"), "0 0 255")
        self.assertEqual(self.fs.read("/sys/class/leds/rgb:kbd_backlight_1/brightness"), "128")

    def test_multicolor_channel_order_and_scale(self):
        # Without multi_max_intensity, RGB keyboard drivers take 0-255 intensities.
        self.fs.led("rgb:kbd_backlight", 50, 50, multi_index="green red blue\n", multi_intensity="0 0 0\n")
        (dev,) = sysfs_leds.discover()
        dev.show(Frame(on=True, level=50, colors=[(255, 51, 0)]))
        self.assertEqual(self.fs.read("/sys/class/leds/rgb:kbd_backlight/multi_intensity"), "51 255 0")

    def test_multicolor_max_intensity_and_uniwill_black(self):
        self.fs.led("uniwill:multicolor:kbd_backlight", 4, 2, multi_index="red green blue\n",
                    multi_intensity="50 50 50\n", multi_max_intensity="50 50 50\n")
        (dev,) = sysfs_leds.discover()
        dev.show(Frame(on=True, level=4, colors=[(255, 0, 102)]))
        self.assertEqual(self.fs.read("/sys/class/leds/uniwill:multicolor:kbd_backlight/multi_intensity"),
                         "50 0 20")
        dev.show(Frame(on=True, level=4, colors=[(0, 0, 0)]))
        self.assertEqual(self.fs.read("/sys/class/leds/uniwill:multicolor:kbd_backlight/multi_intensity"),
                         "0 0 0")   # 1,1,1 out of 255 rounds to 0 at a 50 maximum

    def test_tuxedo_hardware_modes(self):
        self.fs.led("rgb:kbd_backlight", 255, 255, multi_index="red green blue\n", multi_intensity="0 0 0\n")
        self.fs.write("/sys/devices/platform/tuxedo_keyboard/kbd_backlight_mode", "0\n")
        (dev,) = sysfs_leds.discover()
        self.assertIn("cycle", {e.id for e in dev.hw_effects})
        dev.show(Frame(on=True, level=255, colors=[(255, 0, 0)], effect="cycle"))
        self.assertEqual(self.fs.read("/sys/devices/platform/tuxedo_keyboard/kbd_backlight_mode"), "2")
        dev.show(Frame(on=True, level=255, colors=[(0, 255, 0)]))
        self.assertEqual(self.fs.read("/sys/devices/platform/tuxedo_keyboard/kbd_backlight_mode"), "0")
        self.assertEqual(self.fs.read("/sys/class/leds/rgb:kbd_backlight/multi_intensity"), "0 255 0")

    def test_ite8291_per_key_layout_and_buffering(self):
        hid = "/sys/devices/pci0000:00/usb1/1-3/1-3:1.1/0003:048D:600B.0005"
        self.fs.write(f"{hid}/controls/buffer_input", "0\n")
        names = ["rgb:kbd_backlight"] + [f"rgb:kbd_backlight_{i}" for i in range(1, 126)]
        for name in names:
            self.fs.led(name, 50, 50, multi_index="red green blue\n", multi_intensity="255 255 255\n")
            self.fs.symlink(hid, f"/sys/class/leds/{name}/device")
        (dev,) = sysfs_leds.discover()
        self.assertEqual(dev.matrix, (6, 21))
        self.assertEqual((dev.zones[0].row, dev.zones[0].col), (5, 0))   # LED 0 = bottom left
        self.assertEqual(dev.max_fps, 20)
        dev.show(Frame(on=True, level=50, colors=[(10, 20, 30)] * 126))
        self.assertEqual(self.fs.read(f"{hid}/controls/buffer_input"), "0")   # flushed again
        self.assertEqual(self.fs.read("/sys/class/leds/rgb:kbd_backlight_125/multi_intensity"), "10 20 30")

    def test_lg_three_levels(self):
        self.fs.write("/sys/devices/platform/lg-laptop/driver/.keep", "")
        self.fs.mkdir("/sys/bus/platform/drivers/lg-laptop")
        self.fs.led("kbd_backlight", 255, 127)
        self.fs.symlink("/sys/devices/platform/lg-laptop", "/sys/class/leds/kbd_backlight/device")
        import os
        os.remove(self.fs.root + "/sys/devices/platform/lg-laptop/driver/.keep")
        os.rmdir(self.fs.root + "/sys/devices/platform/lg-laptop/driver")
        self.fs.symlink("/sys/bus/platform/drivers/lg-laptop", "/sys/devices/platform/lg-laptop/driver")
        (dev,) = sysfs_leds.discover()
        self.assertEqual(dev.vendor, "LG")
        self.assertEqual(dev.level_names(), ["Off", "Low", "High"])
        self.assertEqual(dev.read_level(), 1)
        dev.show(Frame(on=True, level=2))
        self.assertEqual(self.fs.read("/sys/class/leds/kbd_backlight/brightness"), "255")

    def test_framework_duplicate_is_skipped(self):
        self.fs.led("chromeos::kbd_backlight", 100, 50)
        self.fs.led("framework_laptop::kbd_backlight", 100, 50)
        self.assertEqual([d.id for d in sysfs_leds.discover()], ["sysfs:chromeos::kbd_backlight"])

    def test_sony(self):
        self.fs.write("/sys/devices/platform/sony-laptop/kbd_backlight", "2\n")
        self.fs.write("/sys/devices/platform/sony-laptop/kbd_backlight_timeout", "1\n")
        (dev,) = sysfs_leds.discover()
        self.assertEqual(dev.read_level(), 1)
        dev.show(Frame(on=False, level=0))
        self.assertEqual(self.fs.read("/sys/devices/platform/sony-laptop/kbd_backlight"), "0")
        dev.set_feature("sony_auto", True)
        self.assertEqual(self.fs.read("/sys/devices/platform/sony-laptop/kbd_backlight"), "1")

    def test_per_key_group(self):
        names = ["rgb:kbd_backlight"] + [f"rgb:kbd_backlight_{i}" for i in range(1, 30)]
        for name in names:
            self.fs.led(name, 255, 0, multi_index="red green blue\n", multi_intensity="0 0 0\n")
        (dev,) = sysfs_leds.discover()
        self.assertEqual(dev.color_mode, ColorMode.PERKEY)
        self.assertEqual(len(dev.zones), 30)
        self.assertLessEqual(dev.max_fps, 5)

    def test_apple_and_unknown_vendor(self):
        self.fs.led("smc::kbd_backlight", 255, 40)
        self.fs.led("platform::kbd_backlight", 1, 0)
        devices = by_id(sysfs_leds.discover())
        self.assertEqual(devices["sysfs:smc::kbd_backlight"].vendor, "Apple")
        self.assertIsNone(devices["sysfs:smc::kbd_backlight"].level_names())
        self.assertEqual(devices["sysfs:platform::kbd_backlight"].level_names(), ["Off", "On"])

    def test_permission_denied_without_logind(self):
        self.fs.led("dell::kbd_backlight", 2, 0)
        import os
        os.chmod(self.fs.root + "/sys/class/leds/dell::kbd_backlight/brightness", 0o444)
        (dev,) = sysfs_leds.discover()
        from bytekeys.hw import logind
        logind._available = False
        try:
            if os.geteuid() == 0:
                self.skipTest("root ignores file permissions")
            self.assertIsNotNone(dev.access_problem())
            with self.assertRaises(AccessError):
                dev.show(Frame(on=True, level=1))
        finally:
            logind._available = None


if __name__ == "__main__":
    unittest.main()
