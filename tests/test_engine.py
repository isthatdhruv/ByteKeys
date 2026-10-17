import shutil
import tempfile
import unittest
from datetime import datetime

from bytekeys.engine import Engine
from bytekeys.engine import rules as rules_mod
from bytekeys.engine.sensors import Snapshot
from bytekeys.hw import demo

from .fakesys import FakeSys, wait_for


def make_engine(state_dir, devices=None, **kwargs):
    devices = devices if devices is not None else demo.discover()
    kwargs.setdefault("mode", "portable")
    engine = Engine(state_dir, privileged=False, watch_input=False,
                    discovery=lambda opts: devices, **kwargs)
    return engine, {d.id: d for d in devices}


class EngineTest(unittest.TestCase):
    def setUp(self):
        self.fs = FakeSys()          # empty machine: only the injected demo devices exist
        self.fs.power(ac=True, battery=90, status="Charging")
        self.dir = tempfile.mkdtemp(prefix="bk-state-")
        self.engine, self.devs = make_engine(self.dir)
        self.engine.start()

    def tearDown(self):
        self.engine.stop()
        shutil.rmtree(self.dir, ignore_errors=True)
        self.fs.close()

    def test_first_run_auto_config(self):
        self.assertTrue(self.engine.first_run)
        names = {p["name"] for p in self.engine.profile_list()}
        self.assertTrue({"Bright", "Night", "Off", "Gaming", "Focus"} <= names)
        rules = self.engine.get_rules()
        self.assertTrue(rules)
        self.assertFalse(any(r["enabled"] for r in rules), "rules are opt-in")
        # Nothing is written to hardware until the user changes something.
        self.assertEqual(self.devs["demo:rgb"].frames, [])

    def test_set_brightness_levels(self):
        self.engine.set("demo:white", {"brightness": 50})
        white = self.devs["demo:white"]
        self.assertTrue(wait_for(lambda: white.frames and white.frames[-1].level == 1))
        self.engine.set("demo:white", {"brightness": 10})
        self.assertTrue(wait_for(lambda: white.frames[-1].level == 1), "non-zero never rounds to off")
        self.engine.set("demo:white", {"on": False})
        self.assertTrue(wait_for(lambda: not white.frames[-1].on))

    def test_colors_and_zones(self):
        self.engine.set("demo:4zone", {"color": "#ff0000"})
        zones = self.devs["demo:4zone"]
        self.assertTrue(wait_for(lambda: zones.frames and zones.frames[-1].colors == [(255, 0, 0)] * 4))
        self.engine.set("demo:4zone", {"zones": {"2": "#00ff00"}})
        self.assertTrue(wait_for(lambda: zones.frames[-1].colors[2] == (0, 255, 0)))
        self.assertEqual(zones.frames[-1].colors[0], (255, 0, 0))
        with self.assertRaises(ValueError):
            self.engine.set("demo:4zone", {"color": "not-a-color"})
        with self.assertRaises(ValueError):
            self.engine.set("demo:white", {"effect": "spectrum"})   # needs RGB

    def test_hardware_effect_frame(self):
        self.engine.set("demo:rgb", {"effect": "hw:breathing", "params": {"speed": "2"},
                                     "effect_colors": ["#0000ff"]})
        rgb = self.devs["demo:rgb"]
        self.assertTrue(wait_for(lambda: rgb.frames and rgb.frames[-1].effect == "breathing"))
        self.assertEqual(rgb.frames[-1].effect_colors, [(0, 0, 255)])

    def test_software_animation_runs(self):
        self.engine.set("demo:4zone", {"effect": "wave", "params": {"speed": 100}})
        zones = self.devs["demo:4zone"]
        self.assertTrue(wait_for(lambda: len(zones.frames) > 5))
        self.assertTrue(zones.frames[-1].transient)
        self.assertNotEqual(zones.frames[-1].colors[0], zones.frames[-1].colors[3])

    def test_firmware_persist_only_when_enabled(self):
        import time

        import bytekeys.engine.core as core
        old = core.PERSIST_DELAY
        core.PERSIST_DELAY = 0.1
        try:
            rgb = self.devs["demo:rgb"]
            self.engine.set("demo:rgb", {"color": "#123456"})
            time.sleep(0.6)
            self.assertFalse(any(f.persist for f in rgb.frames), "flash writes are opt-in")
            self.engine.set_settings({"save_to_firmware": True})
            self.engine.set("demo:rgb", {"color": "#654321"})
            self.assertTrue(wait_for(lambda: any(f.persist for f in rgb.frames), timeout=3))
        finally:
            core.PERSIST_DELAY = old

    def test_rule_overrides_and_manual_change_wins(self):
        rules = [{"id": "bat", "name": "Dim", "enabled": True,
                  "trigger": {"type": "power", "source": "battery"},
                  "action": {"type": "brightness", "value": 30}}]
        self.engine.set_rules(rules)
        self.engine.set("demo:perkey", {"brightness": 100})
        perkey = self.devs["demo:perkey"]
        self.assertTrue(wait_for(lambda: perkey.frames and perkey.frames[-1].level == 10))
        self.fs.power(ac=False, battery=50)
        self.assertTrue(wait_for(lambda: perkey.frames[-1].level == 3, timeout=4))
        self.assertIn("bat", self.engine.device("demo:perkey")["rules_active"])
        # The user turns brightness up while on battery: their choice wins.
        self.engine.set("demo:perkey", {"brightness": 80})
        self.assertTrue(wait_for(lambda: perkey.frames[-1].level == 8))
        self.assertNotIn("bat", self.engine.device("demo:perkey")["rules_active"])

    def test_profiles(self):
        self.engine.set("demo:rgb", {"color": "#00ff00", "brightness": 100})
        self.engine.profile_save("Green")
        self.engine.set("demo:rgb", {"color": "#ff0000"})
        self.engine.profile_apply("Green")
        self.assertEqual(self.engine.device("demo:rgb")["state"]["color"], "#00ff00")
        self.engine.profile_rename("Green", "Lime")
        self.assertIn("Lime", {p["name"] for p in self.engine.profile_list()})
        self.engine.profile_delete("Lime")
        with self.assertRaises(KeyError):
            self.engine.profile_apply("Lime")

    def test_nudge_and_toggle(self):
        self.engine.set("demo:rgb", {"brightness": 33})
        self.engine.nudge("demo:rgb", 1)
        self.assertEqual(self.engine.device("demo:rgb")["state"]["brightness"], 67)
        self.engine.toggle("demo:rgb")
        self.assertFalse(self.engine.device("demo:rgb")["state"]["on"])
        self.engine.toggle("demo:rgb")
        self.assertTrue(self.engine.device("demo:rgb")["state"]["on"])

    def test_features_for_write_only_attributes(self):
        view = self.engine.set_feature("demo:rgb", "sleep", True)
        self.assertTrue(next(f for f in view["features"] if f["id"] == "sleep")["value"])
        with self.assertRaises(KeyError):
            self.engine.set_feature("demo:rgb", "nope", 1)

    def test_flash(self):
        self.engine.set("demo:rgb", {"color": "#ffffff"})
        self.engine.flash("demo:rgb", "#ff0000", count=2, period=0.2)
        rgb = self.devs["demo:rgb"]
        self.assertTrue(wait_for(lambda: any(f.colors == [(255, 0, 0)] for f in rgb.frames)))
        self.assertTrue(wait_for(lambda: rgb.frames[-1].colors == [(255, 255, 255)], timeout=3))

    def test_state_persists_and_restores(self):
        self.engine.set("demo:rgb", {"color": "#abcdef"})
        self.engine.stop()
        engine2, devs2 = make_engine(self.dir)
        engine2.start()
        try:
            self.assertFalse(engine2.first_run)
            self.assertEqual(engine2.device("demo:rgb")["state"]["color"], "#abcdef")
            self.assertTrue(wait_for(lambda: devs2["demo:rgb"].frames), "restored state is re-applied")
        finally:
            engine2.stop()
        self.engine, self.devs = make_engine(self.dir)
        self.engine.start()

    def test_report_mentions_devices(self):
        text = self.engine.report()
        self.assertIn("demo:4zone", text)
        self.assertIn("diagnostic report", text)


class RuleConditionTest(unittest.TestCase):
    def test_time_window_wraps_midnight(self):
        t = {"type": "time", "start": "22:00", "end": "07:00"}
        self.assertTrue(rules_mod.holds(t, Snapshot(), False, datetime(2026, 1, 1, 23, 30)))
        self.assertTrue(rules_mod.holds(t, Snapshot(), False, datetime(2026, 1, 1, 6, 59)))
        self.assertFalse(rules_mod.holds(t, Snapshot(), False, datetime(2026, 1, 1, 12, 0)))

    def test_battery_needs_discharging_and_has_hysteresis(self):
        t = {"type": "battery", "level": 15}
        self.assertTrue(rules_mod.holds(t, Snapshot(battery=10, charging=False), False))
        self.assertFalse(rules_mod.holds(t, Snapshot(battery=10, charging=True), False))
        self.assertFalse(rules_mod.holds(t, Snapshot(battery=16, charging=False), False))
        self.assertTrue(rules_mod.holds(t, Snapshot(battery=16, charging=False), True))

    def test_validation(self):
        with self.assertRaises(ValueError):
            rules_mod.clean_rule({"trigger": {"type": "nope"}, "action": {"type": "off"}})
        with self.assertRaises(ValueError):
            rules_mod.clean_rule({"trigger": {"type": "time", "start": "25:00", "end": "01:00"},
                                  "action": {"type": "off"}})
        rule = rules_mod.clean_rule({"trigger": {"type": "idle", "seconds": 1}, "action": {"type": "off"}})
        self.assertEqual(rule["trigger"]["seconds"], 5)   # clamped to the minimum

    def test_temperature_color(self):
        action = rules_mod.clean_rule({"trigger": {"type": "always"},
                                       "action": {"type": "temperature_color"}})["action"]
        cool = rules_mod.override(action, {"id": "x", "color_mode": "single"}, Snapshot(temperature=30), {}, set())
        hot = rules_mod.override(action, {"id": "x", "color_mode": "single"}, Snapshot(temperature=99), {}, set())
        self.assertEqual(cool["color"], "#00a0ff")
        self.assertEqual(hot["color"], "#ff2000")
        self.assertIsNone(rules_mod.override(action, {"id": "x", "color_mode": "none"},
                                             Snapshot(temperature=50), {}, set()))


if __name__ == "__main__":
    unittest.main()
