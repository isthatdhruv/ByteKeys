"""Draggable fan curve: temperature (°C) on X, fan duty (%) on Y."""

from __future__ import annotations

from .. import theme
from ..qt import QtCore, QtGui, QtWidgets, Qt, Signal

AA = QtGui.QPainter.RenderHint.Antialiasing


class FanCurveEditor(QtWidgets.QWidget):
    changed = Signal(list)      # [[temp, percent], ...] after a drag ends

    T_MIN, T_MAX = 20, 100

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points: list[list[int]] = []
        self.editable = True
        self.current_temp: float | None = None
        self._drag: int | None = None
        self._hover: int | None = None
        self.setMinimumHeight(230)
        self.setMouseTracking(True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)

    def set_points(self, points: list[list[int]]) -> None:
        if self._drag is None:
            self.points = [list(p) for p in points]
            self.update()

    def set_current_temp(self, temp: float | None) -> None:
        self.current_temp = temp
        self.update()

    def set_editable(self, editable: bool) -> None:
        self.editable = editable
        self.setCursor(Qt.CursorShape.PointingHandCursor if editable else Qt.CursorShape.ArrowCursor)
        self.update()

    # ------------------------------------------------------------ geometry
    def _plot(self) -> QtCore.QRectF:
        return QtCore.QRectF(44, 12, self.width() - 60, self.height() - 44)

    def _to_px(self, temp: float, pct: float) -> QtCore.QPointF:
        r = self._plot()
        x = r.left() + (temp - self.T_MIN) / (self.T_MAX - self.T_MIN) * r.width()
        y = r.bottom() - pct / 100.0 * r.height()
        return QtCore.QPointF(x, y)

    def _from_px(self, pos: QtCore.QPointF) -> tuple[float, float]:
        r = self._plot()
        temp = self.T_MIN + (pos.x() - r.left()) / max(1.0, r.width()) * (self.T_MAX - self.T_MIN)
        pct = (r.bottom() - pos.y()) / max(1.0, r.height()) * 100.0
        return temp, pct

    def _point_at(self, pos: QtCore.QPointF) -> int | None:
        best, best_d = None, 14.0
        for i, (t, pct) in enumerate(self.points):
            pt = self._to_px(t, pct)
            d = ((pt.x() - pos.x()) ** 2 + (pt.y() - pos.y()) ** 2) ** 0.5
            if d < best_d:
                best, best_d = i, d
        return best

    # ---------------------------------------------------------- interaction
    def mousePressEvent(self, e) -> None:  # noqa: N802
        if self.editable and e.button() == Qt.MouseButton.LeftButton:
            self._drag = self._point_at(e.position())

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        if self._drag is None:
            hover = self._point_at(e.position()) if self.editable else None
            if hover != self._hover:
                self._hover = hover
                self.update()
            return
        i = self._drag
        temp, pct = self._from_px(e.position())
        lo_t = self.points[i - 1][0] + 1 if i > 0 else self.T_MIN
        hi_t = self.points[i + 1][0] - 1 if i < len(self.points) - 1 else self.T_MAX
        lo_p = self.points[i - 1][1] if i > 0 else 0
        hi_p = self.points[i + 1][1] if i < len(self.points) - 1 else 100
        self.points[i] = [int(round(max(lo_t, min(hi_t, temp)))), int(round(max(lo_p, min(hi_p, pct))))]
        self.update()

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        if self._drag is not None:
            self._drag = None
            self.changed.emit([list(p) for p in self.points])

    def leaveEvent(self, e) -> None:  # noqa: N802
        self._hover = None
        self.update()

    # ------------------------------------------------------------- painting
    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(AA)
        r = self._plot()
        p.setFont(theme.font(8, 600))
        grid = QtGui.QPen(theme.c("border"), 1, Qt.PenStyle.DashLine)
        for pct in range(0, 101, 25):
            y = r.bottom() - pct / 100 * r.height()
            p.setPen(grid)
            p.drawLine(QtCore.QPointF(r.left(), y), QtCore.QPointF(r.right(), y))
            p.setPen(theme.c("faint"))
            p.drawText(QtCore.QRectF(0, y - 8, r.left() - 8, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{pct}%")
        for temp in range(self.T_MIN, self.T_MAX + 1, 10):
            x = r.left() + (temp - self.T_MIN) / (self.T_MAX - self.T_MIN) * r.width()
            p.setPen(grid)
            p.drawLine(QtCore.QPointF(x, r.top()), QtCore.QPointF(x, r.bottom()))
            p.setPen(theme.c("faint"))
            p.drawText(QtCore.QRectF(x - 20, r.bottom() + 6, 40, 16), Qt.AlignmentFlag.AlignCenter, f"{temp}°")
        if self.current_temp is not None and self.T_MIN <= self.current_temp <= self.T_MAX:
            x = r.left() + (self.current_temp - self.T_MIN) / (self.T_MAX - self.T_MIN) * r.width()
            p.setPen(QtGui.QPen(theme.c("warn", 0.8), 1.5, Qt.PenStyle.DashLine))
            p.drawLine(QtCore.QPointF(x, r.top()), QtCore.QPointF(x, r.bottom()))
            p.setPen(theme.c("warn"))
            p.drawText(QtCore.QRectF(x + 4, r.top(), 60, 16), Qt.AlignmentFlag.AlignLeft,
                       f"{self.current_temp:.0f}°C now")
        if not self.points:
            return
        pts = [self._to_px(t, pct) for t, pct in self.points]
        line = QtGui.QPainterPath(QtCore.QPointF(r.left(), pts[0].y()))
        for pt in pts:
            line.lineTo(pt)
        line.lineTo(QtCore.QPointF(r.right(), pts[-1].y()))
        area = QtGui.QPainterPath(line)
        area.lineTo(r.bottomRight())
        area.lineTo(r.bottomLeft())
        area.closeSubpath()
        fill = QtGui.QLinearGradient(r.topLeft(), r.bottomLeft())
        alpha = 0.32 if self.editable else 0.14
        fill.setColorAt(0, theme.c("glow", alpha * 0.8))
        fill.setColorAt(1, theme.c("accent", 0.01))
        p.fillPath(area, fill)
        stroke = QtGui.QLinearGradient(r.topLeft(), r.topRight())
        stroke.setColorAt(0, theme.c("accent2" if self.editable else "faint"))
        stroke.setColorAt(1, theme.c("accent" if self.editable else "faint"))
        p.setPen(QtGui.QPen(QtGui.QBrush(stroke), 3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(line)
        for i, pt in enumerate(pts):
            active = i in (self._drag, self._hover)
            if active:
                glow = QtGui.QRadialGradient(pt, 18)
                glow.setColorAt(0, theme.c("glow", 0.55))
                glow.setColorAt(1, theme.c("glow", 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(glow)
                p.drawEllipse(pt, 18, 18)
            p.setPen(QtGui.QPen(theme.c("glow" if self.editable else "faint"), 2.5))
            p.setBrush(QtGui.QColor("#ffffff") if self.editable else theme.c("surface3"))
            p.drawEllipse(pt, 7 if active else 5.5, 7 if active else 5.5)
        for i, pt in enumerate(pts):          # labels last, above every point
            if i in (self._drag, self._hover):
                t, pct = self.points[i]
                label = f"{t}°C · {pct}%"
                box = QtCore.QRectF(pt.x() - 44, pt.y() - 36, 88, 22)
                box.moveLeft(max(r.left(), min(r.right() - box.width(), box.left())))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(theme.c("surface3"))
                p.drawRoundedRect(box, 8, 8)
                p.setPen(theme.c("text"))
                p.setFont(theme.font(8.5, 700))
                p.drawText(box, Qt.AlignmentFlag.AlignCenter, label)
