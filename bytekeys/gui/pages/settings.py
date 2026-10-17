"""Settings: this laptop, keyboards, launch key, service, preferences, diagnostics."""

from __future__ import annotations

from ... import APP_NAME, ISSUES_URL, PROJECT_URL, __version__, models
from .. import shortcuts
from ..launchkey import KeyCatcher
from ..devicectl import BACKEND_TEXT
from ..prefs import autostart_enabled, launch_command, set_autostart
from ..qt import QtCore, QtGui, QtWidgets, Qt
from ..widgets.forms import InfoGrid, clear_layout
from ..widgets.kit import Banner, Card, Chip, NeonSlider, RowList, Segmented, SettingRow, Switch, text_label
from .base import Page

KIND = {"none": "Single color", "single": "RGB", "zones": "RGB · {n} zones", "perkey": "Per-key RGB · {n} keys"}


class SettingsPage(Page):
    def __init__(self, window):
        super().__init__(window, "Settings", "")
        prefs = window.prefs

        cols = QtWidgets.QHBoxLayout()
        cols.setSpacing(16)
        left = QtWidgets.QVBoxLayout()
        left.setSpacing(16)
        right = QtWidgets.QVBoxLayout()
        right.setSpacing(16)
        cols.addLayout(left, 1)
        cols.addLayout(right, 1)
        self.add(cols)

        # This laptop -------------------------------------------------------
        self.computer = Card("This laptop", "info")
        self.computer_info = InfoGrid()
        self.computer.body.addWidget(self.computer_info)
        self.hints_box = QtWidgets.QVBoxLayout()
        self.hints_box.setSpacing(8)
        self.computer.body.addLayout(self.hints_box)
        left.addWidget(self.computer)

        # Keyboards ---------------------------------------------------------
        self.keyboards = Card("Keyboard lights", "keyboard")
        rescan = QtWidgets.QPushButton("Rescan")
        rescan.setCursor(Qt.CursorShape.PointingHandCursor)
        rescan.clicked.connect(self._rescan)
        self.keyboards.add_header_widget(rescan)
        self.keyboards_box = QtWidgets.QVBoxLayout()
        self.keyboards_box.setSpacing(14)
        self.keyboards.body.addLayout(self.keyboards_box)
        left.addWidget(self.keyboards)

        # Service -------------------------------------------------------------
        self.service = Card("Background service", "shield")
        self.service_chip = Chip("", "good")
        self.service.add_header_widget(self.service_chip)
        self.service_text = text_label("", "dim", wrap=True)
        self.service.body.addWidget(self.service_text)
        srow = QtWidgets.QHBoxLayout()
        self.install_btn = QtWidgets.QPushButton("Install service")
        self.install_btn.setObjectName("primary")
        self.install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.install_btn.clicked.connect(window.install_service)
        self.remove_btn = QtWidgets.QPushButton("Remove service")
        self.remove_btn.setObjectName("danger")
        self.remove_btn.clicked.connect(window.uninstall_service)
        srow.addWidget(self.install_btn)
        srow.addWidget(self.remove_btn)
        srow.addStretch(1)
        self.service.body.addLayout(srow)
        left.addWidget(self.service)
        left.addStretch(1)

        # Launch key ----------------------------------------------------------
        self.launch = Card("Launch key", "key")
        self.launch.body.addWidget(text_label(
            "Gaming laptops have a key that opens the vendor's control center (Armoury Crate, NitroSense, "
            "OMEN Gaming Hub, MSI Center…). On Linux it can open ByteKeys instead.", "dim", wrap=True))
        lrows = RowList()
        self.launch_switch = Switch()
        self.launch_switch.toggled.connect(self._on_launch_toggled)
        self.launch_row = SettingRow("Open ByteKeys with the launch key", "", self.launch_switch)
        lrows.add(self.launch_row)
        self.shortcut_switch = Switch()
        self.shortcut_switch.toggled.connect(self._on_shortcut_toggled)
        self.shortcut_row = SettingRow("Also when ByteKeys is closed", "", self.shortcut_switch)
        lrows.add(self.shortcut_row)
        self.launch.body.addWidget(lrows)
        self.launch_warning = Banner("warn", "")
        self.launch.body.addWidget(self.launch_warning)
        lbuttons = QtWidgets.QHBoxLayout()
        self.detect_btn = QtWidgets.QPushButton("Detect key…")
        self.detect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.detect_btn.clicked.connect(self._detect)
        lbuttons.addWidget(self.detect_btn)
        lbuttons.addStretch(1)
        self.launch.body.addLayout(lbuttons)
        self.launch_note = text_label("", "faint", wrap=True)
        self.launch.body.addWidget(self.launch_note)
        right.addWidget(self.launch)

        # App -------------------------------------------------------------------
        app_card = Card("App", "gear")
        rows = RowList()
        self.theme = Segmented([("dark", "Dark"), ("light", "Light"), ("system", "System")], stretch=False)
        self.theme.set_value(prefs["theme"])
        self.theme.changed.connect(window.set_theme)
        rows.add(SettingRow("Theme", None, self.theme))
        self.autostart = Switch()
        self.autostart.setChecked(autostart_enabled())
        self.autostart.toggled.connect(self._set_autostart)
        rows.add(SettingRow("Start at login", "Starts hidden in the tray when you log in.", self.autostart))
        self.tray = Switch()
        self.tray.setChecked(bool(prefs["tray"]))
        self.tray.toggled.connect(lambda on: window.set_tray_enabled(on))
        rows.add(SettingRow("Tray icon", "Quick brightness, effect and profile controls.", self.tray))
        self.close_to_tray = Switch()
        self.close_to_tray.setChecked(bool(prefs["close_to_tray"]))
        self.close_to_tray.toggled.connect(lambda on: prefs.__setitem__("close_to_tray", on))
        rows.add(SettingRow("Keep running when closed", "Closing the window leaves ByteKeys running in the "
                                                        "background.", self.close_to_tray))
        self.layout_choice = Segmented([("auto", "Auto"), ("compact", "Compact"), ("full", "Numpad")],
                                       stretch=False)
        self.layout_choice.set_value(prefs["keyboard_layout"])
        self.layout_choice.changed.connect(window.set_keyboard_layout)
        rows.add(SettingRow("Keyboard picture", "How the preview draws your keyboard.", self.layout_choice,
                            stacked=True))
        app_card.body.addWidget(rows)
        right.addWidget(app_card)

        # Lighting engine --------------------------------------------------------
        engine_card = Card("Lighting engine", "sparkle")
        erows = RowList()
        self.restore = Switch()
        self.restore.toggled.connect(lambda on: self.bridge.set_settings({"restore_on_boot": on}))
        erows.add(SettingRow("Restore lighting", "Re-apply your lighting at startup and after sleep.",
                             self.restore))
        self.firmware = Switch()
        self.firmware.toggled.connect(lambda on: self.bridge.set_settings({"save_to_firmware": on}))
        erows.add(SettingRow("Save to keyboard memory",
                             "Also store the look in the keyboard's firmware, so it shows before ByteKeys "
                             "starts. Writes flash memory, so it is off by default.", self.firmware))
        fps_box = QtWidgets.QWidget()
        fps_row = QtWidgets.QHBoxLayout(fps_box)
        fps_row.setContentsMargins(0, 0, 0, 0)
        self.fps = NeonSlider(5, 60)
        self.fps.setFixedWidth(170)
        self.fps.released.connect(lambda v: self.bridge.set_settings({"fps": v}))
        self.fps_label = text_label("", "dim")
        self.fps_label.setFixedWidth(48)
        self.fps.valueChanged.connect(lambda v: self.fps_label.setText(f"{v} fps"))
        fps_row.addWidget(self.fps)
        fps_row.addWidget(self.fps_label)
        fps_row.addStretch(1)
        erows.add(SettingRow("Animation smoothness", "Frames per second for software effects.", fps_box,
                             stacked=True))
        self.openrgb = Switch()
        self.openrgb.toggled.connect(lambda on: self.bridge.set_settings({"openrgb": on}))
        erows.add(SettingRow("Use OpenRGB", "Also control keyboards that a running OpenRGB server supports "
                                            "(openrgb --server).", self.openrgb))
        engine_card.body.addWidget(erows)
        right.addWidget(engine_card)

        # Diagnostics + about ------------------------------------------------------
        diag = Card("Help & diagnostics", "info")
        diag.body.addWidget(text_label("Keyboard not detected or misbehaving? A report helps add support for it.",
                                       "dim", wrap=True))
        drow = QtWidgets.QHBoxLayout()
        for text, fn in (("Copy report", self._copy_report), ("Save…", self._save_report),
                         ("Report issue", lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(ISSUES_URL)))):
            b = QtWidgets.QPushButton(text)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(fn)
            drow.addWidget(b)
        drow.addStretch(1)
        diag.body.addLayout(drow)
        right.addWidget(diag)

        about = Card(f"About {APP_NAME}", "sparkle")
        arow = QtWidgets.QHBoxLayout()
        arow.setSpacing(16)
        logo = QtWidgets.QLabel()
        logo.setPixmap(window.windowIcon().pixmap(64, 64))
        arow.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)
        info = text_label(f"<b>{APP_NAME} {__version__}</b><br>Keyboard lighting, fans and performance for Linux "
                          f"laptops.<br>Free software under the GNU GPL v3 or later.<br>"
                          f"<a href='{PROJECT_URL}' style='color:inherit'>{PROJECT_URL}</a>", "dim", wrap=True)
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setOpenExternalLinks(True)
        arow.addWidget(info, 1)
        about.body.addLayout(arow)
        right.addWidget(about)
        right.addStretch(1)
        self.finish()

        self.listen(self.bridge.connectionChanged, self.refresh)
        self.listen(self.bridge.devicesChanged, self.refresh)
        self.listen(self.bridge.settingsChanged, self._sync_settings)

    # ---------------------------------------------------------------- sync
    def refresh(self) -> None:
        sysinfo = self.bridge.system
        self.set_subtitle(sysinfo.get("model", ""))
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
            self.keyboards_box.addWidget(text_label("No keyboard lighting found.", "dim"))
        for i, dev_id in enumerate(self.bridge.order):
            dev = self.bridge.devices[dev_id]
            if i:
                line = QtWidgets.QFrame()
                line.setFixedHeight(1)
                line.setStyleSheet("background: rgba(128,128,140,0.18);")
                self.keyboards_box.addWidget(line)
            head = QtWidgets.QHBoxLayout()
            head.setSpacing(8)
            head.addWidget(text_label(dev["name"], "rowTitle", wrap=True), 1)
            n = len(dev.get("zones") or [])
            head.addWidget(Chip(KIND[dev["color_mode"]].format(n=n), "accent"))
            head.addWidget(Chip(BACKEND_TEXT.get(dev["backend"], dev["backend"]), "dim"))
            if dev.get("experimental"):
                head.addWidget(Chip("Experimental", "warn"))
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
        if self.bridge.outdated:
            self.service_chip.set(f"Outdated · {self.bridge.service_version or '?'}", "warn")
            self.service_text.setText(
                f"The running service is an older version than this app ({__version__}), so fan control, "
                "performance modes and the launch key are unavailable. Update it to fix this.")
        elif not portable:
            self.service_chip.set("Running", "good")
            self.service_text.setText(
                "The service keeps your lighting, fan curves and automations active in the background, "
                "restores them after reboot and sleep, and answers the launch key.")
        else:
            self.service_chip.set("Not running", "warn")
            self.service_text.setText(
                "ByteKeys works in portable mode: only settings your user may change are available, and "
                "automations run only while ByteKeys is open. Installing the service asks for your password once.")
        managed = status.get("managed_by_package")
        self.install_btn.setVisible(portable or (self.bridge.outdated and not managed))
        self.install_btn.setText("Update service" if self.bridge.outdated else
                                 "Start service" if managed else "Install service")
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
        if not self.fps.is_dragging():
            self.fps.set_value(int(s.get("fps", 30)))
            self.fps_label.setText(f"{self.fps.value()} fps")
        self._sync_launch()

    # ------------------------------------------------------------ launch key
    def _launch_code(self) -> int:
        return int(self.bridge.settings.get("launch_key") or 0)

    def _sync_launch(self) -> None:
        code = self._launch_code()
        dmi = self.bridge.system.get("dmi", {})
        kind = shortcuts.backend()
        service = self.bridge.mode == "service"
        self.launch_switch.blockSignals(True)
        self.launch_switch.setChecked(bool(code))
        self.launch_switch.blockSignals(False)
        if code:
            self.launch_row.hint.setText(f"{models.launch_key_name(dmi, code)} · "
                                         f"{shortcuts.keysym(code) or 'key code ' + str(code)}")
        else:
            default = models.default_launch_key(dmi)
            self.launch_row.hint.setText(f"Off. This laptop's key: {models.launch_key_name(dmi, default)}."
                                         if default else "Off. Use “Detect key” to choose the key.")
        self.launch_row.hint.show()
        accel = shortcuts.binding(code) if code else None
        installed = shortcuts.installed()
        has_shortcut = bool(accel) and installed == accel
        self.shortcut_row.setVisible(bool(accel))
        if accel:
            self.shortcut_switch.blockSignals(True)
            self.shortcut_switch.setChecked(has_shortcut)
            self.shortcut_switch.blockSignals(False)
            self.shortcut_row.hint.setText("Adds a keyboard shortcut to GNOME." if kind == "gnome" else
                                           "Adds a KDE shortcut, active after you log in again.")
            self.shortcut_row.hint.show()
        if code in models.DESKTOP_KEYS and not (kind == "gnome" and has_shortcut):
            self.launch_warning.set("warn", "Your desktop also uses this key (for example to open its Settings)."
                                    + (" The desktop shortcut hands it to ByteKeys." if kind == "gnome" else ""))
            self.launch_warning.show()
        else:
            self.launch_warning.hide()
        if not code:
            note = "Only special keys can be chosen, never letters or digits."
        elif has_shortcut:
            note = "The key opens ByteKeys at any time, even when it is closed."
        elif service:
            note = ("The key opens ByteKeys while it runs; it starts in the background at login."
                    if autostart_enabled() else
                    "The key opens ByteKeys while it is running. Turn on “Start at login” so it is always ready.")
        elif kind:
            note = "Without the ByteKeys service, the desktop shortcut above makes the key work."
        else:
            note = shortcuts.manual_instructions(code, launch_command(False))
        self.launch_note.setText(note)

    def _on_launch_toggled(self, on: bool) -> None:
        prefs = self.window.prefs
        if on:
            code = int(prefs["launch_key_last"] or 0) or models.default_launch_key(self.bridge.system.get("dmi", {}))
            if code:
                self._set_launch_key(code)
            else:
                self.launch_switch.blockSignals(True)
                self.launch_switch.setChecked(False)
                self.launch_switch.blockSignals(False)
                self._detect()
            return
        if self._launch_code():
            prefs["launch_key_last"] = self._launch_code()
        if shortcuts.installed():
            shortcuts.uninstall()
        self.bridge.set_settings({"launch_key": 0})
        self._sync_launch()

    def _set_launch_key(self, code: int) -> None:
        """Use *code* as the launch key: the service watches it and the desktop shortcut follows it."""
        self.window.prefs["launch_key_last"] = code
        self.bridge.set_settings({"launch_key": code})
        if shortcuts.binding(code):
            ok, message = shortcuts.install(code, launch_command(False))
            self.window.toast(message, error=not ok)
        elif self.bridge.mode == "service" and not autostart_enabled():
            try:
                set_autostart(True)
                self.autostart.blockSignals(True)
                self.autostart.setChecked(True)
                self.autostart.blockSignals(False)
                self.window.toast("ByteKeys now starts in the background at login, ready for the key")
            except OSError:
                pass
        self._sync_launch()

    def _on_shortcut_toggled(self, on: bool) -> None:
        if on:
            ok, message = shortcuts.install(self._launch_code(), launch_command(False))
            self.window.toast(message, error=not ok)
        else:
            shortcuts.uninstall()
            self.window.toast("Desktop shortcut removed")
        self._sync_launch()

    def _detect(self) -> None:
        dialog = KeyCatcher(self, service=self.bridge.mode == "service")
        if dialog.exec() and dialog.code:
            self._set_launch_key(dialog.code)
        elif dialog.timed_out:
            self.window.toast("No launch key was pressed. If nothing reacted, your desktop may already use it "
                              "or it needs the ByteKeys service.", error=True)

    # -------------------------------------------------------------- actions
    def _set_autostart(self, on: bool) -> None:
        try:
            set_autostart(on)
        except OSError as e:
            self.window.toast(f"Could not change autostart: {e}", error=True)
        self._sync_launch()

    def _rescan(self) -> None:
        self.bridge.rescan()
        n = len(self.bridge.order)
        self.window.toast(f"Found {n} keyboard light{'s' if n != 1 else ''}")

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
