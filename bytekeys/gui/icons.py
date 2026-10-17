"""A small vector icon set, drawn with QPainter (no SVG or theme dependency).

Icons are designed on a 24x24 grid with 2px round strokes.
"""

from __future__ import annotations

import math

from .qt import QtCore, QtGui, Qt

_cache: dict[tuple, QtGui.QPixmap] = {}


def _pen(p: QtGui.QPainter, color: QtGui.QColor, width: float = 2.0) -> None:
    pen = QtGui.QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)


def _poly(p, pts, close=False):
    path = QtGui.QPainterPath(QtCore.QPointF(*pts[0]))
    for pt in pts[1:]:
        path.lineTo(QtCore.QPointF(*pt))
    if close:
        path.closeSubpath()
    p.drawPath(path)


def _home(p, c):
    _poly(p, [(3, 11), (12, 3.5), (21, 11)])
    _poly(p, [(5.5, 9.5), (5.5, 20), (18.5, 20), (18.5, 9.5)])
    _poly(p, [(10, 20), (10, 14), (14, 14), (14, 20)])


def _keyboard(p, c):
    p.drawRoundedRect(QtCore.QRectF(2.5, 6, 19, 12), 2.5, 2.5)
    for x in (6, 9, 12, 15, 18):
        p.drawPoint(QtCore.QPointF(x, 10))
    for x in (7.5, 16.5):
        p.drawPoint(QtCore.QPointF(x, 13.2))
    p.drawLine(QtCore.QPointF(9.5, 14.8), QtCore.QPointF(14.5, 14.8))


def _fan(p, c):
    p.drawEllipse(QtCore.QPointF(12, 12), 1.8, 1.8)
    for angle in (0, 120, 240):
        p.save()
        p.translate(12, 12)
        p.rotate(angle)
        path = QtGui.QPainterPath(QtCore.QPointF(0, -2))
        path.cubicTo(QtCore.QPointF(-1, -7), QtCore.QPointF(3.5, -10.5), QtCore.QPointF(6, -8))
        path.cubicTo(QtCore.QPointF(7.5, -6), QtCore.QPointF(4, -3), QtCore.QPointF(1.8, -0.8))
        p.drawPath(path)
        p.restore()


def _bolt(p, c):
    _poly(p, [(13.5, 2.5), (5, 13.5), (11.5, 13.5), (10.5, 21.5), (19, 10), (12.5, 10), (13.5, 2.5)], close=True)


def _layers(p, c):
    _poly(p, [(12, 3), (21, 8), (12, 13), (3, 8)], close=True)
    _poly(p, [(3, 12.5), (12, 17.5), (21, 12.5)])
    _poly(p, [(3, 16.5), (12, 21.5), (21, 16.5)])


def _gear(p, c):
    p.drawEllipse(QtCore.QPointF(12, 12), 3, 3)
    path = QtGui.QPainterPath()
    teeth = 8
    for i in range(teeth * 2):
        r = 9 if i % 2 == 0 else 7
        a0 = (i / (teeth * 2)) * 2 * math.pi
        a1 = ((i + 1) / (teeth * 2)) * 2 * math.pi
        pt0 = QtCore.QPointF(12 + r * math.cos(a0), 12 + r * math.sin(a0))
        pt1 = QtCore.QPointF(12 + r * math.cos(a1), 12 + r * math.sin(a1))
        if i == 0:
            path.moveTo(pt0)
        else:
            path.lineTo(pt0)
        path.lineTo(pt1)
    path.closeSubpath()
    p.drawPath(path)


def _cpu(p, c):
    p.drawRoundedRect(QtCore.QRectF(6, 6, 12, 12), 2, 2)
    p.drawRect(QtCore.QRectF(9.5, 9.5, 5, 5))
    for v in (9, 12, 15):
        p.drawLine(QtCore.QPointF(v, 2.5), QtCore.QPointF(v, 6))
        p.drawLine(QtCore.QPointF(v, 18), QtCore.QPointF(v, 21.5))
        p.drawLine(QtCore.QPointF(2.5, v), QtCore.QPointF(6, v))
        p.drawLine(QtCore.QPointF(18, v), QtCore.QPointF(21.5, v))


def _gpu(p, c):
    p.drawRoundedRect(QtCore.QRectF(2.5, 6, 19, 11), 2, 2)
    p.drawEllipse(QtCore.QPointF(9, 11.5), 3, 3)
    p.drawLine(QtCore.QPointF(15, 9.5), QtCore.QPointF(18.5, 9.5))
    p.drawLine(QtCore.QPointF(15, 13.5), QtCore.QPointF(18.5, 13.5))
    p.drawLine(QtCore.QPointF(5, 17), QtCore.QPointF(5, 20))
    p.drawLine(QtCore.QPointF(8, 17), QtCore.QPointF(8, 20))


def _thermo(p, c):
    path = QtGui.QPainterPath()
    path.moveTo(10, 14.5)
    path.lineTo(10, 5)
    path.arcTo(QtCore.QRectF(10, 3, 4, 4), 180, -180)
    path.lineTo(14, 14.5)
    p.drawPath(path)
    p.drawEllipse(QtCore.QPointF(12, 17.5), 3.5, 3.5)
    p.drawLine(QtCore.QPointF(12, 9), QtCore.QPointF(12, 15))


def _battery(p, c):
    p.drawRoundedRect(QtCore.QRectF(2.5, 7, 17, 10), 2, 2)
    p.drawLine(QtCore.QPointF(21.5, 10.5), QtCore.QPointF(21.5, 13.5))
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    p.drawRoundedRect(QtCore.QRectF(5, 9.5, 8, 5), 1, 1)
    p.restore()


def _sun(p, c):
    p.drawEllipse(QtCore.QPointF(12, 12), 4, 4)
    for i in range(8):
        a = i * math.pi / 4
        p.drawLine(QtCore.QPointF(12 + 7 * math.cos(a), 12 + 7 * math.sin(a)),
                   QtCore.QPointF(12 + 9.5 * math.cos(a), 12 + 9.5 * math.sin(a)))


def _leaf(p, c):
    path = QtGui.QPainterPath(QtCore.QPointF(5, 19))
    path.cubicTo(QtCore.QPointF(4, 9), QtCore.QPointF(11, 4), QtCore.QPointF(20, 4))
    path.cubicTo(QtCore.QPointF(20, 13), QtCore.QPointF(15, 19.5), QtCore.QPointF(5, 19))
    p.drawPath(path)
    p.drawLine(QtCore.QPointF(5, 19), QtCore.QPointF(14, 10))


def _gauge(p, c):
    path = QtGui.QPainterPath()
    path.arcMoveTo(QtCore.QRectF(3, 5, 18, 18), 200)
    path.arcTo(QtCore.QRectF(3, 5, 18, 18), 200, -220)
    p.drawPath(path)
    p.drawLine(QtCore.QPointF(12, 14), QtCore.QPointF(16, 9))
    p.drawEllipse(QtCore.QPointF(12, 14), 1.2, 1.2)


def _flame(p, c):
    path = QtGui.QPainterPath(QtCore.QPointF(12, 21.5))
    path.cubicTo(QtCore.QPointF(6.5, 21.5), QtCore.QPointF(4.5, 16.5), QtCore.QPointF(7, 12.5))
    path.cubicTo(QtCore.QPointF(8.5, 10), QtCore.QPointF(9, 7.5), QtCore.QPointF(9, 4))
    path.cubicTo(QtCore.QPointF(13, 6), QtCore.QPointF(14, 9.5), QtCore.QPointF(13.5, 12))
    path.cubicTo(QtCore.QPointF(15, 11), QtCore.QPointF(15.5, 9.5), QtCore.QPointF(15.5, 8.5))
    path.cubicTo(QtCore.QPointF(19.5, 12.5), QtCore.QPointF(19.5, 21.5), QtCore.QPointF(12, 21.5))
    p.drawPath(path)


def _palette(p, c):
    path = QtGui.QPainterPath(QtCore.QPointF(12, 3))
    path.cubicTo(QtCore.QPointF(5.5, 3), QtCore.QPointF(2.5, 8), QtCore.QPointF(3, 12.5))
    path.cubicTo(QtCore.QPointF(3.5, 18), QtCore.QPointF(8, 21), QtCore.QPointF(11.5, 21))
    path.cubicTo(QtCore.QPointF(13.5, 21), QtCore.QPointF(13.5, 19), QtCore.QPointF(12.5, 18))
    path.cubicTo(QtCore.QPointF(11.5, 16.5), QtCore.QPointF(12.5, 15), QtCore.QPointF(14.5, 15))
    path.lineTo(17, 15)
    path.cubicTo(QtCore.QPointF(19.5, 15), QtCore.QPointF(21, 13.5), QtCore.QPointF(21, 11.5))
    path.cubicTo(QtCore.QPointF(21, 6.5), QtCore.QPointF(17, 3), QtCore.QPointF(12, 3))
    p.drawPath(path)
    for x, y in ((7.5, 11), (9.5, 7), (14, 6.5), (17, 9.5)):
        p.drawPoint(QtCore.QPointF(x, y))


def _sparkle(p, c):
    path = QtGui.QPainterPath(QtCore.QPointF(11, 3))
    path.cubicTo(QtCore.QPointF(11.5, 8), QtCore.QPointF(13, 9.5), QtCore.QPointF(18, 10))
    path.cubicTo(QtCore.QPointF(13, 10.5), QtCore.QPointF(11.5, 12), QtCore.QPointF(11, 17))
    path.cubicTo(QtCore.QPointF(10.5, 12), QtCore.QPointF(9, 10.5), QtCore.QPointF(4, 10))
    path.cubicTo(QtCore.QPointF(9, 9.5), QtCore.QPointF(10.5, 8), QtCore.QPointF(11, 3))
    p.drawPath(path)
    p.drawLine(QtCore.QPointF(18, 15.5), QtCore.QPointF(18, 20.5))
    p.drawLine(QtCore.QPointF(15.5, 18), QtCore.QPointF(20.5, 18))


def _power(p, c):
    path = QtGui.QPainterPath()
    path.arcMoveTo(QtCore.QRectF(4, 4.5, 16, 16), 55)
    path.arcTo(QtCore.QRectF(4, 4.5, 16, 16), 55, 290)
    p.drawPath(path)
    p.drawLine(QtCore.QPointF(12, 2.5), QtCore.QPointF(12, 11))


def _plus(p, c):
    p.drawLine(QtCore.QPointF(12, 5), QtCore.QPointF(12, 19))
    p.drawLine(QtCore.QPointF(5, 12), QtCore.QPointF(19, 12))


def _check(p, c):
    _poly(p, [(5, 12.5), (10, 17.5), (19.5, 7)])


def _edit(p, c):
    _poly(p, [(4, 20), (4.8, 15.8), (15.5, 5), (19, 8.5), (8.2, 19.2), (4, 20)])
    p.drawLine(QtCore.QPointF(13.2, 7.3), QtCore.QPointF(16.7, 10.8))


def _trash(p, c):
    p.drawLine(QtCore.QPointF(4, 7), QtCore.QPointF(20, 7))
    _poly(p, [(9, 7), (9.5, 4), (14.5, 4), (15, 7)])
    _poly(p, [(6, 7), (7, 20), (17, 20), (18, 7)])


def _info(p, c):
    p.drawEllipse(QtCore.QPointF(12, 12), 9, 9)
    p.drawLine(QtCore.QPointF(12, 11), QtCore.QPointF(12, 16.5))
    p.drawPoint(QtCore.QPointF(12, 7.8))


def _warning(p, c):
    _poly(p, [(12, 3.5), (21.5, 20), (2.5, 20)], close=True)
    p.drawLine(QtCore.QPointF(12, 9.5), QtCore.QPointF(12, 14))
    p.drawPoint(QtCore.QPointF(12, 17))


def _wave(p, c):
    path = QtGui.QPainterPath(QtCore.QPointF(2.5, 12))
    path.cubicTo(QtCore.QPointF(5, 5), QtCore.QPointF(8, 5), QtCore.QPointF(10, 12))
    path.cubicTo(QtCore.QPointF(12, 19), QtCore.QPointF(15, 19), QtCore.QPointF(17, 12))
    path.cubicTo(QtCore.QPointF(18.5, 7), QtCore.QPointF(20.5, 7), QtCore.QPointF(21.5, 9))
    p.drawPath(path)


def _rocket(p, c):
    path = QtGui.QPainterPath(QtCore.QPointF(14.5, 3.5))
    path.cubicTo(QtCore.QPointF(19.5, 3), QtCore.QPointF(21, 4.5), QtCore.QPointF(20.5, 9.5))
    path.lineTo(12.5, 17.5)
    path.lineTo(6.5, 11.5)
    path.closeSubpath()
    p.drawPath(path)
    _poly(p, [(8.5, 9.5), (4.5, 9.5), (2.5, 13), (6.5, 11.5)])
    _poly(p, [(14.5, 15.5), (14.5, 19.5), (11, 21.5), (12.5, 17.5)])
    p.drawEllipse(QtCore.QPointF(15.5, 8.5), 1.5, 1.5)
    p.drawLine(QtCore.QPointF(6, 18), QtCore.QPointF(3.5, 20.5))


def _key(p, c):
    p.drawRoundedRect(QtCore.QRectF(3.5, 5, 17, 14), 3, 3)
    p.drawRoundedRect(QtCore.QRectF(6.5, 7.5, 11, 7.5), 2, 2)


def _chevron(p, c):
    _poly(p, [(9, 5.5), (15.5, 12), (9, 18.5)])


def _refresh(p, c):
    path = QtGui.QPainterPath()
    path.arcMoveTo(QtCore.QRectF(4, 4, 16, 16), 30)
    path.arcTo(QtCore.QRectF(4, 4, 16, 16), 30, 300)
    p.drawPath(path)
    _poly(p, [(19.5, 3.5), (19.5, 8.5), (14.5, 8.5)])


def _pulse(p, c):
    _poly(p, [(2.5, 12.5), (7, 12.5), (9.5, 6), (13.5, 19), (16, 12.5), (21.5, 12.5)])


def _drop(p, c):
    path = QtGui.QPainterPath(QtCore.QPointF(12, 3))
    path.cubicTo(QtCore.QPointF(15, 7.5), QtCore.QPointF(18.5, 11), QtCore.QPointF(18.5, 14.5))
    path.cubicTo(QtCore.QPointF(18.5, 18.5), QtCore.QPointF(15.5, 21), QtCore.QPointF(12, 21))
    path.cubicTo(QtCore.QPointF(8.5, 21), QtCore.QPointF(5.5, 18.5), QtCore.QPointF(5.5, 14.5))
    path.cubicTo(QtCore.QPointF(5.5, 11), QtCore.QPointF(9, 7.5), QtCore.QPointF(12, 3))
    p.drawPath(path)


def _moon(p, c):
    path = QtGui.QPainterPath(QtCore.QPointF(19.5, 14.5))
    path.cubicTo(QtCore.QPointF(14, 16.5), QtCore.QPointF(7.5, 10), QtCore.QPointF(9.5, 4))
    path.cubicTo(QtCore.QPointF(5.5, 5.5), QtCore.QPointF(3, 9.5), QtCore.QPointF(4, 14))
    path.cubicTo(QtCore.QPointF(5.5, 19.5), QtCore.QPointF(13, 22), QtCore.QPointF(19.5, 14.5))
    p.drawPath(path)


def _clock(p, c):
    p.drawEllipse(QtCore.QPointF(12, 12), 9, 9)
    _poly(p, [(12, 7), (12, 12), (15.5, 14)])


def _dots(p, c):
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    for x in (6, 12, 18):
        p.drawEllipse(QtCore.QPointF(x, 12), 1.7, 1.7)
    p.restore()


def _external(p, c):
    _poly(p, [(10, 5), (5, 5), (5, 19), (19, 19), (19, 14)])
    _poly(p, [(14, 4.5), (19.5, 4.5), (19.5, 10)])
    p.drawLine(QtCore.QPointF(19.5, 4.5), QtCore.QPointF(11, 13))


def _save(p, c):
    _poly(p, [(12, 3.5), (12, 15)])
    _poly(p, [(7, 10.5), (12, 15.5), (17, 10.5)])
    _poly(p, [(4, 15.5), (4, 20), (20, 20), (20, 15.5)])


def _copy(p, c):
    p.drawRoundedRect(QtCore.QRectF(8.5, 8.5, 12, 12), 2, 2)
    _poly(p, [(15.5, 5.5), (15.5, 4.5), (4.5, 4.5), (4.5, 15.5), (5.5, 15.5)])


def _shield(p, c):
    path = QtGui.QPainterPath(QtCore.QPointF(12, 2.5))
    path.lineTo(19.5, 5.5)
    path.cubicTo(QtCore.QPointF(19.5, 13), QtCore.QPointF(17, 18.5), QtCore.QPointF(12, 21.5))
    path.cubicTo(QtCore.QPointF(7, 18.5), QtCore.QPointF(4.5, 13), QtCore.QPointF(4.5, 5.5))
    path.closeSubpath()
    p.drawPath(path)
    _poly(p, [(8.5, 12), (11, 14.5), (15.5, 9.5)])


def _plug(p, c):
    p.drawLine(QtCore.QPointF(9, 3), QtCore.QPointF(9, 7.5))
    p.drawLine(QtCore.QPointF(15, 3), QtCore.QPointF(15, 7.5))
    path = QtGui.QPainterPath(QtCore.QPointF(6, 7.5))
    path.lineTo(18, 7.5)
    path.lineTo(18, 11)
    path.cubicTo(QtCore.QPointF(18, 14.5), QtCore.QPointF(15.5, 16.5), QtCore.QPointF(12, 16.5))
    path.cubicTo(QtCore.QPointF(8.5, 16.5), QtCore.QPointF(6, 14.5), QtCore.QPointF(6, 11))
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(QtCore.QPointF(12, 16.5), QtCore.QPointF(12, 21.5))


def _close(p, c):
    p.drawLine(QtCore.QPointF(6, 6), QtCore.QPointF(18, 18))
    p.drawLine(QtCore.QPointF(18, 6), QtCore.QPointF(6, 18))


def _up(p, c):
    _poly(p, [(6, 14.5), (12, 8.5), (18, 14.5)])


def _down(p, c):
    _poly(p, [(6, 9.5), (12, 15.5), (18, 9.5)])


ICONS = {
    "home": _home, "keyboard": _keyboard, "fan": _fan, "bolt": _bolt, "layers": _layers, "gear": _gear,
    "cpu": _cpu, "gpu": _gpu, "thermo": _thermo, "battery": _battery, "sun": _sun, "leaf": _leaf,
    "gauge": _gauge, "flame": _flame, "palette": _palette, "sparkle": _sparkle, "power": _power,
    "plus": _plus, "check": _check, "edit": _edit, "trash": _trash, "info": _info, "warning": _warning,
    "wave": _wave, "rocket": _rocket, "key": _key, "chevron": _chevron, "refresh": _refresh,
    "pulse": _pulse, "drop": _drop, "moon": _moon, "clock": _clock, "dots": _dots, "external": _external,
    "save": _save, "copy": _copy, "shield": _shield, "plug": _plug, "close": _close, "up": _up, "down": _down,
}


def paint(p: QtGui.QPainter, name: str, rect: QtCore.QRectF, color, width: float = 2.0) -> None:
    """Draw icon *name* into *rect* (any size) on an existing painter."""
    fn = ICONS.get(name)
    if fn is None:
        return
    p.save()
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    p.translate(rect.x(), rect.y())
    p.scale(rect.width() / 24.0, rect.height() / 24.0)
    qc = QtGui.QColor(color)
    _pen(p, qc, width)
    fn(p, qc)
    p.restore()


def pixmap(name: str, color, size: int = 20, width: float = 2.0) -> QtGui.QPixmap:
    qc = QtGui.QColor(color)
    key = (name, qc.rgba(), size, width)
    if key in _cache:
        return _cache[key]
    ratio = 2.0
    pm = QtGui.QPixmap(int(size * ratio), int(size * ratio))
    pm.fill(Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pm)
    paint(p, name, QtCore.QRectF(0, 0, size * ratio, size * ratio), qc, width)
    p.end()
    pm.setDevicePixelRatio(ratio)
    _cache[key] = pm
    return pm


def icon(name: str, color, size: int = 20) -> QtGui.QIcon:
    return QtGui.QIcon(pixmap(name, color, size))
