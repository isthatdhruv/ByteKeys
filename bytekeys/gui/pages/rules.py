"""Rules page: automation ("when this happens, do that")."""

from __future__ import annotations

import copy
import uuid

from ..qt import QtCore, QtGui, QtWidgets, Qt
from ..widgets.common import (
    Banner, Card, ParamForm, Pill, Switch, add_action, clear_layout, color_dot, label,
)
from .base import Page

TEMPLATES = [
    ("Turn off when idle", {"type": "idle", "seconds": 120}, {"type": "off"}),
    ("Dim on battery", {"type": "power", "source": "battery"}, {"type": "brightness", "value": 40}),
    ("Night mode", {"type": "time", "start": "22:00", "end": "07:00"}, {"type": "profile", "profile": "Night"}),
    ("Low battery warning", {"type": "battery", "level": 15},
     {"type": "alert", "color": "#ff0000", "style": "pulse", "speed": 60}),
    ("Caps Lock indicator", {"type": "capslock"}, {"type": "color", "color": "#ff2a2a"}),
    ("Overheat warning", {"type": "temperature", "celsius": 90},
     {"type": "alert", "color": "#ff6a00", "style": "pulse", "speed": 70}),
    ("Color by CPU temperature", {"type": "always"},
     {"type": "temperature_color", "low": 45, "high": 90, "cool": "#00a0ff", "hot": "#ff2000"}),
    ("Color by battery level", {"type": "always"}, {"type": "battery_color"}),
    ("Lights on in the dark", {"type": "dark", "lux": 20}, {"type": "brightness", "value": 80}),
]


def _duration(seconds: int) -> str:
    if seconds % 3600 == 0:
        h = seconds // 3600
        return f"{h} hour{'s' if h > 1 else ''}"
    if seconds % 60 == 0:
        m = seconds // 60
        return f"{m} minute{'s' if m > 1 else ''}"
    return f"{seconds} seconds"


def trigger_text(t: dict) -> str:
    kind = t["type"]
    return {
        "always": lambda: "Always",
        "power": lambda: "On battery" if t.get("source") == "battery" else "When plugged in",
        "battery": lambda: f"Battery below {t.get('level')}%",
        "time": lambda: f"Between {t.get('start')} and {t.get('end')}",
        "idle": lambda: f"After {_duration(int(t.get('seconds', 60)))} without input",
        "capslock": lambda: "While Caps Lock is on",
        "temperature": lambda: f"CPU above {t.get('celsius')} °C",
        "cpu": lambda: f"CPU load above {t.get('percent')}%",
        "dark": lambda: f"Room darker than {t.get('lux')} lux",
    }.get(kind, lambda: kind)()


def _swatch(color, rich: bool) -> str:
    return color_dot(color, 11) if rich else str(color)


def action_text(a: dict, effects: dict[str, str], rich: bool = False) -> str:
    kind = a["type"]
    return {
        "off": lambda: "turn the lights off",
        "brightness": lambda: f"set brightness to {a.get('value')}%",
        "color": lambda: f"set color {_swatch(a.get('color'), rich)}",
        "effect": lambda: f"play {effects.get(a.get('effect'), a.get('effect'))}",
        "profile": lambda: f"switch to profile “{a.get('profile')}”",
        "alert": lambda: f"{a.get('style', 'pulse')} in {_swatch(a.get('color'), rich)}",
        "temperature_color": lambda: "color follows CPU temperature",
        "battery_color": lambda: "color follows battery level",
        "cpu_color": lambda: "color follows CPU load",
    }.get(kind, lambda: kind)()


class RuleDialog(QtWidgets.QDialog):
    def __init__(self, page: "RulesPage", rule: dict | None):
        super().__init__(page)
        self.page = page
        self.bridge = page.bridge
        self.setWindowTitle("Edit rule" if rule else "New rule")
        self.setMinimumWidth(520)
        cat = self.bridge.catalog
        self.triggers = cat.get("triggers", {})
        self.actions = cat.get("actions", {})
        self.rule = copy.deepcopy(rule) if rule else {
            "id": uuid.uuid4().hex[:10], "name": "", "enabled": True,
            "trigger": {"type": "power", "source": "battery"},
            "action": {"type": "brightness", "value": 40}, "target": "all",
        }
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(14)
        form = QtWidgets.QFormLayout()
        form.setVerticalSpacing(12)
        self.name = QtWidgets.QLineEdit(self.rule["name"])
        self.name.setPlaceholderText("e.g. Dim on battery")
        form.addRow("Name", self.name)
        self.trigger_combo = QtWidgets.QComboBox()
        for key, spec in self.triggers.items():
            self.trigger_combo.addItem(spec["name"], key)
        form.addRow("When", self.trigger_combo)
        lay.addLayout(form)
        self.trigger_box = QtWidgets.QVBoxLayout()
        lay.addLayout(self.trigger_box)
        self.warning = label("", "cardHint", wrap=True)
        lay.addWidget(self.warning)
        form2 = QtWidgets.QFormLayout()
        self.action_combo = QtWidgets.QComboBox()
        for key, spec in self.actions.items():
            self.action_combo.addItem(spec["name"], key)
        form2.addRow("Then", self.action_combo)
        self.target = QtWidgets.QComboBox()
        self.target.addItem("All keyboards", "all")
        for dev_id in self.bridge.order:
            self.target.addItem(self.bridge.devices[dev_id]["name"], dev_id)
        form2.addRow("Apply to", self.target)
        lay.addLayout(form2)
        self.action_box = QtWidgets.QVBoxLayout()
        lay.addLayout(self.action_box)
        lay.addStretch(1)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        self.trigger_form: ParamForm | None = None
        self.action_form: ParamForm | None = None
        self.trigger_combo.setCurrentIndex(max(0, self.trigger_combo.findData(self.rule["trigger"]["type"])))
        self.action_combo.setCurrentIndex(max(0, self.action_combo.findData(self.rule["action"]["type"])))
        self.target.setCurrentIndex(max(0, self.target.findData(self.rule.get("target", "all"))))
        self.trigger_combo.currentIndexChanged.connect(lambda _i: self._build_trigger())
        self.action_combo.currentIndexChanged.connect(lambda _i: self._build_action())
        self._build_trigger(initial=True)
        self._build_action(initial=True)

    def _effects(self) -> list[dict]:
        dev = self.page.device()
        if not dev:
            return []
        return [e for e in dev["effects"] if e["id"] != "static"]

    def _build_trigger(self, initial: bool = False) -> None:
        clear_layout(self.trigger_box)
        key = self.trigger_combo.currentData()
        spec = self.triggers.get(key, {"params": []})
        values = self.rule["trigger"] if initial else {}
        self.trigger_form = ParamForm(spec["params"], values)
        self.trigger_box.addWidget(self.trigger_form)
        sensor = spec.get("sensor")
        sensors = self.bridge.catalog.get("sensors", {})
        msg = ""
        if sensor and not sensors.get(sensor, True):
            msg = {
                "idle": "Idle detection needs the ByteKeys service (or a GNOME session).",
                "ambient": "No ambient light sensor was found on this laptop.",
                "battery": "No battery was found.",
                "capslock": "No Caps Lock indicator was found.",
                "temperature": "No CPU temperature sensor was found.",
            }.get(sensor, "The sensor this rule needs was not found.")
        self.warning.setText(f"⚠ {msg}" if msg else "")
        self.warning.setVisible(bool(msg))

    def _build_action(self, initial: bool = False) -> None:
        clear_layout(self.action_box)
        key = self.action_combo.currentData()
        spec = self.actions.get(key, {"params": []})
        values = self.rule["action"] if initial else {}
        self.action_form = ParamForm(spec["params"], values, effects=self._effects(),
                                     profiles=[p["name"] for p in self.bridge.profiles])
        self.action_box.addWidget(self.action_form)
        if spec.get("rgb") and not any(d["color_mode"] != "none" for d in self.bridge.devices.values()):
            self.action_box.addWidget(label("This action needs an RGB keyboard.", "cardHint"))

    def result_rule(self) -> dict:
        trigger = {"type": self.trigger_combo.currentData(), **(self.trigger_form.values() if self.trigger_form else {})}
        action = {"type": self.action_combo.currentData(), **(self.action_form.values() if self.action_form else {})}
        name = self.name.text().strip() or f"{trigger_text(trigger)} → {action_text(action, {})}"[:60]
        return {**self.rule, "name": name, "trigger": trigger, "action": action,
                "target": self.target.currentData()}


class RuleCard(QtWidgets.QFrame):
    def __init__(self, page: "RulesPage", index: int, rule: dict, active: bool, effects: dict[str, str]):
        super().__init__()
        self.setObjectName("card")
        self.page = page
        self.index = index
        self.rule = rule
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 12, 12)
        lay.setSpacing(14)
        self.switch = Switch()
        self.switch.setChecked(rule["enabled"])
        self.switch.toggled.connect(lambda on: page.set_enabled(index, on))
        lay.addWidget(self.switch)
        text = QtWidgets.QVBoxLayout()
        text.setSpacing(2)
        name = label(rule["name"], "cardTitle")
        text.addWidget(name)
        summary = label(f"{trigger_text(rule['trigger'])} → {action_text(rule['action'], effects, rich=True)}",
                        "cardHint", wrap=True)
        summary.setTextFormat(Qt.TextFormat.RichText)
        text.addWidget(summary)
        lay.addLayout(text, 1)
        if active:
            lay.addWidget(Pill("Active now", "good"))
        edit = QtWidgets.QPushButton("Edit")
        edit.clicked.connect(lambda: page.edit(index))
        lay.addWidget(edit)
        more = QtWidgets.QPushButton("⋯")
        more.setObjectName("flat")
        menu = QtWidgets.QMenu(more)
        add_action(menu, "Move up", lambda: page.move(index, -1))
        add_action(menu, "Move down", lambda: page.move(index, 1))
        add_action(menu, "Duplicate", lambda: page.duplicate(index))
        menu.addSeparator()
        add_action(menu, "Delete", lambda: page.delete(index))
        more.setMenu(menu)
        lay.addWidget(more)


class RulesPage(Page):
    def __init__(self, window):
        super().__init__(window, "Rules", "Make the lighting react on its own: dim on battery, switch off "
                                          "when idle, warn about low battery or a hot CPU. Rules apply top "
                                          "to bottom; later rules win.")
        bar = QtWidgets.QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        add = QtWidgets.QPushButton("＋ New rule")
        add.setObjectName("primary")
        add.clicked.connect(lambda: self.edit(None))
        bar.addWidget(add)
        quick = QtWidgets.QPushButton("Quick add  ▾")
        menu = QtWidgets.QMenu(quick)
        for name, trigger, action in TEMPLATES:
            add_action(menu, name, lambda n=name, t=trigger, a=action: self.add_template(n, t, a))
        quick.setMenu(menu)
        bar.addWidget(quick)
        bar.addStretch(1)
        holder = QtWidgets.QWidget()
        holder.setLayout(bar)
        self.add(holder)
        self.notice = Banner("info", "")
        self.notice.action.connect(self.window.install_service)
        self.add(self.notice)
        self.list_box = QtWidgets.QVBoxLayout()
        self.list_box.setContentsMargins(0, 0, 0, 0)
        self.list_box.setSpacing(10)
        holder2 = QtWidgets.QWidget()
        holder2.setLayout(self.list_box)
        self.add(holder2)
        self.finish()
        self.bridge.rulesChanged.connect(self.refresh)
        self.bridge.automationChanged.connect(self.refresh)
        self.bridge.connectionChanged.connect(self.refresh)

    def refresh(self) -> None:
        clear_layout(self.list_box)
        dev = self.device()
        effects = {e["id"]: e["name"] for e in (dev or {}).get("effects", [])}
        if self.bridge.mode == "portable":
            self.notice.set("info", "Rules only run while ByteKeys is open. Install the service to keep "
                                    "them running in the background and to detect idle time reliably.",
                            "Install service")
            self.notice.show()
        else:
            self.notice.hide()
        if not self.bridge.rules:
            empty = Card("No rules yet")
            empty.body.addWidget(label("Use “New rule” or “Quick add” to create one.", "cardHint"))
            self.list_box.addWidget(empty)
        for i, rule in enumerate(self.bridge.rules):
            self.list_box.addWidget(RuleCard(self, i, rule, rule["id"] in self.bridge.active_rules, effects))

    def _save(self, rules: list[dict]) -> None:
        self.bridge.set_rules(rules)

    def set_enabled(self, index: int, on: bool) -> None:
        rules = copy.deepcopy(self.bridge.rules)
        rules[index]["enabled"] = on
        self._save(rules)

    def edit(self, index: int | None) -> None:
        rule = self.bridge.rules[index] if index is not None else None
        dlg = RuleDialog(self, rule)
        if dlg.exec():
            rules = copy.deepcopy(self.bridge.rules)
            new = dlg.result_rule()
            if index is None:
                rules.append(new)
            else:
                rules[index] = new
            self._save(rules)

    def add_template(self, name: str, trigger: dict, action: dict) -> None:
        rules = copy.deepcopy(self.bridge.rules)
        rules.append({"id": uuid.uuid4().hex[:10], "name": name, "enabled": True,
                      "trigger": dict(trigger), "action": dict(action), "target": "all"})
        self._save(rules)

    def move(self, index: int, delta: int) -> None:
        rules = copy.deepcopy(self.bridge.rules)
        j = index + delta
        if 0 <= j < len(rules):
            rules[index], rules[j] = rules[j], rules[index]
            self._save(rules)

    def duplicate(self, index: int) -> None:
        rules = copy.deepcopy(self.bridge.rules)
        dup = copy.deepcopy(rules[index])
        dup["id"] = uuid.uuid4().hex[:10]
        dup["name"] = (dup["name"] + " (copy)")[:60]
        rules.insert(index + 1, dup)
        self._save(rules)

    def delete(self, index: int) -> None:
        rule = self.bridge.rules[index]
        answer = QtWidgets.QMessageBox.question(self, "Delete rule", f"Delete the rule “{rule['name']}”?")
        if answer == QtWidgets.QMessageBox.StandardButton.Yes:
            rules = copy.deepcopy(self.bridge.rules)
            del rules[index]
            self._save(rules)
