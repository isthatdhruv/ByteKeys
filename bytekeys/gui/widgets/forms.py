"""Form helpers: parameter forms, color buttons, info grids and menus."""

from __future__ import annotations

from ...color import SWATCHES
from .. import icons, theme
from ..qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .kit import ColorPanel, NeonSlider, Segmented, Switch, text_label

AA = QtGui.QPainter.RenderHint.Antialiasing


def clear_layout(layout: QtWidgets.QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget, child = item.widget(), item.layout()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        elif child is not None:
            clear_layout(child)


def add_action(menu: QtWidgets.QMenu, text: str, fn=None, *, checkable: bool = False,
               checked: bool = False, enabled: bool = True, icon: str | None = None) -> QtGui.QAction:
    """menu.addAction that behaves the same on PyQt6 and PySide6."""
    act = menu.addAction(text)
    if icon:
        act.setIcon(icons.icon(icon, theme.colors["dim"], 16))
    act.setCheckable(checkable)
    if checkable:
        act.setChecked(checked)
    act.setEnabled(enabled)
    if fn is not None:
        act.triggered.connect(lambda _checked=False: fn())
    return act


def hline() -> QtWidgets.QFrame:
    line = QtWidgets.QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {theme.colors['border']};")
    return line


class IconButton(QtWidgets.QAbstractButton):
    """Round, borderless icon button (menus, edit, delete...)."""

    def __init__(self, icon: str, tooltip: str = "", size: int = 34, parent=None):
        super().__init__(parent)
        self.icon_name = icon
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(size, size)
        self._menu: QtWidgets.QMenu | None = None
        self.clicked.connect(self._show_menu)

    def setMenu(self, menu: QtWidgets.QMenu) -> None:  # noqa: N802
        self._menu = menu

    def _show_menu(self) -> None:
        if self._menu is not None:
            self._menu.exec(self.mapToGlobal(QtCore.QPoint(0, self.height() + 4)))

    def enterEvent(self, e) -> None:  # noqa: N802
        self.update()

    def leaveEvent(self, e) -> None:  # noqa: N802
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(AA)
        r = QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if self.underMouse() or self.isDown():
            p.setPen(QtGui.QPen(theme.c("border_hi"), 1))
            p.setBrush(theme.c("surface2"))
            p.drawEllipse(r)
        s = r.width() * 0.52
        color = theme.c("text" if self.underMouse() else "dim")
        if not self.isEnabled():
            color = theme.c("faint")
        icons.paint(p, self.icon_name, QtCore.QRectF(r.center().x() - s / 2, r.center().y() - s / 2, s, s),
                    color, 1.9)


class ColorPopup(QtWidgets.QFrame):
    """A floating color picker: wheel, hex field, swatches."""

    colorChanged = Signal(str)
    colorPicked = Signal(str)

    def __init__(self, color: str, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("popup")
        self.setStyleSheet(f"#popup {{ background: {theme.colors['card']}; border: 1px solid "
                           f"{theme.colors['border_hi']}; border-radius: 14px; }}")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        self.panel = ColorPanel(SWATCHES)
        self.panel.set_color(color)
        self.panel.colorChanged.connect(self.colorChanged.emit)
        self.panel.colorPicked.connect(self.colorPicked.emit)
        lay.addWidget(self.panel)
        self.setFixedWidth(500)

    def popup_at(self, widget: QtWidgets.QWidget) -> None:
        pos = widget.mapToGlobal(QtCore.QPoint(0, widget.height() + 6))
        screen = widget.screen().availableGeometry() if widget.screen() else None
        self.adjustSize()
        if screen is not None:
            pos.setX(max(screen.left() + 8, min(pos.x(), screen.right() - self.width() - 8)))
            if pos.y() + self.height() > screen.bottom():
                pos.setY(widget.mapToGlobal(QtCore.QPoint(0, 0)).y() - self.height() - 6)
        self.move(pos)
        self.show()


class ColorButton(QtWidgets.QAbstractButton):
    """A color dot that opens a ColorPopup."""

    colorChanged = Signal(str)

    def __init__(self, color: str = "#ffffff", size: int = 30, parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(size + 8, size + 8)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(color)
        self.clicked.connect(self._pick)

    def color(self) -> str:
        return self._color

    def set_color(self, color: str) -> None:
        self._color = color
        self.setToolTip(color)
        self.update()

    def _pick(self) -> None:
        popup = ColorPopup(self._color, self)
        popup.colorPicked.connect(self._picked)
        popup.popup_at(self)

    def _picked(self, color: str) -> None:
        if color != self._color:
            self.set_color(color)
            self.colorChanged.emit(color)

    def enterEvent(self, e) -> None:  # noqa: N802
        self.update()

    def leaveEvent(self, e) -> None:  # noqa: N802
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(AA)
        r = QtCore.QRectF(self.rect()).adjusted(4, 4, -4, -4)
        if self.underMouse():
            p.setPen(QtGui.QPen(theme.c("dim"), 1.5))
            p.drawEllipse(r.adjusted(-3, -3, 3, 3))
        p.setPen(QtGui.QPen(theme.c("border_hi"), 1))
        p.setBrush(QtGui.QColor(self._color))
        p.drawEllipse(r)


class ParamForm(QtWidgets.QWidget):
    """Input controls for parameter specs coming from the engine."""

    changed = Signal()

    def __init__(self, params: list[dict], values: dict | None = None, *, effects=None,
                 profiles=None, parent=None):
        super().__init__(parent)
        self.params = params
        self.controls: dict[str, tuple[str, QtWidgets.QWidget]] = {}
        form = QtWidgets.QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        values = values or {}
        for p in params:
            value = values.get(p["id"], p.get("default"))
            kind = p.get("kind", "range")
            if kind == "range":
                w = QtWidgets.QWidget()
                row = QtWidgets.QHBoxLayout(w)
                row.setContentsMargins(0, 0, 0, 0)
                slider = NeonSlider(int(p.get("min", 0)), int(p.get("max", 100)))
                try:
                    slider.set_value(int(value if value is not None else p.get("min", 0)))
                except (TypeError, ValueError):
                    slider.set_value(int(p.get("min", 0)))
                val = text_label(str(slider.value()), "dim")
                val.setMinimumWidth(34)
                val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                slider.valueChanged.connect(lambda v, lbl=val: lbl.setText(str(v)))
                slider.released.connect(lambda _v: self.changed.emit())
                row.addWidget(slider, 1)
                row.addWidget(val)
                self.controls[p["id"]] = ("range", slider)
            elif kind in ("choice", "effect", "profile"):
                choices = p.get("choices") or []
                if kind == "effect":
                    choices = [[e["id"], e["name"] + (" (hardware)" if e.get("hardware") else "")]
                               for e in (effects or [])]
                elif kind == "profile":
                    choices = [[name, name] for name in (profiles or [])]
                if kind == "choice" and 1 < len(choices) <= 4 and all(len(str(t)) <= 12 for _v, t in choices):
                    w = Segmented([(str(v), str(t)) for v, t in choices], stretch=False)
                    w.set_value(str(value))
                    if w.value() is None and choices:
                        w.set_value(str(choices[0][0]))
                    w.changed.connect(lambda _v: self.changed.emit())
                    self.controls[p["id"]] = ("segmented", w)
                    w._types = {str(v): v for v, _t in choices}
                else:
                    w = QtWidgets.QComboBox()
                    for v, text in choices:
                        w.addItem(str(text), v)
                    idx = w.findData(value)
                    w.setCurrentIndex(idx if idx >= 0 else 0)
                    w.currentIndexChanged.connect(lambda _i: self.changed.emit())
                    self.controls[p["id"]] = ("choice", w)
            elif kind == "bool":
                w = Switch()
                w.setChecked(bool(value))
                w.toggled.connect(lambda _c: self.changed.emit())
                self.controls[p["id"]] = ("bool", w)
            elif kind == "color":
                w = ColorButton(value or "#ffffff")
                w.colorChanged.connect(lambda _c: self.changed.emit())
                self.controls[p["id"]] = ("color", w)
            elif kind == "time":
                w = QtWidgets.QTimeEdit()
                w.setDisplayFormat("HH:mm")
                t = QtCore.QTime.fromString(str(value or "00:00"), "HH:mm")
                w.setTime(t if t.isValid() else QtCore.QTime(0, 0))
                w.timeChanged.connect(lambda _t: self.changed.emit())
                self.controls[p["id"]] = ("time", w)
            else:
                w = QtWidgets.QLineEdit(str(value or ""))
                w.editingFinished.connect(self.changed.emit)
                self.controls[p["id"]] = ("text", w)
            form.addRow(text_label(p.get("name", p["id"]), "dim"), w)

    def values(self) -> dict:
        out = {}
        for pid, (kind, w) in self.controls.items():
            if kind == "range":
                out[pid] = w.value()
            elif kind == "segmented":
                out[pid] = w._types.get(w.value(), w.value())
            elif kind == "choice":
                out[pid] = w.currentData()
            elif kind == "bool":
                out[pid] = w.isChecked()
            elif kind == "color":
                out[pid] = w.color()
            elif kind == "time":
                out[pid] = w.time().toString("HH:mm")
            else:
                out[pid] = w.text()
        return out


class InfoGrid(QtWidgets.QWidget):
    """Aligned "name: value" pairs; empty values are skipped."""

    def __init__(self, label_width: int = 110, parent=None):
        super().__init__(parent)
        self.grid = QtWidgets.QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(8)
        self.grid.setColumnMinimumWidth(0, label_width)
        self.grid.setColumnStretch(1, 1)
        self._row = 0

    def add(self, name: str, value: str) -> None:
        if not value or not str(value).strip():
            return
        key = text_label(name, "dim")
        key.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        val = text_label(str(value), wrap=True)
        val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.grid.addWidget(key, self._row, 0)
        self.grid.addWidget(val, self._row, 1)
        self._row += 1

    def clear(self) -> None:
        clear_layout(self.grid)
        self._row = 0


def color_dot(color: str, size: int = 12) -> str:
    """Rich-text colored dot, for labels."""
    return f"<span style='color:{color}; font-size:{size}pt'>●</span>"
