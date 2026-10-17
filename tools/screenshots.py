#!/usr/bin/env python3
"""Render README screenshots of the control panel with simulated keyboards.

    QT_QPA_PLATFORM=offscreen python3 tools/screenshots.py [dark|light]
"""

from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "screenshots")
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
work = tempfile.mkdtemp(prefix="bk-shots-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(work, "config")
os.environ["XDG_STATE_HOME"] = os.path.join(work, "state")
os.environ["BYTEKEYS_FSROOT"] = os.path.join(work, "root")   # hide the real hardware
os.makedirs(os.environ["BYTEKEYS_FSROOT"])

from bytekeys.color import hsv, to_hex  # noqa: E402
from bytekeys.gui import theme  # noqa: E402
from bytekeys.gui.app import MainWindow, app_icon  # noqa: E402
from bytekeys.gui.bridge import Bridge  # noqa: E402
from bytekeys.gui.prefs import Prefs  # noqa: E402
from bytekeys.gui.qt import QtCore, QtWidgets  # noqa: E402

mode = sys.argv[1] if len(sys.argv) > 1 else "dark"
app = QtWidgets.QApplication([sys.argv[0]])
app.setQuitOnLastWindowClosed(False)
prefs = Prefs()
prefs["theme"] = mode
prefs["keyboard_layout"] = "full"
theme.apply(app, mode)
app.setWindowIcon(app_icon())
bridge = Bridge(demo=True, local=True)
bridge.start()

# A colorful scene.
keys = len(bridge.devices["demo:perkey"]["zones"])
rainbow = [to_hex(hsv(0.55 + 0.45 * (z["col"] or 0) / 20, 0.85, 1.0))
           for z in bridge.devices["demo:perkey"]["zones"]]
bridge.set_state("demo:perkey", {"zones": rainbow, "brightness": 100})
bridge.set_state("demo:4zone", {"zones": ["#3fa2ff", "#6d7bff", "#9a6bff", "#ff4fd1"]})
bridge.set_state("demo:rgb", {"color": "#5a7dff"})
bridge.set_rules([dict(r, enabled=r["id"] in ("battery-dim", "low-battery", "capslock")) for r in bridge.rules])

win = MainWindow(bridge, prefs, app)
win.resize(1180, 820)
win.show()


def settle(ms=500):
    timer = QtCore.QDeadlineTimer(ms)
    while not timer.hasExpired():
        app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 50)


def select(device):
    win.device_combo.setCurrentIndex(win.device_combo.findData(device))
    settle()


os.makedirs(OUT, exist_ok=True)
shots = [("lighting", 0, "demo:perkey"), ("lighting-zones", 0, "demo:4zone"), ("effects", 1, "demo:4zone"),
         ("rules", 2, "demo:4zone"), ("profiles", 3, "demo:4zone"), ("system", 4, "demo:4zone")]
for name, page, device in shots:
    select(device)
    win.nav.setCurrentRow(page)
    settle(700)
    path = os.path.join(OUT, f"{name}-{mode}.png")
    win.grab().save(path)
    print("wrote", os.path.relpath(path, ROOT))
bridge.close()
