"""Automation rules ("custom functions"): when <trigger> then <action>.

Rules are evaluated continuously. While a rule's trigger holds, its action
is layered on top of the user's chosen lighting; when the trigger stops
holding, the lighting goes back. Rules apply top to bottom, so later rules
win where they touch the same setting.
"""

from __future__ import annotations

import copy
import re
import uuid
from dataclasses import asdict
from datetime import datetime

from ..color import gradient, normalize, parse, to_hex
from ..hw.base import SPEED, Param
from .state import as_bool, as_int, clean_name

TRIGGERS: dict[str, dict] = {
    "always": {"name": "Always", "params": [], "sensor": None},
    "power": {
        "name": "Power source is",
        "params": [Param("source", "Source", "choice", default="battery",
                         choices=[["battery", "On battery"], ["ac", "Plugged in"]])],
        "sensor": "power",
    },
    "battery": {
        "name": "Battery is below",
        "params": [Param("level", "Level (%)", "range", default=20, min=1, max=99)],
        "sensor": "battery",
    },
    "time": {
        "name": "Time is between",
        "params": [Param("start", "From", "time", default="22:00"),
                   Param("end", "Until", "time", default="07:00")],
        "sensor": None,
    },
    "idle": {
        "name": "No keyboard or mouse input for",
        "params": [Param("seconds", "Seconds", "range", default=60, min=5, max=3600)],
        "sensor": "idle",
    },
    "capslock": {"name": "Caps Lock is on", "params": [], "sensor": "capslock"},
    "temperature": {
        "name": "CPU is hotter than",
        "params": [Param("celsius", "Temperature (°C)", "range", default=85, min=40, max=105)],
        "sensor": "temperature",
    },
    "cpu": {
        "name": "CPU load is above",
        "params": [Param("percent", "Load (%)", "range", default=80, min=5, max=100)],
        "sensor": "cpu",
    },
    "dark": {
        "name": "Room is darker than",
        "params": [Param("lux", "Light level (lux)", "range", default=20, min=1, max=1000)],
        "sensor": "ambient",
    },
}

ACTIONS: dict[str, dict] = {
    "off": {"name": "Turn the lights off", "params": []},
    "brightness": {
        "name": "Set brightness",
        "params": [Param("value", "Brightness (%)", "range", default=40, min=0, max=100)],
    },
    "color": {
        "name": "Set color",
        "params": [Param("color", "Color", "color", default="#ff3030")],
        "rgb": True,
    },
    "effect": {
        "name": "Play an effect",
        "params": [Param("effect", "Effect", "effect", default="breathing"), SPEED],
    },
    "profile": {
        "name": "Switch to profile",
        "params": [Param("profile", "Profile", "profile", default="")],
    },
    "alert": {
        "name": "Flash as a warning",
        "params": [Param("color", "Color", "color", default="#ff0000"),
                   Param("style", "Style", "choice", default="pulse",
                         choices=[["pulse", "Pulse"], ["blink", "Blink"]]),
                   Param("speed", "Speed", "range", default=60)],
    },
    "temperature_color": {
        "name": "Color by CPU temperature",
        "params": [Param("low", "Cool at (°C)", "range", default=45, min=20, max=90),
                   Param("high", "Hot at (°C)", "range", default=90, min=40, max=110),
                   Param("cool", "Cool color", "color", default="#00a0ff"),
                   Param("hot", "Hot color", "color", default="#ff2000")],
        "rgb": True,
        "sensor": "temperature",
    },
    "battery_color": {
        "name": "Color by battery level",
        "params": [],
        "rgb": True,
        "sensor": "battery",
    },
    "cpu_color": {
        "name": "Color by CPU load",
        "params": [Param("idle", "Idle color", "color", default="#00ff80"),
                   Param("busy", "Busy color", "color", default="#ff0040")],
        "rgb": True,
        "sensor": "cpu",
    },
}

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def catalog() -> dict:
    """Trigger and action definitions for building rule editors."""
    def spec(table):
        return {
            k: {"name": v["name"], "params": [asdict(p) for p in v["params"]],
                "sensor": v.get("sensor"), "rgb": v.get("rgb", False)}
            for k, v in table.items()
        }
    return {"triggers": spec(TRIGGERS), "actions": spec(ACTIONS)}


def _clean_part(raw, table: dict, what: str) -> dict:
    if not isinstance(raw, dict) or raw.get("type") not in table:
        raise ValueError(f"unknown {what}: {raw!r}")
    kind = raw["type"]
    out: dict = {"type": kind}
    for p in table[kind]["params"]:
        value = raw.get(p.id, p.default)
        if p.kind == "range":
            out[p.id] = as_int(value, p.min, p.max)
        elif p.kind == "bool":
            out[p.id] = as_bool(value)
        elif p.kind == "choice":
            valid = [c[0] for c in p.choices]
            out[p.id] = value if value in valid else p.default
        elif p.kind == "color":
            out[p.id] = normalize(value)
        elif p.kind == "time":
            text = str(value).strip()
            if not _TIME_RE.match(text):
                raise ValueError(f"invalid time {value!r}, expected HH:MM")
            h, m = text.split(":")
            out[p.id] = f"{int(h):02d}:{m}"
        else:  # "effect" / "profile": free text, validated when applied
            out[p.id] = str(value)[:64]
    return out


def clean_rule(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("a rule must be an object")
    rid = str(raw.get("id") or uuid.uuid4().hex[:10])
    if not re.fullmatch(r"[A-Za-z0-9_\-]{1,40}", rid):
        raise ValueError(f"invalid rule id {rid!r}")
    rule = {
        "id": rid,
        "name": clean_name(raw.get("name") or "Rule"),
        "enabled": as_bool(raw.get("enabled", True)),
        "trigger": _clean_part(raw.get("trigger"), TRIGGERS, "trigger"),
        "action": _clean_part(raw.get("action"), ACTIONS, "action"),
        "target": str(raw.get("target") or "all")[:120],
    }
    return rule


def clean_rules(raw) -> list[dict]:
    if not isinstance(raw, list):
        raise ValueError("rules must be a list")
    rules = [clean_rule(r) for r in raw[:100]]
    ids = [r["id"] for r in rules]
    if len(ids) != len(set(ids)):
        raise ValueError("rule ids must be unique")
    return rules


def needed_sensors(rules: list[dict]) -> set[str]:
    out: set[str] = set()
    for r in rules:
        if not r.get("enabled"):
            continue
        for part, table in ((r["trigger"], TRIGGERS), (r["action"], ACTIONS)):
            sensor = table[part["type"]].get("sensor")
            if sensor:
                out.add(sensor)
    return out


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def holds(trigger: dict, snap, was_active: bool, now: datetime | None = None) -> bool:
    """Whether *trigger* currently holds. Thresholds use a little hysteresis."""
    kind = trigger["type"]
    if kind == "always":
        return True
    if kind == "power":
        if snap.ac_online is None:
            return False
        return snap.ac_online if trigger["source"] == "ac" else not snap.ac_online
    if kind == "battery":
        if snap.battery is None or snap.charging:
            return False
        limit = trigger["level"] + (2 if was_active else 0)
        return snap.battery < limit
    if kind == "time":
        now = now or datetime.now()
        cur = now.hour * 60 + now.minute
        start, end = _minutes(trigger["start"]), _minutes(trigger["end"])
        if start == end:
            return True
        if start < end:
            return start <= cur < end
        return cur >= start or cur < end
    if kind == "idle":
        return snap.idle is not None and snap.idle >= trigger["seconds"]
    if kind == "capslock":
        return bool(snap.capslock)
    if kind == "temperature":
        if snap.temperature is None:
            return False
        return snap.temperature > trigger["celsius"] - (3 if was_active else 0)
    if kind == "cpu":
        if snap.cpu is None:
            return False
        return snap.cpu > trigger["percent"] - (5 if was_active else 0)
    if kind == "dark":
        if snap.lux is None:
            return False
        return snap.lux < trigger["lux"] * (1.5 if was_active else 1.0)
    return False


def override(action: dict, desc: dict, snap, profiles: dict, effect_ids: set[str]) -> dict | None:
    """The partial lighting state an active rule imposes on one device."""
    kind = action["type"]
    rgb = desc.get("color_mode", "none") != "none"
    if kind == "off":
        return {"on": False}
    if kind == "brightness":
        return {"brightness": action["value"]}
    if kind == "color":
        return {"color": action["color"], "zones": None} if rgb else None
    if kind == "effect":
        effect = action["effect"]
        if effect not in effect_ids:
            return None
        return {"effect": effect, "params": {"speed": action.get("speed", 50)}}
    if kind == "profile":
        prof = profiles.get(action["profile"])
        state = prof and prof.get("devices", {}).get(desc["id"])
        return copy.deepcopy(state) if state else None
    if kind == "alert":
        ov = {"on": True, "brightness": 100, "params": {"speed": action["speed"]},
              "effect": "breathing" if action["style"] == "pulse" else "blink"}
        if rgb:
            ov.update({"color": action["color"], "zones": None})
        return ov
    if not rgb:
        return None
    if kind == "temperature_color":
        if snap.temperature is None:
            return None
        lo, hi = action["low"], max(action["high"], action["low"] + 1)
        t = (snap.temperature - lo) / (hi - lo)
        color = gradient([parse(action["cool"]), parse(action["hot"])], t)
        return {"color": to_hex(color), "zones": None}
    if kind == "battery_color":
        if snap.battery is None:
            return None
        color = gradient([(255, 0, 0), (255, 200, 0), (0, 255, 60)], snap.battery / 100.0)
        return {"color": to_hex(color), "zones": None}
    if kind == "cpu_color":
        if snap.cpu is None:
            return None
        color = gradient([parse(action["idle"]), parse(action["busy"])], snap.cpu / 100.0)
        return {"color": to_hex(color), "zones": None}
    return None


def default_rules(rgb: bool) -> list[dict]:
    """Ready-made rules offered on first run, all disabled until the user opts in."""
    rules = [
        {"id": "idle-off", "name": "Turn off when idle", "enabled": False,
         "trigger": {"type": "idle", "seconds": 120}, "action": {"type": "off"}},
        {"id": "battery-dim", "name": "Dim on battery", "enabled": False,
         "trigger": {"type": "power", "source": "battery"},
         "action": {"type": "brightness", "value": 40}},
        {"id": "night", "name": "Night mode", "enabled": False,
         "trigger": {"type": "time", "start": "22:00", "end": "07:00"},
         "action": {"type": "profile", "profile": "Night"}},
        {"id": "low-battery", "name": "Low battery warning", "enabled": False,
         "trigger": {"type": "battery", "level": 15},
         "action": {"type": "alert", "color": "#ff0000", "style": "pulse", "speed": 60}},
    ]
    if rgb:
        rules += [
            {"id": "capslock", "name": "Caps Lock indicator", "enabled": False,
             "trigger": {"type": "capslock"}, "action": {"type": "color", "color": "#ff2a2a"}},
            {"id": "hot-cpu", "name": "Overheat warning", "enabled": False,
             "trigger": {"type": "temperature", "celsius": 90},
             "action": {"type": "alert", "color": "#ff6a00", "style": "pulse", "speed": 70}},
        ]
    return clean_rules(rules)
