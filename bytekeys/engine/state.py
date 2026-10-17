"""Lighting state: defaults and validation of anything a client sends us.

The daemon runs as root and takes input from unprivileged clients, so every
value is checked and normalized here before it can reach the hardware.
"""

from __future__ import annotations

import copy
import re

from ..color import normalize

DEFAULT_STATE: dict = {
    "on": True,
    "brightness": 100,        # percent
    "color": "#ffffff",       # base color for RGB keyboards
    "zones": None,            # per-zone colors, or None when every zone uses "color"
    "effect": "static",       # software effect id, or "hw:<id>" for firmware effects
    "params": {},
    "effect_colors": [],
}

DEFAULT_SETTINGS: dict = {
    "restore_on_boot": True,
    "save_to_firmware": False,
    "fps": 30,
    "openrgb": True,
    "openrgb_host": "127.0.0.1",
    "openrgb_port": 6742,
    "openrgb_all_devices": False,
}

MAX_ZONES = 512
MAX_NAME = 60


def as_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def as_int(value, lo: int, hi: int) -> int:
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        raise ValueError(f"not a number: {value!r}") from None
    return max(lo, min(hi, n))


def clean_name(value) -> str:
    name = re.sub(r"[\x00-\x1f\x7f]", "", str(value)).strip()
    if not name:
        raise ValueError("name must not be empty")
    return name[:MAX_NAME]


def clean_params(value) -> dict:
    if not isinstance(value, dict):
        raise ValueError("params must be an object")
    out = {}
    for k, v in list(value.items())[:16]:
        key = str(k)[:32]
        if isinstance(v, bool) or v is None:
            out[key] = v
        elif isinstance(v, (int, float)):
            out[key] = max(-1_000_000, min(1_000_000, v))
        else:
            out[key] = str(v)[:64]
    return out


def zone_count(desc: dict) -> int:
    mode = desc.get("color_mode", "none")
    if mode == "none":
        return 0
    if mode == "single":
        return 1
    return len(desc.get("zones") or [])


def clean_state(changes: dict, desc: dict, base: dict | None, effect_ids: set[str]) -> dict:
    """Merge validated *changes* into *base* for the device described by *desc*."""
    if not isinstance(changes, dict):
        raise ValueError("state changes must be an object")
    s = copy.deepcopy(base) if base else copy.deepcopy(DEFAULT_STATE)
    for key, value in DEFAULT_STATE.items():
        s.setdefault(key, copy.deepcopy(value))
    n = min(zone_count(desc), MAX_ZONES)

    if "on" in changes:
        s["on"] = as_bool(changes["on"])
    if "brightness" in changes:
        s["brightness"] = as_int(changes["brightness"], 0, 100)
    if "color" in changes:
        s["color"] = normalize(changes["color"])
        if "zones" not in changes:
            s["zones"] = None
    if "zones" in changes:
        zones = changes["zones"]
        if zones is None:
            s["zones"] = None
        elif isinstance(zones, dict):
            current = list(s["zones"] or [])
            current = (current + [s["color"]] * n)[:n]
            for k, v in zones.items():
                i = int(k)
                if 0 <= i < n:
                    current[i] = normalize(v)
            s["zones"] = current
        elif isinstance(zones, list):
            current = [normalize(v) for v in zones[:n]]
            s["zones"] = current + [s["color"]] * (n - len(current))
        else:
            raise ValueError("zones must be a list, an object or null")
    if "effect" in changes:
        effect = str(changes["effect"])
        if effect not in effect_ids:
            raise ValueError(f"effect {effect!r} is not available on this device")
        s["effect"] = effect
    if "params" in changes:
        s["params"] = {**s.get("params", {}), **clean_params(changes["params"])}
    if "effect_colors" in changes:
        colors = changes["effect_colors"] or []
        if not isinstance(colors, list):
            raise ValueError("effect_colors must be a list")
        s["effect_colors"] = [normalize(c) for c in colors[:8]]

    if n == 0:
        s["zones"] = None
    elif s["zones"] is not None and len(s["zones"]) != n:
        s["zones"] = (list(s["zones"]) + [s["color"]] * n)[:n]
    if s["effect"] not in effect_ids:
        s["effect"] = "static"
    return s


def clean_settings(changes: dict, current: dict) -> dict:
    if not isinstance(changes, dict):
        raise ValueError("settings must be an object")
    out = copy.deepcopy(current)
    for key, value in changes.items():
        if key not in DEFAULT_SETTINGS:
            raise ValueError(f"unknown setting {key!r}")
        default = DEFAULT_SETTINGS[key]
        if isinstance(default, bool):
            out[key] = as_bool(value)
        elif key == "fps":
            out[key] = as_int(value, 5, 60)
        elif key == "openrgb_port":
            out[key] = as_int(value, 1, 65535)
        elif key == "openrgb_host":
            host = str(value).strip()
            if not re.fullmatch(r"[A-Za-z0-9.\-:\[\]]{1,253}", host):
                raise ValueError("invalid host name")
            out[key] = host
        else:
            out[key] = value
    return out
