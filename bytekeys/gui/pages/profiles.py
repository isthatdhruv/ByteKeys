"""Profiles page: saved looks you can switch between."""

from __future__ import annotations

import time

from ..qt import QtWidgets, Qt
from ..widgets.common import Card, add_action, clear_layout, color_dot, label
from .base import Page


class ProfilesPage(Page):
    def __init__(self, window):
        super().__init__(window, "Profiles", "Save the current lighting of all keyboards as a profile and "
                                             "switch with one click (rules can switch profiles too).")
        bar = QtWidgets.QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        save = QtWidgets.QPushButton("Save current lighting…")
        save.setObjectName("primary")
        save.clicked.connect(self.save_current)
        bar.addWidget(save)
        bar.addStretch(1)
        holder = QtWidgets.QWidget()
        holder.setLayout(bar)
        self.add(holder)
        self.grid = QtWidgets.QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(12)
        grid_holder = QtWidgets.QWidget()
        grid_holder.setLayout(self.grid)
        self.add(grid_holder)
        self.finish()
        self.bridge.profilesChanged.connect(self.refresh)
        window.deviceSelected.connect(lambda _id: self.refresh())

    def refresh(self) -> None:
        clear_layout(self.grid)
        cols = 3
        if not self.bridge.profiles:
            empty = Card("No profiles yet")
            empty.body.addWidget(label("Set up the lighting you like, then save it as a profile.", "cardHint"))
            self.grid.addWidget(empty, 0, 0, 1, cols)
        for i, prof in enumerate(self.bridge.profiles):
            card = Card(prof["name"])
            looks = prof.get("looks", [])
            current = self.device()
            look = next((lk for lk in looks if current and lk["device"] == current["id"]),
                        looks[0] if looks else None)
            if look:
                preview = label(self._look_text(look), wrap=True)
                preview.setTextFormat(Qt.TextFormat.RichText)
                card.body.addWidget(preview)
            when = prof.get("updated")
            n = len(prof.get("devices", []))
            detail = f"{n} keyboard{'s' if n != 1 else ''}"
            if when:
                detail += " · saved " + time.strftime("%d %b %Y", time.localtime(when))
            card.body.addWidget(label(detail, "cardHint"))
            row = QtWidgets.QHBoxLayout()
            apply = QtWidgets.QPushButton("Apply")
            apply.setObjectName("primary")
            apply.clicked.connect(lambda _=False, name=prof["name"]: self._apply(name))
            row.addWidget(apply)
            row.addStretch(1)
            more = QtWidgets.QPushButton("⋯")
            more.setObjectName("flat")
            menu = QtWidgets.QMenu(more)
            add_action(menu, "Update with current lighting", lambda name=prof["name"]: self._overwrite(name))
            add_action(menu, "Rename…", lambda name=prof["name"]: self._rename(name))
            menu.addSeparator()
            add_action(menu, "Delete", lambda name=prof["name"]: self._delete(name))
            more.setMenu(menu)
            row.addWidget(more)
            card.body.addLayout(row)
            self.grid.addWidget(card, i // cols, i % cols)
        for c in range(cols):
            self.grid.setColumnStretch(c, 1)

    @staticmethod
    def _look_text(look: dict) -> str:
        if not look.get("on"):
            return "<span style='color:gray'>●</span> Lights off"
        colors = look.get("colors") or []
        dots = "".join(color_dot(c, 12) for c in colors[:6])
        effect = look.get("effect_name") or "Static"
        return f"{dots} {effect} · {look.get('brightness', 100)}%"

    def _apply(self, name: str) -> None:
        self.bridge.apply_profile(name)
        self.window.toast(f"Profile “{name}” applied")

    def save_current(self) -> None:
        name, ok = QtWidgets.QInputDialog.getText(self, "Save profile", "Profile name:")
        name = name.strip()
        if not ok or not name:
            return
        existing = {p["name"] for p in self.bridge.profiles}
        if name in existing:
            answer = QtWidgets.QMessageBox.question(self, "Replace profile",
                                                    f"A profile named “{name}” exists. Replace it?")
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        self.bridge.save_profile(name)
        self.window.toast(f"Saved profile “{name}”")

    def _overwrite(self, name: str) -> None:
        self.bridge.save_profile(name)
        self.window.toast(f"Updated profile “{name}”")

    def _rename(self, name: str) -> None:
        new, ok = QtWidgets.QInputDialog.getText(self, "Rename profile", "New name:", text=name)
        new = new.strip()
        if ok and new and new != name:
            self.bridge.rename_profile(name, new)

    def _delete(self, name: str) -> None:
        answer = QtWidgets.QMessageBox.question(self, "Delete profile", f"Delete the profile “{name}”?")
        if answer == QtWidgets.QMessageBox.StandardButton.Yes:
            self.bridge.delete_profile(name)
