"""System tray icon with quick controls."""

from __future__ import annotations

from .. import APP_NAME
from .qt import QtCore, QtWidgets
from .widgets.common import add_action


class Tray(QtCore.QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.bridge = window.bridge
        self.icon = QtWidgets.QSystemTrayIcon(window.windowIcon(), window)
        self.icon.setToolTip(APP_NAME)
        self.menu = QtWidgets.QMenu()
        self.menu.aboutToShow.connect(self._rebuild)
        self.icon.setContextMenu(self.menu)
        self.icon.activated.connect(self._activated)
        self._rebuild()

    @staticmethod
    def available() -> bool:
        return QtWidgets.QSystemTrayIcon.isSystemTrayAvailable()

    def set_visible(self, visible: bool) -> None:
        self.icon.setVisible(visible)

    def notify(self, title: str, text: str) -> None:
        if self.icon.isVisible():
            self.icon.showMessage(title, text, self.window.windowIcon(), 4000)

    def _activated(self, reason) -> None:
        if reason in (QtWidgets.QSystemTrayIcon.ActivationReason.Trigger,
                      QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick):
            self.window.toggle_window()

    def _rebuild(self) -> None:
        m = self.menu
        m.clear()
        add_action(m, self.bridge.system.get("model", APP_NAME), enabled=False)
        m.addSeparator()
        dev = self.window.current_device()
        if dev:
            st = dev["effective"]
            lit = st["on"] and st["brightness"] > 0
            add_action(m, "Lights on", lambda: self.bridge.toggle(dev["id"]), checkable=True, checked=lit)
            bright = m.addMenu("Brightness")
            levels = dev.get("levels")
            if levels:
                top = dev["brightness_max"]
                current = round(st["brightness"] / 100 * top) if lit else 0
                for i, name in enumerate(levels):
                    pct = round(i * 100 / top)
                    add_action(bright, name, lambda p=pct: self._brightness(dev["id"], p),
                               checkable=True, checked=i == current)
            else:
                for pct in (0, 25, 50, 75, 100):
                    add_action(bright, "Off" if pct == 0 else f"{pct}%",
                               lambda p=pct: self._brightness(dev["id"], p),
                               checkable=True, checked=(st["brightness"] if lit else 0) == pct)
            fx = m.addMenu("Effect")
            for e in dev["effects"]:
                add_action(fx, e["name"] + ("  (HW)" if e["hardware"] else ""),
                           lambda eid=e["id"]: self.bridge.set_state(dev["id"], {"effect": eid, "on": True}),
                           checkable=True, checked=dev["state"]["effect"] == e["id"])
        if self.bridge.profiles:
            prof = m.addMenu("Profile")
            for p in self.bridge.profiles:
                add_action(prof, p["name"], lambda n=p["name"]: self.bridge.apply_profile(n))
        m.addSeparator()
        add_action(m, f"Open {APP_NAME}", self.window.show_window)
        add_action(m, "Quit", self.window.quit)

    def _brightness(self, dev_id: str, pct: int) -> None:
        self.bridge.set_state(dev_id, {"on": pct > 0, **({"brightness": pct} if pct > 0 else {})})
