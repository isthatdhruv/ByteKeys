"""The lighting engine.

The engine owns every device, the user's chosen lighting per device, the
automation rules and the profiles. A single render thread turns all of that
into frames and pushes them to the hardware; the public methods (called from
IPC handler threads or directly by the GUI in portable mode) only change
state and wake the render thread.
"""

from __future__ import annotations

import copy
import logging
import math
import os
import threading
import time
from typing import Callable

from .. import __version__, fsroot, models, sysinfo
from ..color import RGB, normalize, parse, scale
from ..hw import registry
from ..hw.base import AccessError, Device, DeviceError, Frame
from . import effects
from . import rules as rules_mod
from .effects import Context, Renderer
from .inputwatch import InputWatcher
from .sensors import Sensors, SessionIdle, Snapshot
from .state import (
    DEFAULT_SETTINGS,
    DEFAULT_STATE,
    as_bool,
    as_int,
    clean_name,
    clean_settings,
    clean_state,
    zone_count,
)
from .store import Store

log = logging.getLogger(__name__)

Listener = Callable[[str, dict], None]

PERSIST_DELAY = 2.5      # seconds a look must stay unchanged before saving it to firmware
SAVE_DELAY = 1.0
SENSOR_PERIOD = 1.0
POLL_PERIOD = 1.0
RESCAN_PERIOD = 20.0


def _round(x: float) -> int:
    """Round half up (Python's round() rounds half to even)."""
    return int(math.floor(x + 0.5))


class _Writer(threading.Thread):
    """Pushes frames to one device. The newest frame wins, so a slow controller
    (some need a second per change) never holds up the other keyboards."""

    def __init__(self, engine: "Engine", dev: Device):
        super().__init__(name=f"bytekeys-io-{dev.id}", daemon=True)
        self.engine = engine
        self.dev = dev
        self.io = threading.Lock()          # serializes every access to the device
        self._cond = threading.Condition()
        self._pending: tuple[Frame, bool] | None = None
        self._stopped = False
        self.last_write = 0.0

    @property
    def busy(self) -> bool:
        return self._pending is not None

    def submit(self, frame: Frame, force: bool) -> None:
        with self._cond:
            force = force or bool(self._pending and self._pending[1])
            self._pending = (frame, force)
            self._cond.notify()

    def stop(self) -> None:
        with self._cond:
            self._stopped = True
            self._cond.notify()

    def run(self) -> None:
        while True:
            with self._cond:
                while self._pending is None and not self._stopped:
                    self._cond.wait()
                if self._stopped:
                    return
                frame, force = self._pending
                self._pending = None
            self.engine._write(self, frame, force)


class Engine:
    def __init__(self, state_dir: str, *, privileged: bool = False, demo: bool = False,
                 mode: str = "service", watch_input: bool | None = None, restore: bool = True,
                 discovery: Callable[[registry.Options], list[Device]] | None = None):
        self.state_dir = state_dir
        self.store = Store(os.path.join(state_dir, "state.json"))
        self.privileged = privileged
        self.demo = demo
        self.mode = mode
        # Re-apply the saved lighting on start (service boot, GUI at login). One-shot
        # CLI runs turn this off so they only change what they were asked to.
        self.restore = restore
        self._saved_states: dict[str, dict] = {}
        self._discovery = discovery or registry.discover
        self.lock = threading.RLock()
        self.devices: dict[str, Device] = {}
        self.desc: dict[str, dict] = {}
        self.states: dict[str, dict] = {}
        self.effective: dict[str, dict] = {}
        self.touched: set[str] = set()
        self.rules: list[dict] = []
        self.profiles: dict[str, dict] = {}
        self.settings: dict = copy.deepcopy(DEFAULT_SETTINGS)
        self.feature_values: dict[str, dict] = {}
        self.first_run = False
        self.snapshot = Snapshot()
        self.active_rules: set[str] = set()
        self.suppressed: set[tuple[str, str]] = set()
        self.flash_state: dict | None = None
        self.sysinfo = sysinfo.summary()

        self._listeners: list[Listener] = []
        self._events: list[tuple[str, dict]] = []
        self._events_lock = threading.Lock()
        self._renderers: dict[str, tuple[tuple, Renderer]] = {}
        self._writers: dict[str, _Writer] = {}
        self._submitted: dict[str, Frame | None] = {}
        self._force_devices: set[str] = set()
        self._started_at = time.monotonic()
        self._written_level: dict[str, int] = {}
        self._next_push: dict[str, float] = {}
        self._persist_due: dict[str, float] = {}
        self._save_due: float | None = None
        self._force_push_at: float | None = None
        self._rescan_due: float | None = None
        self._sensor_now = True
        self._signature: tuple = ()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.t0 = time.monotonic()

        self.input: InputWatcher | None = None
        if watch_input is None:
            watch_input = privileged
        if watch_input:
            self.input = InputWatcher(on_wake=self._input_wake)
        idle_source = self.input.idle_seconds if self.input else None
        if idle_source is None and mode == "portable":
            session_idle = SessionIdle()
            idle_source = session_idle if session_idle.ok else None
        self.sensors = Sensors(idle_source)

    # ================================================================ lifecycle
    def start(self) -> None:
        data = self.store.load()
        self.first_run = not data
        with self.lock:
            try:
                self.settings = clean_settings(data.get("settings", {}), DEFAULT_SETTINGS)
            except ValueError:
                self.settings = copy.deepcopy(DEFAULT_SETTINGS)
            try:
                self.rules = rules_mod.clean_rules(data.get("rules", []))
            except ValueError:
                log.warning("stored rules are invalid; ignoring them")
                self.rules = []
            self.profiles = {k: v for k, v in data.get("profiles", {}).items()
                             if isinstance(v, dict) and isinstance(v.get("devices"), dict)}
            self.feature_values = {k: v for k, v in data.get("features", {}).items() if isinstance(v, dict)}
            self._saved_states = {k: v for k, v in data.get("devices", {}).items() if isinstance(v, dict)}
        if self.input and not self.input.available():
            log.info("no readable input devices; idle detection disabled")
            self.input = None
            self.sensors.idle_source = None
        self._discover(initial=True)
        if self.first_run:
            self._auto_config()
        if self.input:
            self.input.start()
        self._thread = threading.Thread(target=self._run, name="bytekeys-engine", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=3)
        if self.input:
            self.input.stop()
        with self.lock:
            self._save()
            writers = list(self._writers.values())
            self._writers = {}
        for writer in writers:
            writer.stop()
            with writer.io:
                writer.dev.close()

    # ================================================================== events
    def subscribe(self, listener: Listener) -> None:
        with self._events_lock:
            self._listeners.append(listener)

    def unsubscribe(self, listener: Listener) -> None:
        with self._events_lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def _emit(self, kind: str, data: dict) -> None:
        with self._events_lock:
            self._events.append((kind, data))

    def _flush(self) -> None:
        with self._events_lock:
            events, self._events = self._events, []
            listeners = list(self._listeners)
        for kind, data in events:
            for listener in listeners:
                try:
                    listener(kind, data)
                except Exception:
                    log.exception("event listener failed")

    # =============================================================== discovery
    def _discovery_options(self) -> registry.Options:
        return registry.Options(
            openrgb=self.settings["openrgb"],
            openrgb_host=self.settings["openrgb_host"],
            openrgb_port=self.settings["openrgb_port"],
            openrgb_all=self.settings["openrgb_all_devices"],
            demo=self.demo,
        )

    def _hw_signature(self) -> tuple:
        leds = tuple(n for n in fsroot.listdir("/sys/class/leds") if "kbd" in n)
        hidraw = tuple(fsroot.listdir("/sys/class/hidraw"))
        return leds, hidraw

    def _discover(self, initial: bool = False) -> None:
        found = self._discovery(self._discovery_options())
        self._signature = self._hw_signature()
        with self.lock:
            old = self.devices
            new = {d.id: d for d in found}
            for dev_id, dev in old.items():
                if new.get(dev_id) is not dev:
                    writer = self._writers.pop(dev_id, None)
                    if writer is not None:
                        writer.stop()
                        with writer.io:
                            dev.close()
                    else:
                        dev.close()
                    self._submitted.pop(dev_id, None)
            for dev_id, dev in new.items():
                if dev_id not in self._writers:
                    writer = _Writer(self, dev)
                    self._writers[dev_id] = writer
                    writer.start()
            self.devices = new
            self.desc = {dev_id: dev.describe() for dev_id, dev in new.items()}
            for dev_id, dev in new.items():
                if dev_id in self.states and not initial:
                    if dev_id in self.touched:
                        self._force_push_at = time.monotonic()
                    continue
                saved = self._saved_states.get(dev_id)
                if saved:
                    try:
                        self.states[dev_id] = clean_state(saved, self.desc[dev_id], None,
                                                          self._effect_ids(dev_id))
                    except ValueError:
                        log.warning("saved state for %s is invalid", dev_id)
                        self.states[dev_id] = self._initial_state(dev)
                        continue
                    if self.restore and self.settings["restore_on_boot"]:
                        self.touched.add(dev_id)
                    else:
                        self._adopt_hardware(dev_id)
                    continue
                self.states[dev_id] = self._initial_state(dev)
            for dev_id in list(self._renderers):
                if dev_id not in new:
                    del self._renderers[dev_id]
            self._recompute()
            self._emit("devices", {"devices": [self._view(i) for i in self.devices]})
        log.info("devices: %s", ", ".join(self.devices) or "none")

    def _initial_state(self, dev: Device) -> dict:
        state = copy.deepcopy(DEFAULT_STATE)
        level = self._read_level(dev)
        if level is not None:
            state["on"] = level > 0
            if level > 0:
                state["brightness"] = self._pct(dev, level)
        return state

    def _adopt_hardware(self, dev_id: str) -> None:
        dev = self.devices[dev_id]
        level = self._read_level(dev)
        if level is not None:
            self.states[dev_id]["on"] = level > 0
            if level > 0:
                self.states[dev_id]["brightness"] = self._pct(dev, level)

    def _read_level(self, dev: Device) -> int | None:
        if not dev.readable:
            return None
        writer = self._writers.get(dev.id)
        try:
            if writer is None:
                return dev.read_level()
            with writer.io:
                return dev.read_level()
        except (OSError, DeviceError):
            return None

    def _auto_config(self) -> None:
        """First run: offer ready-made profiles and (disabled) rules for this hardware."""
        with self.lock:
            rgb = any(d["color_mode"] != "none" for d in self.desc.values())
            if not self.rules:
                self.rules = rules_mod.default_rules(rgb)
            if not self.profiles:
                self.profiles = self._default_profiles()
            self._dirty()
            self._emit("rules", {"rules": self.rules})
            self._emit("profiles", {"profiles": self.profile_list()})
        self._flush()

    def _default_profiles(self) -> dict:
        def build(make) -> dict:
            devices = {}
            for dev_id, desc in self.desc.items():
                changes = make(desc)
                try:
                    devices[dev_id] = clean_state(changes, desc, None, self._effect_ids(dev_id))
                except ValueError:
                    continue
            return {"devices": devices, "updated": time.time()}

        def gaming(desc):
            ids = self._effect_ids(desc["id"])
            effect = next((e for e in ("wave", "spectrum", "breathing") if e in ids), "static")
            return {"on": True, "brightness": 100, "effect": effect, "params": {"speed": 45}}

        profiles = {
            "Bright": build(lambda d: {"on": True, "brightness": 100, "effect": "static", "color": "#ffffff"}),
            "Night": build(lambda d: {"on": True, "brightness": 25, "effect": "static", "color": "#ff7a2f"}),
            "Off": build(lambda d: {"on": False}),
        }
        if any(d["color_mode"] != "none" for d in self.desc.values()):
            profiles["Focus"] = build(lambda d: {"on": True, "brightness": 70, "effect": "static",
                                                 "color": "#cfe6ff"})
            profiles["Gaming"] = build(gaming)
        return profiles

    # ================================================================ helpers
    def _targets(self, device: str | None) -> list[str]:
        if device in (None, "", "all", "*"):
            if not self.devices:
                raise KeyError("no devices")
            return list(self.devices)
        if device not in self.devices:
            # Accept unique prefixes / substrings for CLI convenience.
            matches = [d for d in self.devices if device in d]
            if len(matches) == 1:
                return matches
            raise KeyError(f"unknown device {device!r}")
        return [device]

    def _input_activity(self) -> bool:
        return self.input is not None

    def _effect_list(self, dev_id: str) -> list[dict]:
        desc = self.desc[dev_id]
        out = []
        for e in effects.available(desc["color_mode"], zone_count(desc), self._input_activity()):
            out.append({"id": e.id, "name": e.name, "hardware": False, "colors": e.colors,
                        "description": e.description,
                        "params": [p.__dict__.copy() for p in e.params]})
        for e in desc.get("hw_effects", []):
            out.append(dict(e, id="hw:" + e["id"]))
        return out

    def _effect_ids(self, dev_id: str) -> set[str]:
        return {e["id"] for e in self._effect_list(dev_id)}

    def _pct(self, dev: Device, level: int) -> int:
        if not dev.brightness_hw:
            return max(0, min(100, level))
        return _round(level * 100 / max(1, dev.brightness_max))

    def _level(self, dev: Device, pct: float, exact: bool = False) -> int:
        if not dev.brightness_hw:
            return _round(max(0.0, min(100.0, pct)))
        top = dev.brightness_max
        level = _round(pct / 100.0 * top)
        if pct > 0 and level == 0 and not exact:
            level = 1
        return max(0, min(top, level))

    def _view(self, dev_id: str) -> dict:
        dev = self.devices[dev_id]
        desc = dict(self.desc[dev_id])
        stored = self.feature_values.get(dev_id, {})
        feats = []
        for f in desc.get("features", []):
            f = dict(f)
            if f.get("value") is None:
                f["value"] = stored.get(f["id"], f.get("default"))
            feats.append(f)
        desc["features"] = feats
        desc.update({
            "state": copy.deepcopy(self.states[dev_id]),
            "effective": copy.deepcopy(self.effective.get(dev_id, self.states[dev_id])),
            "effects": self._effect_list(dev_id),
            "touched": dev_id in self.touched,
            "error": dev.error,
            "access": dev.access_problem(),
            "rules_active": self._rules_active(dev_id),
        })
        return desc

    def _rules_active(self, dev_id: str) -> list[str]:
        return [r["id"] for r in self.rules if r["id"] in self.active_rules
                and r["target"] in ("all", dev_id) and (r["id"], dev_id) not in self.suppressed]

    def _dirty(self) -> None:
        self._save_due = time.monotonic() + SAVE_DELAY

    def _save(self) -> None:
        # Only lighting the user actually chose is worth restoring later.
        saved = self._saved_states
        for dev_id in self.touched:
            if dev_id in self.states:
                saved[dev_id] = copy.deepcopy(self.states[dev_id])
        data = {
            "devices": saved,
            "rules": self.rules,
            "profiles": self.profiles,
            "settings": self.settings,
            "features": self.feature_values,
        }
        try:
            self.store.save(data)
        except OSError as e:
            log.error("could not save state to %s: %s", self.store.path, e)
        self._save_due = None

    # ============================================================ public API
    def hello(self) -> dict:
        return {"version": __version__, "mode": self.mode, "privileged": self.privileged,
                "pid": os.getpid(), "demo": self.demo}

    def system(self) -> dict:
        with self.lock:
            devices = [self._view(i) for i in self.devices]
            openrgb_seen = any(d["backend"] == "openrgb" for d in devices)
            family = models.family_for(self.sysinfo["dmi"])
            return {
                **self.sysinfo,
                "version": __version__,
                "mode": self.mode,
                "privileged": self.privileged,
                "first_run": self.first_run,
                "input_watch": self._input_activity(),
                "sensors": self.sensors.available(),
                "family": family.title if family else None,
                "layout": family.layout if family else "compact",
                "hints": models.hints(self.sysinfo["dmi"], devices, privileged=self.privileged,
                                      openrgb_seen=openrgb_seen),
            }

    def device_list(self) -> list[dict]:
        with self.lock:
            return [self._view(i) for i in self.devices]

    def device(self, device: str) -> dict:
        with self.lock:
            return self._view(self._targets(device)[0])

    def set(self, device: str | None, changes: dict) -> list[dict]:
        with self.lock:
            ids = self._targets(device)
            new_states = {}
            for dev_id in ids:
                new_states[dev_id] = clean_state(changes, self.desc[dev_id], self.states[dev_id],
                                                 self._effect_ids(dev_id))
            now = time.monotonic()
            for dev_id, state in new_states.items():
                self.states[dev_id] = state
                self.touched.add(dev_id)
                self._suppress(dev_id, set(changes))
                self._persist_due[dev_id] = now + PERSIST_DELAY
            self._recompute(ids)
            self._dirty()
            views = [self._view(i) for i in ids]
        self._wake.set()
        self._flush()
        return views

    def toggle(self, device: str | None) -> list[dict]:
        with self.lock:
            ids = self._targets(device)
            turn_on = not any(self.effective.get(i, self.states[i])["on"] for i in ids)
        return self.set(device, {"on": turn_on})

    def nudge(self, device: str | None, step: int) -> list[dict]:
        """Brightness up (+) or down (-): one level on coarse keyboards, else 10%."""
        with self.lock:
            ids = self._targets(device)
            results = []
            for dev_id in ids:
                dev = self.devices[dev_id]
                state = self.effective.get(dev_id, self.states[dev_id])
                pct = state["brightness"] if state["on"] else 0
                if dev.brightness_hw and dev.brightness_max <= 10:
                    level = self._level(dev, pct) + (1 if step > 0 else -1)
                    level = max(0, min(dev.brightness_max, level))
                    new_pct = self._pct(dev, level)
                else:
                    new_pct = max(0, min(100, pct + (10 if step > 0 else -10)))
                changes = {"on": new_pct > 0}
                if new_pct > 0:
                    changes["brightness"] = new_pct
                results.append((dev_id, changes))
        views = []
        for dev_id, changes in results:
            views += self.set(dev_id, changes)
        return views

    def set_feature(self, device: str, feature: str, value) -> dict:
        with self.lock:
            dev_id = self._targets(device)[0]
            dev = self.devices[dev_id]
            spec = next((f for f in self.desc[dev_id]["features"] if f["id"] == feature), None)
            if spec is None:
                raise KeyError(f"unknown feature {feature!r}")
            if spec["kind"] == "bool":
                value = as_bool(value)
            elif spec["kind"] == "range":
                value = as_int(value, spec["min"], spec["max"])
            elif spec["kind"] == "choice":
                if str(value) not in [str(c[0]) for c in spec["choices"]]:
                    raise ValueError(f"invalid value {value!r} for {feature}")
                value = str(value)
            values = dict(self.feature_values.get(dev_id, {}))
            for f in self.desc[dev_id]["features"]:
                values.setdefault(f["id"], f["value"] if f["value"] is not None else f["default"])
            values[feature] = value
            # Write-only attribute groups (e.g. ASUS power states) need every flag at once.
            arg = values if feature.startswith("asus_") else value
            writer = self._writers.get(dev_id)
        if writer is not None:
            with writer.io:
                dev.set_feature(feature, arg)
        else:
            dev.set_feature(feature, arg)
        with self.lock:
            self._force_devices.add(dev_id)     # some features change how frames are drawn
            self.feature_values[dev_id] = values
            self.desc[dev_id] = dev.describe()
            self._dirty()
            view = self._view(dev_id)
            self._emit("device", {"device": view})
        self._flush()
        return view

    # ------------------------------------------------------------------ rules
    def rule_catalog(self) -> dict:
        cat = rules_mod.catalog()
        cat["sensors"] = self.sensors.available()
        return cat

    def get_rules(self) -> list[dict]:
        with self.lock:
            return copy.deepcopy(self.rules)

    def set_rules(self, rules: list) -> list[dict]:
        cleaned = rules_mod.clean_rules(rules)
        with self.lock:
            self.rules = cleaned
            self.suppressed.clear()
            self._sensor_now = True
            self._dirty()
            self._emit("rules", {"rules": copy.deepcopy(self.rules)})
        self._wake.set()
        self._flush()
        return copy.deepcopy(cleaned)

    def _suppress(self, dev_id: str, fields: set[str]) -> None:
        """A manual change wins over the rules currently overriding the same settings."""
        if "zones" in fields:
            fields = fields | {"color"}
        for rule in self.rules:
            if rule["id"] not in self.active_rules or rule["target"] not in ("all", dev_id):
                continue
            ov = rules_mod.override(rule["action"], self.desc[dev_id], self.snapshot,
                                    self.profiles, self._effect_ids(dev_id)) or {}
            if set(ov) & fields:
                self.suppressed.add((rule["id"], dev_id))

    # --------------------------------------------------------------- profiles
    def _look(self, dev_id: str, state: dict) -> dict:
        """A short description of a lighting state, for profile previews."""
        desc = self.desc.get(dev_id, {})
        names = {e["id"]: e["name"] for e in self._effect_list(dev_id)} if dev_id in self.desc else {}
        rgb = desc.get("color_mode", "none") != "none"
        effect = state.get("effect", "static")
        return {
            "device": dev_id,
            "on": bool(state.get("on", True)) and state.get("brightness", 100) > 0,
            "brightness": state.get("brightness", 100),
            "colors": (state.get("zones") or [state.get("color", "#ffffff")])[:6] if rgb else ["#fff1d6"],
            "effect_name": names.get(effect, "Static") if effect != "static" else "Static",
        }

    def profile_list(self) -> list[dict]:
        with self.lock:
            out = []
            for name, p in sorted(self.profiles.items()):
                devices = p.get("devices", {})
                looks = [self._look(d, devices[d]) for d in self.devices if d in devices]
                out.append({"name": name, "devices": sorted(devices), "updated": p.get("updated"),
                            "looks": looks})
            return out

    def profile_save(self, name: str) -> list[dict]:
        name = clean_name(name)
        with self.lock:
            if len(self.profiles) >= 50 and name not in self.profiles:
                raise ValueError("too many profiles")
            self.profiles[name] = {
                "devices": {i: copy.deepcopy(self.states[i]) for i in self.devices},
                "updated": time.time(),
            }
            self._dirty()
            self._emit("profiles", {"profiles": self.profile_list()})
        self._flush()
        return self.profile_list()

    def profile_apply(self, name: str) -> list[dict]:
        with self.lock:
            if name not in self.profiles:
                raise KeyError(f"unknown profile {name!r}")
            prof = self.profiles[name]
            now = time.monotonic()
            applied = []
            for dev_id, state in prof.get("devices", {}).items():
                if dev_id not in self.devices:
                    continue
                try:
                    self.states[dev_id] = clean_state(state, self.desc[dev_id], None,
                                                      self._effect_ids(dev_id))
                except ValueError:
                    continue
                self.touched.add(dev_id)
                self._suppress(dev_id, set(DEFAULT_STATE))
                self._persist_due[dev_id] = now + PERSIST_DELAY
                applied.append(dev_id)
            self._recompute(applied)
            self._dirty()
            self._emit("profile_applied", {"name": name})
            views = [self._view(i) for i in applied]
        self._wake.set()
        self._flush()
        return views

    def profile_delete(self, name: str) -> list[dict]:
        with self.lock:
            if self.profiles.pop(name, None) is None:
                raise KeyError(f"unknown profile {name!r}")
            self._dirty()
            self._emit("profiles", {"profiles": self.profile_list()})
        self._flush()
        return self.profile_list()

    def profile_rename(self, old: str, new: str) -> list[dict]:
        new = clean_name(new)
        with self.lock:
            if old not in self.profiles:
                raise KeyError(f"unknown profile {old!r}")
            if new in self.profiles and new != old:
                raise ValueError(f"a profile named {new!r} already exists")
            self.profiles[new] = self.profiles.pop(old)
            for rule in self.rules:
                if rule["action"]["type"] == "profile" and rule["action"]["profile"] == old:
                    rule["action"]["profile"] = new
            self._dirty()
            self._emit("profiles", {"profiles": self.profile_list()})
            self._emit("rules", {"rules": copy.deepcopy(self.rules)})
        self._flush()
        return self.profile_list()

    # --------------------------------------------------------------- settings
    def get_settings(self) -> dict:
        with self.lock:
            return copy.deepcopy(self.settings)

    def set_settings(self, changes: dict) -> dict:
        with self.lock:
            before = copy.deepcopy(self.settings)
            self.settings = clean_settings(changes, self.settings)
            rescan = any(before[k] != self.settings[k] for k in self.settings if k.startswith("openrgb"))
            self._dirty()
            self._emit("settings", {"settings": copy.deepcopy(self.settings)})
        self._flush()
        if rescan:
            self.rescan()
        return self.get_settings()

    # ------------------------------------------------------------------ misc
    def sensor_readings(self) -> dict:
        snap = self.sensors.read(None)
        return {"readings": snap.to_dict(), "available": self.sensors.available()}

    def flash(self, device: str | None = None, color: str = "#ffffff", count: int = 3,
              period: float = 0.5) -> dict:
        """Blink the keyboard briefly (notifications, scripts)."""
        with self.lock:
            ids = self._targets(device)
            count = as_int(count, 1, 20)
            period = max(0.1, min(3.0, float(period)))
            self.flash_state = {"until": time.monotonic() + count * period, "devices": set(ids),
                                "color": normalize(color), "period": period}
            self._recompute(ids)
        self._wake.set()
        self._flush()
        return {"devices": ids, "seconds": count * period}

    def rescan(self) -> list[dict]:
        self._discover()
        self._flush()
        self._wake.set()
        return self.device_list()

    def report(self) -> str:
        from ..report import build_report
        return build_report(self)

    # =========================================================== composition
    def _compose(self, dev_id: str, now: float) -> dict:
        state = copy.deepcopy(self.states[dev_id])
        desc = self.desc[dev_id]
        effect_ids = self._effect_ids(dev_id)
        for rule in self.rules:
            if rule["id"] not in self.active_rules or rule["target"] not in ("all", dev_id):
                continue
            if (rule["id"], dev_id) in self.suppressed:
                continue
            ov = rules_mod.override(rule["action"], desc, self.snapshot, self.profiles, effect_ids)
            if ov:
                params = {**state.get("params", {}), **ov.pop("params", {})}
                state.update(ov)
                state["params"] = params
        flash = self.flash_state
        if flash and dev_id in flash["devices"] and now < flash["until"]:
            state.update({"on": True, "brightness": 100, "effect": "blink",
                          "params": {"period": flash["period"]}})
            if desc["color_mode"] != "none":
                state.update({"color": flash["color"], "zones": None})
        return state

    def _recompute(self, ids: list[str] | None = None) -> None:
        now = time.monotonic()
        for dev_id in (ids if ids is not None else list(self.devices)):
            if dev_id not in self.devices:
                continue
            eff = self._compose(dev_id, now)
            if eff != self.effective.get(dev_id):
                self.effective[dev_id] = eff
                self._emit("state", {"device": dev_id, "state": copy.deepcopy(self.states[dev_id]),
                                     "effective": copy.deepcopy(eff),
                                     "rules_active": self._rules_active(dev_id)})

    def _evaluate_rules(self) -> None:
        needed = rules_mod.needed_sensors(self.rules)
        self.snapshot = self.sensors.read(needed)
        active = set()
        for rule in self.rules:
            if rule["enabled"] and rules_mod.holds(rule["trigger"], self.snapshot,
                                                   rule["id"] in self.active_rules):
                active.add(rule["id"])
        if active != self.active_rules:
            ended = self.active_rules - active
            self.suppressed = {(r, d) for r, d in self.suppressed if r not in ended}
            self.active_rules = active
            self._emit("automation", {"active": sorted(active)})
        self._recompute()

    # ================================================================ render
    def _zone_colors(self, dev: Device, state: dict) -> list[RGB] | None:
        n = dev.zone_count
        if n == 0:
            return None
        zones = state.get("zones")
        if zones:
            return [parse(zones[i] if i < len(zones) else state["color"]) for i in range(n)]
        return [parse(state["color"])] * n

    def _positions(self, dev_id: str) -> list[float]:
        desc = self.desc[dev_id]
        n = zone_count(desc)
        if n <= 1:
            return [0.0]
        cols = [z.get("col") for z in desc["zones"]]
        if all(c is not None for c in cols):
            top = max(cols) or 1
            return [c / top for c in cols]
        return [i / (n - 1) for i in range(n)]

    def _renderer(self, dev_id: str, state: dict, colors: list[RGB] | None) -> Renderer:
        key = (state["effect"], repr(sorted(state.get("params", {}).items())),
               tuple(colors or ()), tuple(state.get("effect_colors", ())))
        cached = self._renderers.get(dev_id)
        if cached and cached[0] == key:
            return cached[1]
        renderer = Renderer(state["effect"], state.get("params", {}),
                            colors or [(255, 255, 255)],
                            [parse(c) for c in state.get("effect_colors", [])],
                            self._positions(dev_id), start=time.monotonic() - self.t0)
        self._renderers[dev_id] = (key, renderer)
        return renderer

    def _frame(self, dev_id: str, now: float) -> tuple[Frame, bool]:
        """The frame to show now, and whether it is part of an animation."""
        dev = self.devices[dev_id]
        state = self.effective.get(dev_id) or self.states[dev_id]
        colors = self._zone_colors(dev, state)
        pct = state["brightness"] if state["on"] else 0
        if pct <= 0:
            return Frame(on=False, level=0, colors=colors), False
        effect = state["effect"]
        if effect.startswith("hw:"):
            return Frame(on=True, level=self._level(dev, pct), colors=colors, effect=effect[3:],
                         params=dict(state.get("params", {})),
                         effect_colors=[parse(c) for c in state.get("effect_colors", [])]
                         or (colors[:1] if colors else [])), False
        renderer = self._renderer(dev_id, state, colors)
        ctx = Context(last_key=(self.input.last_key - self.t0) if self.input and self.input.last_key else None)
        factor, out = renderer.frame(now - self.t0, ctx)
        factor = max(0.0, min(1.0, factor))
        if dev.rgb:
            if dev.brightness_hw:
                level = self._level(dev, pct)
                out = [scale(c, factor) for c in out]
            else:
                level = self._level(dev, pct * factor, exact=True)
            frame = Frame(on=True, level=level, colors=out[:dev.zone_count])
        else:
            level = self._level(dev, pct * factor, exact=renderer.animated)
            frame = Frame(on=level > 0 or renderer.animated, level=level, colors=None)
        frame.transient = renderer.animated
        return frame, renderer.animated

    def _push(self, dev_id: str, frame: Frame, force: bool = False) -> None:
        """Hand a frame to the device's writer unless it is already showing it."""
        writer = self._writers.get(dev_id)
        if writer is None:
            return
        if not force and not frame.persist and frame.same_lighting(self._submitted.get(dev_id)):
            return
        self._submitted[dev_id] = frame
        writer.submit(frame, force)

    def _write(self, writer: _Writer, frame: Frame, force: bool) -> None:
        """Runs on the device's writer thread."""
        dev = writer.dev
        dev_id = dev.id
        had_error = dev.error
        try:
            with writer.io:
                dev.show(frame, force=force)
            self._written_level[dev_id] = frame.level if frame.on else 0
        except AccessError as e:
            dev.error = f"{e}. {e.hint}" if e.hint else str(e)
            dev.last = frame   # do not retry the same frame forever
        except (DeviceError, OSError) as e:
            dev.error = str(e)
            dev.last = None
            self._submitted[dev_id] = None   # retry with the next frame
            self._rescan_due = time.monotonic() + 5
        except Exception as e:  # a driver bug must not take the engine down
            log.exception("driver error on %s", dev_id)
            dev.error = f"internal error: {e}"
            dev.last = frame
        writer.last_write = time.monotonic()
        if dev.error != had_error:
            if dev.error:
                log.warning("%s: %s", dev_id, dev.error)
            with self.lock:
                if dev_id in self.devices:
                    self._emit("device", {"device": self._view(dev_id)})
            self._flush()

    def _poll_levels(self) -> None:
        """Notice brightness changes made with the laptop's Fn keys."""
        for dev_id, dev in list(self.devices.items()):
            if not dev.readable or not dev.brightness_hw:
                continue
            renderer = self._renderers.get(dev_id)
            if renderer and renderer[1].animated and not dev.rgb:
                continue   # we are stepping the brightness ourselves
            writer = self._writers.get(dev_id)
            if writer is not None and (writer.busy or time.monotonic() - writer.last_write < 1.5):
                continue   # many drivers apply brightness asynchronously; let a write settle first
            level = self._read_level(dev)
            if level is None:
                continue
            with self.lock:
                if dev_id not in self.devices:
                    continue
                expected = self._written_level.get(dev_id)
                if dev_id not in self.touched or expected is None:
                    state = self.states[dev_id]
                    if (level > 0) != state["on"] or (level > 0 and self._level(dev, state["brightness"]) != level):
                        self._adopt_hardware(dev_id)
                        self._recompute([dev_id])
                    continue
                if level == expected:
                    continue
                state = self.states[dev_id]
                state["on"] = level > 0
                if level > 0:
                    state["brightness"] = self._pct(dev, level)
                self._written_level[dev_id] = level
                for frame in (dev.last, self._submitted.get(dev_id)):
                    if frame is not None:
                        frame.level = level
                        frame.on = level > 0
                self._suppress(dev_id, {"on", "brightness"})
                self._recompute([dev_id])
                self._dirty()

    @staticmethod
    def _boot_offset() -> float:
        try:
            return time.clock_gettime(time.CLOCK_BOOTTIME) - time.clock_gettime(time.CLOCK_MONOTONIC)
        except (AttributeError, OSError):
            return 0.0

    def _input_wake(self) -> None:
        self._sensor_now = True
        self._wake.set()

    def _run(self) -> None:
        last_sensor = last_poll = 0.0
        last_rescan = time.monotonic()
        boot_offset = self._boot_offset()
        while not self._stop.is_set():
            now = time.monotonic()
            animating = False
            try:
                offset = self._boot_offset()
                if offset - boot_offset > 2.0:
                    log.info("resume from suspend detected; restoring lighting")
                    self._force_push_at = now + 1.5
                    self._rescan_due = now + 3.0
                boot_offset = offset

                if self._sensor_now or now - last_sensor >= SENSOR_PERIOD:
                    self._sensor_now = False
                    last_sensor = now
                    with self.lock:
                        if self.flash_state and now >= self.flash_state["until"]:
                            self.flash_state = None
                        self._evaluate_rules()
                elif self.flash_state:
                    with self.lock:
                        if now >= self.flash_state["until"]:
                            self.flash_state = None
                        self._recompute(list(self.flash_state["devices"]) if self.flash_state else None)

                force_all = self._force_push_at is not None and now >= self._force_push_at
                if force_all:
                    self._force_push_at = None
                with self.lock:
                    forced, self._force_devices = self._force_devices, set()
                frames: list[tuple[str, Frame, bool]] = []
                with self.lock:
                    fps = self.settings["fps"]
                    for dev_id in [d for d in self._persist_due if d not in self.devices]:
                        del self._persist_due[dev_id]
                    for dev_id, dev in self.devices.items():
                        if dev_id not in self.touched:
                            continue
                        frame, animated = self._frame(dev_id, now)
                        due = self._persist_due.get(dev_id)
                        if due is not None and now >= due:
                            del self._persist_due[dev_id]
                            overridden = self.effective.get(dev_id) != self.states[dev_id]
                            if (not animated and dev.can_persist and not overridden
                                    and self.settings["save_to_firmware"]):
                                frame.persist = True
                        if animated:
                            animating = True
                            if now < self._next_push.get(dev_id, 0.0) and not force_all:
                                continue
                            self._next_push[dev_id] = now + 1.0 / max(1, min(fps, dev.max_fps))
                        frames.append((dev_id, frame, force_all or dev_id in forced))
                for dev_id, frame, force in frames:
                    self._push(dev_id, frame, force)

                if now - last_poll >= POLL_PERIOD:
                    last_poll = now
                    self._poll_levels()

                if self._rescan_due is not None and now >= self._rescan_due:
                    self._rescan_due = None
                    self._discover()
                    last_rescan = now
                elif now - last_rescan >= (RESCAN_PERIOD if now - self._started_at > 60 else 2.0):
                    last_rescan = now
                    if self._hw_signature() != self._signature:
                        log.info("hardware changed; rescanning")
                        self._discover()

                if self._save_due is not None and now >= self._save_due:
                    with self.lock:
                        self._save()
            except Exception:
                log.exception("render loop error")
            self._flush()

            if animating or self.flash_state:
                timeout = 1.0 / max(1, self.settings["fps"])
            else:
                timeout = max(0.05, SENSOR_PERIOD - (time.monotonic() - last_sensor))
                if self._save_due is not None:
                    timeout = min(timeout, max(0.05, self._save_due - time.monotonic()))
                if self._persist_due:
                    timeout = min(timeout, max(0.05, min(self._persist_due.values()) - time.monotonic()))
            self._wake.wait(timeout)
            self._wake.clear()
