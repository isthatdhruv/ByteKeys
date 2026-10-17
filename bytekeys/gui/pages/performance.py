"""Performance: power profiles, live fans, firmware fan curves, full fan speed and battery care."""

from __future__ import annotations

from ... import power as power_mod
from ..qt import QtWidgets, Qt
from ..widgets.fancurve import FanCurveEditor
from ..widgets.forms import clear_layout
from ..widgets.kit import (
    Banner, Card, Chip, MeterBar, ModeTile, Segmented, SettingRow, Switch, text_label,
)
from .base import Page

# Example curves (temperature °C, fan %). All pass power.validate_curve().
PRESETS = {
    "silent": ("Silent", [[40, 0], [50, 10], [60, 25], [70, 40], [75, 50], [80, 60], [90, 80], [95, 100]]),
    "balanced": ("Balanced", [[40, 15], [50, 25], [60, 35], [70, 50], [75, 60], [80, 70], [90, 90], [95, 100]]),
    "turbo": ("Turbo", [[40, 30], [50, 40], [60, 55], [70, 70], [75, 80], [80, 90], [90, 100], [95, 100]]),
}


class FanRow(QtWidgets.QWidget):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        top = QtWidgets.QHBoxLayout()
        self.name = text_label(label, "rowTitle")
        top.addWidget(self.name)
        top.addStretch(1)
        self.value = text_label("", "value")
        top.addWidget(self.value)
        lay.addLayout(top)
        self.meter = MeterBar()
        lay.addWidget(self.meter)

    def set(self, text: str, fraction: float, tone: str = "accent") -> None:
        self.value.setText(text)
        self.meter.set_value(fraction, tone)


class PerformancePage(Page):
    def __init__(self, window):
        super().__init__(window, "Performance", "Performance modes, fan curves and battery care, run by your "
                                                "laptop's own firmware.")
        self._profile_ids: list[str] = []
        self._curve_ids: list[str] = []
        self._fan: str | None = None
        self._draft: list[list[int]] | None = None
        self._fan_rows: dict[str, FanRow] = {}
        self._fan_top: dict[str, float] = {}
        self._temps: dict[str, float | None] = {}
        self.picker: Segmented | None = None

        self.via_chip = Chip("", "dim")
        self.header_right.addWidget(self.via_chip, 0, Qt.AlignmentFlag.AlignTop)
        self.access = Banner("warn", "", "Install service")
        self.access.action.connect(window.install_service)
        self.add(self.access)

        # Modes -----------------------------------------------------------
        self.modes = Card("Performance mode", "rocket")
        self.mode_row = QtWidgets.QHBoxLayout()
        self.mode_row.setSpacing(12)
        self.modes.body.addLayout(self.mode_row)
        self.mode_group = QtWidgets.QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.modes_hint = text_label("", "dim", wrap=True)
        self.modes.body.addWidget(self.modes_hint)
        self.add(self.modes)

        # Fan curve + live fans ---------------------------------------------
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(16)
        self.curve_card = Card("Fan curve", "wave")
        self.fan_picker_slot = QtWidgets.QHBoxLayout()
        self.curve_card.header.addLayout(self.fan_picker_slot)
        self.curve_card.add_header_widget(text_label("Custom", "dim"))
        self.custom = Switch()
        self.custom.toggled.connect(self._on_custom)
        self.curve_card.add_header_widget(self.custom)
        self.editor = FanCurveEditor()
        self.editor.setMinimumHeight(240)
        self.editor.changed.connect(self._on_edited)
        self.curve_card.body.addWidget(self.editor)
        tools = QtWidgets.QHBoxLayout()
        tools.setSpacing(8)
        tools.addWidget(text_label("Presets", "dim"))
        self.preset_buttons = []
        for key, (name, points) in PRESETS.items():
            b = QtWidgets.QPushButton(name)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, pts=points: self._use_preset(pts))
            tools.addWidget(b)
            self.preset_buttons.append(b)
        tools.addStretch(1)
        self.reset_btn = QtWidgets.QPushButton("Factory curve")
        self.reset_btn.setObjectName("ghost")
        self.reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_btn.setToolTip("Discard the custom curve and use the firmware's own curve")
        self.reset_btn.clicked.connect(self._reset)
        tools.addWidget(self.reset_btn)
        self.revert_btn = QtWidgets.QPushButton("Undo")
        self.revert_btn.setObjectName("ghost")
        self.revert_btn.clicked.connect(self._revert)
        tools.addWidget(self.revert_btn)
        self.apply_btn = QtWidgets.QPushButton("Apply curve")
        self.apply_btn.setObjectName("primary")
        self.apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_btn.clicked.connect(self._apply)
        tools.addWidget(self.apply_btn)
        self.tools_holder = QtWidgets.QWidget()
        tools.setContentsMargins(0, 0, 0, 0)
        self.tools_holder.setLayout(tools)
        self.curve_card.body.addWidget(self.tools_holder)
        self.curve_hint = text_label("", "faint", wrap=True)
        self.curve_card.body.addWidget(self.curve_hint)
        self.no_curves = text_label(
            "Custom fan curves are not available on this laptop. ByteKeys only uses fan controls that the "
            "laptop's firmware runs itself, so a crash can never leave a fan stopped. Today that means ASUS "
            "laptops whose firmware exposes fan curves through asus-wmi (most TUF and ROG models since 2021).",
            "dim", wrap=True)
        self.curve_card.body.addWidget(self.no_curves)
        row.addWidget(self.curve_card, 5)

        side = QtWidgets.QVBoxLayout()
        side.setSpacing(16)
        self.fans_card = Card("Fans & temperatures", "fan")
        self.fan_list = QtWidgets.QVBoxLayout()
        self.fan_list.setSpacing(10)
        self.fans_card.body.addLayout(self.fan_list)
        self.cpu_row = FanRow("CPU")
        self.gpu_row = FanRow("GPU")
        self.fans_card.body.addWidget(self.cpu_row)
        self.fans_card.body.addWidget(self.gpu_row)
        self.fans_empty = text_label("No fan sensors were found.", "dim", wrap=True)
        self.fans_card.body.addWidget(self.fans_empty)
        self.boost = Switch()
        self.boost.toggled.connect(self._on_boost)
        self.boost_row = SettingRow("Full fan speed", "Loud; your curves return when it is off.", self.boost,
                                    icon="flame")
        self.fans_card.body.addWidget(self.boost_row)
        self.fans_card.body.addStretch(1)
        side.addWidget(self.fans_card, 1)
        self.battery_card = Card("Battery care", "battery")
        self.limit_slot = QtWidgets.QHBoxLayout()
        self.battery_card.body.addLayout(self.limit_slot)
        self.battery_hint = text_label("", "dim", wrap=True)
        self.battery_card.body.addWidget(self.battery_hint)
        side.addWidget(self.battery_card)
        row.addLayout(side, 3)
        self.add(row)
        self.finish()

        self.listen(self.bridge.powerChanged, self.refresh)
        self.listen(self.bridge.monitorUpdated, self._on_monitor)

    def on_show(self) -> None:
        self.start_monitoring()

    def on_hide(self) -> None:
        self.stop_monitoring()

    # -------------------------------------------------------------- refresh
    def _can_write(self) -> bool:
        return bool((self.bridge.power or {}).get("write_access"))

    def refresh(self) -> None:
        power = self.bridge.power or {}
        writable = self._can_write()
        via = power.get("profile_via")
        self.via_chip.set({"power-profiles-daemon": "Synced with system settings",
                           "sysfs": "Firmware profile"}.get(via, "No profiles"),
                          "good" if via else "dim")
        portable = self.bridge.mode == "portable"
        if not writable and (power.get("curves") or power.get("boost") or power.get("charge")):
            self.access.set("warn", "Fan curves, full fan speed and the charge limit need the ByteKeys service "
                                    "(it runs with the rights to change them).",
                            "Install service" if portable else None)
            self.access.show()
        else:
            self.access.hide()
        self._sync_modes(power)
        self._sync_curves(power)
        boost = power.get("boost")
        self.boost_row.setVisible(boost is not None)
        if boost is not None:
            self.boost.blockSignals(True)
            self.boost.setChecked(bool(boost.get("on")))
            self.boost.blockSignals(False)
            self.boost.setEnabled(writable)
        self._sync_battery(power.get("charge"), writable)
        if self.bridge.monitor:
            self._on_monitor(self.bridge.monitor)

    def _sync_modes(self, power: dict) -> None:
        profiles = power.get("profiles") or []
        ids = [p["id"] for p in profiles]
        if ids != self._profile_ids:
            self._profile_ids = ids
            for b in self.mode_group.buttons():
                self.mode_group.removeButton(b)
            clear_layout(self.mode_row)
            for prof in profiles:
                tile = ModeTile(prof["icon"], prof["name"], prof["description"])
                tile.setProperty("profile", prof["id"])
                tile.clicked.connect(lambda _=False, pid=prof["id"]: self.bridge.set_power_profile(pid))
                self.mode_group.addButton(tile)
                self.mode_row.addWidget(tile)
        can = self._can_write() or power.get("profile_via") == "power-profiles-daemon"
        for b in self.mode_group.buttons():
            b.setChecked(b.property("profile") == power.get("profile"))
            b.setEnabled(can)
        if not profiles:
            self.modes_hint.setText("This laptop does not offer performance modes to Linux (no ACPI platform "
                                    "profile was found).")
        else:
            self.modes_hint.setText("")
        self.modes_hint.setVisible(bool(self.modes_hint.text()))

    # ------------------------------------------------------------ fan curves
    def _curves(self) -> dict[str, dict]:
        return {c["fan"]: c for c in (self.bridge.power or {}).get("curves") or []}

    def _sync_curves(self, power: dict) -> None:
        curves = self._curves()
        has = bool(curves)
        for w in (self.editor, self.tools_holder, self.curve_hint, self.custom):
            w.setVisible(has)
        self.no_curves.setVisible(not has)
        ids = list(curves)
        if ids != self._curve_ids:
            self._curve_ids = ids
            clear_layout(self.fan_picker_slot)
            if len(ids) > 1:
                picker = Segmented([(fan, curves[fan]["label"]) for fan in ids], stretch=False)
                picker.changed.connect(self._pick_fan)
                self.fan_picker_slot.addWidget(picker)
                self.picker = picker
            else:
                self.picker = None
            if self._fan not in curves:
                self._fan = ids[0] if ids else None
                self._draft = None
        if not has:
            return
        if self.picker is not None:
            self.picker.set_value(self._fan)
        curve = curves[self._fan]
        self.custom.blockSignals(True)
        self.custom.setChecked(bool(curve["enabled"]))
        self.custom.blockSignals(False)
        writable = self._can_write()
        self.custom.setEnabled(writable)
        self.editor.set_editable(writable)
        for b in (*self.preset_buttons, self.reset_btn, self.apply_btn):
            b.setEnabled(writable)
        self.editor.set_points(self._draft or curve["points"])
        self._update_curve_state()

    def _pick_fan(self, fan: str) -> None:
        if fan == self._fan:
            return
        if self._draft is not None and not self._confirm_discard():
            self.picker.set_value(self._fan)
            return
        self._fan = fan
        self._draft = None
        self._sync_curves(self.bridge.power or {})
        self._update_marker()

    def _confirm_discard(self) -> bool:
        answer = QtWidgets.QMessageBox.question(self, "Unsaved fan curve",
                                                "Discard the changes to this fan curve?")
        return answer == QtWidgets.QMessageBox.StandardButton.Yes

    def _update_curve_state(self) -> None:
        curve = self._curves().get(self._fan)
        if not curve:
            return
        dirty = self._draft is not None
        self.apply_btn.setText("Applied" if curve["enabled"] and not dirty else "Apply curve")
        self.apply_btn.setEnabled(self._can_write() and dirty)
        self.revert_btn.setVisible(dirty)
        profile = (self.bridge.power or {}).get("profile")
        name = next((p["name"] for p in (self.bridge.power or {}).get("profiles", []) if p["id"] == profile), None)
        if dirty:
            text = "Unsaved changes. Drag the points, then apply. For safety the fans always run at 50 % or " \
                   "more from 80 °C and at 70 % or more at the last point."
        elif curve["enabled"]:
            text = "Your curve is active" + (f" in {name} mode" if name else "") + \
                   ". Each mode keeps its own curves; ByteKeys switches them with the mode (also via Fn keys)."
        else:
            text = "The firmware's curve is active" + (f" in {name} mode" if name else "") + \
                   ". Drag the points or pick a preset to make your own."
        self.curve_hint.setText(text)

    def _on_edited(self, points: list) -> None:
        self._draft = [list(p) for p in points]
        self._update_curve_state()

    def _use_preset(self, points: list) -> None:
        self._draft = [list(p) for p in points]
        self.editor.set_points(self._draft)
        self._update_curve_state()

    def _revert(self) -> None:
        self._draft = None
        self._sync_curves(self.bridge.power or {})

    def _apply(self) -> None:
        curve = self._curves().get(self._fan)
        if not curve:
            return
        points = self._draft or curve["points"]
        try:
            points = power_mod.validate_curve(points)
        except ValueError as e:
            self.window.toast(str(e).capitalize(), error=True)
            return
        self._draft = None
        self.bridge.set_fan_curve(self._fan, points, True)
        if self._curves().get(self._fan, {}).get("enabled"):
            self.window.toast(f"{curve['label']} curve applied")

    def _on_custom(self, on: bool) -> None:
        curve = self._curves().get(self._fan)
        if not curve:
            return
        if on and self._draft is not None:
            self._apply()
        else:   # on: the service brings back your last custom curve for this mode
            self._draft = None
            self.bridge.set_fan_curve(self._fan, None, on)

    def _reset(self) -> None:
        if self._fan is None:
            return
        self._draft = None
        self.bridge.reset_fan_curve(self._fan)
        self.window.toast("Back to the factory fan curve")

    # ------------------------------------------------------------ boost/battery
    def _on_boost(self, on: bool) -> None:
        self.bridge.set_fan_boost(on)

    def _sync_battery(self, charge: dict | None, writable: bool) -> None:
        clear_layout(self.limit_slot)
        self.battery_card.setVisible(charge is not None)
        if not charge:
            return
        if charge["kind"] == "conservation":
            choices = [("60", "Conservation"), ("100", "Full charge")]
        else:
            choices = [(str(v), f"{v}%" if v < 100 else "100%") for v in charge["presets"]]
        seg = Segmented(choices, stretch=False)
        seg.set_value(str(charge["limit"]))
        seg.setEnabled(writable)
        seg.changed.connect(lambda v: self.bridge.set_charge_limit(int(v)))
        self.limit_slot.addWidget(seg)
        self.limit_slot.addStretch(1)
        if charge["kind"] == "conservation":
            self.battery_hint.setText("Conservation mode keeps the battery around 60 % while plugged in.")
        else:
            self.battery_hint.setText("80 % or less extends battery life if you are mostly plugged in.")

    # -------------------------------------------------------------- monitor
    def _update_marker(self) -> None:
        curve = self._curves().get(self._fan)
        label = (curve or {}).get("label", "")
        temp = self._temps.get("gpu") if label.startswith("GPU") else self._temps.get("cpu")
        self.editor.set_current_temp(temp)

    def _on_monitor(self, data: dict) -> None:
        self._temps = {"cpu": data.get("cpu_temp"), "gpu": data.get("gpu_temp")}
        self._update_marker()
        cpu = data.get("cpu_temp")
        self.cpu_row.setVisible(cpu is not None)
        if cpu is not None:
            self.cpu_row.set(f"{cpu:.0f} °C", cpu / 100, "bad" if cpu >= 90 else "accent")
        gpu = data.get("gpu_temp")
        self.gpu_row.setVisible(gpu is not None or data.get("gpu_note") == "sleeping")
        if gpu is not None:
            self.gpu_row.set(f"{gpu:.0f} °C", gpu / 100, "bad" if gpu >= 87 else "accent")
        elif data.get("gpu_note") == "sleeping":
            self.gpu_row.set("Asleep", 0)
        fans = data.get("fans") or []
        ids = [f["id"] for f in fans]
        if ids != list(self._fan_rows):
            clear_layout(self.fan_list)
            self._fan_rows = {}
            for f in fans:
                fr = FanRow(f["label"])
                self.fan_list.addWidget(fr)
                self._fan_rows[f["id"]] = fr
        for f in fans:
            rpm = f.get("rpm") or 0
            top = max(self._fan_top.get(f["id"], 6500.0), rpm * 1.1)
            self._fan_top[f["id"]] = top
            self._fan_rows[f["id"]].set(f"{rpm:,} RPM" if rpm else "Stopped", rpm / top)
        self.fans_empty.setVisible(not fans and cpu is None)
