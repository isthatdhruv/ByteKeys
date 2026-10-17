"""System page: detected hardware, service, preferences, diagnostics."""

from __future__ import annotations

from ... import APP_NAME, ISSUES_URL, PROJECT_URL, __version__
from ..prefs import autostart_enabled, set_autostart
from ..qt import QtCore, QtGui, QtWidgets, Qt
from ..widgets.common import (
    Banner,
    Card,
    InfoGrid,
    Pill,
    RowList,
    Segmented,
    SettingRow,
    Switch,
    clear_layout,
    label,
)
from .base import Page

KIND = {"none": "Single-color backlight", "single": "RGB (one zone)", "zones": "RGB ({n} zones)",
        "perkey": "Per-key RGB ({n} keys)"}
BACKEND = {"sysfs": "Linux kernel driver", "hid": "USB controller", "openrgb": "OpenRGB", "demo": "Simulated"}


class SystemPage(Page):
    def __init__(self, window):
        super().__init__(window, "System", "What ByteKeys found on this computer, and how it runs.")
        prefs = window.prefs

        # This computer ------------------------------------------------
        self.computer = Card("This computer")
        self.computer_info = InfoGrid()
        self.computer.body.addWidget(self.computer_info)
        self.hints_box = QtWidgets.QVBoxLayout()
        self.hints_box.setSpacing(8)
        self.computer.body.addLayout(self.hints_box)
        self.add(self.computer)

        # Keyboards ----------------------------------------------------
        self.keyboards = Card("Keyboards")
        rescan = QtWidgets.QPushButton("Rescan")
        rescan.clicked.connect(self._rescan)
        self.keyboards.add_header_widget(rescan)
        self.keyboards_box = QtWidgets.QVBoxLayout()
        self.keyboards_box.setSpacing(14)
        self.keyboards.body.addLayout(self.keyboards_box)
        self.add(self.keyboards)

        # Service --------------------------------------------------------
        self.service = Card("Background service")
        self.service_text = label("", wrap=True)
        self.service.body.addWidget(self.service_text)
        srow = QtWidgets.QHBoxLayout()
        self.install_btn = QtWidgets.QPushButton("Install service")
        self.install_btn.setObjectName("primary")
        self.install_btn.clicked.connect(window.install_service)
        self.remove_btn = QtWidgets.QPushButton("Remove service")
        self.remove_btn.setObjectName("danger")
        self.remove_btn.clicked.connect(window.uninstall_service)
        srow.addWidget(self.install_btn)
        srow.addWidget(self.remove_btn)
        srow.addStretch(1)
        self.service.body.addLayout(srow)
        self.add(self.service)

        # Control panel ----------------------------------------------------
        app_card = Card("Control panel")
        rows = RowList()
        self.autostart = Switch()
        self.autostart.setChecked(autostart_enabled())
        self.autostart.toggled.connect(self._set_autostart)
        rows.add(SettingRow("Start at login", "Starts hidden in the tray when you log in.", self.autostart))
        self.tray = Switch()
        self.tray.setChecked(bool(prefs["tray"]))
        self.tray.toggled.connect(lambda on: window.set_tray_enabled(on))
        rows.add(SettingRow("Show tray icon", "Quick brightness, mode and profile controls.", self.tray))
        self.close_to_tray = Switch()
        self.close_to_tray.setChecked(bool(prefs["close_to_tray"]))
        self.close_to_tray.toggled.connect(lambda on: prefs.__setitem__("close_to_tray", on))
        rows.add(SettingRow("Keep running when closed", "Closing the window leaves ByteKeys in the tray.",
                            self.close_to_tray))
        self.theme = Segmented([("system", "System"), ("light", "Light"), ("dark", "Dark")], stretch=False)
        self.theme.set_value(prefs["theme"])
        self.theme.changed.connect(window.set_theme)
        rows.add(SettingRow("Theme", None, self._fixed(self.theme)))
        self.layout_choice = Segmented([("auto", "Automatic"), ("compact", "Compact"), ("full", "With numpad")],
                                       stretch=False)
        self.layout_choice.set_value(prefs["keyboard_layout"])
        self.layout_choice.changed.connect(window.set_keyboard_layout)
        rows.add(SettingRow("Keyboard picture", "How the keyboard is drawn in the preview.",
                            self._fixed(self.layout_choice)))
        app_card.body.addWidget(rows)
        self.add(app_card)

        # Lighting engine --------------------------------------------------
        engine_card = Card("Lighting engine")
        erows = RowList()
        self.restore = Switch()
        self.restore.toggled.connect(lambda on: self.bridge.set_settings({"restore_on_boot": on}))
        erows.add(SettingRow("Restore lighting", "Re-apply your lighting at startup and after sleep.",
                             self.restore))
        self.firmware = Switch()
        self.firmware.toggled.connect(lambda on: self.bridge.set_settings({"save_to_firmware": on}))
        erows.add(SettingRow("Save to keyboard memory",
                             "Also store the look in the keyboard's firmware (shown before ByteKeys starts). "
                             "Writes flash memory, so it is off by default.", self.firmware))
        fps_box = QtWidgets.QWidget()
        fps_row = QtWidgets.QHBoxLayout(fps_box)
        fps_row.setContentsMargins(0, 0, 0, 0)
        self.fps = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.fps.setRange(5, 60)
        self.fps.setFixedWidth(200)
        self.fps.sliderReleased.connect(lambda: self.bridge.set_settings({"fps": self.fps.value()}))
        self.fps_label = label("", "faint")
        self.fps_label.setFixedWidth(48)
        self.fps.valueChanged.connect(lambda v: self.fps_label.setText(f"{v} fps"))
        fps_row.addWidget(self.fps)
        fps_row.addWidget(self.fps_label)
        erows.add(SettingRow("Animation smoothness", "Frames per second for software effects.", fps_box))
        self.openrgb = Switch()
        self.openrgb.toggled.connect(lambda on: self.bridge.set_settings({"openrgb": on}))
        erows.add(SettingRow("Use OpenRGB", "Also control keyboards supported by a running OpenRGB server "
                                            "(openrgb --server).", self.openrgb))
        engine_card.body.addWidget(erows)
        self.add(engine_card)

        # Diagnostics ----------------------------------------------------
        diag = Card("Help & diagnostics",
                    "If your keyboard is not detected or misbehaves, a report helps add support for it.")
        drow = QtWidgets.QHBoxLayout()
        copy_btn = QtWidgets.QPushButton("Copy report")
        copy_btn.clicked.connect(self._copy_report)
        save_btn = QtWidgets.QPushButton("Save report…")
        save_btn.clicked.connect(self._save_report)
        issue_btn = QtWidgets.QPushButton("Report a problem")
        issue_btn.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(ISSUES_URL)))
        for b in (copy_btn, save_btn, issue_btn):
            drow.addWidget(b)
        drow.addStretch(1)
        diag.body.addLayout(drow)
        self.add(diag)

        about = Card(f"About {APP_NAME}")
        info = label(f"{APP_NAME} {__version__} · Free software under the GNU GPL v3 or later.<br>"
                     f"<a href='{PROJECT_URL}'>{PROJECT_URL}</a>", wrap=True)
        info.setOpenExternalLinks(True)
        about.body.addWidget(info)
        self.add(about)
        self.finish()

        self.bridge.connectionChanged.connect(self.refresh)
        self.bridge.devicesChanged.connect(self.refresh)
        self.bridge.settingsChanged.connect(self._sync_settings)

    @staticmethod
    def _fixed(widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
        widget.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum, QtWidgets.QSizePolicy.Policy.Fixed)
        return widget

    # ---------------------------------------------------------------- sync
    def refresh(self) -> None:
        sysinfo = self.bridge.system
        self.computer_info.clear()
        if sysinfo:
            dmi = sysinfo.get("dmi", {})
            self.computer_info.add("Model", sysinfo.get("model", ""))
            self.computer_info.add("Family", sysinfo.get("family") or "")
            self.computer_info.add("Board", f"{dmi.get('board_vendor', '')} {dmi.get('board_name', '')}".strip())
            self.computer_info.add("BIOS", dmi.get("bios_version", ""))
            self.computer_info.add("System", f"{sysinfo.get('os', '')} · Linux {sysinfo.get('kernel', '')}")
            self.computer_info.add("Drivers", ", ".join(sysinfo.get("modules") or []))
        clear_layout(self.hints_box)
        for hint in sysinfo.get("hints", []):
            if hint["level"] == "info":
                continue
            self.hints_box.addWidget(Banner("warn" if hint["level"] == "warn" else "info", hint["text"]))

        clear_layout(self.keyboards_box)
        if not self.bridge.order:
            self.keyboards_box.addWidget(label("No keyboard lighting found.", "cardHint"))
        for i, dev_id in enumerate(self.bridge.order):
            dev = self.bridge.devices[dev_id]
            if i:
                line = QtWidgets.QFrame()
                line.setFixedHeight(1)
                line.setObjectName("divider")
                self.keyboards_box.addWidget(line)
            head = QtWidgets.QHBoxLayout()
            head.setSpacing(8)
            head.addWidget(label(dev["name"], "rowTitle"))
            n = len(dev.get("zones") or [])
            head.addWidget(Pill(KIND[dev["color_mode"]].format(n=n)))
            head.addWidget(Pill(BACKEND.get(dev["backend"], dev["backend"])))
            if dev.get("experimental"):
                head.addWidget(Pill("Experimental", "warn"))
            head.addStretch(1)
            self.keyboards_box.addLayout(head)
            grid = InfoGrid()
            path = dev.get("path", "")
            grid.add("Device", dev["id"] + (f"  ·  {path}" if path and path not in dev["id"] else ""))
            levels = dev.get("levels")
            grid.add("Brightness", " / ".join(levels) if levels else f"0–{dev['brightness_max']}"
                     if dev.get("brightness_hw", True) else "Software dimming")
            hw = [e["name"] for e in dev["effects"] if e["hardware"]]
            grid.add("Hardware modes", ", ".join(hw))
            for note in dev.get("notes", []):
                grid.add("Note", note)
            grid.add("Access", dev.get("access") or "")
            self.keyboards_box.addWidget(grid)

        portable = self.bridge.mode == "portable"
        status = self.window.service_status()
        if not portable:
            self.service_text.setText(
                "✓ The ByteKeys service is running. It keeps your lighting and rules active in the "
                "background, restores them after reboot and sleep, and handles keyboards that need "
                "administrator rights.")
        else:
            self.service_text.setText(
                "The service is not running, so ByteKeys works in portable mode: only settings your "
                "user may change are available, and rules run only while this window (or the tray "
                "icon) is open. Installing the service asks for your password once.")
        managed = status.get("managed_by_package")
        self.install_btn.setVisible(portable)
        self.install_btn.setText("Start service" if managed else "Install service")
        self.remove_btn.setVisible(status.get("installed", False) and not managed)
        self._sync_settings()

    def _sync_settings(self) -> None:
        s = self.bridge.settings
        if not s:
            return
        for widget, key in ((self.restore, "restore_on_boot"), (self.firmware, "save_to_firmware"),
                            (self.openrgb, "openrgb")):
            widget.blockSignals(True)
            widget.setChecked(bool(s.get(key)))
            widget.blockSignals(False)
        if not self.fps.isSliderDown():
            self.fps.blockSignals(True)
            self.fps.setValue(int(s.get("fps", 30)))
            self.fps.blockSignals(False)
            self.fps_label.setText(f"{self.fps.value()} fps")

    # -------------------------------------------------------------- actions
    def _set_autostart(self, on: bool) -> None:
        try:
            set_autostart(on)
        except OSError as e:
            self.window.toast(f"Could not change autostart: {e}", error=True)

    def _rescan(self) -> None:
        self.bridge.rescan()
        self.window.toast(f"Found {len(self.bridge.order)} keyboard(s)")

    def _report(self) -> str:
        return self.bridge.call("report") or ""

    def _copy_report(self) -> None:
        QtWidgets.QApplication.clipboard().setText(self._report())
        self.window.toast("Report copied to the clipboard")

    def _save_report(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save report", "bytekeys-report.txt",
                                                        "Text files (*.txt)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self._report())
                self.window.toast("Report saved")
            except OSError as e:
                self.window.toast(f"Could not save: {e}", error=True)
