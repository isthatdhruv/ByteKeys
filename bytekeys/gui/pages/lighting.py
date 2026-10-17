"""Lighting: live preview, effects, brightness, colors and device options."""

from __future__ import annotations

from ...color import SWATCHES, normalize
from ..devicectl import BACKEND_TEXT, DeviceControl, kind_text
from ..qt import QtCore, QtWidgets, Qt
from ..widgets.forms import ColorButton, ParamForm, clear_layout
from ..widgets.keyboard import KeyboardView
from ..widgets.kit import (
    Banner, Card, Chip, ColorPanel, EffectTile, NeonSlider, RowList, Segmented, SettingRow, Switch, text_label,
)
from .base import Page


class LightingPage(Page):
    def __init__(self, window):
        super().__init__(window, "Lighting", "")
        self.ctl = DeviceControl(self)
        self._dev_id: str | None = None
        self._effect_ids: list[str] = []
        self._params_key = None
        self._form: ParamForm | None = None
        self._color_buttons: list[ColorButton] = []
        self._feature_ids: list[str] = []
        self._feature_widgets: dict[str, QtWidgets.QWidget] = {}
        self._selection: list[int] = []
        self._color_live = False

        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.setMinimumWidth(220)
        self.device_combo.activated.connect(self._on_device_combo)
        self.kind_chip = Chip("", "accent")
        self.backend_chip = Chip("", "dim")
        for w in (self.device_combo, self.kind_chip, self.backend_chip):
            self.header_right.addWidget(w, 0, Qt.AlignmentFlag.AlignTop)

        self.access_banner = Banner("warn", "", "Install service")
        self.access_banner.action.connect(window.install_service)
        self.add(self.access_banner)
        self.rules_banner = Banner("info", "")
        self.add(self.rules_banner)

        cols = QtWidgets.QHBoxLayout()
        cols.setSpacing(16)
        left = QtWidgets.QVBoxLayout()
        left.setSpacing(16)
        right = QtWidgets.QVBoxLayout()
        right.setSpacing(16)
        cols.addLayout(left, 3)
        cols.addLayout(right, 2)
        self.columns = QtWidgets.QWidget()
        cols.setContentsMargins(0, 0, 0, 0)
        self.columns.setLayout(cols)
        self.add(self.columns)

        # Preview ----------------------------------------------------------
        self.preview = Card("Preview", "keyboard")
        self.effect_label = text_label("", "dim")
        self.preview.add_header_widget(self.effect_label)
        self.keyboard = KeyboardView()
        self.keyboard.setMaximumHeight(300)
        self.keyboard.selectionChanged.connect(self._on_selection)
        self.preview.body.addWidget(self.keyboard)
        sel = QtWidgets.QHBoxLayout()
        self.selection_hint = text_label("", "faint")
        sel.addWidget(self.selection_hint)
        sel.addStretch(1)
        self.select_all = QtWidgets.QPushButton("Select all")
        self.select_all.setObjectName("ghost")
        self.select_all.clicked.connect(self._select_all)
        self.select_none = QtWidgets.QPushButton("Clear selection")
        self.select_none.setObjectName("ghost")
        self.select_none.clicked.connect(self._clear_selection)
        sel.addWidget(self.select_all)
        sel.addWidget(self.select_none)
        self.selection_bar = QtWidgets.QWidget()
        sel.setContentsMargins(0, 0, 0, 0)
        self.selection_bar.setLayout(sel)
        self.preview.body.addWidget(self.selection_bar)
        left.addWidget(self.preview)

        # Effects ----------------------------------------------------------
        self.effects = Card("Effects", "sparkle")
        self.effects.add_header_widget(text_label("HW = runs on the keyboard itself", "faint"))
        self.grid = QtWidgets.QGridLayout()
        self.grid.setSpacing(10)
        self.effects.body.addLayout(self.grid)
        self.effect_group = QtWidgets.QButtonGroup(self)
        self.effect_group.setExclusive(True)
        left.addWidget(self.effects)

        self.params = Card("Effect settings", "gear")
        self.params_box = QtWidgets.QVBoxLayout()
        self.params_box.setSpacing(12)
        self.params.body.addLayout(self.params_box)
        left.addWidget(self.params)
        left.addStretch(1)

        # Brightness ------------------------------------------------------
        self.bright = Card("Brightness", "sun")
        self.power = Switch()
        self.power.toggled.connect(self._on_power)
        self.bright.add_header_widget(self.power)
        row = QtWidgets.QHBoxLayout()
        self.slider = NeonSlider(0, 100)
        self.slider.valueChanged.connect(self._on_slider)
        self.slider.released.connect(lambda v: self.ctl.set_slider(v, final=True))
        row.addWidget(self.slider, 1)
        self.level = text_label("", "value")
        self.level.setMinimumWidth(70)
        self.level.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.level)
        self.bright.body.addLayout(row)
        self.bright_hint = text_label("", "faint", wrap=True)
        self.bright.body.addWidget(self.bright_hint)
        right.addWidget(self.bright)

        # Color -------------------------------------------------------------
        self.color = Card("Color", "palette")
        self.target = Segmented([("all", "All"), ("selected", "Selection")], stretch=False)
        self.target.set_value("all")
        self.target.changed.connect(lambda _v: self._update_selection_hint())
        self.color.add_header_widget(self.target)
        self.panel = ColorPanel(SWATCHES, vertical=True)
        self.panel.colorChanged.connect(self._color_dragged)
        self.panel.colorPicked.connect(self._color_picked)
        self.color.body.addWidget(self.panel)
        self.color_hint = text_label("", "faint", wrap=True)
        self.color.body.addWidget(self.color_hint)
        right.addWidget(self.color)

        # Device options ------------------------------------------------------
        self.features = Card("Device options", "gear")
        self.feature_rows = RowList()
        self.features.body.addWidget(self.feature_rows)
        right.addWidget(self.features)
        right.addStretch(1)

        # Empty state ---------------------------------------------------------
        self.empty = Card("No keyboard lighting found", "info")
        self.empty_text = text_label("", "dim", wrap=True)
        self.empty.body.addWidget(self.empty_text)
        rescan = QtWidgets.QPushButton("Scan again")
        rescan.setObjectName("primary")
        rescan.setCursor(Qt.CursorShape.PointingHandCursor)
        rescan.clicked.connect(self._rescan)
        holder = QtWidgets.QHBoxLayout()
        holder.addWidget(rescan)
        holder.addStretch(1)
        self.empty.body.addLayout(holder)
        self.add(self.empty)
        self.finish()

        self._params_timer = QtCore.QTimer(self)
        self._params_timer.setSingleShot(True)
        self._params_timer.setInterval(120)
        self._params_timer.timeout.connect(self._apply_params)

        self.listen(self.bridge.deviceChanged, self._on_device_changed)
        self.listen(self.bridge.devicesChanged, self.refresh)
        self.listen(window.deviceSelected, self._on_selected)

    # ---------------------------------------------------------------- sync
    def _on_device_changed(self, dev_id: str) -> None:
        if dev_id == self._dev_id:
            self.refresh()

    def _on_selected(self, _dev_id: str) -> None:
        self.refresh()

    def _on_device_combo(self, _index: int) -> None:
        self.window.select_device(self.device_combo.currentData())

    def layout_changed(self) -> None:
        self._dev_id = None
        self.refresh()

    def refresh(self) -> None:
        dev = self.device()
        has = dev is not None
        self.columns.setVisible(has)
        self.empty.setVisible(not has)
        for w in (self.kind_chip, self.backend_chip):
            w.setVisible(has)
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        for dev_id in self.bridge.order:
            self.device_combo.addItem(self.bridge.devices[dev_id]["name"], dev_id)
        if dev:
            self.device_combo.setCurrentIndex(max(0, self.device_combo.findData(dev["id"])))
        self.device_combo.setVisible(len(self.bridge.order) > 1)
        self.device_combo.blockSignals(False)
        if not has:
            self._dev_id = None
            self.set_subtitle("")
            self.access_banner.hide()
            self.rules_banner.hide()
            hints = [h["text"] for h in self.bridge.system.get("hints", []) if h["level"] != "info"]
            self.empty_text.setText("\n\n".join(hints) or "ByteKeys did not find a keyboard light it can control.")
            self.keyboard.set_device(None)
            return
        if dev["id"] != self._dev_id:
            self._dev_id = dev["id"]
            self._selection = []
            self._effect_ids = []
            self._params_key = None
            self._feature_ids = []
            self.keyboard.set_device(dev, self.window.keyboard_layout())
            self.target.set_value("all")
        st = dev["effective"]
        self.set_subtitle(dev["name"])
        self.kind_chip.set(kind_text(dev), "accent")
        self.backend_chip.set(BACKEND_TEXT.get(dev["backend"], dev["backend"]), "dim")
        effect = next((e for e in dev["effects"] if e["id"] == st["effect"]), None)
        self.effect_label.setText(f"{effect['name']}{' · on the keyboard' if effect['hardware'] else ''}"
                                  if effect and st["effect"] != "static" else "")
        self.keyboard.set_state(st)
        self._sync_banners(dev)
        self._sync_brightness(dev)
        self._sync_effects(dev)
        self._sync_params(dev)
        self._sync_color(dev)
        self._sync_features(dev)

    def _sync_banners(self, dev: dict) -> None:
        problem = dev.get("error") or dev.get("access")
        if problem:
            self.access_banner.set("warn", problem,
                                   "Install service" if self.bridge.mode == "portable" else None)
            self.access_banner.show()
        else:
            self.access_banner.hide()
        active = [r for r in self.bridge.rules if r["id"] in dev.get("rules_active", [])]
        if active:
            names = ", ".join(r["name"] for r in active)
            self.rules_banner.set("info", f"An automation is adjusting the lighting right now: {names}. "
                                          "Changing a setting here takes over until it stops applying.")
            self.rules_banner.show()
        else:
            self.rules_banner.hide()

    # ------------------------------------------------------------ brightness
    def _sync_brightness(self, dev: dict) -> None:
        st = dev["effective"]
        top, labels = DeviceControl.slider_range(dev)
        self.slider.set_range(0, top)
        self.slider.set_labels(labels if labels and len(labels) <= 6 else None)
        if not self.slider.is_dragging() and not self.ctl.busy:
            self.slider.set_value(DeviceControl.slider_value(dev))
        self.level.setText(DeviceControl.level_text(dev, self.slider.value()))
        self.power.blockSignals(True)
        self.power.setChecked(bool(st["on"] and st["brightness"] > 0))
        self.power.blockSignals(False)
        if not dev.get("brightness_hw", True):
            self.bright_hint.setText("This keyboard has no brightness control of its own; ByteKeys dims the "
                                     "colors instead.")
        elif labels and len(labels) > 6:
            self.bright_hint.setText(f"{top} brightness steps.")
        else:
            self.bright_hint.setText("")
        self.bright_hint.setVisible(bool(self.bright_hint.text()))

    def _on_slider(self, value: int) -> None:
        dev = self.device()
        if not dev:
            return
        self.level.setText(DeviceControl.level_text(dev, value))
        self.power.blockSignals(True)
        self.power.setChecked(value > 0)
        self.power.blockSignals(False)
        self.ctl.set_slider(value)

    def _on_power(self, on: bool) -> None:
        self.ctl.set_power(on)

    # --------------------------------------------------------------- effects
    def _sync_effects(self, dev: dict) -> None:
        ids = [e["id"] for e in dev["effects"]]
        if ids != self._effect_ids:
            self._effect_ids = ids
            for b in self.effect_group.buttons():
                self.effect_group.removeButton(b)
            clear_layout(self.grid)
            colors = dev["state"].get("effect_colors") or [dev["state"]["color"]]
            if dev["color_mode"] == "none":
                colors = ["#fff4e1"]
            n_cols = 3
            for i, effect in enumerate(dev["effects"]):
                tile = EffectTile(effect, colors)
                tile.clicked.connect(lambda _=False, eid=effect["id"]: self.ctl.choose_effect(eid))
                self.effect_group.addButton(tile)
                self.grid.addWidget(tile, i // n_cols, i % n_cols)
            for c in range(n_cols):
                self.grid.setColumnStretch(c, 1)
        current = dev["state"]["effect"]
        for b in self.effect_group.buttons():
            b.setChecked(b.effect["id"] == current)

    def _sync_params(self, dev: dict) -> None:
        effect = next((e for e in dev["effects"] if e["id"] == dev["state"]["effect"]), None)
        key = (dev["id"], dev["state"]["effect"])
        if key == self._params_key:
            return
        self._params_key = key
        clear_layout(self.params_box)
        self._form = None
        self._color_buttons = []
        if not effect or (not effect["params"] and not effect.get("colors")):
            self.params.hide()
            return
        self.params.show()
        self.params.title_label.setText(f"{effect['name']} settings".upper())
        if effect["params"]:
            self._form = ParamForm(effect["params"], dev["state"].get("params", {}))
            self._form.changed.connect(self._params_timer.start)
            self.params_box.addWidget(self._form)
        if effect.get("colors"):
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(4)
            row.addWidget(text_label("Colors", "dim"))
            row.addSpacing(12)
            colors = dev["state"].get("effect_colors") or []
            for i in range(effect["colors"]):
                btn = ColorButton(colors[i] if i < len(colors) else "#ffffff")
                btn.colorChanged.connect(lambda _c: self._params_timer.start())
                self._color_buttons.append(btn)
                row.addWidget(btn)
            row.addStretch(1)
            self.params_box.addLayout(row)

    def _apply_params(self) -> None:
        dev = self.device()
        if not dev:
            return
        changes: dict = {}
        if self._form is not None:
            changes["params"] = self._form.values()
        if self._color_buttons:
            changes["effect_colors"] = [b.color() for b in self._color_buttons]
        if changes:
            self.bridge.set_state(dev["id"], changes)

    # ----------------------------------------------------------------- color
    def _sync_color(self, dev: dict) -> None:
        rgb = dev["color_mode"] != "none"
        self.color.setVisible(rgb)
        zoned = dev["color_mode"] in ("zones", "perkey")
        self.selection_bar.setVisible(zoned)
        self.target.setVisible(zoned)
        if not rgb:
            return
        base = dev["state"]
        if not self._color_live:
            zones = base.get("zones") or []
            shown = zones[self._selection[0]] if (self._selection and self._selection[0] < len(zones)
                                                  and self.target.value() == "selected") else base["color"]
            self.panel.set_color(normalize(shown))
        effect = next((e for e in dev["effects"] if e["id"] == base["effect"]), None)
        if effect and effect["hardware"] and not effect.get("colors"):
            self.color_hint.setText("This mode picks its own colors; choosing a color switches back to Static.")
        else:
            self.color_hint.setText("")
        self.color_hint.setVisible(bool(self.color_hint.text()))
        self._update_selection_hint()

    def _zones_target(self) -> list[int] | None:
        dev = self.device()
        if dev and dev["color_mode"] in ("zones", "perkey") and self.target.value() == "selected":
            return list(self._selection)
        return None

    def _color_dragged(self, color: str) -> None:
        zones = self._zones_target()
        if zones == []:
            return
        self._color_live = True
        self.ctl.preview_color(color, zones)

    def _color_picked(self, color: str) -> None:
        self._color_live = False
        zones = self._zones_target()
        if zones == []:
            self.window.toast("Select keys or zones on the preview first")
            return
        self.ctl.apply_color(color, zones)

    def _on_selection(self, zones: list) -> None:
        self._selection = list(zones)
        self.target.set_value("selected" if zones else "all")
        self._update_selection_hint()

    def _select_all(self) -> None:
        dev = self.device()
        if not dev:
            return
        n = len(dev.get("zones") or [])
        self.keyboard.set_selection(range(n))
        self._on_selection(list(range(n)))

    def _clear_selection(self) -> None:
        self.keyboard.set_selection([])
        self._on_selection([])

    def _update_selection_hint(self) -> None:
        dev = self.device()
        unit = "key" if dev and dev["color_mode"] == "perkey" else "zone"
        n = len(self._selection)
        if n:
            self.selection_hint.setText(f"{n} {unit}{'s' if n != 1 else ''} selected")
        else:
            self.selection_hint.setText(f"Click {unit}s to color them separately"
                                        + (" (drag to paint)" if unit == "key" else ""))
        self.select_none.setVisible(bool(n))

    # -------------------------------------------------------------- features
    def _sync_features(self, dev: dict) -> None:
        feats = dev.get("features") or []
        ids = [f["id"] for f in feats]
        if ids != self._feature_ids:
            self._feature_ids = ids
            self._build_features(feats)
        else:
            self._update_features(feats)
        self.features.setVisible(bool(feats))

    def _build_features(self, feats: list[dict]) -> None:
        self.feature_rows.clear()
        self._feature_widgets = {}
        for f in feats:
            if f["kind"] == "bool":
                w = Switch()
                w.setChecked(bool(f["value"]))
                w.toggled.connect(lambda v, fid=f["id"]: self.bridge.set_feature(self._dev_id, fid, v))
            elif f["kind"] == "choice":
                w = QtWidgets.QComboBox()
                w.setMinimumWidth(150)
                for value, text in f["choices"]:
                    w.addItem(text, value)
                w.setCurrentIndex(max(0, w.findData(str(f["value"]))))
                w.activated.connect(lambda _i, fid=f["id"], combo=w:
                                    self.bridge.set_feature(self._dev_id, fid, combo.currentData()))
            else:
                w = QtWidgets.QSpinBox()
                w.setRange(int(f["min"]), int(f["max"]))
                w.setValue(int(f["value"] or f["min"]))
                w.setMinimumWidth(90)
                w.editingFinished.connect(lambda fid=f["id"], spin=w:
                                          self.bridge.set_feature(self._dev_id, fid, spin.value()))
            self.feature_rows.add(SettingRow(f["name"], f.get("description") or None, w))
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

    def _rescan(self) -> None:
        self.bridge.rescan()
        n = len(self.bridge.order)
        self.window.toast(f"Found {n} keyboard light{'s' if n != 1 else ''}" if n else "Still nothing found")
