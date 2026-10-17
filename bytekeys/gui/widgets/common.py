"""Small reusable widgets: cards, switches, color swatches, banners, parameter forms."""

from __future__ import annotations

from ...color import normalize
from .. import theme
from ..qt import QtCore, QtGui, QtWidgets, Qt, Signal


def repolish(widget: QtWidgets.QWidget) -> None:
    """Re-evaluate style sheet rules after a dynamic property changed."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def label(text: str = "", name: str | None = None, wrap: bool = False) -> QtWidgets.QLabel:
    lbl = QtWidgets.QLabel(text)
    if name:
        lbl.setObjectName(name)
    lbl.setWordWrap(wrap)
    return lbl


def clear_layout(layout: QtWidgets.QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


class Card(QtWidgets.QFrame):
    """A rounded panel with an optional title row."""

    def __init__(self, title: str | None = None, hint: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 18)
        outer.setSpacing(12)
        self.header = QtWidgets.QHBoxLayout()
        self.header.setSpacing(10)
        self.title_label = label(title or "", "cardTitle")
        self.header.addWidget(self.title_label)
        self.header.addStretch(1)
        if title:
            outer.addLayout(self.header)
        self.hint_label = label(hint or "", "cardHint", wrap=True)
        if hint:
            outer.addWidget(self.hint_label)
        self.body = QtWidgets.QVBoxLayout()
        self.body.setSpacing(10)
        outer.addLayout(self.body)

    def add_header_widget(self, widget: QtWidgets.QWidget) -> None:
        self.header.addWidget(widget)


class Pill(QtWidgets.QLabel):
    def __init__(self, text: str, tone: str | None = None, parent=None):
        super().__init__(text, parent)
        self.setObjectName("pill")
        if tone:
            self.setProperty("tone", tone)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum, QtWidgets.QSizePolicy.Policy.Fixed)

    def set_tone(self, tone: str | None) -> None:
        self.setProperty("tone", tone or "")
        repolish(self)


class Switch(QtWidgets.QAbstractButton):
    """An animated on/off toggle."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(46, 26)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self._pos = 0.0
        self._anim = QtCore.QVariantAnimation(self)
        self._anim.setDuration(140)
        self._anim.valueChanged.connect(self._on_anim)
        self.toggled.connect(self._animate)

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(46, 26)

    def _on_anim(self, value) -> None:
        self._pos = float(value)
        self.update()

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def setChecked(self, checked: bool) -> None:  # noqa: N802 - Qt naming
        super().setChecked(checked)
        self._anim.stop()
        self._pos = 1.0 if checked else 0.0
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        c = theme.colors
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        r = QtCore.QRectF(1, 1, self.width() - 2, self.height() - 2)
        track_off = QtGui.QColor(c["surface3"])
        track_on = QtGui.QColor(c["accent"])
        t = self._pos
        track = QtGui.QColor(
            int(track_off.red() + (track_on.red() - track_off.red()) * t),
            int(track_off.green() + (track_on.green() - track_off.green()) * t),
            int(track_off.blue() + (track_on.blue() - track_off.blue()) * t),
        )
        if not self.isEnabled():
            track.setAlpha(110)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.left() + 3 + (r.width() - d - 6) * t
        p.setBrush(QtGui.QColor("#ffffff"))
        p.drawEllipse(QtCore.QRectF(x, r.top() + 3, d, d))


class Swatch(QtWidgets.QAbstractButton):
    """A round color button; shows a ring when selected."""

    def __init__(self, color: str, size: int = 30, parent=None):
        super().__init__(parent)
        self.color = color
        self._size = size
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(color)
        self.setFixedSize(size + 8, size + 8)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        r = QtCore.QRectF(4, 4, self._size, self._size)
        if self.isChecked():
            p.setPen(QtGui.QPen(QtGui.QColor(theme.colors["text"]), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(r.adjusted(-3, -3, 3, 3))
        elif self.underMouse():
            p.setPen(QtGui.QPen(QtGui.QColor(theme.colors["faint"]), 1.5))
            p.drawEllipse(r.adjusted(-2.5, -2.5, 2.5, 2.5))
        p.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 60), 1))
        p.setBrush(QtGui.QColor(self.color))
        p.drawEllipse(r)

    def enterEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().leaveEvent(event)


def pick_color(parent, initial: str, title: str = "Choose a color") -> str | None:
    dlg = QtWidgets.QColorDialog(QtGui.QColor(initial), parent)
    dlg.setWindowTitle(title)
    dlg.setOption(QtWidgets.QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
    if dlg.exec():
        return dlg.selectedColor().name()
    return None


class ColorButton(QtWidgets.QPushButton):
    colorChanged = Signal(str)

    def __init__(self, color: str = "#ffffff", parent=None):
        super().__init__(parent)
        self._color = normalize(color)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._pick)
        self._refresh()

    def color(self) -> str:
        return self._color

    def set_color(self, color: str) -> None:
        self._color = normalize(color)
        self._refresh()

    def _refresh(self) -> None:
        self.setText(f"  {self._color}")
        pix = QtGui.QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.setBrush(QtGui.QColor(self._color))
        p.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 80)))
        p.drawEllipse(1, 1, 14, 14)
        p.end()
        self.setIcon(QtGui.QIcon(pix))

    def _pick(self) -> None:
        color = pick_color(self, self._color)
        if color:
            self.set_color(color)
            self.colorChanged.emit(self._color)


class Banner(QtWidgets.QFrame):
    action = Signal()

    def __init__(self, level: str = "info", text: str = "", action_text: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("banner")
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 10, 10)
        lay.setSpacing(12)
        self.icon = label("", "bannerIcon")
        self.icon.setFixedSize(22, 22)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text = label(text, wrap=True)
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.button = QtWidgets.QPushButton(action_text or "")
        self.button.clicked.connect(self.action.emit)
        self.button.setVisible(bool(action_text))
        lay.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        lay.addWidget(self.text, 1)
        lay.addWidget(self.button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.set(level, text, action_text)

    def set(self, level: str, text: str, action_text: str | None = None) -> None:
        self.setProperty("level", level)
        self.icon.setProperty("level", level)
        self.icon.setText({"warn": "!", "error": "✕", "good": "✓"}.get(level, "i"))
        repolish(self.icon)
        self.text.setText(text)
        self.button.setVisible(bool(action_text))
        if action_text:
            self.button.setText(action_text)
        repolish(self)


class Segmented(QtWidgets.QWidget):
    """A row of mutually exclusive buttons."""

    changed = Signal(str)

    def __init__(self, choices: list[tuple[str, str]], parent=None, stretch: bool = True):
        super().__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.group = QtWidgets.QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, QtWidgets.QPushButton] = {}
        for value, text in choices:
            b = QtWidgets.QPushButton(text)
            b.setObjectName("segment")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, v=value: self.changed.emit(v))
            self.group.addButton(b)
            self.buttons[value] = b
            lay.addWidget(b)
        if stretch:
            lay.addStretch(1)

    def value(self) -> str | None:
        for v, b in self.buttons.items():
            if b.isChecked():
                return v
        return None

    def set_value(self, value: str) -> None:
        b = self.buttons.get(str(value))
        if b:
            b.setChecked(True)


class ParamForm(QtWidgets.QWidget):
    """Builds input controls for parameter specs coming from the engine."""

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
        values = values or {}
        for p in params:
            value = values.get(p["id"], p.get("default"))
            kind = p.get("kind", "range")
            if kind == "range":
                w = QtWidgets.QWidget()
                row = QtWidgets.QHBoxLayout(w)
                row.setContentsMargins(0, 0, 0, 0)
                slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
                slider.setRange(int(p.get("min", 0)), int(p.get("max", 100)))
                slider.setValue(int(value if value is not None else p.get("min", 0)))
                val = label(str(slider.value()), "faint")
                val.setMinimumWidth(36)
                slider.valueChanged.connect(lambda v, lbl=val: lbl.setText(str(v)))
                slider.sliderReleased.connect(self.changed.emit)
                slider.valueChanged.connect(lambda _v, s=slider: None if s.isSliderDown() else self.changed.emit())
                row.addWidget(slider, 1)
                row.addWidget(val)
                self.controls[p["id"]] = ("range", slider)
            elif kind in ("choice", "effect", "profile"):
                w = QtWidgets.QComboBox()
                choices = p.get("choices") or []
                if kind == "effect":
                    choices = [[e["id"], e["name"] + (" (hardware)" if e.get("hardware") else "")]
                               for e in (effects or [])]
                elif kind == "profile":
                    choices = [[name, name] for name in (profiles or [])]
                for v, text in choices:
                    w.addItem(text, v)
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
            form.addRow(label(p.get("name", p["id"]), "cardHint"), w)

    def values(self) -> dict:
        out = {}
        for pid, (kind, w) in self.controls.items():
            if kind == "range":
                out[pid] = w.value()
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


def hline() -> QtWidgets.QFrame:
    line = QtWidgets.QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {theme.colors['border']};")
    return line


def status_dot(color: str) -> QtWidgets.QLabel:
    dot = QtWidgets.QLabel()
    dot.setObjectName("statusDot")
    dot.setStyleSheet(f"background: {color};")
    return dot


def add_action(menu: QtWidgets.QMenu, text: str, fn=None, *, checkable: bool = False,
               checked: bool = False, enabled: bool = True) -> QtGui.QAction:
    """menu.addAction that behaves the same on PyQt6 and PySide6."""
    act = menu.addAction(text)
    act.setCheckable(checkable)
    if checkable:
        act.setChecked(checked)
    act.setEnabled(enabled)
    if fn is not None:
        act.triggered.connect(lambda _checked=False: fn())
    return act


class SettingRow(QtWidgets.QWidget):
    """A settings line: title (and optional hint) on the left, the control on the right."""

    def __init__(self, title: str, hint: str | None = None, control: QtWidgets.QWidget | None = None,
                 parent=None):
        super().__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 8)
        lay.setSpacing(18)
        text = QtWidgets.QVBoxLayout()
        text.setSpacing(2)
        self.title = label(title, "rowTitle", wrap=True)
        text.addWidget(self.title)
        self.hint = label(hint or "", "cardHint", wrap=True)
        self.hint.setVisible(bool(hint))
        text.addWidget(self.hint)
        lay.addLayout(text, 1)
        self.control = control
        if control is not None:
            lay.addWidget(control, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)


class RowList(QtWidgets.QWidget):
    """SettingRows separated by hairlines (like a libadwaita boxed list)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.box = QtWidgets.QVBoxLayout(self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(0)
        self.rows: list[QtWidgets.QWidget] = []

    def add(self, row: QtWidgets.QWidget) -> QtWidgets.QWidget:
        if self.rows:
            self.box.addWidget(hline())
        self.box.addWidget(row)
        self.rows.append(row)
        return row

    def clear(self) -> None:
        clear_layout(self.box)
        self.rows = []


class InfoGrid(QtWidgets.QWidget):
    """Aligned "name: value" pairs; empty values are skipped."""

    def __init__(self, label_width: int = 150, parent=None):
        super().__init__(parent)
        self.grid = QtWidgets.QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(6)
        self.grid.setColumnMinimumWidth(0, label_width)
        self.grid.setColumnStretch(1, 1)
        self._row = 0

    def add(self, name: str, value: str) -> None:
        if not value or not str(value).strip():
            return
        key = label(name, "cardHint")
        key.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        val = label(str(value), wrap=True)
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
