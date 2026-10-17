"""Navigation sidebar: logo, page buttons, device and service status."""

from __future__ import annotations

from .. import icons, theme
from ..qt import QtCore, QtGui, QtWidgets, Qt, Signal

AA = QtGui.QPainter.RenderHint.Antialiasing


class Wordmark(QtWidgets.QWidget):
    """The logo icon plus "Byte" + silver "Keys"."""

    def __init__(self, icon: QtGui.QIcon, parent=None):
        super().__init__(parent)
        self.icon = icon
        self.setFixedHeight(48)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(AA)
        p.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        p.drawPixmap(QtCore.QRect(0, 3, 42, 42), self.icon.pixmap(84, 84))
        f = theme.font(16.5, 700)
        p.setFont(f)
        fm = QtGui.QFontMetrics(f)
        baseline = 24 + fm.ascent() / 2 - 2
        p.setPen(theme.c("text"))
        p.drawText(QtCore.QPointF(54, baseline), "Byte")
        x = 54 + fm.horizontalAdvance("Byte")
        grad = QtGui.QLinearGradient(QtCore.QPointF(x, 8), QtCore.QPointF(x + fm.horizontalAdvance("Keys"), 40))
        if theme.dark_mode:   # silver, like the logo's wordmark
            grad.setColorAt(0, QtGui.QColor("#e4e4ea"))
            grad.setColorAt(1, QtGui.QColor("#8d8d97"))
        else:
            grad.setColorAt(0, QtGui.QColor("#77777f"))
            grad.setColorAt(1, QtGui.QColor("#3d3d45"))
        p.setPen(QtGui.QPen(QtGui.QBrush(grad), 1))
        p.drawText(QtCore.QPointF(x, baseline), "Keys")


class NavButton(QtWidgets.QAbstractButton):
    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(parent)
        self.icon_name, self.label = icon, label
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(44)

    def enterEvent(self, e) -> None:  # noqa: N802
        self.update()

    def leaveEvent(self, e) -> None:  # noqa: N802
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(AA)
        r = QtCore.QRectF(self.rect()).adjusted(0, 2, 0, -2)
        on = self.isChecked()
        if on or self.underMouse():
            bg = QtGui.QLinearGradient(r.topLeft(), r.topRight())
            bg.setColorAt(0, theme.c("surface3" if on else "surface"))
            bg.setColorAt(1, theme.c("surface2" if on else "surface", 0.4))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(r, 12, 12)
        if on:
            bar = QtCore.QRectF(r.left() + 2, r.center().y() - 9, 3.5, 18)
            glow = QtGui.QRadialGradient(bar.center(), 16)
            glow.setColorAt(0, theme.c("glow", 0.55))
            glow.setColorAt(1, theme.c("glow", 0))
            p.setBrush(glow)
            p.drawEllipse(bar.center(), 16, 16)
            p.setBrush(theme.c("glow") if theme.dark_mode else theme.c("accent"))
            p.drawRoundedRect(bar, 1.75, 1.75)
        color = theme.c("text") if on else theme.c("dim")
        icons.paint(p, self.icon_name, QtCore.QRectF(r.left() + 16, r.center().y() - 10, 20, 20), color, 1.9)
        p.setPen(color)
        p.setFont(theme.font(10.5, 650 if on else 500))
        p.drawText(QtCore.QRectF(r.left() + 48, r.top(), r.width() - 52, r.height()),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.label)


class Sidebar(QtWidgets.QFrame):
    pageSelected = Signal(int)
    statusClicked = Signal()

    def __init__(self, app_icon: QtGui.QIcon, pages: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setFixedWidth(232)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(18, 22, 18, 18)
        lay.setSpacing(4)
        lay.addWidget(Wordmark(app_icon))
        lay.addSpacing(26)
        self.group = QtWidgets.QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: list[NavButton] = []
        for i, (icon, label) in enumerate(pages):
            b = NavButton(icon, label)
            b.clicked.connect(lambda _=False, idx=i: self.pageSelected.emit(idx))
            self.group.addButton(b)
            self.buttons.append(b)
            lay.addWidget(b)
        lay.addStretch(1)
        self.model = QtWidgets.QLabel("")
        self.model.setObjectName("faint")
        self.model.setWordWrap(True)
        lay.addWidget(self.model)
        lay.addSpacing(6)
        self.status = QtWidgets.QPushButton("")
        self.status.setObjectName("ghost")
        self.status.setCursor(Qt.CursorShape.PointingHandCursor)
        self.status.clicked.connect(self.statusClicked.emit)
        self.status.setStyleSheet("text-align: left; padding-left: 4px;")
        lay.addWidget(self.status)

    def set_current(self, index: int) -> None:
        if 0 <= index < len(self.buttons):
            self.buttons[index].setChecked(True)

    def set_status(self, text: str, tone: str) -> None:
        dot = QtGui.QPixmap(24, 24)
        dot.fill(Qt.GlobalColor.transparent)
        p = QtGui.QPainter(dot)
        p.setRenderHint(AA)
        color = theme.c(tone)
        glow = QtGui.QRadialGradient(QtCore.QPointF(12, 12), 12)
        glow.setColorAt(0, QtGui.QColor(color.red(), color.green(), color.blue(), 140))
        glow.setColorAt(1, QtGui.QColor(color.red(), color.green(), color.blue(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QtCore.QRectF(0, 0, 24, 24))
        p.setBrush(color)
        p.drawEllipse(QtCore.QRectF(7, 7, 10, 10))
        p.end()
        dot.setDevicePixelRatio(2)
        self.status.setIcon(QtGui.QIcon(dot))
        self.status.setText(" " + text)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        r = QtCore.QRectF(self.rect())
        grad = QtGui.QLinearGradient(r.topLeft(), r.bottomLeft())
        grad.setColorAt(0, theme.c("sidebar"))
        grad.setColorAt(1, theme.c("bg"))
        p.fillRect(r, grad)
        if theme.dark_mode:   # warm light in the top corner, like the logo artwork
            glow = QtGui.QRadialGradient(r.topLeft(), r.width() * 1.1)
            glow.setColorAt(0, QtGui.QColor(138, 117, 89, 46))
            glow.setColorAt(1, QtGui.QColor(138, 117, 89, 0))
            p.fillRect(r, glow)
        p.setPen(theme.c("border"))
        p.drawLine(r.topRight() - QtCore.QPointF(0.5, 0), r.bottomRight() - QtCore.QPointF(0.5, 0))
