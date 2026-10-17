"""Live keyboard preview with zone/key selection."""

from __future__ import annotations

import time

from ... import layouts
from ...color import parse
from ...engine.effects import Context, Renderer
from .. import theme
from ..qt import QtCore, QtGui, QtWidgets, Qt, Signal

SHORT = {
    "Backspace": "⌫", "Enter": "⏎", "Enter ": "⏎", "Shift": "⇧", "Shift ": "⇧", "Tab": "⇥",
    "Caps": "⇪", "Up": "▲", "Down": "▼", "Left": "◀", "Right": "▶", "Space": "", "Win": "❖",
    "Menu": "☰", "Ctrl ": "Ctrl", "PrtSc": "Prt",
}

# Firmware effects previewed with the closest software effect.
HW_PREVIEW = {
    "breathing": "breathing", "breath": "breathing", "pulse": "breathing",
    "cycle": "spectrum", "spectrum": "spectrum", "smooth": "spectrum", "hue": "spectrum",
    "rainbow": "wave", "wave": "wave", "strobe": "blink", "flash": "blink", "blink": "blink",
}


def _preview_effect(effect: str) -> str:
    if not effect.startswith("hw:"):
        return effect
    name = effect[3:].lower()
    if name.startswith("mode-"):
        name = name[5:]
    for key, value in HW_PREVIEW.items():
        if key in name:
            return value
    return "static"


class KeyboardView(QtWidgets.QWidget):
    selectionChanged = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumHeight(170)
        sp = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                                   QtWidgets.QSizePolicy.Policy.Preferred)
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)
        self.device: dict | None = None
        self.state: dict | None = None
        self.layout_name = "compact"
        self.mode = "geometry"
        self.keys: list[layouts.Key] = layouts.get("compact")
        self.key_zone: list[int | None] = []
        self.cells: list[tuple[int, float, float, float, float, str]] = []  # zone, x, y, w, h, label
        self.selected: set[int] = set()
        self.selectable = False
        self._hover: int | None = None
        self._drag_add: bool | None = None
        self._renderer: Renderer | None = None
        self._renderer_key = None
        self._t0 = time.monotonic()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self.update)

    # ------------------------------------------------------------ geometry
    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, w: int) -> int:  # noqa: N802
        gw, gh = self._grid_size()
        return int(min(360, max(170, (w - 40) * gh / max(gw, 1) + 40)))

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(760, self.heightForWidth(760))

    def _grid_size(self) -> tuple[float, float]:
        if self.mode == "geometry":
            return layouts.width(self.keys), layouts.height(self.keys)
        if not self.cells:
            return 15.0, 6.0
        return (max(x + w for _, x, _, w, _, _ in self.cells),
                max(y + h for _, _, y, _, h, _ in self.cells))

    # ---------------------------------------------------------------- model
    def set_device(self, device: dict | None, layout_hint: str = "compact") -> None:
        self.device = device
        self.selected.clear()
        self.cells = []
        self.key_zone = []
        if device is None:
            self.update()
            return
        mode = device["color_mode"]
        zones = device.get("zones") or []
        lay = device.get("layout") or ""
        self.selectable = mode in ("zones", "perkey")
        if mode == "perkey" and lay.startswith("perkey-") and lay.split("-", 1)[1] in layouts.LAYOUTS:
            self.mode = "geometry"
            self.layout_name = lay.split("-", 1)[1]
            self.keys = layouts.get(self.layout_name)
            self.key_zone = [i if i < len(zones) else None for i in range(len(self.keys))]
        elif mode == "perkey" and zones and all(z.get("row") is not None for z in zones):
            self.mode = "matrix"
            for z in zones:
                text = (z.get("key") or z.get("name") or "")[:5]
                self.cells.append((z["index"], float(z["col"]), float(z["row"]), 0.92, 0.92, text))
        elif mode == "perkey":
            self.mode = "list"
            per_row = 16
            for z in zones:
                i = z["index"]
                self.cells.append((i, float(i % per_row), float(i // per_row), 0.92, 0.92,
                                   (z.get("key") or str(i + 1))[:4]))
        else:
            self.mode = "geometry"
            self.layout_name = "full" if (mode == "zones" and len(zones) == 4) else layout_hint
            self.keys = layouts.get(self.layout_name)
            if mode == "zones":
                self.key_zone = [layouts.zone_of(k, len(zones), self.keys) for k in self.keys]
            else:
                self.key_zone = [0 if mode == "single" else None] * len(self.keys)
        self.updateGeometry()
        self.update()

    def set_state(self, state: dict | None) -> None:
        self.state = state
        key = None
        if state:
            effect = _preview_effect(state.get("effect", "static"))
            key = (effect, repr(sorted((state.get("params") or {}).items())), state.get("color"),
                   tuple(state.get("zones") or ()), tuple(state.get("effect_colors") or ()))
        if key != self._renderer_key:
            self._renderer_key = key
            self._renderer = None
            if state and self.device:
                n = self._zone_count()
                base = self._base_colors(n)
                self._renderer = Renderer(_preview_effect(state.get("effect", "static")),
                                          state.get("params") or {}, base,
                                          [parse(c) for c in state.get("effect_colors") or []],
                                          self._positions(n), start=time.monotonic() - self._t0)
        animated = bool(self._renderer and self._renderer.animated and state and state.get("on"))
        if animated and not self._timer.isActive():
            self._timer.start()
        elif not animated:
            self._timer.stop()
        self.update()

    def set_selection(self, zones) -> None:
        self.selected = set(zones)
        self.update()

    def _zone_count(self) -> int:
        if not self.device or self.device["color_mode"] == "none":
            return 1
        if self.device["color_mode"] == "single":
            return 1
        return max(1, len(self.device.get("zones") or []))

    def _positions(self, n: int) -> list[float]:
        zones = (self.device or {}).get("zones") or []
        if n <= 1:
            return [0.0]
        cols = [z.get("col") for z in zones]
        if len(cols) == n and all(c is not None for c in cols):
            top = max(cols) or 1
            return [c / top for c in cols]
        return [i / (n - 1) for i in range(n)]

    def _base_colors(self, n: int):
        st = self.state or {}
        if not self.device or self.device["color_mode"] == "none":
            return [(255, 244, 225)]
        zones = st.get("zones")
        color = st.get("color", "#ffffff")
        if zones:
            return [parse(zones[i] if i < len(zones) else color) for i in range(n)]
        return [parse(color)] * n

    def _frame(self):
        """Brightness factor and per-zone colors to draw right now."""
        st = self.state or {}
        n = self._zone_count()
        if not st or not st.get("on", True) or st.get("brightness", 100) <= 0:
            return 0.0, self._base_colors(n)
        level = st.get("brightness", 100) / 100.0
        if self._renderer:
            factor, colors = self._renderer.frame(time.monotonic() - self._t0, Context(last_key=None))
            if self.device and self.device["color_mode"] == "none":
                colors = self._base_colors(n)
            return level * max(0.0, min(1.0, factor)), colors
        return level, self._base_colors(n)

    # ----------------------------------------------------------- painting
    def _transform(self) -> tuple[float, float, float]:
        gw, gh = self._grid_size()
        margin = 22.0
        unit = min((self.width() - 2 * margin) / gw, (self.height() - 2 * margin) / gh)
        ox = (self.width() - gw * unit) / 2
        oy = (self.height() - gh * unit) / 2
        return unit, ox, oy

    def _items(self):
        """(zone index or None, rect, label) for everything we draw."""
        unit, ox, oy = self._transform()
        gap = max(2.0, unit * 0.09)
        out = []
        if self.mode == "geometry":
            for i, k in enumerate(self.keys):
                rect = QtCore.QRectF(ox + k.x * unit + gap / 2, oy + k.y * unit + gap / 2,
                                     k.w * unit - gap, k.h * unit - gap)
                zone = self.key_zone[i] if i < len(self.key_zone) else None
                out.append((zone, rect, SHORT.get(k.label, k.label.strip())))
        else:
            for zone, x, y, w, h, text in self.cells:
                rect = QtCore.QRectF(ox + x * unit + gap / 2, oy + y * unit + gap / 2,
                                     w * unit - gap / 2, h * unit - gap / 2)
                out.append((zone, rect, text))
        return out, unit

    def paintEvent(self, _event) -> None:  # noqa: N802
        c = theme.colors
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        items, unit = self._items()
        if not items:
            return
        bounds = QtCore.QRectF()
        for _, rect, _ in items:
            bounds = bounds.united(rect)
        chassis = bounds.adjusted(-12, -12, 12, 12)
        p.setPen(QtGui.QPen(QtGui.QColor(c["key_edge"]), 1))
        p.setBrush(QtGui.QColor(c["chassis"]))
        p.drawRoundedRect(chassis, 14, 14)

        factor, colors = self._frame()
        rgb = bool(self.device and self.device["color_mode"] != "none")
        font = QtGui.QFont(self.font())
        font.setPixelSize(max(7, int(unit * 0.26)))
        font.setWeight(QtGui.QFont.Weight.DemiBold)
        p.setFont(font)
        radius = max(3.0, unit * 0.14)
        for zone, rect, text in items:
            if zone is None and rgb:
                color = (90, 96, 112)
                lit = 0.0
            else:
                color = colors[zone if zone is not None and zone < len(colors) else 0] if colors else (255, 255, 255)
                lit = factor
            qc = QtGui.QColor(*color)
            if lit > 0.02:
                glow = QtGui.QColor(qc)
                glow.setAlphaF(min(1.0, 0.18 + 0.5 * lit))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(glow)
                p.drawRoundedRect(rect.adjusted(-2, -2, 2, 2), radius + 2, radius + 2)
            grad = QtGui.QLinearGradient(rect.topLeft(), rect.bottomLeft())
            grad.setColorAt(0, QtGui.QColor(c["key"]).lighter(118))
            grad.setColorAt(1, QtGui.QColor(c["key"]))
            p.setBrush(grad)
            edge = QtGui.QColor(qc) if lit > 0.02 else QtGui.QColor(c["key_edge"])
            if lit > 0.02:
                edge.setAlphaF(min(1.0, 0.35 + 0.6 * lit))
            p.setPen(QtGui.QPen(edge, 1.2))
            p.drawRoundedRect(rect, radius, radius)
            if text:
                legend = QtGui.QColor(qc) if lit > 0.02 else QtGui.QColor(c["faint"])
                if lit > 0.02:
                    legend = QtGui.QColor(
                        min(255, int(color[0] * (0.35 + 0.65 * lit) + 40 * lit)),
                        min(255, int(color[1] * (0.35 + 0.65 * lit) + 40 * lit)),
                        min(255, int(color[2] * (0.35 + 0.65 * lit) + 40 * lit)),
                    )
                p.setPen(legend)
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
            if zone is not None and (zone in self.selected or zone == self._hover) and self.selectable:
                pen = QtGui.QPen(QtGui.QColor(c["accent"] if zone in self.selected else c["dim"]),
                                 2.2 if zone in self.selected else 1.2)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(rect.adjusted(-1.5, -1.5, 1.5, 1.5), radius + 1, radius + 1)

    # ---------------------------------------------------------- interaction
    def _zone_at(self, pos: QtCore.QPointF) -> int | None:
        items, _ = self._items()
        for zone, rect, _ in items:
            if rect.contains(pos):
                return zone
        return None

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if not self.selectable or event.button() != Qt.MouseButton.LeftButton:
            return
        zone = self._zone_at(event.position())
        mods = event.modifiers()
        additive = bool(mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier))
        if zone is None:
            if not additive:
                self.selected.clear()
                self.selectionChanged.emit([])
            self.update()
            return
        if additive or self.device["color_mode"] == "perkey":
            self._drag_add = zone not in self.selected
            if self._drag_add:
                self.selected.add(zone)
            else:
                self.selected.discard(zone)
        else:
            self.selected = set() if self.selected == {zone} else {zone}
            self._drag_add = None
        self.selectionChanged.emit(sorted(self.selected))
        self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        zone = self._zone_at(event.position())
        if zone != self._hover:
            self._hover = zone
            if zone is not None and self.device:
                zones = self.device.get("zones") or []
                name = zones[zone]["name"] if zone < len(zones) else ""
                self.setToolTip(name)
            self.update()
        if self._drag_add is not None and zone is not None and event.buttons() & Qt.MouseButton.LeftButton:
            changed = (zone not in self.selected) if self._drag_add else (zone in self.selected)
            if changed:
                (self.selected.add if self._drag_add else self.selected.discard)(zone)
                self.selectionChanged.emit(sorted(self.selected))
                self.update()

    def mouseReleaseEvent(self, _event) -> None:  # noqa: N802
        self._drag_add = None

    def leaveEvent(self, _event) -> None:  # noqa: N802
        self._hover = None
        self.update()
