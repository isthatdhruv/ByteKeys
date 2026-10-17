"""Shared keyboard actions for the pages: brightness, power, colors and modes."""

from __future__ import annotations

from .. import modes
from .qt import QtCore


class DeviceControl(QtCore.QObject):
    """Turns UI gestures into state changes, batching rapid ones (slider drags)."""

    def __init__(self, page):
        super().__init__(page)
        self.page = page
        self.bridge = page.bridge
        self._pending: dict = {}
        self._dev_id: str | None = None
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(70)
        self._timer.timeout.connect(self.flush)

    def device(self) -> dict | None:
        return self.page.device()

    @property
    def busy(self) -> bool:
        return bool(self._pending)

    def queue(self, changes: dict) -> None:
        dev = self.device()
        if not dev:
            return
        if self._dev_id != dev["id"]:
            self.flush()
            self._dev_id = dev["id"]
        self._pending.update(changes)
        self._timer.start()

    def flush(self) -> None:
        self._timer.stop()
        if self._pending and self._dev_id:
            changes, self._pending = self._pending, {}
            self.bridge.set_state(self._dev_id, changes)

    def cancel(self) -> None:
        self._timer.stop()
        self._pending = {}

    # ----------------------------------------------------------- brightness
    @staticmethod
    def slider_range(dev: dict) -> tuple[int, list[str] | None]:
        """(top value, labels) for a brightness slider."""
        levels = dev.get("levels")
        if levels:
            return dev["brightness_max"], list(levels)
        return 100, None

    @staticmethod
    def slider_value(dev: dict) -> int:
        st = dev["effective"]
        top, levels = DeviceControl.slider_range(dev)
        pct = st["brightness"] if st["on"] else 0
        if levels:
            return max(1, round(pct / 100 * top)) if pct > 0 else 0
        return pct

    @staticmethod
    def level_text(dev: dict, value: int) -> str:
        top, levels = DeviceControl.slider_range(dev)
        if value <= 0:
            return "Off"
        if levels:
            return levels[min(value, len(levels) - 1)]
        return f"{value}%"

    def set_slider(self, value: int, final: bool = False) -> None:
        dev = self.device()
        if not dev:
            return
        top, levels = self.slider_range(dev)
        pct = int(round(value * 100 / max(1, top))) if levels else int(value)
        self.queue({"on": pct > 0, **({"brightness": pct} if pct > 0 else {})})
        if final:
            self.flush()

    def set_power(self, on: bool) -> None:
        dev = self.device()
        if not dev:
            return
        changes: dict = {"on": on}
        if on and dev["state"]["brightness"] == 0:
            changes["brightness"] = 100
        self.queue(changes)
        self.flush()

    # ---------------------------------------------------------------- color
    def color_changes(self, color: str, zones: list[int] | None = None) -> dict:
        dev = self.device()
        if not dev:
            return {}
        st = dev["state"]
        changes: dict = {"on": True}
        if zones:
            changes["zones"] = {str(i): color for i in zones}
        else:
            changes["color"] = color
        effect = next((e for e in dev["effects"] if e["id"] == st["effect"]), None)
        if effect and effect["hardware"]:
            if effect.get("colors"):
                changes["effect_colors"] = [color] + list(st.get("effect_colors") or [])[1:effect["colors"]]
            else:
                changes["effect"] = "static"   # e.g. a firmware rainbow cannot show one color
        return changes

    def preview_color(self, color: str, zones: list[int] | None = None) -> None:
        """Live update while a color is being dragged."""
        changes = self.color_changes(color, zones)
        if changes:
            self.queue(changes)

    def apply_color(self, color: str, zones: list[int] | None = None) -> None:
        changes = self.color_changes(color, zones)
        if changes:
            self.queue(changes)
            self.flush()

    # ---------------------------------------------------------------- modes
    def choose_effect(self, effect_id: str) -> None:
        dev = self.device()
        if not dev:
            return
        effect = next((e for e in dev["effects"] if e["id"] == effect_id), None)
        if effect:
            self.flush()
            self.bridge.set_state(dev["id"], modes.effect_changes(dev, effect))


MODE_ICONS = {"static": "sun", "breathing": "pulse", "cycle": "palette", "wave": "wave", "strobe": "sparkle"}
KIND_TEXT = {"none": "Single color", "single": "RGB", "zones": "{n}-zone RGB", "perkey": "Per-key RGB"}
BACKEND_TEXT = {"sysfs": "Kernel driver", "hid": "USB", "openrgb": "OpenRGB", "demo": "Simulated"}


def kind_text(dev: dict) -> str:
    return KIND_TEXT[dev["color_mode"]].format(n=len(dev.get("zones") or []))


def effect_icon(effect: dict) -> str:
    text = (effect["id"] + " " + effect["name"]).lower()
    for words, icon in ((("static",), "sun"), (("breath", "pulse"), "pulse"),
                        (("cycle", "spectrum", "smooth", "rainbow", "hue"), "palette"), (("wave",), "wave"),
                        (("strobe", "flash", "blink"), "sparkle"), (("candle", "fire"), "flame"),
                        (("star", "twinkle", "rain"), "sparkle"), (("react", "ripple", "type"), "keyboard"),
                        (("gradient",), "layers")):
        if any(w in text for w in words):
            return icon
    return "sparkle"
