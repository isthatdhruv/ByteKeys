"""Drive the control center offscreen with simulated keyboards and fans."""

import os
import shutil
import sys
import tempfile
import unittest

try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from bytekeys.gui.qt import QtCore, QtWidgets
except Exception:  # noqa: BLE001 - no Qt binding installed
    QtWidgets = None

from .fakesys import FakeSys


@unittest.skipIf(QtWidgets is None, "needs PySide6 or PyQt6")
class GuiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([sys.argv[0]])

    def setUp(self):
        self.fs = FakeSys()
        self.fs.dmi(sys_vendor="ByteKeys", product_name="Test Laptop")
        self.dir = tempfile.mkdtemp(prefix="bk-gui-")
        self.env = {k: os.environ.get(k) for k in ("XDG_CONFIG_HOME", "XDG_STATE_HOME")}
        os.environ["XDG_CONFIG_HOME"] = os.path.join(self.dir, "config")
        os.environ["XDG_STATE_HOME"] = os.path.join(self.dir, "state")
        from bytekeys.gui import theme
        from bytekeys.gui.app import MainWindow
        from bytekeys.gui.bridge import Bridge
        from bytekeys.gui.prefs import Prefs
        self.prefs = Prefs()
        self.prefs["tray"] = False
        theme.apply(self.app, "dark")
        self.bridge = Bridge(demo=True, local=True)
        self.bridge.start()
        self.errors = []
        self.bridge.errorOccurred.connect(self.errors.append)
        self.win = MainWindow(self.bridge, self.prefs, self.app, "home")
        self.win.resize(1240, 860)
        self.win.show()
        self.settle()

    def tearDown(self):
        self.win.quit()
        self.win.deleteLater()
        self.settle(50)
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.dir, ignore_errors=True)
        self.fs.close()

    def settle(self, ms: int = 150) -> None:
        timer = QtCore.QDeadlineTimer(ms)
        while not timer.hasExpired():
            self.app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 20)

    def test_every_page_renders(self):
        for key in ("home", "lighting", "performance", "automation", "profiles", "settings"):
            self.win.go(key)
            self.settle(80)
            self.assertFalse(self.win.grab().isNull(), key)
            self.assertLessEqual(self.win.pages[key].widget().minimumSizeHint().width(),
                                 self.win.stack.width(), f"{key} is wider than the window")
        self.assertEqual(self.errors, [])

    def test_home_controls(self):
        home = self.win.pages["home"]
        self.win.select_device("demo:4zone")
        self.settle()
        tiles = home.mode_group.buttons()
        self.assertGreaterEqual(len(tiles), 3)
        tiles[1].click()     # Breathing
        self.settle()
        self.assertIn("breath", self.bridge.devices["demo:4zone"]["state"]["effect"])
        home.swatches[2].click()
        self.settle()
        self.assertEqual(self.bridge.devices["demo:4zone"]["state"]["color"], "#ff3b30")
        home.kb_switch.click()
        self.settle()
        self.assertFalse(self.bridge.devices["demo:4zone"]["state"]["on"])
        perf = [b for b in home.perf_group.buttons() if b.property("profile") == "performance"][0]
        perf.click()
        self.settle()
        self.assertEqual(self.bridge.power["profile"], "performance")
        self.assertEqual(self.errors, [])

    def test_performance_curve_editing(self):
        self.win.go("performance")
        page = self.win.pages["performance"]
        self.settle(300)
        page._use_preset([[40, 30], [50, 40], [60, 55], [70, 70], [75, 80], [80, 90], [90, 100], [95, 100]])
        self.assertTrue(page.apply_btn.isEnabled())
        page.apply_btn.click()
        self.settle()
        curve = next(c for c in self.bridge.power["curves"] if c["fan"] == page._fan)
        self.assertTrue(curve["enabled"])
        self.assertEqual(curve["points"][0], [40, 30])
        page.custom.click()     # back to the firmware curve
        self.settle()
        curve = next(c for c in self.bridge.power["curves"] if c["fan"] == page._fan)
        self.assertFalse(curve["enabled"])
        page.boost.click()
        self.settle()
        self.assertTrue(self.bridge.power["boost"]["on"])
        self.assertEqual(self.errors, [])

    def test_lighting_effects_and_colors(self):
        self.win.select_device("demo:perkey")
        self.win.go("lighting")
        page = self.win.pages["lighting"]
        self.settle()
        wave = next(b for b in page.effect_group.buttons() if b.effect["id"] == "wave")
        wave.click()
        self.settle()
        self.assertEqual(self.bridge.devices["demo:perkey"]["state"]["effect"], "wave")
        self.assertTrue(page.params.isVisible())
        page._on_selection([0, 1, 2])
        page._color_picked("#00ff00")
        self.settle()
        zones = self.bridge.devices["demo:perkey"]["state"]["zones"]
        self.assertEqual(zones[:3], ["#00ff00"] * 3)
        self.assertEqual(self.errors, [])

    def test_theme_switch_rebuilds(self):
        self.win.go("lighting")
        self.win.set_theme("light")
        self.settle()
        self.assertEqual(self.win.current_page_key(), "lighting")
        self.win.set_theme("dark")
        self.settle()
        self.bridge.set_state("demo:rgb", {"color": "#123456"})   # old pages must not react anymore
        self.settle()
        self.assertEqual(self.errors, [])

    def test_key_catcher_takes_only_special_keys(self):
        from bytekeys.gui.launchkey import KeyCatcher
        from bytekeys.gui.qt import QtGui, Qt
        dialog = KeyCatcher(self.win, service=False)
        dialog.show()
        self.settle(50)

        def key(scan, qt_key=0):     # xkb keycode = evdev code + 8
            return QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, qt_key, Qt.KeyboardModifier.NoModifier, scan, 0, 0)
        dialog.keyPressEvent(key(30 + 8, Qt.Key.Key_A.value))
        self.assertIsNone(dialog.code, "letters are never learned")
        dialog.keyPressEvent(key(202 + 8))
        self.assertEqual(dialog.code, 202)
        dialog.deleteLater()

    def test_launch_event_shows_the_window(self):
        self.win.hide()
        self.bridge._on_event("launch", {})
        self.settle()
        self.assertTrue(self.win.isVisible())


if __name__ == "__main__":
    unittest.main()
