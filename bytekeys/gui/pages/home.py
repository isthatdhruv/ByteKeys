"""Home: live temperatures and fans, performance mode, keyboard and battery at a glance."""

from __future__ import annotations

from ... import modes
from ...color import normalize
from ..devicectl import MODE_ICONS, DeviceControl, kind_text
from ..qt import QtWidgets, Qt
from ..widgets.forms import clear_layout
from ..widgets.kit import (
    Card, Chip, MeterBar, ModeTile, NeonSlider, QuickTile, RingGauge, Segmented, Swatch, Switch, text_label,
)
from .base import Page

QUICK_COLORS = ["#ffffff", "#ffd7a8", "#ff3b30", "#ff9500", "#ffcc00", "#34c759", "#30b0ff", "#af52de"]


def _link(text: str, fn) -> QtWidgets.QPushButton:
    b = QtWidgets.QPushButton(text)
    b.setObjectName("link")
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.clicked.connect(fn)
    return b


class HomePage(Page):
    def __init__(self, window):
        super().__init__(window, "Control Center", "")
        self.ctl = DeviceControl(self)
        self._fan_gauges: dict[str, RingGauge] = {}
        self._fan_max: dict[str, float] = {}
        self._profile_ids: list[str] = []
        self._mode_key = None

        self.power_chip = Chip("", "dim")
        self.service_chip = Chip("", "good")
        self.header_right.addWidget(self.power_chip, 0, Qt.AlignmentFlag.AlignTop)
        self.header_right.addWidget(self.service_chip, 0, Qt.AlignmentFlag.AlignTop)

        # Live ------------------------------------------------------------
        self.live = Card("Live", "gauge")
        self.live.add_header_widget(_link("Fans && power  ›", lambda: window.go("performance")))
        self.gauges = QtWidgets.QHBoxLayout()
        self.gauges.setSpacing(6)
        self.cpu_gauge = RingGauge("CPU", "°C", 100, "cpu", warn=90)
        self.gpu_gauge = RingGauge("GPU", "°C", 100, "gpu", warn=87)
        self.load_gauge = RingGauge("CPU load", "%", 100, "gauge")
        for g in (self.cpu_gauge, self.gpu_gauge, self.load_gauge):
            self._gauge(g)
            self.gauges.addWidget(g, 1)
        self.live.body.addLayout(self.gauges)
        self.add(self.live)

        # Performance mode -------------------------------------------------
        self.perf = Card("Performance mode", "rocket")
        self.perf_via = text_label("", "faint")
        self.perf.add_header_widget(self.perf_via)
        self.perf_row = QtWidgets.QHBoxLayout()
        self.perf_row.setSpacing(12)
        self.perf.body.addLayout(self.perf_row)
        self.perf_group = QtWidgets.QButtonGroup(self)
        self.perf_group.setExclusive(True)
        self.perf_hint = text_label("", "dim", wrap=True)
        self.perf.body.addWidget(self.perf_hint)
        self.add(self.perf)

        # Keyboard + battery ----------------------------------------------
        bottom = QtWidgets.QHBoxLayout()
        bottom.setSpacing(16)
        self.kb = Card("Keyboard", "keyboard")
        self.kb.add_header_widget(_link("Customize  ›", lambda: window.go("lighting")))
        self.kb_switch = Switch()
        self.kb_switch.toggled.connect(self.ctl.set_power)
        self.kb.add_header_widget(self.kb_switch)
        self.kb_name = text_label("", "rowTitle")
        self.kb_kind = text_label("", "dim")
        top = QtWidgets.QHBoxLayout()
        top.addWidget(self.kb_name)
        top.addWidget(self.kb_kind)
        top.addStretch(1)
        self.kb_level = text_label("", "value")
        top.addWidget(self.kb_level)
        self.kb.body.addLayout(top)
        self.kb_slider = NeonSlider(0, 100)
        self.kb_slider.valueChanged.connect(self._on_slider)
        self.kb_slider.released.connect(lambda v: self.ctl.set_slider(v, final=True))
        self.kb.body.addWidget(self.kb_slider)
        self.kb_modes = QtWidgets.QHBoxLayout()
        self.kb_modes.setSpacing(8)
        self.kb.body.addLayout(self.kb_modes)
        self.mode_group = QtWidgets.QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.colors_row = QtWidgets.QHBoxLayout()
        self.colors_row.setSpacing(0)
        self.swatch_group = QtWidgets.QButtonGroup(self)
        self.swatch_group.setExclusive(True)
        self.swatches: list[Swatch] = []
        for color in QUICK_COLORS:
            sw = Swatch(color, 24)
            sw.clicked.connect(lambda _=False, c=color: self.ctl.apply_color(c))
            self.swatch_group.addButton(sw)
            self.swatches.append(sw)
            self.colors_row.addWidget(sw)
        self.colors_row.addStretch(1)
        self.colors_row.addWidget(_link("More colors  ›", lambda: window.go("lighting")))
        self.colors_holder = QtWidgets.QWidget()
        self.colors_holder.setLayout(self.colors_row)
        self.colors_row.setContentsMargins(0, 0, 0, 0)
        self.kb.body.addWidget(self.colors_holder)
        self.kb_empty = text_label("", "dim", wrap=True)
        self.kb.body.addWidget(self.kb_empty)
        self.kb.body.addStretch(1)
        bottom.addWidget(self.kb, 3)

        self.batt = Card("Battery", "battery")
        row = QtWidgets.QHBoxLayout()
        self.batt_value = text_label("", "big")
        row.addWidget(self.batt_value)
        row.addStretch(1)
        self.batt_state = Chip("", "dim")
        row.addWidget(self.batt_state, 0, Qt.AlignmentFlag.AlignVCenter)
        self.batt.body.addLayout(row)
        self.batt_meter = MeterBar()
        self.batt.body.addWidget(self.batt_meter)
        self.limit_title = text_label("Charge limit", "dim")
        self.batt.body.addSpacing(4)
        self.batt.body.addWidget(self.limit_title)
        self.limit_holder = QtWidgets.QHBoxLayout()
        self.batt.body.addLayout(self.limit_holder)
        self.limit_hint = text_label("", "faint", wrap=True)
        self.batt.body.addWidget(self.limit_hint)
        self.batt.body.addStretch(1)
        bottom.addWidget(self.batt, 2)
        self.add(bottom)
        self.finish()

        self.listen(self.bridge.deviceChanged, self._on_device_changed)
        self.listen(self.bridge.devicesChanged, self.refresh)
        self.listen(self.bridge.powerChanged, self._sync_power)
        self.listen(self.bridge.monitorUpdated, self._on_monitor)
        self.listen(window.deviceSelected, self._on_selected)

    @staticmethod
    def _gauge(g: RingGauge) -> None:
        g.setMinimumSize(128, 168)
        g.setMaximumHeight(190)

    # -------------------------------------------------------------- refresh
    def on_show(self) -> None:
        self.start_monitoring()

    def on_hide(self) -> None:
        self.stop_monitoring()

    def _on_device_changed(self, dev_id: str) -> None:
        dev = self.device()
        if dev and dev["id"] == dev_id:
            self._sync_keyboard()

    def _on_selected(self, _dev_id: str) -> None:
        self._mode_key = None
        self._sync_keyboard()

    def refresh(self) -> None:
        system = self.bridge.system
        self.set_subtitle(system.get("model", ""))
        if self.bridge.mode == "service":
            self.service_chip.set("Service running", "good")
        else:
            self.service_chip.set("Portable mode", "warn")
        self._sync_keyboard()
        self._sync_power()
        if self.bridge.monitor:
            self._on_monitor(self.bridge.monitor)

    # ------------------------------------------------------------- keyboard
    def _sync_keyboard(self) -> None:
        dev = self.device()
        has = dev is not None
        for w in (self.kb_switch, self.kb_slider, self.kb_level, self.kb_kind):
            w.setVisible(has)
        self.kb_empty.setVisible(not has)
        if not has:
            self.kb_name.setText("No keyboard light found")
            hints = [h["text"] for h in self.bridge.system.get("hints", []) if h["level"] != "info"]
            self.kb_empty.setText(hints[0] if hints else "ByteKeys did not find a keyboard light it can control.")
            self.colors_holder.hide()
            self._clear_modes()
            return
        st = dev["effective"]
        self.kb_name.setText(dev["name"])
        self.kb_kind.setText("·  " + kind_text(dev))
        top, labels = DeviceControl.slider_range(dev)
        self.kb_slider.set_range(0, top)
        self.kb_slider.set_labels(labels if labels and len(labels) <= 6 else None)
        if not self.kb_slider.is_dragging() and not self.ctl.busy:
            self.kb_slider.set_value(DeviceControl.slider_value(dev))
        self.kb_level.setText(DeviceControl.level_text(dev, self.kb_slider.value()))
        self.kb_switch.blockSignals(True)
        self.kb_switch.setChecked(bool(st["on"] and st["brightness"] > 0))
        self.kb_switch.blockSignals(False)
        rgb = dev["color_mode"] != "none"
        self.colors_holder.setVisible(rgb)
        current = normalize(dev["state"]["color"])
        for sw in self.swatches:
            sw.setChecked(rgb and sw.color == current and not dev["state"].get("zones"))
        self._sync_modes(dev)

    def _clear_modes(self) -> None:
        for b in self.mode_group.buttons():
            self.mode_group.removeButton(b)
        clear_layout(self.kb_modes)
        self._mode_key = None

    def _sync_modes(self, dev: dict) -> None:
        available = modes.quick_modes(dev)
        key = (dev["id"], tuple(available))
        if key != self._mode_key:
            self._clear_modes()
            self._mode_key = key
            for mode, text, effect_id in available:
                tile = QuickTile(MODE_ICONS.get(mode, "sparkle"), text)
                tile.setProperty("mode", mode)
                eff = next((e for e in dev["effects"] if e["id"] == effect_id), None)
                if eff and eff["hardware"] and mode != "static":
                    tile.badge = "HW"
                    tile.setToolTip("Runs on the keyboard itself")
                tile.clicked.connect(lambda _=False, eid=effect_id: self.ctl.choose_effect(eid))
                self.mode_group.addButton(tile)
                self.kb_modes.addWidget(tile)
            if len(available) <= 1:
                self._clear_modes()
                self._mode_key = key
        current = modes.mode_of(dev)
        for b in self.mode_group.buttons():
            b.setChecked(b.property("mode") == current)

    def _on_slider(self, value: int) -> None:
        dev = self.device()
        if not dev:
            return
        self.kb_level.setText(DeviceControl.level_text(dev, value))
        self.kb_switch.blockSignals(True)
        self.kb_switch.setChecked(value > 0)
        self.kb_switch.blockSignals(False)
        self.ctl.set_slider(value)

    # ---------------------------------------------------------------- power
    def _sync_power(self) -> None:
        power = self.bridge.power or {}
        profiles = power.get("profiles") or []
        ids = [p["id"] for p in profiles]
        if ids != self._profile_ids:
            self._profile_ids = ids
            for b in self.perf_group.buttons():
                self.perf_group.removeButton(b)
            clear_layout(self.perf_row)
            for prof in profiles:
                tile = ModeTile(prof["icon"], prof["name"], prof["description"])
                tile.setProperty("profile", prof["id"])
                tile.clicked.connect(lambda _=False, pid=prof["id"]: self._set_profile(pid))
                self.perf_group.addButton(tile)
                self.perf_row.addWidget(tile)
        self._check_profile(power.get("profile"))
        can_write = bool(power.get("write_access")) or power.get("profile_via") == "power-profiles-daemon"
        for b in self.perf_group.buttons():
            b.setEnabled(can_write)
        via = power.get("profile_via")
        self.perf_via.setText({"power-profiles-daemon": "synced with system power settings",
                               "sysfs": "firmware platform profile"}.get(via, ""))
        if not profiles:
            self.perf_hint.setText("This laptop does not offer performance modes to Linux "
                                   "(no ACPI platform profile was found).")
        elif not can_write:
            self.perf_hint.setText(power.get("access") or "")
        else:
            self.perf_hint.setText("")
        self.perf_hint.setVisible(bool(self.perf_hint.text()))
        self._sync_limit(power.get("charge"))

    def _check_profile(self, current: str | None) -> None:
        for b in self.perf_group.buttons():
            b.setChecked(b.property("profile") == current)

    def _set_profile(self, profile: str) -> None:
        self.bridge.set_power_profile(profile)
        name = next((p["name"] for p in self.bridge.power.get("profiles", []) if p["id"] == profile), profile)
        if self.bridge.power.get("profile") == profile:
            self.window.toast(f"{name} mode")

    def _sync_limit(self, charge: dict | None) -> None:
        clear_layout(self.limit_holder)
        self.limit_title.setVisible(bool(charge))
        if not charge:
            self.limit_hint.setText("This laptop has no battery charge limit that Linux can set.")
            return
        if charge["kind"] == "conservation":
            choices = [("60", "Conservation"), ("100", "Full")]
        else:
            choices = [(str(v), f"{v}%" if v < 100 else "Full") for v in charge["presets"]]
        self.limit = Segmented(choices, stretch=False)
        self.limit.set_value(str(charge["limit"]))
        self.limit.changed.connect(lambda v: self.bridge.set_charge_limit(int(v)))
        self.limit_holder.addWidget(self.limit)
        self.limit_holder.addStretch(1)
        self.limit_hint.setText("Charging to 80% or less helps the battery last longer when you are "
                                "mostly plugged in." if charge["limit"] >= 100 else "")

    # -------------------------------------------------------------- monitor
    def _on_monitor(self, data: dict) -> None:
        self.cpu_gauge.set_value(data.get("cpu_temp"), "no sensor")
        gpu = data.get("gpu_temp")
        self.gpu_gauge.set_value(gpu, "asleep" if data.get("gpu_note") == "sleeping" else "no sensor")
        self.gpu_gauge.setVisible(gpu is not None or bool(data.get("gpu_note")))
        fans = data.get("fans") or []
        ids = [f["id"] for f in fans[:3]]
        if ids != list(self._fan_gauges):
            for g in self._fan_gauges.values():
                self.gauges.removeWidget(g)
                g.deleteLater()
            self._fan_gauges = {}
            for i, f in enumerate(fans[:3]):
                g = RingGauge(f["label"], "RPM", 6500, "fan")
                self._gauge(g)
                self.gauges.insertWidget(2 + i, g, 1)
                self._fan_gauges[f["id"]] = g
        for f in fans[:3]:
            rpm = f.get("rpm")
            if rpm is not None:
                top = self._fan_max.get(f["id"], 6500.0)
                if rpm > top:
                    top = rpm * 1.15
                    self._fan_max[f["id"]] = top
                self._fan_gauges[f["id"]].maximum = top
            self._fan_gauges[f["id"]].set_value(rpm, "–")
        self.load_gauge.set_value(data.get("cpu_load"), "–")
        self.load_gauge.setVisible(len(fans) < 3)
        # battery
        level, charging, ac = data.get("battery"), data.get("charging"), data.get("ac")
        if level is None:
            self.batt_value.setText("—")
            self.batt_state.set("Plugged in" if ac else "No battery", "dim")
            self.batt_meter.set_value(0)
            self.power_chip.set("Plugged in" if ac else "No battery", "dim")
        else:
            self.batt_value.setText(f"{level}%")
            tone = "bad" if level <= 15 and not ac else "good" if charging else "accent"
            self.batt_meter.set_value(level / 100, tone if tone != "accent" else "accent")
            if charging and level >= 100:
                state = "Full"
            elif charging:
                state = "Charging"
            elif ac:
                state = "Plugged in"
            else:
                state = "On battery"
            self.batt_state.set(state, "good" if charging else "warn" if level <= 15 else "dim")
            self.power_chip.set(f"{state} · {level}%", "good" if ac else "dim")
