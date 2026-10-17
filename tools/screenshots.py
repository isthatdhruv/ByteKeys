#!/usr/bin/env python3
"""Render README screenshots of the control center with simulated keyboards and fans.

    QT_QPA_PLATFORM=offscreen python3 tools/screenshots.py [dark|light] [page ...]
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
os.environ["BYTEKEYS_FSROOT"] = root = os.path.join(work, "root")   # hide the real hardware
dmi = os.path.join(root, "sys/class/dmi/id")
os.makedirs(dmi)
for name, value in (("sys_vendor", "ByteKeys"), ("product_name", "Demo Laptop 16"), ("board_vendor", "ByteKeys"),
                    ("board_name", "DEMO-16"), ("bios_version", "1.0.0")):
    with open(os.path.join(dmi, name), "w") as f:
        f.write(value + "\n")

from bytekeys.color import hsv, to_hex  # noqa: E402
from bytekeys.gui import theme  # noqa: E402
from bytekeys.gui.app import MainWindow, app_icon  # noqa: E402
from bytekeys.gui.bridge import Bridge  # noqa: E402
from bytekeys.gui.pages.performance import PRESETS  # noqa: E402
from bytekeys.gui.prefs import Prefs  # noqa: E402
from bytekeys.gui.qt import QtCore, QtWidgets  # noqa: E402

mode = sys.argv[1] if len(sys.argv) > 1 else "dark"
only = set(sys.argv[2:])
app = QtWidgets.QApplication([sys.argv[0]])
app.setQuitOnLastWindowClosed(False)
prefs = Prefs()
prefs["theme"] = mode
prefs["keyboard_layout"] = "full"
prefs["tray"] = False
theme.apply(app, mode)
app.setWindowIcon(app_icon())
bridge = Bridge(demo=True, local=True)
bridge.start()

# A colorful scene.
rainbow = [to_hex(hsv(0.08 + 0.10 * (z["col"] or 0) / 20, 0.9, 1.0))
           for z in bridge.devices["demo:perkey"]["zones"]]
bridge.set_state("demo:perkey", {"zones": rainbow, "brightness": 100})
bridge.set_state("demo:4zone", {"zones": ["#ffb35c", "#ff8a3d", "#ff5f6d", "#c86bff"]})
bridge.set_state("demo:rgb", {"color": "#ffb35c"})
bridge.set_rules([dict(r, enabled=r["id"] in ("battery-dim", "low-battery", "capslock")) for r in bridge.rules])
bridge.set_fan_curve("1", PRESETS["balanced"][1], True)

win = MainWindow(bridge, prefs, app, "home")
win.resize(1240, 860)
win.show()


def settle(ms=600):
    timer = QtCore.QDeadlineTimer(ms)
    while not timer.hasExpired():
        app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 50)


os.makedirs(OUT, exist_ok=True)
shots = [("home", "home", "demo:perkey"), ("lighting", "lighting", "demo:perkey"),
         ("lighting-zones", "lighting", "demo:4zone"), ("performance", "performance", None),
         ("automation", "automation", None), ("profiles", "profiles", "demo:perkey"),
         ("settings", "settings", None)]
for name, page, device in shots:
    if only and name not in only:
        continue
    if device:
        win.select_device(device)
    win.go(page)
    settle(1600 if page in ("home", "performance") else 800)
    path = os.path.join(OUT, f"{name}-{mode}.png")
    win.grab().save(path)
    print("wrote", os.path.relpath(path, ROOT))
bridge.close()
