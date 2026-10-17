"""Effects page: pick an animation and tune it."""

from __future__ import annotations

from ... import modes
from ..qt import QtCore, QtWidgets, Qt
from ..widgets.common import Card, ColorButton, ParamForm, Pill, clear_layout, label
from ..widgets.keyboard import KeyboardView
from .base import Page


class EffectTile(QtWidgets.QPushButton):
    def __init__(self, effect: dict):
        super().__init__()
        self.effect = effect
        self.setObjectName("tile")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(92)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)
        top = QtWidgets.QHBoxLayout()
        name = label(effect["name"])
        name.setStyleSheet("font-weight: 650; background: transparent;")
        top.addWidget(name)
        top.addStretch(1)
        if effect["hardware"]:
            top.addWidget(Pill("HW", "accent"))
        lay.addLayout(top)
        desc = label(effect.get("description") or ("Runs on the keyboard's own controller"
                                                   if effect["hardware"] else ""), "cardHint", wrap=True)
        desc.setStyleSheet("background: transparent;")
        lay.addWidget(desc)
        lay.addStretch(1)
        for child in self.findChildren(QtWidgets.QLabel):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


class EffectsPage(Page):
    def __init__(self, window):
        super().__init__(window, "Effects", "Animations and lighting modes for the selected keyboard.")
        self._dev_id = None
        self._effect_ids: list[str] = []
        self._form: ParamForm | None = None
        self._color_buttons: list[ColorButton] = []

        preview = self.preview_card = Card()
        self.keyboard = KeyboardView()
        self.keyboard.setMinimumHeight(150)
        self.keyboard.setMaximumHeight(250)
        preview.body.addWidget(self.keyboard)
        self.add(preview)

        self.grid_card = Card("Choose an effect", "Software effects work on any keyboard; HW effects "
                                                  "run on the keyboard's own controller.")
        self.grid = QtWidgets.QGridLayout()
        self.grid.setSpacing(10)
        self.grid_card.body.addLayout(self.grid)
        self.group = QtWidgets.QButtonGroup(self)
        self.group.setExclusive(True)
        self.add(self.grid_card)

        self.params_card = Card("Settings")
        self.params_box = QtWidgets.QVBoxLayout()
        self.params_card.body.addLayout(self.params_box)
        self.add(self.params_card)
        self.finish()

        self._apply_timer = QtCore.QTimer(self)
        self._apply_timer.setSingleShot(True)
        self._apply_timer.setInterval(120)
        self._apply_timer.timeout.connect(self._apply_params)

        self.bridge.deviceChanged.connect(lambda i: self.refresh() if i == self._dev_id else None)
        self.bridge.devicesChanged.connect(self.refresh)
        window.deviceSelected.connect(lambda _i: self.refresh())

    def refresh(self) -> None:
        dev = self.device()
        visible = dev is not None
        for card in (self.preview_card, self.grid_card, self.params_card):
            card.setVisible(visible)
        if not dev:
            return
        if dev["id"] != self._dev_id:
            self._dev_id = dev["id"]
            self.keyboard.set_device(dev, self.window.keyboard_layout())
        self.keyboard.set_state(dev["effective"])
        ids = [e["id"] for e in dev["effects"]]
        if ids != self._effect_ids:
            self._effect_ids = ids
            self._build_tiles(dev)
        current = dev["state"]["effect"]
        for b in self.group.buttons():
            b.setChecked(b.effect["id"] == current)
        self._build_params(dev)

    def _build_tiles(self, dev: dict) -> None:
        for b in self.group.buttons():
            self.group.removeButton(b)
        clear_layout(self.grid)
        cols = 3
        for i, effect in enumerate(dev["effects"]):
            tile = EffectTile(effect)
            tile.clicked.connect(lambda _=False, e=effect: self._choose(e))
            self.group.addButton(tile)
            self.grid.addWidget(tile, i // cols, i % cols)
        for c in range(cols):
            self.grid.setColumnStretch(c, 1)

    def _effect(self, dev: dict, effect_id: str) -> dict | None:
        return next((e for e in dev["effects"] if e["id"] == effect_id), None)

    def _choose(self, effect: dict) -> None:
        dev = self.device()
        if dev:
            self.bridge.set_state(dev["id"], modes.effect_changes(dev, effect))

    def _build_params(self, dev: dict) -> None:
        effect = self._effect(dev, dev["state"]["effect"])
        key = (dev["id"], dev["state"]["effect"])
        if getattr(self, "_params_key", None) == key and self._form is not None:
            return
        self._params_key = key
        clear_layout(self.params_box)
        self._form = None
        self._color_buttons = []
        if not effect or (not effect["params"] and not effect.get("colors")):
            self.params_box.addWidget(label("This effect has no settings.", "cardHint"))
            return
        if effect["params"]:
            self._form = ParamForm(effect["params"], dev["state"].get("params", {}))
            self._form.changed.connect(self._apply_timer.start)
            self.params_box.addWidget(self._form)
        if effect.get("colors"):
            row = QtWidgets.QHBoxLayout()
            row.addWidget(label("Colors", "cardHint"))
            colors = dev["state"].get("effect_colors") or []
            for i in range(effect["colors"]):
                btn = ColorButton(colors[i] if i < len(colors) else "#ffffff")
                btn.colorChanged.connect(lambda _c: self._apply_timer.start())
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
