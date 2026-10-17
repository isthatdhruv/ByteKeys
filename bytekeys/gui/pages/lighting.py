"""Lighting page: preview, power, brightness, mode, colors and device settings."""

from __future__ import annotations

from ...color import SWATCHES, is_color, normalize
from ... import modes
from ..qt import QtCore, QtGui, QtWidgets, Qt
from ..widgets.common import (
    Banner,
    Card,
    Pill,
    RowList,
    Segmented,
    SettingRow,
    Swatch,
    Switch,
    clear_layout,
    label,
)
from ..widgets.keyboard import KeyboardView
from .base import Page

KIND_TEXT = {"none": "Single color", "single": "RGB", "zones": "{n}-zone RGB", "perkey": "Per-key RGB"}
BACKEND_TEXT = {"sysfs": "Kernel driver", "hid": "USB", "openrgb": "OpenRGB", "demo": "Simulated"}


class LightingPage(Page):
    def __init__(self, window):
        super().__init__(window, "Lighting", "Brightness, mode and colors of your keyboard.")
        self._dev_id: str | None = None
        self._feature_ids: list[str] = []
        self._feature_widgets: dict[str, QtWidgets.QWidget] = {}
        self._modes_key = None
        self._selection: list[int] = []
        self._pending: dict = {}
        self._send_timer = QtCore.QTimer(self)
        self._send_timer.setSingleShot(True)
        self._send_timer.setInterval(70)
        self._send_timer.timeout.connect(self._flush)

        self.access_banner = Banner("warn", "", "Install service")
        self.access_banner.action.connect(self.window.install_service)
        self.add(self.access_banner)
        self.rules_banner = Banner("info", "")
        self.add(self.rules_banner)

        # Preview -------------------------------------------------------
        preview = self.preview_card = Card()
        top = QtWidgets.QHBoxLayout()
        top.setSpacing(8)
        self.dev_name = label("", "cardTitle")
        top.addWidget(self.dev_name)
        self.kind_pill = Pill("")
        self.backend_pill = Pill("")
        top.addWidget(self.kind_pill)
        top.addWidget(self.backend_pill)
        top.addStretch(1)
        self.effect_label = label("", "cardHint")
        top.addWidget(self.effect_label)
        preview.body.addLayout(top)
        self.keyboard = KeyboardView()
        self.keyboard.selectionChanged.connect(self._on_selection)
        preview.body.addWidget(self.keyboard)
        self.add(preview)

        # Power & brightness --------------------------------------------
        power = self.power_card = Card("Power & brightness")
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(18)
        self.power = Switch()
        self.power.toggled.connect(self._on_power)
        row.addWidget(self.power)
        self.slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.slider.valueChanged.connect(self._on_slider)
        row.addWidget(self.slider, 1)
        self.level_label = label("", "big")
        self.level_label.setMinimumWidth(130)
        self.level_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.level_label)
        power.body.addLayout(row)
        self.levels_hint = label("", "cardHint")
        power.body.addWidget(self.levels_hint)
        self.add(power)

        # Mode ------------------------------------------------------------
        self.mode_card = Card("Mode")
        more = QtWidgets.QPushButton("All effects →")
        more.setObjectName("link")
        more.setCursor(Qt.CursorShape.PointingHandCursor)
        more.clicked.connect(lambda: self.window.nav.setCurrentRow(1))
        self.mode_card.add_header_widget(more)
        self.mode_row = QtWidgets.QHBoxLayout()
        self.mode_row.setSpacing(6)
        self.mode_card.body.addLayout(self.mode_row)
        self.mode_group = QtWidgets.QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.speed_row = QtWidgets.QHBoxLayout()
        self.speed_row.setSpacing(12)
        self.speed_label = label("Speed", "cardHint")
        self.speed_row.addWidget(self.speed_label)
        self.speed_holder = QtWidgets.QHBoxLayout()
        self.speed_row.addLayout(self.speed_holder)
        self.speed_row.addStretch(1)
        self.mode_card.body.addLayout(self.speed_row)
        self.mode_hint = label("", "cardHint", wrap=True)
        self.mode_card.body.addWidget(self.mode_hint)
        self.add(self.mode_card)

        # Color -----------------------------------------------------------
        self.color_card = Card("Color")
        self.target = Segmented([("all", "Whole keyboard"), ("selected", "Selected zones")])
        self.target.set_value("all")
        self.target.changed.connect(lambda _v: self._update_selection_hint())
        self.color_card.add_header_widget(self.target)
        swatch_row = QtWidgets.QHBoxLayout()
        swatch_row.setSpacing(2)
        self.swatch_group = QtWidgets.QButtonGroup(self)
        self.swatch_group.setExclusive(True)
        self.swatches: list[Swatch] = []
        for color in SWATCHES:
            sw = Swatch(color)
            sw.clicked.connect(lambda _=False, c=color: self._apply_color(c))
            self.swatch_group.addButton(sw)
            self.swatches.append(sw)
            swatch_row.addWidget(sw)
        swatch_row.addStretch(1)
        self.color_card.body.addLayout(swatch_row)
        custom = QtWidgets.QHBoxLayout()
        self.custom_btn = QtWidgets.QPushButton("Custom color…")
        self.custom_btn.clicked.connect(self._custom_color)
        custom.addWidget(self.custom_btn)
        self.hex_edit = QtWidgets.QLineEdit()
        self.hex_edit.setPlaceholderText("#rrggbb")
        self.hex_edit.setFixedWidth(110)
        self.hex_edit.returnPressed.connect(self._hex_entered)
        custom.addWidget(self.hex_edit)
        custom.addStretch(1)
        self.selection_hint = label("", "cardHint")
        custom.addWidget(self.selection_hint)
        self.select_all = QtWidgets.QPushButton("Select all")
        self.select_all.setObjectName("flat")
        self.select_all.clicked.connect(self._select_all)
        custom.addWidget(self.select_all)
        self.color_card.body.addLayout(custom)
        self.color_hint = label("", "cardHint", wrap=True)
        self.color_card.body.addWidget(self.color_hint)
        self.add(self.color_card)

        # Device settings -----------------------------------------------
        self.features_card = Card("Device settings")
        self.features = RowList()
        self.features_card.body.addWidget(self.features)
        self.add(self.features_card)

        self.empty_card = Card("No keyboard lighting found")
        self.empty_text = label("", "cardHint", wrap=True)
        self.empty_card.body.addWidget(self.empty_text)
        self.add(self.empty_card)
        self.finish()

        self.bridge.deviceChanged.connect(self._on_device_changed)
        self.bridge.devicesChanged.connect(self.refresh)
        window.deviceSelected.connect(lambda _id: self.refresh())

    # ----------------------------------------------------------------- sync
    def _on_device_changed(self, dev_id: str) -> None:
        if dev_id == self._dev_id:
            self.refresh()

    def refresh(self) -> None:
        dev = self.device()
        has = dev is not None
        for card in (self.preview_card, self.power_card, self.mode_card):
            card.setVisible(has)
        self.empty_card.setVisible(not has)
        if not has:
            self._dev_id = None
            for w in (self.access_banner, self.rules_banner, self.color_card, self.features_card):
                w.hide()
            hints = [h["text"] for h in self.bridge.system.get("hints", []) if h["level"] != "info"]
            self.empty_text.setText("\n\n".join(hints) or "ByteKeys did not find a keyboard light it can control.")
            self.keyboard.set_device(None)
            return
        if dev["id"] != self._dev_id:
            self._dev_id = dev["id"]
            self._selection = []
            self._modes_key = None
            self.keyboard.set_device(dev, self.window.keyboard_layout())
            self.target.set_value("all")
        st = dev["effective"]
        base = dev["state"]

        # header
        self.dev_name.setText(dev["name"])
        n = len(dev.get("zones") or [])
        self.kind_pill.setText(KIND_TEXT[dev["color_mode"]].format(n=n))
        self.backend_pill.setText(BACKEND_TEXT.get(dev["backend"], dev["backend"]))
        effect = next((e for e in dev["effects"] if e["id"] == st["effect"]), None)
        if effect and st["effect"] != "static":
            self.effect_label.setText(f"{effect['name']}{' · on the keyboard' if effect['hardware'] else ''}")
        else:
            self.effect_label.setText("")
        self.keyboard.set_state(st)

        # banners
        problem = dev.get("error") or dev.get("access")
        portable = self.bridge.mode == "portable"
        if problem:
            self.access_banner.set("warn", problem, "Install service" if portable else None)
            self.access_banner.show()
        else:
            self.access_banner.hide()
        active = [r for r in self.bridge.rules if r["id"] in dev.get("rules_active", [])]
        if active:
            names = ", ".join(r["name"] for r in active)
            self.rules_banner.set("info", f"A rule is adjusting the lighting right now: {names}. "
                                          "Changing a setting here takes over until the rule stops applying.")
            self.rules_banner.show()
        else:
            self.rules_banner.hide()

        self._sync_brightness(dev, st)
        self._sync_mode(dev)
        self._sync_color(dev, base)
        self._sync_features(dev)

    def _sync_brightness(self, dev: dict, st: dict) -> None:
        levels = dev.get("levels")
        top = dev["brightness_max"] if levels else 100
        self.slider.blockSignals(True)
        self.slider.setRange(0, top)
        self.slider.setPageStep(1 if levels else 10)
        self.slider.setTickPosition(QtWidgets.QSlider.TickPosition.TicksBelow if levels and top <= 10
                                    else QtWidgets.QSlider.TickPosition.NoTicks)
        if not self.slider.isSliderDown() and not self._pending:
            pct = st["brightness"] if st["on"] else 0
            self.slider.setValue(max(1, round(pct / 100 * top)) if levels and pct > 0 else
                                 (0 if levels else pct))
        self.slider.blockSignals(False)
        self.power.blockSignals(True)
        self.power.setChecked(bool(st["on"] and st["brightness"] > 0))
        self.power.blockSignals(False)
        self._update_level_label()
        self.levels_hint.setText(f"This keyboard has {top} brightness steps." if levels else "")
        self.levels_hint.setVisible(bool(levels))

    # ------------------------------------------------------------------ mode
    def _sync_mode(self, dev: dict) -> None:
        available = modes.quick_modes(dev)
        key = (dev["id"], tuple(available))
        if key != self._modes_key:
            self._modes_key = key
            for b in self.mode_group.buttons():
                self.mode_group.removeButton(b)
            clear_layout(self.mode_row)
            for mode, text, effect_id in available:
                b = QtWidgets.QPushButton(text)
                b.setObjectName("segment")
                b.setCheckable(True)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setProperty("mode", mode)
                eff = next((e for e in dev["effects"] if e["id"] == effect_id), None)
                if eff and eff["hardware"]:
                    b.setToolTip("Runs on the keyboard itself")
                b.clicked.connect(lambda _=False, eid=effect_id: self._choose_mode(eid))
                self.mode_group.addButton(b)
                self.mode_row.addWidget(b)
            self.mode_row.addStretch(1)
        current = modes.mode_of(dev)
        for b in self.mode_group.buttons():
            b.setChecked(b.property("mode") == current)
        effect = next((e for e in dev["effects"] if e["id"] == dev["state"]["effect"]), None)
        self._build_speed(dev, effect)
        if current is None and effect:
            self.mode_hint.setText(f"Playing “{effect['name']}”. Pick a mode above or open All effects.")
        elif effect and effect["hardware"] and effect["id"] != "static":
            self.mode_hint.setText("This mode runs on the keyboard's own controller.")
        else:
            self.mode_hint.setText("")
        self.mode_hint.setVisible(bool(self.mode_hint.text()))

    def _build_speed(self, dev: dict, effect: dict | None) -> None:
        clear_layout(self.speed_holder)
        param = modes.speed_param(effect)
        self.speed_label.setVisible(param is not None)
        if param is None:
            return
        value = dev["state"].get("params", {}).get("speed", param.get("default"))
        if param.get("kind") == "choice":
            seg = Segmented([(str(v), text) for v, text in param["choices"]])
            seg.set_value(str(value))
            seg.changed.connect(lambda v: self.bridge.set_state(self._dev_id, {"params": {"speed": v}}))
            self.speed_holder.addWidget(seg)
        else:
            slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
            slider.setFixedWidth(260)
            slider.setRange(int(param.get("min", 0)), int(param.get("max", 100)))
            try:
                slider.setValue(int(value))
            except (TypeError, ValueError):
                slider.setValue(int(param.get("default", 50)))
            slider.sliderReleased.connect(
                lambda s=slider: self.bridge.set_state(self._dev_id, {"params": {"speed": s.value()}}))
            self.speed_holder.addWidget(slider)

    def _choose_mode(self, effect_id: str) -> None:
        dev = self.device()
        if not dev:
            return
        effect = next((e for e in dev["effects"] if e["id"] == effect_id), None)
        if effect:
            self.bridge.set_state(dev["id"], modes.effect_changes(dev, effect))

    # ---------------------------------------------------------------- color
    def _sync_color(self, dev: dict, base: dict) -> None:
        rgb = dev["color_mode"] != "none"
        self.color_card.setVisible(rgb)
        if not rgb:
            return
        zoned = dev["color_mode"] in ("zones", "perkey")
        self.target.setVisible(zoned)
        self.select_all.setVisible(zoned)
        self.selection_hint.setVisible(zoned)
        self.target.buttons["selected"].setText("Selected keys" if dev["color_mode"] == "perkey"
                                                else "Selected zones")
        current = normalize(base["color"])
        for sw in self.swatches:
            sw.setChecked(sw.color == current and not base.get("zones"))
        if not self.hex_edit.hasFocus():
            self.hex_edit.setText(current)
        effect = next((e for e in dev["effects"] if e["id"] == base["effect"]), None)
        if effect and effect["hardware"] and not effect.get("colors"):
            self.color_hint.setText("The current mode picks its own colors; choosing a color "
                                    "switches back to Static.")
        else:
            self.color_hint.setText("")
        self.color_hint.setVisible(bool(self.color_hint.text()))
        self._update_selection_hint()

    # -------------------------------------------------------------- features
    def _sync_features(self, dev: dict) -> None:
        feats = dev.get("features") or []
        ids = [f["id"] for f in feats]
        if ids != self._feature_ids:
            self._feature_ids = ids
            self._build_features(feats)
        else:
            self._update_features(feats)
        self.features_card.setVisible(bool(feats))

    def _build_features(self, feats: list[dict]) -> None:
        self.features.clear()
        self._feature_widgets = {}
        for f in feats:
            if f["kind"] == "bool":
                w = Switch()
                w.setChecked(bool(f["value"]))
                w.toggled.connect(lambda v, fid=f["id"]: self.bridge.set_feature(self._dev_id, fid, v))
            elif f["kind"] == "choice":
                w = QtWidgets.QComboBox()
                w.setMinimumWidth(190)
                for value, text in f["choices"]:
                    w.addItem(text, value)
                idx = w.findData(str(f["value"]))
                w.setCurrentIndex(max(0, idx))
                w.activated.connect(lambda _i, fid=f["id"], combo=w:
                                    self.bridge.set_feature(self._dev_id, fid, combo.currentData()))
            else:
                w = QtWidgets.QSpinBox()
                w.setRange(int(f["min"]), int(f["max"]))
                w.setValue(int(f["value"] or f["min"]))
                w.setMinimumWidth(110)
                w.editingFinished.connect(lambda fid=f["id"], spin=w:
                                          self.bridge.set_feature(self._dev_id, fid, spin.value()))
            self.features.add(SettingRow(f["name"], f.get("description") or None, w))
            self._feature_widgets[f["id"]] = w

    def _update_features(self, feats: list[dict]) -> None:
        for f in feats:
            w = self._feature_widgets.get(f["id"])
            if w is None:
                continue
            w.blockSignals(True)
            if isinstance(w, Switch):
                w.setChecked(bool(f["value"]))
            elif isinstance(w, QtWidgets.QComboBox):
                idx = w.findData(str(f["value"]))
                if idx >= 0:
                    w.setCurrentIndex(idx)
            elif isinstance(w, QtWidgets.QSpinBox) and not w.hasFocus() and f["value"] is not None:
                w.setValue(int(f["value"]))
            w.blockSignals(False)

    # ------------------------------------------------------------- brightness
    def _queue(self, changes: dict) -> None:
        self._pending.update(changes)
        self._send_timer.start()

    def _flush(self) -> None:
        if self._pending and self._dev_id:
            changes, self._pending = self._pending, {}
            self.bridge.set_state(self._dev_id, changes)

    def _slider_pct(self) -> int:
        dev = self.device()
        if dev and dev.get("levels"):
            return int(round(self.slider.value() * 100 / max(1, dev["brightness_max"])))
        return self.slider.value()

    def _update_level_label(self) -> None:
        dev = self.device()
        if not dev:
            return
        levels = dev.get("levels")
        value = self.slider.value()
        if not self.power.isChecked() or value == 0:
            self.level_label.setText("Off")
        elif levels:
            self.level_label.setText(levels[min(value, len(levels) - 1)])
        else:
            self.level_label.setText(f"{value}%")

    def _on_slider(self, _value: int) -> None:
        pct = self._slider_pct()
        self.power.blockSignals(True)
        self.power.setChecked(pct > 0)
        self.power.blockSignals(False)
        self._update_level_label()
        self._queue({"on": pct > 0, **({"brightness": pct} if pct > 0 else {})})

    def _on_power(self, on: bool) -> None:
        changes: dict = {"on": on}
        dev = self.device()
        if on and dev and dev["state"]["brightness"] == 0:
            changes["brightness"] = 100
        self._queue(changes)
        self._flush()

    # ------------------------------------------------------------------ color
    def _on_selection(self, zones: list) -> None:
        self._selection = list(zones)
        if zones:
            self.target.set_value("selected")
        self._update_selection_hint()

    def _select_all(self) -> None:
        dev = self.device()
        if not dev:
            return
        n = len(dev.get("zones") or [])
        self.keyboard.set_selection(range(n))
        self._on_selection(list(range(n)))

    def _update_selection_hint(self) -> None:
        n = len(self._selection)
        dev = self.device()
        unit = "key" if dev and dev["color_mode"] == "perkey" else "zone"
        if self.target.value() == "selected":
            self.selection_hint.setText(f"{n} {unit}{'s' if n != 1 else ''} selected" if n
                                        else f"Click {unit}s on the keyboard to select them")
        else:
            self.selection_hint.setText("")

    def _color_changes(self, color: str) -> dict:
        dev = self.device()
        st = dev["state"]
        changes: dict = {"on": True}
        if dev["color_mode"] in ("zones", "perkey") and self.target.value() == "selected":
            if not self._selection:
                self.window.toast("Select zones on the keyboard first")
                return {}
            changes["zones"] = {str(i): color for i in self._selection}
        else:
            changes["color"] = color
        effect = next((e for e in dev["effects"] if e["id"] == st["effect"]), None)
        if effect and effect["hardware"]:
            if effect.get("colors"):
                changes["effect_colors"] = [color] + list(st.get("effect_colors") or [])[1:effect["colors"]]
            else:
                changes["effect"] = "static"   # e.g. a firmware rainbow cannot show one color
        return changes

    def _apply_color(self, color: str) -> None:
        if not self._dev_id:
            return
        changes = self._color_changes(color)
        if changes:
            self._queue(changes)
            self._flush()

    def _hex_entered(self) -> None:
        text = self.hex_edit.text().strip()
        if is_color(text):
            self._apply_color(normalize(text))
        else:
            self.window.toast(f"'{text}' is not a color (use #rrggbb)", error=True)

    def _custom_color(self) -> None:
        dev = self.device()
        if not dev:
            return
        original = dev["state"]
        dlg = QtWidgets.QColorDialog(QtGui.QColor(original["color"]), self)
        dlg.setWindowTitle("Keyboard color")
        dlg.setOption(QtWidgets.QColorDialog.ColorDialogOption.DontUseNativeDialog, True)

        def live(qcolor):
            changes = self._color_changes(qcolor.name())
            if changes:
                self._queue(changes)

        dlg.currentColorChanged.connect(live)
        if dlg.exec():
            self._apply_color(dlg.selectedColor().name())
        else:
            self._send_timer.stop()
            self._pending = {}
            restore = {k: original[k] for k in ("color", "zones", "effect", "effect_colors")}
            self.bridge.set_state(dev["id"], restore)
