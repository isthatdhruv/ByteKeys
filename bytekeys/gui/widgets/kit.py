"""Custom-painted controls for the control-center look."""

from __future__ import annotations

import math
import time

from ...color import parse
from ...engine.effects import Context, Renderer
from .. import icons, theme
from ..qt import QtCore, QtGui, QtWidgets, Qt, Signal

AA = QtGui.QPainter.RenderHint.Antialiasing


def _rounded(rect: QtCore.QRectF, radius: float) -> QtGui.QPainterPath:
    path = QtGui.QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def caption(text: str) -> QtWidgets.QLabel:
    lbl = QtWidgets.QLabel(text.upper())
    lbl.setObjectName("caption")
    return lbl


def text_label(text: str = "", name: str | None = None, wrap: bool = False) -> QtWidgets.QLabel:
    lbl = QtWidgets.QLabel(text)
    if name:
        lbl.setObjectName(name)
    lbl.setWordWrap(wrap)
    return lbl


# --------------------------------------------------------------------- cards
class Card(QtWidgets.QFrame):
    """Glass panel with an optional icon + caption header."""

    def __init__(self, title: str | None = None, icon: str | None = None, parent=None,
                 padding: tuple[int, int, int, int] = (20, 18, 20, 20)):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.active = False
        self.icon_name = icon
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(*padding)
        outer.setSpacing(14)
        self.header = QtWidgets.QHBoxLayout()
        self.header.setSpacing(10)
        if title:
            if icon:
                self.icon_label = QtWidgets.QLabel()
                self.icon_label.setPixmap(icons.pixmap(icon, theme.colors["accent"], 18))
                self.header.addWidget(self.icon_label)
            self.title_label = caption(title)
            self.header.addWidget(self.title_label)
            self.header.addStretch(1)
            outer.addLayout(self.header)
        self.body = QtWidgets.QVBoxLayout()
        self.body.setSpacing(12)
        outer.addLayout(self.body)

    def add_header_widget(self, widget: QtWidgets.QWidget) -> None:
        self.header.addWidget(widget)

    def set_active(self, active: bool) -> None:
        self.active = active
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(AA)
        r = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        grad = QtGui.QLinearGradient(r.topLeft(), r.bottomLeft())
        grad.setColorAt(0, theme.c("card"))
        grad.setColorAt(1, theme.c("card2"))
        p.fillPath(_rounded(r, 18), grad)
        border = QtGui.QLinearGradient(r.topLeft(), r.bottomRight())
        if self.active:
            border.setColorAt(0, theme.c("accent", 0.9))
            border.setColorAt(1, theme.c("accent2", 0.9))
        else:
            border.setColorAt(0, theme.c("border_hi", 0.9))
            border.setColorAt(0.5, theme.c("border"))
            border.setColorAt(1, theme.c("border", 0.7))
        p.setPen(QtGui.QPen(QtGui.QBrush(border), 1.2))
        p.drawPath(_rounded(r, 18))
        if theme.dark_mode:   # a faint highlight along the top edge
            p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 14), 1))
            p.drawLine(QtCore.QPointF(r.left() + 18, r.top() + 1.5), QtCore.QPointF(r.right() - 18, r.top() + 1.5))


# ------------------------------------------------------------------- switch
class Switch(QtWidgets.QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(50, 28)
        self._pos = 0.0
        self._anim = QtCore.QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        self.toggled.connect(self._animate)

    def _on_anim(self, value) -> None:
        self._pos = float(value)
        self.update()

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        super().setChecked(checked)
        self._anim.stop()
        self._pos = 1.0 if checked else 0.0
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(AA)
        r = QtCore.QRectF(2, 3, self.width() - 4, self.height() - 6)
        t = self._pos
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.c("surface3"))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        if t > 0:
            on = QtGui.QLinearGradient(r.topLeft(), r.topRight())
            on.setColorAt(0, theme.c("accent", t))
            on.setColorAt(1, theme.c("accent2", t))
            p.setBrush(on)
            p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.left() + 3 + (r.width() - d - 6) * t
        knob = QtCore.QRectF(x, r.top() + 3, d, d)
        if t > 0.5 and self.isEnabled():
            glow = QtGui.QRadialGradient(knob.center(), d)
            glow.setColorAt(0, theme.c("accent3", 0.35 * t))
            glow.setColorAt(1, theme.c("accent3", 0))
            p.setBrush(glow)
            p.drawEllipse(knob.center(), d, d)
        if not self.isEnabled():
            p.setBrush(theme.c("faint"))
        elif t > 0.5:
            p.setBrush(theme.c("accent_text"))
        else:
            p.setBrush(theme.c("text", 0.9))
        p.drawEllipse(knob)


# ------------------------------------------------------------------- slider
class NeonSlider(QtWidgets.QWidget):
    """Gradient track slider. Discrete when *labels* are given (one per step)."""

    valueChanged = Signal(int)      # while dragging
    released = Signal(int)          # when the user lets go (or uses keys / wheel)

    def __init__(self, minimum: int = 0, maximum: int = 100, value: int = 0, parent=None):
        super().__init__(parent)
        self.minimum, self.maximum = minimum, maximum
        self._value = value
        self.labels: list[str] | None = None
        self.unit = ""
        self._drag = False
        self._hover = False
        self.setMinimumHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

    def set_range(self, minimum: int, maximum: int) -> None:
        self.minimum, self.maximum = minimum, max(minimum + 1, maximum)
        self._value = max(self.minimum, min(self.maximum, self._value))
        self.update()

    def set_labels(self, labels: list[str] | None) -> None:
        self.labels = labels
        self.setMinimumHeight(58 if labels else 40)
        self.update()

    def value(self) -> int:
        return self._value

    def set_value(self, value: int) -> None:
        if self._drag:
            return
        self._value = max(self.minimum, min(self.maximum, int(value)))
        self.update()

    def is_dragging(self) -> bool:
        return self._drag

    def _track(self) -> QtCore.QRectF:
        return QtCore.QRectF(14, 14, self.width() - 28, 8)

    def _x_for(self, value: int) -> float:
        t = self._track()
        span = self.maximum - self.minimum
        return t.left() + t.width() * (value - self.minimum) / span

    def _value_at(self, x: float) -> int:
        t = self._track()
        frac = max(0.0, min(1.0, (x - t.left()) / max(1.0, t.width())))
        return int(round(self.minimum + frac * (self.maximum - self.minimum)))

    def _set_from_user(self, value: int, final: bool) -> None:
        value = max(self.minimum, min(self.maximum, value))
        changed = value != self._value
        self._value = value
        self.update()
        if changed:
            self.valueChanged.emit(value)
        if final:
            self.released.emit(value)

    def mousePressEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = True
            self._set_from_user(self._value_at(e.position().x()), False)

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        if self._drag:
            self._set_from_user(self._value_at(e.position().x()), False)

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        if self._drag:
            self._drag = False
            self._set_from_user(self._value_at(e.position().x()), True)

    def wheelEvent(self, e) -> None:  # noqa: N802
        step = 1 if self.labels or self.maximum - self.minimum <= 20 else 5
        delta = step if e.angleDelta().y() > 0 else -step
        self._set_from_user(self._value + delta, True)

    def keyPressEvent(self, e) -> None:  # noqa: N802
        step = 1 if self.labels or self.maximum - self.minimum <= 20 else 5
        if e.key() in (Qt.Key.Key_Right, Qt.Key.Key_Up):
            self._set_from_user(self._value + step, True)
        elif e.key() in (Qt.Key.Key_Left, Qt.Key.Key_Down):
            self._set_from_user(self._value - step, True)
        else:
            super().keyPressEvent(e)

    def enterEvent(self, e) -> None:  # noqa: N802
        self._hover = True
        self.update()

    def leaveEvent(self, e) -> None:  # noqa: N802
        self._hover = False
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(AA)
        t = self._track()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.c("surface3"))
        p.drawRoundedRect(t, 4, 4)
        x = self._x_for(self._value)
        if x > t.left():
            fill = QtCore.QRectF(t.left(), t.top(), x - t.left(), t.height())
            grad = QtGui.QLinearGradient(t.topLeft(), t.topRight())
            grad.setColorAt(0, theme.c("accent2") if self.isEnabled() else theme.c("faint"))
            grad.setColorAt(1, theme.c("accent") if self.isEnabled() else theme.c("faint"))
            p.setBrush(grad)
            p.drawRoundedRect(fill, 4, 4)
        if self.labels:
            steps = len(self.labels) - 1
            p.setFont(theme.font(8.5, 600))
            for i, name in enumerate(self.labels):
                vx = self._x_for(self.minimum + i * (self.maximum - self.minimum) / max(1, steps))
                active = self.minimum + i <= self._value
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(theme.c("text", 0.9) if active else theme.c("faint"))
                p.drawEllipse(QtCore.QPointF(vx, t.center().y()), 2.2, 2.2)
                p.setPen(theme.c("text") if self.minimum + i == self._value else theme.c("dim"))
                p.drawText(QtCore.QRectF(vx - 50, t.bottom() + 12, 100, 18), Qt.AlignmentFlag.AlignCenter, name)
        center = QtCore.QPointF(x, t.center().y())
        if self._hover or self._drag or self.hasFocus():
            glow = QtGui.QRadialGradient(center, 18)
            glow.setColorAt(0, theme.c("glow", 0.45))
            glow.setColorAt(1, theme.c("glow", 0))
            p.setBrush(glow)
            p.drawEllipse(center, 18, 18)
        p.setBrush(QtGui.QColor("#ffffff"))
        p.setPen(QtGui.QPen(theme.c("glow") if theme.dark_mode else theme.c("accent"), 3))
        p.drawEllipse(center, 9, 9)


# --------------------------------------------------------------- color wheel
class ColorWheel(QtWidgets.QWidget):
    """Hue ring with a saturation/value square inside."""

    colorChanged = Signal(str)     # live while dragging
    colorPicked = Signal(str)      # on release

    RING = 16

    def __init__(self, parent=None):
        super().__init__(parent)
        self.h, self.s, self.v = 0.6, 0.7, 1.0
        self._mode: str | None = None
        self._ring: QtGui.QImage | None = None
        self.setMinimumSize(190, 190)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(220, 220)

    def color(self) -> str:
        return QtGui.QColor.fromHsvF(self.h % 1.0, self.s, self.v).name()

    def set_color(self, color: str) -> None:
        if self._mode:
            return
        qc = QtGui.QColor(color)
        h, s, v, _ = qc.getHsvF()
        if h >= 0:
            self.h = h
        self.s, self.v = s, v
        self.update()

    def _geometry(self):
        side = min(self.width(), self.height()) - 4
        outer = QtCore.QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        inner_r = side / 2 - self.RING - 8
        sq = inner_r * math.sqrt(2) * 0.92
        square = QtCore.QRectF(outer.center().x() - sq / 2, outer.center().y() - sq / 2, sq, sq)
        return outer, square

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(AA)
        outer, square = self._geometry()
        center = outer.center()
        ring = QtGui.QConicalGradient(center, 0)
        for i in range(13):
            ring.setColorAt(i / 12, QtGui.QColor.fromHsvF((i / 12) % 1.0, 1, 1))
        path = QtGui.QPainterPath()
        path.addEllipse(outer)
        path.addEllipse(outer.adjusted(self.RING, self.RING, -self.RING, -self.RING))
        p.fillPath(path, ring)
        # saturation / value square
        base = QtGui.QColor.fromHsvF(self.h % 1.0, 1, 1)
        horiz = QtGui.QLinearGradient(square.topLeft(), square.topRight())
        horiz.setColorAt(0, QtGui.QColor("#ffffff"))
        horiz.setColorAt(1, base)
        clip = _rounded(square, 10)
        p.fillPath(clip, horiz)
        vert = QtGui.QLinearGradient(square.topLeft(), square.bottomLeft())
        vert.setColorAt(0, QtGui.QColor(0, 0, 0, 0))
        vert.setColorAt(1, QtGui.QColor(0, 0, 0, 255))
        p.fillPath(clip, vert)
        # markers
        angle = self.h * 2 * math.pi
        radius = outer.width() / 2 - self.RING / 2
        hp = QtCore.QPointF(center.x() + radius * math.cos(angle), center.y() - radius * math.sin(angle))
        sp = QtCore.QPointF(square.left() + self.s * square.width(), square.top() + (1 - self.v) * square.height())
        for point, radius_px, fill in ((hp, self.RING / 2 + 2, base), (sp, 8, QtGui.QColor(self.color()))):
            p.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 110), 5))   # dark halo: visible on light colors too
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(point, radius_px, radius_px)
            p.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), 3))
            p.setBrush(fill)
            p.drawEllipse(point, radius_px, radius_px)

    def _update_from(self, pos: QtCore.QPointF, final: bool) -> None:
        outer, square = self._geometry()
        center = outer.center()
        if self._mode == "ring":
            angle = math.atan2(center.y() - pos.y(), pos.x() - center.x())
            self.h = (angle / (2 * math.pi)) % 1.0
        elif self._mode == "square":
            self.s = max(0.0, min(1.0, (pos.x() - square.left()) / square.width()))
            self.v = max(0.0, min(1.0, 1 - (pos.y() - square.top()) / square.height()))
        self.update()
        self.colorChanged.emit(self.color())
        if final:
            self.colorPicked.emit(self.color())

    def mousePressEvent(self, e) -> None:  # noqa: N802
        outer, square = self._geometry()
        pos = e.position()
        dist = math.hypot(pos.x() - outer.center().x(), pos.y() - outer.center().y())
        if square.adjusted(-6, -6, 6, 6).contains(pos):
            self._mode = "square"
        elif outer.width() / 2 - self.RING - 6 <= dist <= outer.width() / 2 + 4:
            self._mode = "ring"
        else:
            return
        self._update_from(pos, False)

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        if self._mode:
            self._update_from(e.position(), False)

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        if self._mode:
            self._update_from(e.position(), True)
            self._mode = None


class Swatch(QtWidgets.QAbstractButton):
    def __init__(self, color: str, size: int = 26, parent=None):
        super().__init__(parent)
        self.color = color
        self._size = size
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(color)
        self.setFixedSize(size + 8, size + 8)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(AA)
        r = QtCore.QRectF(4, 4, self._size, self._size)
        if self.isChecked():
            p.setPen(QtGui.QPen(theme.c("text"), 2))
            p.drawEllipse(r.adjusted(-3, -3, 3, 3))
        elif self.underMouse():
            p.setPen(QtGui.QPen(theme.c("dim"), 1.5))
            p.drawEllipse(r.adjusted(-2.5, -2.5, 2.5, 2.5))
        p.setPen(QtGui.QPen(theme.c("border_hi"), 1))
        p.setBrush(QtGui.QColor(self.color))
        p.drawEllipse(r)

    def enterEvent(self, e) -> None:  # noqa: N802
        self.update()

    def leaveEvent(self, e) -> None:  # noqa: N802
        self.update()


class ColorPanel(QtWidgets.QWidget):
    """Color wheel, hex field and quick swatches. Emits live and final picks."""

    colorChanged = Signal(str)
    colorPicked = Signal(str)

    def __init__(self, swatches: list[str], parent=None, vertical: bool = False):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self) if vertical else QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14 if vertical else 18)
        self.wheel = ColorWheel()
        self.wheel.colorChanged.connect(self._live)
        self.wheel.colorPicked.connect(self._picked)
        if vertical:
            self.wheel.setFixedHeight(220)
        lay.addWidget(self.wheel, 0)
        side = QtWidgets.QVBoxLayout()
        side.setSpacing(10)
        top = QtWidgets.QHBoxLayout()
        self.preview = QtWidgets.QLabel()
        self.preview.setFixedSize(42, 42)
        top.addWidget(self.preview)
        self.hex = QtWidgets.QLineEdit()
        self.hex.setFixedWidth(110)
        self.hex.setPlaceholderText("#rrggbb")
        self.hex.returnPressed.connect(self._hex_entered)
        top.addWidget(self.hex)
        top.addStretch(1)
        side.addLayout(top)
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(2)
        self.group = QtWidgets.QButtonGroup(self)
        self.swatches: list[Swatch] = []
        for i, color in enumerate(swatches):
            sw = Swatch(color)
            sw.clicked.connect(lambda _=False, c=color: self._swatch(c))
            self.group.addButton(sw)
            self.swatches.append(sw)
            grid.addWidget(sw, i // 6, i % 6)
        grid.setColumnStretch(6, 1)
        side.addLayout(grid)
        side.addStretch(1)
        lay.addLayout(side, 1)
        self._color = "#ffffff"

    def set_color(self, color: str) -> None:
        self._color = color
        self.wheel.set_color(color)
        if not self.hex.hasFocus():
            self.hex.setText(color)
        self._paint_preview(color)
        for sw in self.swatches:
            sw.setChecked(sw.color.lower() == color.lower())

    def _paint_preview(self, color: str) -> None:
        pm = QtGui.QPixmap(84, 84)
        pm.fill(Qt.GlobalColor.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(AA)
        glow = QtGui.QRadialGradient(QtCore.QPointF(42, 42), 42)
        qc = QtGui.QColor(color)
        glow.setColorAt(0.55, qc)
        qc2 = QtGui.QColor(qc)
        qc2.setAlpha(0)
        glow.setColorAt(1, qc2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QtCore.QRectF(0, 0, 84, 84))
        p.setBrush(qc)
        p.setPen(QtGui.QPen(theme.c("border_hi"), 1.5))
        p.drawEllipse(QtCore.QRectF(16, 16, 52, 52))
        p.end()
        pm.setDevicePixelRatio(2)
        self.preview.setPixmap(pm)

    def _live(self, color: str) -> None:
        self.hex.setText(color)
        self._paint_preview(color)
        self.colorChanged.emit(color)

    def _picked(self, color: str) -> None:
        self._color = color
        self.colorPicked.emit(color)

    def _swatch(self, color: str) -> None:
        self.set_color(color)
        self.colorPicked.emit(color)

    def _hex_entered(self) -> None:
        text = self.hex.text().strip()
        if not text.startswith("#"):
            text = "#" + text
        qc = QtGui.QColor(text)
        if qc.isValid():
            self.set_color(qc.name())
            self.colorPicked.emit(qc.name())


# -------------------------------------------------------------------- gauge
class RingGauge(QtWidgets.QWidget):
    """Arc gauge with a big number, e.g. temperatures and fan speeds."""

    def __init__(self, label: str, unit: str, maximum: float, icon: str | None = None,
                 warn: float | None = None, parent=None):
        super().__init__(parent)
        self.label, self.unit, self.maximum, self.icon, self.warn = label, unit, maximum, icon, warn
        self._value: float | None = None
        self._shown = 0.0
        self.caption = ""
        self._anim = QtCore.QVariantAnimation(self)
        self._anim.setDuration(600)
        self._anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        self.setMinimumSize(150, 150)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)

    def _on_anim(self, v) -> None:
        self._shown = float(v)
        self.update()

    def set_value(self, value: float | None, caption: str = "") -> None:
        self.caption = caption
        if value is None:
            self._value = None
            self.update()
            return
        self._anim.stop()
        self._anim.setStartValue(self._shown)
        self._anim.setEndValue(float(value))
        self._value = float(value)
        self._anim.start()

    def heightForWidth(self, w: int) -> int:  # noqa: N802
        return w

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(AA)
        side = min(self.width(), self.height()) - 16
        rect = QtCore.QRectF((self.width() - side) / 2, (self.height() - side) / 2 + 4, side, side)
        start, span = 225, -270
        pen = QtGui.QPen(theme.c("surface3"), 10)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, start * 16, span * 16)
        frac = 0.0 if self._value is None else max(0.0, min(1.0, self._shown / self.maximum))
        if frac > 0:
            grad = QtGui.QConicalGradient(rect.center(), 225)
            hot = self.warn is not None and self._shown >= self.warn
            grad.setColorAt(0.0, theme.c("accent"))
            grad.setColorAt(0.4, theme.c("accent2"))
            grad.setColorAt(0.75, theme.c("bad") if hot else theme.c("accent3"))
            grad.setColorAt(1.0, theme.c("accent"))
            pen = QtGui.QPen(QtGui.QBrush(grad), 10)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawArc(rect, start * 16, int(span * frac * 16))
            angle = math.radians(start + span * frac)
            r = side / 2
            tip = QtCore.QPointF(rect.center().x() + r * math.cos(angle), rect.center().y() - r * math.sin(angle))
            glow = QtGui.QRadialGradient(tip, 16)
            glow.setColorAt(0, theme.c("glow", 0.6))
            glow.setColorAt(1, theme.c("glow", 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(tip, 16, 16)
        cx, cy = rect.center().x(), rect.center().y()
        if self.icon:
            icons.paint(p, self.icon, QtCore.QRectF(cx - 10, cy - side * 0.33, 20, 20), theme.c("dim"), 2)
        p.setPen(theme.c("text"))
        p.setFont(theme.font(max(14.0, side / 7.5), 800))
        text = "–" if self._value is None else f"{self._shown:.0f}"
        p.drawText(QtCore.QRectF(rect.left(), cy - side * 0.16, side, side * 0.3), Qt.AlignmentFlag.AlignCenter, text)
        p.setPen(theme.c("dim"))
        p.setFont(theme.font(9, 600))
        p.drawText(QtCore.QRectF(rect.left(), cy + side * 0.12, side, 18), Qt.AlignmentFlag.AlignCenter,
                   self.unit if self._value is not None else (self.caption or "n/a"))
        p.setFont(theme.font(8.5, 700, 1.1))
        p.drawText(QtCore.QRectF(rect.left(), rect.bottom() - side * 0.12, side, 18),
                   Qt.AlignmentFlag.AlignCenter, self.label.upper())


# --------------------------------------------------------------------- tiles
class ModeTile(QtWidgets.QAbstractButton):
    """Large selectable tile with icon, title and subtitle (performance modes...)."""

    def __init__(self, icon: str, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.icon_name, self.title, self.subtitle = icon, title, subtitle
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(86)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(170, 86)

    def enterEvent(self, e) -> None:  # noqa: N802
        self.update()

    def leaveEvent(self, e) -> None:  # noqa: N802
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(AA)
        r = QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1)
        on = self.isChecked()
        if on:
            bg = QtGui.QLinearGradient(r.topLeft(), r.bottomRight())
            bg.setColorAt(0, theme.c("glow", 0.16))
            bg.setColorAt(1, theme.c("accent2", 0.10))
        else:
            bg = QtGui.QLinearGradient(r.topLeft(), r.bottomLeft())
            bg.setColorAt(0, theme.c("surface2" if self.underMouse() else "surface"))
            bg.setColorAt(1, theme.c("surface"))
        p.fillPath(_rounded(r, 14), bg)
        border = QtGui.QLinearGradient(r.topLeft(), r.bottomRight())
        border.setColorAt(0, theme.c("accent" if on else "border_hi"))
        border.setColorAt(1, theme.c("glow" if on else "border"))
        p.setPen(QtGui.QPen(QtGui.QBrush(border), 1.6 if on else 1))
        p.drawPath(_rounded(r, 14))
        icon_rect = QtCore.QRectF(r.left() + 16, r.center().y() - 15, 30, 30)
        if on:
            glow = QtGui.QRadialGradient(icon_rect.center(), 26)
            glow.setColorAt(0, theme.c("glow", 0.45))
            glow.setColorAt(1, theme.c("glow", 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(icon_rect.center(), 26, 26)
        icons.paint(p, self.icon_name, icon_rect, theme.c("text" if on else "dim"), 1.8)
        p.setPen(theme.c("text"))
        p.setFont(theme.font(11.5, 750))
        text_x = icon_rect.right() + 14
        p.drawText(QtCore.QRectF(text_x, r.top() + 18, r.width() - text_x - 8, 22),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.title)
        if self.subtitle:
            p.setPen(theme.c("dim"))
            p.setFont(theme.font(9, 500))
            p.drawText(QtCore.QRectF(text_x, r.top() + 42, r.width() - text_x - 8, 34),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                       self.subtitle)


class _PreviewClock(QtCore.QObject):
    """One shared timer animating every visible effect preview."""

    tick = Signal()
    _instance = None

    def __init__(self):
        super().__init__()
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(60)
        self.timer.timeout.connect(self.tick.emit)
        self.timer.start()

    @classmethod
    def get(cls) -> "_PreviewClock":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


class EffectTile(QtWidgets.QAbstractButton):
    """Selectable effect with a small animated preview strip."""

    LEDS = 14

    def __init__(self, effect: dict, colors: list[str], parent=None):
        super().__init__(parent)
        self.effect = effect
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(80)
        self.setMinimumWidth(140)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setToolTip(effect.get("description") or effect["name"])
        self._t0 = time.monotonic()
        from .keyboard import _preview_effect
        base = [parse(c) for c in colors] or [(90, 125, 255)]
        positions = [i / (self.LEDS - 1) for i in range(self.LEDS)]
        params = {p["id"]: p.get("default") for p in effect.get("params", [])}
        if not isinstance(params.get("speed"), (int, float)):
            params["speed"] = 60       # firmware speed choices: preview at a lively pace
        self.renderer = Renderer(_preview_effect(effect["id"]), params,
                                 [base[i % len(base)] for i in range(self.LEDS)], [], positions)
        _PreviewClock.get().tick.connect(self._tick)

    def _tick(self) -> None:
        if self.isVisible() and self.renderer.animated:
            self.update()

    def enterEvent(self, e) -> None:  # noqa: N802
        self.update()

    def leaveEvent(self, e) -> None:  # noqa: N802
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(AA)
        r = QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1)
        on = self.isChecked()
        bg = QtGui.QLinearGradient(r.topLeft(), r.bottomRight())
        if on:
            bg.setColorAt(0, theme.c("glow", 0.14))
            bg.setColorAt(1, theme.c("accent2", 0.08))
        else:
            bg.setColorAt(0, theme.c("surface2" if self.underMouse() else "surface"))
            bg.setColorAt(1, theme.c("surface"))
        p.fillPath(_rounded(r, 14), bg)
        p.setPen(QtGui.QPen(theme.c("accent" if on else "border"), 1.6 if on else 1))
        p.drawPath(_rounded(r, 14))
        # name + badge
        p.setPen(theme.c("text"))
        name_font = theme.font(10, 700)
        p.setFont(name_font)
        room = r.width() - (62 if self.effect.get("hardware") else 28)
        name = QtGui.QFontMetrics(name_font).elidedText(self.effect["name"], Qt.TextElideMode.ElideRight, int(room))
        p.drawText(QtCore.QRectF(r.left() + 14, r.top() + 10, room, 22),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)
        if self.effect.get("hardware"):
            badge = QtCore.QRectF(r.right() - 42, r.top() + 12, 30, 18)
            p.setPen(Qt.PenStyle.NoPen)
            grad = QtGui.QLinearGradient(badge.topLeft(), badge.topRight())
            grad.setColorAt(0, theme.c("accent"))
            grad.setColorAt(1, theme.c("accent2"))
            p.setBrush(grad)
            p.drawRoundedRect(badge, 9, 9)
            p.setPen(theme.c("accent_text"))
            p.setFont(theme.font(7.5, 800))
            p.drawText(badge, Qt.AlignmentFlag.AlignCenter, "HW")
        # preview strip
        factor, cols = self.renderer.frame(time.monotonic() - self._t0, Context(last_key=None))
        factor = 0.3 + 0.7 * max(0.0, min(1.0, factor))   # keep dark phases readable
        strip = QtCore.QRectF(r.left() + 14, r.bottom() - 30, r.width() - 28, 17)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.c("chassis"))   # a dark keyboard-like backing so every color reads
        p.drawRoundedRect(strip.adjusted(-5, -4, 5, 4), 7, 7)
        gap = 3.0
        w = (strip.width() - gap * (self.LEDS - 1)) / self.LEDS
        for i in range(self.LEDS):
            col = cols[i] if i < len(cols) else cols[-1]
            qc = QtGui.QColor(int(col[0] * factor), int(col[1] * factor), int(col[2] * factor))
            cell = QtCore.QRectF(strip.left() + i * (w + gap), strip.top(), w, strip.height())
            p.setPen(Qt.PenStyle.NoPen)
            glow = QtGui.QColor(qc)
            glow.setAlpha(90)
            p.setBrush(glow)
            p.drawRoundedRect(cell.adjusted(-1, -1, 1, 1), 4, 4)
            p.setBrush(qc)
            p.drawRoundedRect(cell.adjusted(1, 1, -1, -1), 3, 3)


class Chip(QtWidgets.QLabel):
    """Small status pill with a colored dot."""

    def __init__(self, text: str = "", tone: str = "dim", parent=None):
        super().__init__(parent)
        self.tone = tone
        self._text = text
        self._resize()

    def set(self, text: str, tone: str) -> None:
        self._text, self.tone = text, tone
        self._resize()
        self.update()

    def _resize(self) -> None:
        fm = QtGui.QFontMetrics(theme.font(9, 650))
        self.setFixedSize(fm.horizontalAdvance(self._text) + 38, 28)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(AA)
        r = QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1)
        tone = theme.c(self.tone if self.tone in theme.colors else "dim")
        bg = QtGui.QColor(tone)
        bg.setAlphaF(0.12)
        p.setPen(QtGui.QPen(QtGui.QColor(tone.red(), tone.green(), tone.blue(), 90), 1))
        p.setBrush(bg)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(tone)
        p.drawEllipse(QtCore.QPointF(r.left() + 14, r.center().y()), 4, 4)
        p.setPen(theme.c("text"))
        p.setFont(theme.font(9, 650))
        p.drawText(r.adjusted(24, 0, -8, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._text)


class Segmented(QtWidgets.QWidget):
    """Mutually exclusive pill buttons."""

    changed = Signal(str)

    def __init__(self, choices: list[tuple[str, str]], parent=None, stretch: bool = True):
        super().__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.group = QtWidgets.QButtonGroup(self)
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
        return next((v for v, b in self.buttons.items() if b.isChecked()), None)

    def set_value(self, value) -> None:
        b = self.buttons.get(str(value))
        if b:
            b.setChecked(True)


class SettingRow(QtWidgets.QWidget):
    """Title and hint on the left, the control on the right (or below them when *stacked*)."""

    def __init__(self, title: str, hint: str | None = None, control: QtWidgets.QWidget | None = None,
                 icon: str | None = None, parent=None, stacked: bool = False):
        super().__init__(parent)
        if stacked and control is not None:
            col = QtWidgets.QVBoxLayout(self)
            col.setContentsMargins(0, 10, 0, 10)
            col.setSpacing(8)
            inner = SettingRow(title, hint, None, icon)
            inner.layout().setContentsMargins(0, 0, 0, 0)
            self.title, self.hint, self.control = inner.title, inner.hint, control
            col.addWidget(inner)
            col.addWidget(control, 0, Qt.AlignmentFlag.AlignLeft)
            return
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 10, 0, 10)
        lay.setSpacing(16)
        if icon:
            ic = QtWidgets.QLabel()
            ic.setPixmap(icons.pixmap(icon, theme.colors["dim"], 20))
            ic.setFixedWidth(24)
            lay.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        text = QtWidgets.QVBoxLayout()
        text.setSpacing(2)
        self.title = text_label(title, "rowTitle", wrap=True)
        text.addWidget(self.title)
        self.hint = text_label(hint or "", "dim", wrap=True)
        self.hint.setVisible(bool(hint))
        text.addWidget(self.hint)
        lay.addLayout(text, 1)
        self.control = control
        if control is not None:
            lay.addWidget(control, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)


class RowList(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.box = QtWidgets.QVBoxLayout(self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(0)
        self.rows: list[QtWidgets.QWidget] = []

    def add(self, row: QtWidgets.QWidget) -> QtWidgets.QWidget:
        if self.rows:
            line = QtWidgets.QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet(f"background: {theme.colors['border']};")
            self.box.addWidget(line)
        self.box.addWidget(row)
        self.rows.append(row)
        return row

    def clear(self) -> None:
        while self.box.count():
            widget = self.box.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.rows = []


class Banner(QtWidgets.QFrame):
    """Inline notice with an icon, text and an optional action button."""

    action = Signal()
    TONES = {"info": "accent2", "warn": "warn", "error": "bad", "good": "good"}
    ICONS = {"info": "info", "warn": "warning", "error": "warning", "good": "check"}

    def __init__(self, level: str = "info", text: str = "", action_text: str | None = None, parent=None):
        super().__init__(parent)
        self.level = level
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(52, 12, 12, 12)
        lay.setSpacing(12)
        self.text = text_label(text, wrap=True)
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.text, 1)
        self.button = QtWidgets.QPushButton(action_text or "")
        self.button.clicked.connect(self.action.emit)
        lay.addWidget(self.button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.set(level, text, action_text)

    def set(self, level: str, text: str, action_text: str | None = None) -> None:
        self.level = level
        self.text.setText(text)
        self.button.setVisible(bool(action_text))
        if action_text:
            self.button.setText(action_text)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(AA)
        r = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        tone = theme.c(self.TONES.get(self.level, "accent"))
        bg = QtGui.QColor(tone)
        bg.setAlphaF(0.10)
        border = QtGui.QColor(tone)
        border.setAlphaF(0.45)
        p.setPen(QtGui.QPen(border, 1))
        p.setBrush(bg)
        p.drawRoundedRect(r, 14, 14)
        icons.paint(p, self.ICONS.get(self.level, "info"), QtCore.QRectF(18, r.center().y() - 11, 22, 22), tone, 2)


class QuickTile(QtWidgets.QAbstractButton):
    """Compact selectable tile: icon over a short label (lighting modes...)."""

    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(parent)
        self.icon_name, self.label = icon, label
        self.badge = ""
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(74)
        self.setMinimumWidth(78)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)

    def enterEvent(self, e) -> None:  # noqa: N802
        self.update()

    def leaveEvent(self, e) -> None:  # noqa: N802
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(AA)
        r = QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1)
        on = self.isChecked()
        if on:
            bg = QtGui.QLinearGradient(r.topLeft(), r.bottomRight())
            bg.setColorAt(0, theme.c("glow", 0.16))
            bg.setColorAt(1, theme.c("accent2", 0.08))
        else:
            bg = QtGui.QLinearGradient(r.topLeft(), r.bottomLeft())
            bg.setColorAt(0, theme.c("surface2" if self.underMouse() else "surface"))
            bg.setColorAt(1, theme.c("surface"))
        p.fillPath(_rounded(r, 14), bg)
        border = QtGui.QLinearGradient(r.topLeft(), r.bottomRight())
        border.setColorAt(0, theme.c("accent" if on else "border_hi"))
        border.setColorAt(1, theme.c("glow" if on else "border"))
        p.setPen(QtGui.QPen(QtGui.QBrush(border), 1.5 if on else 1))
        p.drawPath(_rounded(r, 14))
        icon_rect = QtCore.QRectF(r.center().x() - 11, r.top() + 13, 22, 22)
        if on:
            glow = QtGui.QRadialGradient(icon_rect.center(), 22)
            glow.setColorAt(0, theme.c("glow", 0.40))
            glow.setColorAt(1, theme.c("glow", 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(icon_rect.center(), 22, 22)
        enabled = self.isEnabled()
        icons.paint(p, self.icon_name, icon_rect,
                    theme.c("faint") if not enabled else theme.c("text" if on else "dim"), 1.8)
        p.setPen(theme.c("faint") if not enabled else theme.c("text" if on else "dim"))
        f = theme.font(9, 700 if on else 600)
        p.setFont(f)
        text = QtGui.QFontMetrics(f).elidedText(self.label, Qt.TextElideMode.ElideRight, int(r.width() - 10))
        p.drawText(QtCore.QRectF(r.left() + 5, r.bottom() - 30, r.width() - 10, 22), Qt.AlignmentFlag.AlignCenter,
                   text)
        if self.badge:
            p.setFont(theme.font(6.5, 800))
            badge = QtCore.QRectF(r.right() - 27, r.top() + 7, 21, 13)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(theme.c("surface3"))
            p.drawRoundedRect(badge, 6.5, 6.5)
            p.setPen(theme.c("dim"))
            p.drawText(badge, Qt.AlignmentFlag.AlignCenter, self.badge)


class MeterBar(QtWidgets.QWidget):
    """Thin horizontal meter (battery level, CPU load...)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 0.0
        self.tone = "accent"
        self.setFixedHeight(8)

    def set_value(self, fraction: float, tone: str = "accent") -> None:
        self.value = max(0.0, min(1.0, fraction))
        self.tone = tone
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(AA)
        r = QtCore.QRectF(self.rect())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.c("surface3"))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        if self.value > 0:
            fill = QtCore.QRectF(r.left(), r.top(), max(r.height(), r.width() * self.value), r.height())
            grad = QtGui.QLinearGradient(fill.topLeft(), fill.topRight())
            if self.tone == "accent":
                grad.setColorAt(0, theme.c("accent2"))
                grad.setColorAt(1, theme.c("accent"))
            else:
                grad.setColorAt(0, theme.c(self.tone, 0.7))
                grad.setColorAt(1, theme.c(self.tone))
            p.setBrush(grad)
            p.drawRoundedRect(fill, r.height() / 2, r.height() / 2)
