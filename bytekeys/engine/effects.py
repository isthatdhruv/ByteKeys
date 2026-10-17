"""Software effects rendered by the engine.

Unlike hardware effects these work on every keyboard: a renderer produces a
brightness factor and per-zone colors for any point in time, and the engine
maps that onto whatever the device can do (on a white backlight "breathing"
steps through the brightness levels, on RGB it fades the colors smoothly).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from ..color import RGB, gradient, hsv, lerp, scale
from ..hw.base import DIRECTION, SPEED, EffectInfo, Param

STATIC = EffectInfo("static", "Static", description="Solid lighting, no animation")
BREATHING = EffectInfo("breathing", "Breathing", params=[SPEED],
                       description="Gently fades in and out")
BLINK = EffectInfo("blink", "Blink", params=[SPEED], description="Switches on and off")
SPECTRUM = EffectInfo("spectrum", "Color cycle", params=[SPEED],
                      description="Cycles smoothly through every color")
WAVE = EffectInfo("wave", "Rainbow wave", params=[SPEED, DIRECTION],
                  description="A rainbow that travels across the keyboard")
GRADIENT = EffectInfo("gradient", "Gradient", colors=2,
                      params=[Param("animate", "Animate", "bool", default=False), SPEED],
                      description="Blend between two colors across the keyboard")
STARLIGHT = EffectInfo("starlight", "Starlight",
                       params=[SPEED, Param("density", "Density", "range", default=35)],
                       description="Keys twinkle in random colors")
REACTIVE = EffectInfo("reactive", "Reactive",
                      params=[Param("fade", "Fade speed", "range", default=50),
                              Param("rest", "Resting brightness", "range", default=15)],
                      description="Lights up while you type, fades when you stop")
CANDLE = EffectInfo("candle", "Candle", params=[SPEED],
                    description="Warm, flickering candle light")

ALL = [STATIC, BREATHING, BLINK, SPECTRUM, WAVE, GRADIENT, STARLIGHT, REACTIVE, CANDLE]
BY_ID = {e.id: e for e in ALL}
ANIMATED = {"breathing", "blink", "spectrum", "wave", "starlight", "reactive", "candle"}


def available(color_mode: str, zones: int, input_activity: bool) -> list[EffectInfo]:
    """Software effects that make sense for a device."""
    rgb = color_mode != "none"
    out = [STATIC, BREATHING, BLINK]
    if rgb:
        out.append(SPECTRUM)
    if rgb and zones >= 2:
        out += [WAVE, GRADIENT]
    if rgb and zones >= 6:
        out.append(STARLIGHT)
    if input_activity:
        out.append(REACTIVE)
    out.append(CANDLE)
    return out


def _speed(params: dict, default: int = 50) -> float:
    try:
        return max(0.0, min(100.0, float(params.get("speed", default)))) / 100.0
    except (TypeError, ValueError):
        return default / 100.0


def _span(params: dict, slow: float, fast: float) -> float:
    return slow + (fast - slow) * _speed(params)


@dataclass
class Context:
    """Live inputs a renderer may react to."""

    last_key: float | None = None   # seconds since engine start of the last key press


class Renderer:
    def __init__(self, effect: str, params: dict, colors: list[RGB],
                 effect_colors: list[RGB], positions: list[float], start: float = 0.0):
        self.effect = effect if effect in BY_ID else "static"
        self.start = start          # periodic effects begin at phase 0 from here
        self.params = params or {}
        self.colors = colors or [(255, 255, 255)]
        self.effect_colors = effect_colors
        self.positions = positions or [0.0]
        self.animated = self.effect in ANIMATED or (
            self.effect == "gradient" and bool(self.params.get("animate"))
        )
        self._stars: list[tuple[float, float]] = []   # (start time, hue) per zone
        self._flame = 0.8
        self._last_t = 0.0
        self._rng = random.Random(7)

    @property
    def n(self) -> int:
        return len(self.positions)

    def _base(self) -> list[RGB]:
        n = self.n
        c = self.colors
        return [c[i] if i < len(c) else c[-1] for i in range(n)]

    def frame(self, t: float, ctx: Context | None = None) -> tuple[float, list[RGB]]:
        """Brightness factor in [0, 1] and one color per zone at time *t* (seconds)."""
        fn = getattr(self, "_" + self.effect)
        if self.effect != "reactive":   # reactive compares t with absolute key times
            t = t - self.start
        return fn(t, ctx or Context())

    # ------------------------------------------------------------- effects
    def _static(self, t, ctx):
        return 1.0, self._base()

    def _breathing(self, t, ctx):
        period = _span(self.params, 7.0, 1.2)
        phase = (t % period) / period
        level = (1 - math.cos(2 * math.pi * phase)) / 2
        return level ** 1.6, self._base()

    def _blink(self, t, ctx):
        period = float(self.params.get("period") or _span(self.params, 2.0, 0.25))
        return (1.0 if (t % period) < period / 2 else 0.0), self._base()

    def _spectrum(self, t, ctx):
        period = _span(self.params, 30.0, 3.0)
        return 1.0, [hsv(t / period)] * self.n

    def _wave(self, t, ctx):
        period = _span(self.params, 12.0, 1.5)
        sign = -1.0 if self.params.get("direction") == "left" else 1.0
        return 1.0, [hsv(t / period - sign * p * 0.8) for p in self.positions]

    def _gradient(self, t, ctx):
        stops = self.effect_colors[:2] if len(self.effect_colors) >= 2 else [self.colors[0], (0, 120, 255)]
        if self.params.get("animate"):
            # Slide the gradient back and forth (triangle wave keeps it seamless).
            phase = t / _span(self.params, 10.0, 1.5)
            return 1.0, [gradient(stops, 1 - abs(((p + phase) % 2.0) - 1)) for p in self.positions]
        return 1.0, [gradient(stops, p) for p in self.positions]

    def _starlight(self, t, ctx):
        n = self.n
        if len(self._stars) != n:
            self._stars = [(-10.0, 0.0)] * n
        dt = max(0.0, min(0.5, t - self._last_t))
        self._last_t = t
        density = float(self.params.get("density", 35)) / 100.0
        life = _span(self.params, 2.5, 0.5)
        spawn = density * n * dt / life * 0.6
        while spawn > 0:
            if self._rng.random() < spawn:
                self._stars[self._rng.randrange(n)] = (t, self._rng.random())
            spawn -= 1
        base = [scale(c, 0.12) for c in self._base()]
        out = []
        for i, (start, hue) in enumerate(self._stars):
            age = (t - start) / life
            if 0 <= age < 1:
                glow = math.sin(math.pi * age)
                out.append(lerp(base[i], hsv(hue, 0.7, 1.0), glow))
            else:
                out.append(base[i])
        return 1.0, out

    def _reactive(self, t, ctx):
        rest = max(0.0, min(1.0, float(self.params.get("rest", 15)) / 100.0))
        fade = 0.4 + (1 - float(self.params.get("fade", 50)) / 100.0) * 3.0
        if ctx.last_key is None:
            return rest, self._base()
        since = t - ctx.last_key
        boost = max(0.0, 1.0 - since / fade) if since >= 0 else 1.0
        return rest + (1 - rest) * boost, self._base()

    def _candle(self, t, ctx):
        dt = max(0.0, min(0.5, t - self._last_t))
        self._last_t = t
        jitter = _span(self.params, 0.6, 2.5)
        target = 0.55 + 0.45 * self._rng.random()
        self._flame += (target - self._flame) * min(1.0, dt * jitter * 6)
        base = self._base()
        if all(c == (255, 255, 255) for c in base):
            base = [(255, 140, 40)] * self.n   # plain white gets a warm flame color
        return self._flame, base
