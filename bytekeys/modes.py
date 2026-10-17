"""Quick lighting modes (Static, Breathing, Color cycle...) and effect selection."""

from __future__ import annotations

# (mode id, label, keywords matched against effect ids/names)
QUICK_MODES = [
    ("static", "Static", ()),
    ("breathing", "Breathing", ("breath",)),
    ("cycle", "Color cycle", ("cycle", "spectrum", "smooth", "rainbow")),
    ("wave", "Wave", ("wave",)),
    ("strobe", "Strobe", ("strobe", "flash", "blink")),
]
FALLBACK = {"breathing": "breathing", "cycle": "spectrum", "wave": "wave", "strobe": "blink"}

PALETTE = ["#00a0ff", "#ff2d92", "#34c759", "#ffcc00"]


def _matches(effect: dict, words: tuple[str, ...], exclude: tuple[str, ...] = ()) -> bool:
    text = (effect["id"] + " " + effect["name"]).lower()
    return any(w in text for w in words) and not any(x in text for x in exclude)


def quick_modes(dev: dict) -> list[tuple[str, str, str]]:
    """(mode id, label, effect id) for the modes this keyboard can do, hardware preferred."""
    effects = dev.get("effects") or []
    ids = {e["id"] for e in effects}
    out = []
    for mode, text, words in QUICK_MODES:
        if mode == "static":
            out.append((mode, text, "static"))
            continue
        exclude = ("wave",) if mode == "cycle" else ()
        hw = next((e for e in effects if e["hardware"] and _matches(e, words, exclude)), None)
        if hw:
            out.append((mode, text, hw["id"]))
        elif FALLBACK[mode] in ids and mode != "strobe":
            out.append((mode, text, FALLBACK[mode]))
    return out


def mode_of(dev: dict) -> str | None:
    effect = dev["state"]["effect"]
    for mode, _text, eid in quick_modes(dev):
        if eid == effect:
            return mode
    return None


def _valid(param: dict, value) -> bool:
    kind = param.get("kind", "range")
    if value is None:
        return False
    if kind == "range":
        return isinstance(value, (int, float)) and param.get("min", 0) <= value <= param.get("max", 100)
    if kind == "choice":
        return str(value) in [str(c[0]) for c in param.get("choices", [])]
    if kind == "bool":
        return isinstance(value, bool)
    return True


def effect_changes(dev: dict, effect: dict) -> dict:
    """State changes that switch *dev* to *effect*, keeping compatible settings."""
    st = dev["state"]
    params = {}
    for p in effect["params"]:
        value = st.get("params", {}).get(p["id"])
        params[p["id"]] = value if _valid(p, value) else p.get("default")
    changes: dict = {"effect": effect["id"], "on": True, "params": params}
    if effect.get("colors"):
        colors = list(st.get("effect_colors") or [])
        base = st.get("zones") or [st["color"]]
        if not colors:
            colors.append(base[0])
        while len(colors) < effect["colors"]:
            colors.append(PALETTE[len(colors) % len(PALETTE)])
        changes["effect_colors"] = colors[:effect["colors"]]
    return changes


def speed_param(effect: dict | None) -> dict | None:
    if not effect:
        return None
    return next((p for p in effect["params"] if p["id"] == "speed"), None)
