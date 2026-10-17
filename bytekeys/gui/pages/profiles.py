"""Profiles: saved looks you can switch between with one click."""

from __future__ import annotations

import time

from .. import icons, theme
from ..qt import QtCore, QtGui, QtWidgets, Qt
from ..widgets.forms import IconButton, add_action, clear_layout
from ..widgets.kit import Card, text_label
from .base import Page


class LookPreview(QtWidgets.QWidget):
    """A row of glowing color dots for a saved look."""

    def __init__(self, look: dict | None, parent=None):
        super().__init__(parent)
        self.look = look or {}
        self.setFixedHeight(34)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        look = self.look
        on = look.get("on", False)
        colors = (look.get("colors") or ["#fff4e1"])[:8] if on else []
        effect = (look.get("effect_name") or "").lower()
        if on and any(w in effect for w in ("rainbow", "cycle", "spectrum", "wave")):
            colors = [QtGui.QColor.fromHsvF(i / 7, 0.85, 1.0).name() for i in range(7)]
        x = 4.0
        cy = self.height() / 2
        if not colors:
            p.setPen(QtGui.QPen(theme.c("faint"), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QtCore.QPointF(x + 11, cy), 8.5, 8.5)
            return
        level = max(0.35, look.get("brightness", 100) / 100)
        for color in colors:
            qc = QtGui.QColor(color)
            glow = QtGui.QRadialGradient(QtCore.QPointF(x + 11, cy), 17)
            g = QtGui.QColor(qc)
            g.setAlphaF(0.55 * level)
            glow.setColorAt(0, g)
            g2 = QtGui.QColor(qc)
            g2.setAlpha(0)
            glow.setColorAt(1, g2)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(QtCore.QPointF(x + 11, cy), 17, 17)
            p.setBrush(qc)
            p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 60), 1))
            p.drawEllipse(QtCore.QPointF(x + 11, cy), 8.5, 8.5)
            x += 26


class ProfileCard(Card):
    def __init__(self, page: "ProfilesPage", prof: dict):
        super().__init__(padding=(20, 18, 16, 16))
        self.setMinimumHeight(170)
        name = prof["name"]
        top = QtWidgets.QHBoxLayout()
        title = text_label(name, "value")
        top.addWidget(title, 1)
        more = IconButton("dots", "More")
        menu = QtWidgets.QMenu(more)
        add_action(menu, "Update with current lighting", lambda: page.overwrite(name), icon="save")
        add_action(menu, "Rename…", lambda: page.rename(name), icon="edit")
        menu.addSeparator()
        add_action(menu, "Delete", lambda: page.delete(name), icon="trash")
        more.setMenu(menu)
        top.addWidget(more, 0, Qt.AlignmentFlag.AlignTop)
        self.body.addLayout(top)
        looks = prof.get("looks", [])
        current = page.device()
        look = next((lk for lk in looks if current and lk["device"] == current["id"]), looks[0] if looks else None)
        self.body.addWidget(LookPreview(look))
        if look:
            effect = look.get("effect_name") or "Static"
            desc = f"{effect} · {look.get('brightness', 100)}%" if look.get("on") else "Lights off"
            self.body.addWidget(text_label(desc, "rowTitle"))
        n = len(prof.get("devices", []))
        detail = f"{n} keyboard{'s' if n != 1 else ''}"
        when = prof.get("updated")
        if when:
            detail += " · saved " + time.strftime("%d %b %Y", time.localtime(when))
        self.body.addWidget(text_label(detail, "faint"))
        self.body.addStretch(1)
        apply = QtWidgets.QPushButton("Apply")
        apply.setObjectName("primary")
        apply.setCursor(Qt.CursorShape.PointingHandCursor)
        apply.clicked.connect(lambda: page.bridge.apply_profile(name))
        row = QtWidgets.QHBoxLayout()
        row.addWidget(apply)
        row.addStretch(1)
        self.body.addLayout(row)


class ProfilesPage(Page):
    def __init__(self, window):
        super().__init__(window, "Profiles", "Save the lighting of all keyboards and switch with one click. "
                                             "Automations can switch profiles too.")
        save = QtWidgets.QPushButton("  Save current lighting")
        save.setIcon(icons.icon("plus", theme.colors["accent_text"], 16))
        save.setObjectName("primary")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(self.save_current)
        self.header_right.addWidget(save, 0, Qt.AlignmentFlag.AlignTop)
        self.grid = QtWidgets.QGridLayout()
        self.grid.setSpacing(16)
        self.add(self.grid)
        self.finish()
        self.listen(self.bridge.profilesChanged, self.refresh)
        self.listen(window.deviceSelected, self._on_selected)

    def _on_selected(self, _dev_id: str) -> None:
        self.refresh()

    def refresh(self) -> None:
        clear_layout(self.grid)
        cols = 3
        if not self.bridge.profiles:
            empty = Card("No profiles yet", "layers")
            empty.body.addWidget(text_label("Set up the lighting you like, then save it as a profile with "
                                            "“Save current lighting”.", "dim", wrap=True))
            self.grid.addWidget(empty, 0, 0, 1, cols)
        for i, prof in enumerate(self.bridge.profiles):
            self.grid.addWidget(ProfileCard(self, prof), i // cols, i % cols)
        for c in range(cols):
            self.grid.setColumnStretch(c, 1)

    def save_current(self) -> None:
        name, ok = QtWidgets.QInputDialog.getText(self, "Save profile", "Profile name:")
        name = name.strip()
        if not ok or not name:
            return
        if name in {p["name"] for p in self.bridge.profiles}:
            answer = QtWidgets.QMessageBox.question(self, "Replace profile",
                                                    f"A profile named “{name}” exists. Replace it?")
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        self.bridge.save_profile(name)
        self.window.toast(f"Saved profile “{name}”")

    def overwrite(self, name: str) -> None:
        self.bridge.save_profile(name)
        self.window.toast(f"Updated profile “{name}”")

    def rename(self, name: str) -> None:
        new, ok = QtWidgets.QInputDialog.getText(self, "Rename profile", "New name:", text=name)
        new = new.strip()
        if ok and new and new != name:
            self.bridge.rename_profile(name, new)

    def delete(self, name: str) -> None:
        answer = QtWidgets.QMessageBox.question(self, "Delete profile", f"Delete the profile “{name}”?")
        if answer == QtWidgets.QMessageBox.StandardButton.Yes:
            self.bridge.delete_profile(name)
