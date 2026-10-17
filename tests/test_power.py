"""Performance profiles, fan curves, full fan speed, charge limits and the launch key."""

import os
import shutil
import subprocess
import tempfile
import threading
import unittest

from bytekeys import power
from bytekeys.engine import Engine
from bytekeys.engine.inputwatch import EVENT, InputWatcher

from .fakesys import FakeSys, wait_for

ASUS = "/sys/class/hwmon/hwmon5"
CURVE = "/sys/class/hwmon/hwmon6"
POINTS = [[40, 15], [50, 25], [60, 35], [70, 50], [75, 60], [80, 70], [90, 90], [95, 100]]


def asus_laptop(fs: FakeSys, agfn: bool = False) -> None:
    fs.dmi(sys_vendor="ASUSTeK COMPUTER INC.", product_name="ASUS TUF Gaming F15 FX507ZC4_FX507ZC4",
           product_family="ASUS TUF Gaming F15")
    fs.write("/sys/firmware/acpi/platform_profile_choices", "quiet balanced performance\n")
    fs.write("/sys/firmware/acpi/platform_profile", "balanced\n")
    fs.write(f"{ASUS}/name", "asus\n")
    fs.write(f"{ASUS}/fan1_input", "3400\n")
    fs.write(f"{ASUS}/fan1_label", "cpu_fan\n")
    fs.write(f"{ASUS}/fan2_input", "3100\n")
    fs.write(f"{ASUS}/fan2_label", "gpu_fan\n")
    fs.write(f"{ASUS}/pwm1_enable", "2\n")
    if agfn:
        fs.write(f"{ASUS}/pwm1", "0\n")
    fs.write(f"{CURVE}/name", "asus_custom_fan_curve\n")
    for fan in ("1", "2"):
        fs.write(f"{CURVE}/pwm{fan}_enable", "2\n")
        for i in range(1, 9):
            fs.write(f"{CURVE}/pwm{fan}_auto_point{i}_temp", f"{30 + i * 8}\n")
            fs.write(f"{CURVE}/pwm{fan}_auto_point{i}_pwm", f"{20 * i}\n")
    fs.power(ac=True, battery=80, status="Charging")
    fs.write("/sys/class/power_supply/BAT0/charge_control_end_threshold", "100\n")
    fs.cpu_temp(55)


class PowerControlTest(unittest.TestCase):
    def setUp(self):
        self.fs = FakeSys()
        asus_laptop(self.fs)
        self.pc = power.PowerControl()

    def tearDown(self):
        self.fs.close()

    def test_info(self):
        info = self.pc.info()
        self.assertEqual([p["id"] for p in info["profiles"]], ["quiet", "balanced", "performance"])
        self.assertEqual([p["name"] for p in info["profiles"]], ["Silent", "Balanced", "Performance"])
        self.assertEqual(info["profile"], "balanced")
        self.assertEqual(info["profile_via"], "sysfs")
        self.assertEqual([(f["label"], f["rpm"]) for f in info["fans"]], [("CPU fan", 3400), ("GPU fan", 3100)])
        self.assertEqual([c["label"] for c in info["curves"]], ["CPU fan", "GPU fan"])
        self.assertEqual(info["curves"][0]["points"][0], [38, round(20 * 100 / 255)])
        self.assertFalse(info["curves"][0]["enabled"])
        self.assertEqual(info["boost"], {"on": False})
        self.assertEqual(info["charge"], {"kind": "threshold", "limit": 100, "presets": [60, 80, 100]})

    def test_set_profile(self):
        self.pc.set_profile("performance")
        self.assertEqual(self.fs.read("/sys/firmware/acpi/platform_profile"), "performance")
        with self.assertRaises(ValueError):
            self.pc.set_profile("turbo")

    def test_set_curve_writes_points_then_enables(self):
        self.pc.set_curve("1", POINTS, True)
        for i, (t, pct) in enumerate(POINTS, start=1):
            self.assertEqual(self.fs.read(f"{CURVE}/pwm1_auto_point{i}_temp"), str(t))
            self.assertEqual(self.fs.read(f"{CURVE}/pwm1_auto_point{i}_pwm"), str(round(pct * 255 / 100)))
        self.assertEqual(self.fs.read(f"{CURVE}/pwm1_enable"), "1")
        self.assertEqual(self.fs.read(f"{CURVE}/pwm2_enable"), "2\n", "the other fan is untouched")
        self.pc.set_curve("1", None, False)
        self.assertEqual(self.fs.read(f"{CURVE}/pwm1_enable"), "2")
        with self.assertRaises(KeyError):
            self.pc.set_curve("3", POINTS, True)

    def test_reset_curve_restores_factory_points(self):
        self.pc.reset_curve("2")
        self.assertEqual(self.fs.read(f"{CURVE}/pwm2_enable"), "3")

    def test_unsafe_curves_are_rejected(self):
        bad = [
            POINTS[:7],                                                       # 7 points
            [[40, 15], [35, 25]] + POINTS[2:],                               # temperature drops
            [[40, 50], [50, 40]] + POINTS[2:],                               # fan slows down
            [[30, 0], [40, 0], [50, 0], [60, 10], [70, 20], [80, 30], [90, 60], [95, 80]],   # too slow when hot
            [[30, 0], [40, 5], [50, 10], [60, 20], [65, 30], [70, 40], [75, 50], [79, 60]],  # last point < 70 %
            [[10, 0]] + POINTS[1:],                                          # below 20 °C
        ]
        for points in bad:
            with self.assertRaises(ValueError, msg=points):
                power.validate_curve(points)
        self.assertEqual(power.validate_curve(POINTS), POINTS)

    def test_full_fan_speed(self):
        self.pc.set_boost(True)
        self.assertEqual(self.fs.read(f"{ASUS}/pwm1_enable"), "0")
        self.assertEqual(self.pc.boost(), {"on": True})
        self.pc.set_boost(False)
        self.assertEqual(self.fs.read(f"{ASUS}/pwm1_enable"), "2")

    def test_agfn_fans_have_no_full_speed_switch(self):
        self.fs.write(f"{ASUS}/pwm1", "0\n")
        self.assertIsNone(self.pc.boost())
        with self.assertRaises(KeyError):
            self.pc.set_boost(True)

    def test_charge_limit(self):
        self.pc.set_charge_limit(80)
        self.assertEqual(self.fs.read("/sys/class/power_supply/BAT0/charge_control_end_threshold"), "80")
        self.pc.set_charge_limit(5)
        self.assertEqual(self.fs.read("/sys/class/power_supply/BAT0/charge_control_end_threshold"), "20")

    def test_ideapad_conservation_mode(self):
        os.unlink(self.fs.root + "/sys/class/power_supply/BAT0/charge_control_end_threshold")
        self.fs.write("/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/conservation_mode", "0\n")
        pc = power.PowerControl()
        self.assertEqual(pc.charge(), {"kind": "conservation", "limit": 100, "presets": [60, 100]})
        pc.set_charge_limit(60)
        self.assertEqual(self.fs.read("/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/conservation_mode"), "1")

    def test_start_threshold_stays_below_the_end(self):
        bat = "/sys/class/power_supply/BAT0"
        self.fs.write(f"{bat}/charge_control_start_threshold", "95\n")
        self.fs.write(f"{bat}/charge_types", "Trickle Fast [Standard] Adaptive Custom\n")
        self.pc.set_charge_limit(60)
        self.assertEqual(self.fs.read(f"{bat}/charge_control_start_threshold"), "55")
        self.assertEqual(self.fs.read(f"{bat}/charge_control_end_threshold"), "60")
        self.assertEqual(self.fs.read(f"{bat}/charge_types"), "Custom", "Dell needs Custom mode")
        self.fs.write(f"{bat}/charge_types", "Trickle Fast Standard Adaptive [Custom]\n")
        self.pc.set_charge_limit(100)
        self.assertEqual(self.fs.read(f"{bat}/charge_types"), "Standard")

    def test_long_life_charge_type(self):
        bat = "/sys/class/power_supply/BAT0"
        os.unlink(self.fs.root + f"{bat}/charge_control_end_threshold")
        self.fs.write(f"{bat}/charge_types", "[Standard] Long_Life Fast\n")
        pc = power.PowerControl()
        self.assertEqual(pc.charge(), {"kind": "conservation", "limit": 100, "presets": [60, 100]})
        pc.set_charge_limit(60)
        self.assertEqual(self.fs.read(f"{bat}/charge_types"), "Long_Life")

    def test_lg_offers_80_and_100(self):
        self.fs.mkdir("/sys/devices/platform/lg-laptop")
        self.assertEqual(power.PowerControl().charge()["presets"], [80, 100])

    def test_monitor(self):
        data = self.pc.monitor()
        self.assertEqual(data["cpu_temp"], 55.0)
        self.assertEqual(data["battery"], 80)
        self.assertEqual(data["profile"], "balanced")
        self.assertIsNone(data["gpu_temp"])

    def test_no_power_features(self):
        with FakeSys():
            info = power.PowerControl().info()
        self.assertEqual((info["profiles"], info["curves"], info["boost"], info["charge"]), ([], [], None, None))


class EnginePowerTest(unittest.TestCase):
    def setUp(self):
        self.fs = FakeSys()
        asus_laptop(self.fs)
        self.dir = tempfile.mkdtemp(prefix="bk-state-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)
        self.fs.close()

    def engine(self, **kwargs) -> Engine:
        kwargs.setdefault("privileged", True)
        engine = Engine(self.dir, watch_input=False, discovery=lambda opts: [], mode="service", **kwargs)
        engine.start()
        self.addCleanup(engine.stop)
        return engine

    def kernel_drops_curves(self) -> None:
        """What asus-wmi does when the profile or the fan mode changes."""
        for fan in ("1", "2"):
            self.fs.write(f"{CURVE}/pwm{fan}_enable", "2\n")

    def test_firmware_curves_are_learned_per_profile(self):
        engine = self.engine()
        # At start the kernel only knows the boot profile's curve, so ByteKeys reloads it ("3")...
        self.assertEqual(self.fs.read(f"{CURVE}/pwm1_enable"), "3")
        self.assertIn("1", engine.power_state["defaults"]["balanced"])
        # ...and next time it only loads the remembered points, without a firmware call.
        self.fs.write(f"{CURVE}/pwm1_enable", "2\n")
        engine.set_power_profile("performance")
        self.assertEqual(self.fs.read(f"{CURVE}/pwm1_enable"), "3", "performance curve learned")
        self.fs.write(f"{CURVE}/pwm1_enable", "2\n")
        engine.set_power_profile("balanced")
        self.assertEqual(self.fs.read(f"{CURVE}/pwm1_enable"), "2\n")

    def test_curves_follow_the_profile(self):
        engine = self.engine()
        info = engine.set_fan_curve("1", POINTS, True)
        self.assertTrue(info["curves"][0]["enabled"])
        self.assertEqual(info["saved"]["curves"]["balanced"]["1"]["enabled"], True)
        engine.set_power_profile("performance")
        self.kernel_drops_curves()
        engine.set_power_profile("balanced")
        self.assertEqual(self.fs.read(f"{CURVE}/pwm1_enable"), "1", "the balanced curve came back")
        self.assertNotEqual(self.fs.read(f"{CURVE}/pwm2_enable"), "1")

    def test_switching_one_curve_off_keeps_the_other(self):
        engine = self.engine()
        engine.set_fan_curve("1", POINTS, True)
        engine.set_fan_curve("2", POINTS, True)
        info = engine.set_fan_curve("2", None, False)    # the kernel resets every fan here
        self.assertEqual(self.fs.read(f"{CURVE}/pwm2_enable"), "2")
        self.assertEqual(self.fs.read(f"{CURVE}/pwm1_enable"), "1", "fan 1 was written again, last")
        saved = info["saved"]["curves"]["balanced"]["2"]
        self.assertEqual(saved, {"points": POINTS, "enabled": False}, "the points are kept")
        info = engine.set_fan_curve("2", None, True)     # switching it back on reuses them
        self.assertTrue(next(c for c in info["curves"] if c["fan"] == "2")["enabled"])

    def test_dropped_curves_come_back(self):
        engine = self.engine()
        engine.set_fan_curve("1", POINTS, True)
        self.kernel_drops_curves()          # e.g. the same profile written again by another program
        self.assertTrue(wait_for(lambda: self.fs.read(f"{CURVE}/pwm1_enable") == "1"))

    def test_curve_returns_after_full_speed(self):
        engine = self.engine()
        engine.set_fan_curve("1", POINTS, True)
        engine.set_fan_boost(True)
        self.kernel_drops_curves()
        engine.set_fan_boost(False)
        self.assertEqual(self.fs.read(f"{CURVE}/pwm1_enable"), "1")

    def test_reset_forgets_the_saved_curve(self):
        engine = self.engine()
        engine.set_fan_curve("1", POINTS, True)
        engine.set_fan_curve("2", POINTS, True)
        info = engine.reset_fan_curve("1")
        self.assertNotIn("1", info["saved"]["curves"]["balanced"])
        self.assertEqual(self.fs.read(f"{CURVE}/pwm1_enable"), "3")
        self.assertEqual(self.fs.read(f"{CURVE}/pwm2_enable"), "1", "the other fan's curve survives")

    def test_settings_restored_after_restart(self):
        engine = self.engine()
        engine.set_charge_limit(80)
        engine.set_fan_curve("2", POINTS, True)
        engine.stop()
        self.fs.write("/sys/class/power_supply/BAT0/charge_control_end_threshold", "100\n")
        self.kernel_drops_curves()
        self.engine()
        self.assertEqual(self.fs.read("/sys/class/power_supply/BAT0/charge_control_end_threshold"), "80")
        self.assertEqual(self.fs.read(f"{CURVE}/pwm2_enable"), "1")

    def test_unsafe_curve_is_refused(self):
        engine = self.engine()
        before = self.fs.read(f"{CURVE}/pwm1_enable")
        with self.assertRaises(ValueError):
            engine.set_fan_curve("1", [[20, 0]] * 8, True)
        self.assertEqual(self.fs.read(f"{CURVE}/pwm1_enable"), before)

    def test_unprivileged_engine_never_writes_fans(self):
        self.engine(privileged=False)
        self.assertEqual(self.fs.read(f"{CURVE}/pwm1_enable"), "2\n")

    def test_launch_key_defaults_to_the_vendor_key(self):
        engine = self.engine(privileged=False)
        self.assertEqual(engine.settings["launch_key"], 202)   # ASUS Armoury Crate key (KEY_PROG3)
        engine.set_settings({"launch_key": 0})
        engine.stop()
        self.assertEqual(self.engine(privileged=False).settings["launch_key"], 0, "turning it off sticks")


class LaunchKeyTest(unittest.TestCase):
    """Feeds input events through a FIFO standing in for /dev/input/event7."""

    def setUp(self):
        self.fs = FakeSys()
        caps = "/sys/class/input/event7/device/capabilities"
        self.fs.write(f"{caps}/ev", "3\n")                      # EV_SYN | EV_KEY
        self.fs.write(f"{caps}/key", f"{1 << (202 - 192):x} 0 0 0\n")   # KEY_PROG3 only: a hotkey device
        self.fs.mkdir("/dev/input")
        self.fifo = self.fs.root + "/dev/input/event7"
        os.mkfifo(self.fifo)
        self.watcher = InputWatcher()
        self.watcher.launch_code = 202
        self.launches = []
        self.watcher.on_launch = lambda: self.launches.append(1)
        self.watcher.start()
        self.writer = os.open(self.fifo, os.O_WRONLY)       # waits until the watcher opened it

    def tearDown(self):
        self.watcher.stop()
        os.close(self.writer)
        self.watcher.join(5)
        self.fs.close()

    def press(self, code: int) -> None:
        os.write(self.writer, EVENT.pack(0, 0, 1, code, 1) + EVENT.pack(0, 0, 1, code, 0))

    def test_launch_key_press(self):
        self.press(30)        # an ordinary key: ignored
        self.press(202)
        self.assertTrue(wait_for(lambda: self.launches == [1]))

    def test_learn_takes_only_special_keys(self):
        result = []
        t = threading.Thread(target=lambda: result.append(self.watcher.learn(5)))
        t.start()
        self.assertTrue(wait_for(lambda: self.watcher._learning is not None))
        self.press(30)        # KEY_A must never be learned
        self.press(149)       # KEY_PROG2
        t.join(6)
        self.assertEqual(result, [149])
        self.assertEqual(self.launches, [], "learning does not launch")


def _has_schema() -> bool:
    if not shutil.which("gsettings"):
        return False
    out = subprocess.run(["gsettings", "list-schemas"], capture_output=True, text=True).stdout
    return "org.gnome.settings-daemon.plugins.media-keys" in out.split()


class _DesktopEnv(unittest.TestCase):
    ENV = ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "GSETTINGS_BACKEND", "XDG_CURRENT_DESKTOP", "KDE_SESSION_VERSION",
           "WAYLAND_DISPLAY", "XDG_SESSION_TYPE")

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="bk-desktop-")
        self.saved = {k: os.environ.get(k) for k in self.ENV}
        for k in self.ENV:
            os.environ.pop(k, None)
        os.environ.update(XDG_CONFIG_HOME=self.dir, XDG_DATA_HOME=self.dir, GSETTINGS_BACKEND="keyfile",
                          XDG_SESSION_TYPE="wayland")
        from bytekeys.gui import shortcuts
        self.sc = shortcuts

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.dir, ignore_errors=True)


@unittest.skipUnless(_has_schema(), "needs gsettings and the GNOME media-keys schema")
class GnomeShortcutTest(_DesktopEnv):
    def setUp(self):
        super().setUp()
        os.environ["XDG_CURRENT_DESKTOP"] = "ubuntu:GNOME"

    def test_install_and_remove(self):
        self.assertIsNone(self.sc.installed())
        ok, _ = self.sc.install(202, "/usr/bin/bytekeys-gui")
        self.assertTrue(ok)
        self.assertEqual(self.sc.installed(), "XF86Launch3")
        self.sc.uninstall()
        self.assertIsNone(self.sc.installed())

    def test_settings_key_is_taken_over_and_given_back(self):
        get = ["gsettings", "get", self.sc.SCHEMA, "control-center-static"]
        ok, _ = self.sc.install(171, "bytekeys-gui")
        self.assertTrue(ok)
        self.assertNotIn("XF86Tools", subprocess.run(get, capture_output=True, text=True).stdout)
        self.sc.uninstall()
        self.assertIn("XF86Tools", subprocess.run(get, capture_output=True, text=True).stdout)

    def test_keys_without_a_keysym_use_the_raw_keycode(self):
        ok, _ = self.sc.install(701, "bytekeys-gui")     # KEY_PERFORMANCE
        self.assertTrue(ok)
        self.assertEqual(self.sc.installed(), "0x2c5")
        os.environ["XDG_SESSION_TYPE"] = "x11"           # X11 keycodes stop at 255
        self.assertIsNone(self.sc.binding(701))


class KdeShortcutTest(_DesktopEnv):
    def setUp(self):
        super().setUp()
        os.environ["XDG_CURRENT_DESKTOP"] = "KDE"

    def test_shortcut_file(self):
        ok, message = self.sc.install(202, "/usr/bin/bytekeys-gui")
        self.assertTrue(ok)
        self.assertIn("log in again", message)
        self.assertEqual(self.sc.installed(), "Launch (3)")
        os.environ["KDE_SESSION_VERSION"] = "5"           # Qt 5 numbers launch keys two higher
        self.assertEqual(self.sc.binding(202), "Launch (5)")
        self.sc.uninstall()
        self.assertIsNone(self.sc.installed())

    def test_keys_qt_cannot_name(self):
        ok, _ = self.sc.install(701, "bytekeys-gui")
        self.assertFalse(ok)


class OtherDesktopTest(_DesktopEnv):
    def test_manual_instructions(self):
        os.environ["XDG_CURRENT_DESKTOP"] = "XFCE"
        ok, message = self.sc.install(148, "bytekeys-gui")
        self.assertFalse(ok)
        self.assertIn("XF86Launch1", message)
