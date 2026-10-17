"""Keyboard backlights exposed by kernel drivers under /sys/class/leds.

This is the most important backend: every mainline laptop driver that knows
about a keyboard light registers an LED class device whose name contains
``kbd_backlight``. On top of plain brightness some drivers add color:

* multicolor LED class (``multi_intensity``) - TUXEDO/Clevo/Uniwill via
  tuxedo-drivers, uniwill-laptop, and others. Several LEDs named ``<base>``,
  ``<base>_1``... form one keyboard with one zone (or key) per LED.
* ``color`` hex attribute - System76 (``system76_acpi``).
* ``kbd_rgb_mode`` / ``kbd_rgb_state`` - ASUS TUF (``asus-wmi``).

Vendor extras (Dell timeouts, Toshiba modes, ...) are surfaced as features.
Sony VAIO keyboards are not LED class devices and are handled at the end.
"""

from __future__ import annotations

import os
import re

from .. import fsroot
from ..color import RGB
from . import logind
from .base import (
    AccessError,
    ColorMode,
    Device,
    DeviceError,
    EffectInfo,
    Feature,
    Frame,
    Param,
    ZoneInfo,
)

LEDS = "/sys/class/leds"
TUXEDO_MODE = "/sys/devices/platform/tuxedo_keyboard/kbd_backlight_mode"
SONY = "/sys/devices/platform/sony-laptop"

_KBD_RE = re.compile(
    r"^(?P<base>.*(?:kbd_backlight|kbd_led|keyboard_backlight|kbd-backlight))(?:_(?P<idx>\d+))?$"
)

# LED name prefix -> vendor shown in the UI.
VENDOR_PREFIXES = {
    "asus": "ASUS", "tpacpi": "ThinkPad", "dell": "Dell", "smc": "Apple", "apple": "Apple", "spi": "Apple",
    "system76_acpi": "System76", "system76": "System76", "chromeos": "Chromebook", "cros_ec": "Chromebook",
    "framework_laptop": "Framework", "hp": "HP", "samsung": "Samsung", "samsung-galaxybook": "Samsung",
    "toshiba": "Toshiba", "huawei": "Huawei", "lg-laptop": "LG", "msiec": "MSI", "msiacpi": "MSI",
    "msi": "MSI", "ideapad": "Lenovo", "legion": "Lenovo", "tuxedo": "TUXEDO", "clevo": "Clevo",
    "clevo-acpi": "Clevo", "uniwill": "Uniwill", "gpd": "GPD", "bitland-mifs-wmi": "Bitland",
    "hammer": "Chromebook", "ybwmi": "Lenovo", "yogabook": "Lenovo",
}

ROOT_HINT = (
    "Install and start the ByteKeys service (bytekeysd) to unlock full control; "
    "the kernel only lets root change this setting."
)

# LEDs owned by other backends (wmi_zones registers them here).
CLAIMED: set[str] = set()


def _led(name: str, attr: str = "") -> str:
    return f"{LEDS}/{name}/{attr}" if attr else f"{LEDS}/{name}"


def _vendor_for(led_name: str) -> str:
    prefix = led_name.split(":", 1)[0].lower()
    return VENDOR_PREFIXES.get(prefix, "")


def _driver_of(led_name: str) -> str:
    """Kernel driver bound to the LED's parent device ("asus-nb-wmi", "lg-laptop"...)."""
    p = _led(led_name, "device/driver")
    return os.path.basename(fsroot.realpath(p)) if fsroot.exists(p) else ""


def discover() -> list[Device]:
    names_all = set(fsroot.listdir(LEDS))
    groups: dict[str, list[tuple[int, str]]] = {}
    for name in names_all:
        if name.startswith("input") or name in CLAIMED:
            continue  # Caps/Num/Scroll lock indicators, or handled elsewhere
        # Framework laptops may show the same light twice; the mainline name wins.
        if name.startswith("framework_laptop::") and "chromeos::kbd_backlight" in names_all:
            continue
        m = _KBD_RE.match(name)
        if not m:
            continue
        groups.setdefault(m["base"], []).append((int(m["idx"] or 0), name))

    devices: list[Device] = []
    for base, members in sorted(groups.items()):
        names = [n for _, n in sorted(members)]
        first = names[0]
        if fsroot.exists(_led(first, "kbd_rgb_mode")):
            devices.append(AsusWmiKeyboard(first))
        elif fsroot.exists(_led(first, "multi_intensity")):
            devices.append(MulticolorKeyboard(base, names))
        elif _looks_like_hex(fsroot.read(_led(first, "color"))):
            devices.append(System76Keyboard(first))
        else:
            devices.extend(SysfsKeyboard(n) for n in names)
    if fsroot.exists(f"{SONY}/kbd_backlight"):
        devices.append(SonyKeyboard())
    return devices


def _looks_like_hex(text: str | None) -> bool:
    return bool(text) and re.fullmatch(r"(0x)?#?[0-9a-fA-F]{6}", text.strip()) is not None


class SysfsKeyboard(Device):
    """A plain LED class keyboard backlight (brightness only)."""

    backend = "sysfs"

    def __init__(self, led_name: str, leds: list[str] | None = None):
        super().__init__(f"sysfs:{led_name}", "Keyboard Backlight")
        self.led = led_name
        self.leds = leds or [led_name]
        self.vendor = _vendor_for(led_name)
        self.driver = _driver_of(led_name)
        if self.driver == "lg-laptop":
            self.vendor = "LG"
        if self.vendor:
            self.name = f"{self.vendor} Keyboard"
        self.path = fsroot.realpath(_led(led_name))
        self.brightness_max = max(1, fsroot.read_int(_led(led_name, "max_brightness"), 1) or 1)
        # Some drivers accept a wide range but only know a few levels.
        self.level_values: list[int] | None = None
        if self.driver == "lg-laptop" and self.brightness_max == 255:
            self.level_values = [0, 127, 255]          # off / low / high
            self.brightness_max = 2
        self.readable = True
        self.max_fps = 15
        self._via_logind = False
        self._trigger_cleared = False
        self._extras = _VendorExtras(led_name)
        trigger = self._active_trigger()
        if trigger and trigger != "none":
            self.notes.append(f"LED trigger '{trigger}' was active; ByteKeys switches it off when it "
                              "takes control.")

    # -------------------------------------------------------------- helpers
    def _active_trigger(self) -> str | None:
        text = fsroot.read(_led(self.led, "trigger"))
        if not text:
            return None
        m = re.search(r"\[([^\]]+)\]", text)
        return m.group(1) if m else None

    def _write_attr(self, led: str, attr: str, value: str) -> None:
        try:
            fsroot.write(_led(led, attr), value)
        except PermissionError:
            raise AccessError(f"no permission to write {attr} of {led}", ROOT_HINT) from None
        except OSError as e:
            raise DeviceError(f"writing {attr}={value!r} to {led} failed: {e.strerror or e}") from None

    def _clear_trigger(self) -> None:
        """A default trigger (e.g. applesmc's nand-disk) would fight every change."""
        if self._trigger_cleared:
            return
        self._trigger_cleared = True
        trigger = self._active_trigger()
        if trigger and trigger != "none" and fsroot.writable(_led(self.led, "trigger")):
            try:
                fsroot.write(_led(self.led, "trigger"), "none")
            except OSError:
                pass

    def _brightness_leds(self) -> list[str]:
        # On big groups (per-key) the firmware brightness is global: one write is enough.
        return self.leds if len(self.leds) <= 3 else self.leds[:1]

    def _write_level(self, level: int) -> None:
        level = max(0, min(self.brightness_max, int(level)))
        value = self.level_values[level] if self.level_values else level
        self._clear_trigger()
        for led in self._brightness_leds():
            if self._via_logind:
                if not logind.set_brightness("leds", led, value):
                    raise AccessError("logind refused the brightness change", ROOT_HINT)
                continue
            try:
                fsroot.write(_led(led, "brightness"), str(value))
            except PermissionError:
                if logind.set_brightness("leds", led, value):
                    self._via_logind = True
                    self.max_fps = 4   # every write spawns a helper process
                    continue
                raise AccessError(f"no permission to change brightness of {led}", ROOT_HINT) from None
            except OSError as e:
                raise DeviceError(f"setting brightness of {led} failed: {e.strerror or e}") from None

    # -------------------------------------------------------------- Device API
    def access_problem(self) -> str | None:
        if fsroot.writable(_led(self.led, "brightness")):
            return None
        if logind.available():
            return None
        return ROOT_HINT

    def read_level(self) -> int | None:
        value = fsroot.read_int(_led(self.led, "brightness"))
        if value is None or not self.level_values:
            return value
        # Map a raw value back to the nearest level (LG reads 127 for "low").
        return min(range(len(self.level_values)), key=lambda i: abs(self.level_values[i] - value))

    def _show(self, frame: Frame, prev: Frame | None) -> None:
        level = frame.level if frame.on else 0
        if prev is None or level != (prev.level if prev.on else 0):
            self._write_level(level)

    def features(self) -> list[Feature]:
        return self._extras.features()

    def set_feature(self, feature_id: str, value) -> None:
        self._extras.set(feature_id, value)

    def diagnostics(self) -> dict:
        info = super().diagnostics()
        attrs = {}
        for led in self.leds[:4]:
            for attr in sorted(fsroot.listdir(_led(led))):
                p = _led(led, attr)
                if os.path.isdir(fsroot.path(p)) or attr in ("uevent",):
                    continue
                val = fsroot.read(p)
                attrs[f"{led}/{attr}"] = val if val is not None else "<unreadable>"
        info["attributes"] = attrs
        info["driver"] = self.driver
        info["via_logind"] = self._via_logind
        return info


class MulticolorKeyboard(SysfsKeyboard):
    """One or more multicolor LEDs; every LED is a zone (or a key)."""

    TUXEDO_MODES = [
        ("breathe", "Breathing", 1), ("cycle", "Color cycle", 2), ("dance", "Dance", 3),
        ("flash", "Flash", 4), ("random", "Random colors", 5), ("tempo", "Tempo", 6), ("wave", "Wave", 7),
    ]

    def __init__(self, base: str, leds: list[str]):
        super().__init__(leds[0], leds)
        self.id = f"sysfs:{base}"
        channels = (fsroot.read(_led(leds[0], "multi_index")) or "").split()
        self.channel_order = [c.lower() for c in channels]
        # Intensity range: per channel when the kernel says (7.2+), else the 0-255 that
        # the RGB keyboard drivers use (TUXEDO's max_brightness is a separate global level).
        maxima = (fsroot.read(_led(leds[0], "multi_max_intensity")) or "").split()
        try:
            self.channel_max = [int(v) for v in maxima] if maxima else [255] * len(self.channel_order)
        except ValueError:
            self.channel_max = [255] * len(self.channel_order)
        self.zero_is_default = self.led.startswith("uniwill")   # EC treats 000000 as "restore default"
        self.tuxedo_modes = False
        parent = os.path.dirname(fsroot.realpath(_led(leds[0], "device")) + "/")
        self.buffer_ctl = f"{parent.rstrip('/')}/controls/buffer_input"
        if not fsroot.exists(self.buffer_ctl):
            self.buffer_ctl = ""
        if not {"red", "green", "blue"} <= set(self.channel_order):
            self.color_mode = ColorMode.NONE      # e.g. a white/amber LED pair
            return
        if len(leds) == 1:
            self.color_mode = ColorMode.SINGLE
        else:
            self.color_mode = ColorMode.ZONES if len(leds) <= 8 else ColorMode.PERKEY
            names = _zone_names(len(leds))
            self.zones = [ZoneInfo(i, names[i]) for i in range(len(leds))]
            self.layout = "zones" if len(leds) <= 8 else "perkey-list"
            if len(leds) in (120, 126):             # ITE 829x 6x20 / ITE 8291 6x21 (row 0 at the bottom)
                cols = 20 if len(leds) == 120 else 21
                bottom_up = len(leds) == 126
                self.matrix = (6, cols)
                self.layout = "perkey-matrix"
                for z in self.zones:
                    row, col = divmod(z.index, cols)
                    z.row, z.col = (5 - row if bottom_up else row), col
                    z.name = f"Key {z.row + 1}.{col + 1}"
        if len(leds) > 16:
            self.max_fps = 20 if self.buffer_ctl else 5
        self.name = f"{self.vendor or 'RGB'} Keyboard".strip()
        self.tuxedo_modes = self.led.startswith("rgb:") and fsroot.exists(TUXEDO_MODE)
        if self.tuxedo_modes:
            self.hw_effects = [EffectInfo(eid, name, True, [], description="Runs on the keyboard controller")
                               for eid, name, _num in self.TUXEDO_MODES]

    def _intensity(self, color: RGB) -> str:
        values = {"red": color[0], "green": color[1], "blue": color[2]}
        if self.zero_is_default and color == (0, 0, 0):
            values = {"red": 1, "green": 1, "blue": 1}
        out = []
        for ch, top in zip(self.channel_order, self.channel_max):
            out.append(str(int(round(values.get(ch, 0) * top / 255.0))))
        return " ".join(out)

    def access_problem(self) -> str | None:
        if self.rgb and not fsroot.writable(_led(self.led, "multi_intensity")):
            return "Changing colors needs root. " + ROOT_HINT
        return super().access_problem()

    def _show(self, frame: Frame, prev: Frame | None) -> None:
        # Brightness first: it may still work (through logind) when colors need root.
        super()._show(frame, prev)
        if self.tuxedo_modes:
            mode = next((num for eid, _n, num in self.TUXEDO_MODES if eid == frame.effect), 0)
            prev_mode = None if prev is None else next(
                (num for eid, _n, num in self.TUXEDO_MODES if eid == prev.effect), 0)
            if mode != prev_mode:
                try:
                    fsroot.write(TUXEDO_MODE, str(mode))
                except PermissionError:
                    raise AccessError("no permission to change the keyboard mode", ROOT_HINT) from None
                except OSError as e:
                    raise DeviceError(f"setting the keyboard mode failed: {e.strerror or e}") from None
            if mode:
                return          # the firmware animation picks its own colors
        if not (self.rgb and frame.colors):
            return
        prev_colors = prev.colors if prev else None
        changes = []
        for i, led in enumerate(self.leds):
            color = frame.colors[i] if i < len(frame.colors) else frame.colors[-1]
            if prev_colors and i < len(prev_colors) and prev_colors[i] == color:
                continue
            changes.append((led, color))
        if not changes:
            return
        buffered = bool(self.buffer_ctl) and len(changes) > 1
        if buffered:
            fsroot.write(self.buffer_ctl, "1")     # collect key updates, flush in one USB transfer
        try:
            for led, color in changes:
                self._write_attr(led, "multi_intensity", self._intensity(color))
        finally:
            if buffered:
                fsroot.write(self.buffer_ctl, "0")


class System76Keyboard(SysfsKeyboard):
    """System76 laptops: ``color`` (and on older models per-zone) hex attributes."""

    ZONE_ATTRS = ["color_left", "color_center", "color_right", "color_extra"]

    def __init__(self, led_name: str):
        super().__init__(led_name)
        self.vendor = "System76"
        self.name = "System76 Keyboard"
        self.zone_attrs = [a for a in self.ZONE_ATTRS if fsroot.exists(_led(led_name, a))]
        if len(self.zone_attrs) > 1:
            self.color_mode = ColorMode.ZONES
            self.zones = [ZoneInfo(i, a.split("_", 1)[1].title()) for i, a in enumerate(self.zone_attrs)]
            self.layout = "zones"
        else:
            self.color_mode = ColorMode.SINGLE
            self.zone_attrs = ["color"]

    def access_problem(self) -> str | None:
        if not fsroot.writable(_led(self.led, self.zone_attrs[0])):
            return "Changing colors needs root. " + ROOT_HINT
        return super().access_problem()

    def _show(self, frame: Frame, prev: Frame | None) -> None:
        super()._show(frame, prev)
        if frame.colors:
            for i, attr in enumerate(self.zone_attrs):
                color = frame.colors[min(i, len(frame.colors) - 1)]
                if prev and prev.colors and i < len(prev.colors) and prev.colors[i] == color:
                    continue
                self._write_attr(self.led, attr, "%02X%02X%02X" % color)


class AsusWmiKeyboard(SysfsKeyboard):
    """ASUS TUF (and some ROG) keyboards driven through asus-wmi.

    ``kbd_rgb_mode`` takes "cmd mode red green blue speed": cmd 0 applies the
    setting for this boot only, cmd 1 also writes it to the keyboard's
    firmware (flash), which only happens for an explicit save. The firmware
    restores the last *saved* look after a cold boot or resume, so the engine
    re-applies its own state then. Each write is one WMI call (~1 ms).
    """

    MODES = [
        ("static", "Static", 0),
        ("breathing", "Breathing", 1),
        ("cycle", "Color cycle", 2),
        ("strobe", "Strobe", 3),
        ("pulse", "Pulse", 10),
    ]
    SPEEDS = [["0", "Slow"], ["1", "Medium"], ["2", "Fast"]]

    def __init__(self, led_name: str):
        super().__init__(led_name)
        self.vendor = "ASUS"
        self.name = "ASUS Keyboard"
        self.color_mode = ColorMode.SINGLE
        self.can_persist = True
        self.max_fps = 10
        speed = Param("speed", "Speed", "choice", default="1", choices=self.SPEEDS)
        self.hw_effects = [
            EffectInfo("breathing", "Breathing", True, [speed], colors=1,
                       description="The keyboard breathes in the chosen color"),
            EffectInfo("cycle", "Color cycle", True, [speed],
                       description="The keyboard cycles through the spectrum"),
            EffectInfo("strobe", "Strobe", True, [speed], colors=1,
                       description="Fast flashing (not supported by every model)"),
            EffectInfo("pulse", "Pulse", True, [speed], colors=1,
                       description="Pulsing flash (not supported by every model)"),
        ]
        self._has_state = fsroot.exists(_led(led_name, "kbd_rgb_state"))

    def access_problem(self) -> str | None:
        if not fsroot.writable(_led(self.led, "kbd_rgb_mode")):
            return "Changing colors and modes needs root. " + ROOT_HINT
        return super().access_problem()

    def _mode_args(self, frame: Frame) -> str:
        """Everything after 'cmd' in a kbd_rgb_mode line."""
        mode, speed = 0, 1
        color: RGB = frame.colors[0] if frame.colors else (255, 255, 255)
        if frame.effect:
            for eid, _name, num in self.MODES:
                if eid == frame.effect:
                    mode = num
            try:
                speed = max(0, min(2, int(frame.params.get("speed", 1))))
            except (TypeError, ValueError):
                speed = 1
            if frame.effect_colors:
                color = frame.effect_colors[0]
        r, g, b = (max(0, min(255, int(v))) for v in color)   # larger values corrupt other fields
        return f"{mode} {r} {g} {b} {speed}"

    def _show(self, frame: Frame, prev: Frame | None) -> None:
        SysfsKeyboard._show(self, frame, prev)
        args = self._mode_args(frame)
        persist = frame.persist and not frame.transient
        # Re-send when anything changed, or when this frame is the persistent write.
        if prev is None or args != self._mode_args(prev) or persist:
            self._write_attr(self.led, "kbd_rgb_mode", f"{1 if persist else 0} {args}")

    def features(self) -> list[Feature]:
        feats = super().features()
        if self._has_state:
            feats += [
                Feature("asus_boot", "Light up while booting", "bool", default=True,
                        description="Keyboard lights during the boot animation"),
                Feature("asus_awake", "Light up while awake", "bool", default=True,
                        description="If this is off the keyboard stays dark whatever else is set"),
                Feature("asus_sleep", "Light up while sleeping", "bool", default=False,
                        description="Keep lights on during suspend"),
                Feature("asus_keyboard", "Light up while shutting down", "bool", default=True,
                        description="Firmware flag; its exact effect differs between models"),
            ]
        return feats

    def set_feature(self, feature_id: str, value) -> None:
        if feature_id.startswith("asus_"):
            # The attribute is write-only, so the engine passes every flag.
            states = value if isinstance(value, dict) else {}
            line = "1 {} {} {} {}".format(
                int(bool(states.get("asus_boot", True))),
                int(bool(states.get("asus_awake", True))),
                int(bool(states.get("asus_sleep", False))),
                int(bool(states.get("asus_keyboard", True))),
            )
            self._write_attr(self.led, "kbd_rgb_state", line)
            return
        super().set_feature(feature_id, value)


class SonyKeyboard(Device):
    """Sony VAIO: platform attributes instead of an LED (0 off, 1 automatic, 2 on)."""

    backend = "sysfs"

    def __init__(self):
        super().__init__("sysfs:sony-laptop", "Sony Keyboard")
        self.vendor = "Sony"
        self.path = f"{SONY}/kbd_backlight"
        self.brightness_max = 1
        self.readable = True
        self.automatic = fsroot.read(f"{SONY}/kbd_backlight") == "1"

    def access_problem(self) -> str | None:
        return None if fsroot.writable(f"{SONY}/kbd_backlight") else ROOT_HINT

    def read_level(self) -> int | None:
        value = fsroot.read_int(f"{SONY}/kbd_backlight")
        return None if value is None else (1 if value else 0)

    def _write(self, attr: str, value: str) -> None:
        try:
            fsroot.write(f"{SONY}/{attr}", value)
        except PermissionError:
            raise AccessError(f"no permission to write {attr}", ROOT_HINT) from None
        except OSError as e:
            raise DeviceError(f"writing {attr} failed: {e.strerror or e}") from None

    def _show(self, frame: Frame, prev: Frame | None) -> None:
        on = frame.on and frame.level > 0
        if prev is None or on != (prev.on and prev.level > 0):
            self._write("kbd_backlight", ("1" if self.automatic else "2") if on else "0")

    def features(self) -> list[Feature]:
        feats = [Feature("sony_auto", "Automatic", "bool", value=self.automatic, default=False,
                         description="Let the firmware switch the backlight with the room light")]
        if fsroot.exists(f"{SONY}/kbd_backlight_timeout"):
            feats.append(Feature("sony_timeout", "Firmware timeout", "choice",
                                 value=fsroot.read(f"{SONY}/kbd_backlight_timeout"),
                                 choices=[["0", "10 seconds"], ["1", "30 seconds"], ["2", "1 minute"],
                                          ["3", "Never"]]))
        return feats

    def set_feature(self, feature_id: str, value) -> None:
        if feature_id == "sony_auto":
            self.automatic = bool(value)
            self._write("kbd_backlight", "1" if self.automatic else "2")
        elif feature_id == "sony_timeout":
            self._write("kbd_backlight_timeout", str(value))
        else:
            raise KeyError(feature_id)


def _zone_names(n: int) -> list[str]:
    if n == 2:
        return ["Left", "Right"]
    if n == 3:
        return ["Left", "Center", "Right"]
    if n == 4:
        return ["Left", "Center", "Right", "Numpad"]
    return [f"Zone {i + 1}" for i in range(n)]


class _VendorExtras:
    """Vendor specific knobs found next to the LED (Dell, Toshiba, Bitland)."""

    DELL_TIMEOUTS = [
        ["0", "Never"], ["5s", "5 seconds"], ["10s", "10 seconds"], ["15s", "15 seconds"],
        ["30s", "30 seconds"], ["1m", "1 minute"], ["5m", "5 minutes"], ["15m", "15 minutes"],
        ["30m", "30 minutes"], ["1h", "1 hour"],
    ]
    TOSHIBA_MODES = {1: "Fn+Z toggles", 2: "Automatic (timeout)", 8: "Always on", 16: "Always off"}
    BITLAND_MODES = [["off", "Off"], ["cyclic", "Cycle"], ["fixed", "Fixed"], ["custom", "Custom"]]

    def __init__(self, led_name: str):
        self.led = led_name
        self.platform = fsroot.realpath(_led(led_name, "device"))

    def _attr(self, name: str) -> str | None:
        for p in (_led(self.led, name), f"{self.platform}/{name}"):
            if fsroot.exists(p):
                return p
        return None

    def features(self) -> list[Feature]:
        feats: list[Feature] = []
        p = self._attr("stop_timeout")
        if p:
            value = fsroot.read(p)
            choices = list(self.DELL_TIMEOUTS)
            if value and value not in [c[0] for c in choices]:
                choices.append([value, value])
            feats.append(Feature(
                "dell_timeout", "Turn off after", "choice", value=value, choices=choices,
                description="Firmware timeout without input (on AC and battery separately on some models)",
            ))
        p = self._attr("als_enabled")
        if p:
            feats.append(Feature(
                "dell_als", "Ambient light sensor control", "bool", value=fsroot.read(p) == "1",
                description="Let the firmware switch the backlight based on room light",
            ))
        p = self._attr("kbd_backlight_mode")
        if p and "tuxedo" not in p:
            available = (fsroot.read(self._attr("available_kbd_modes") or "") or "").split()
            nums = []
            for item in available:
                try:
                    nums.append(int(item, 0))
                except ValueError:
                    continue
            nums = nums or list(self.TOSHIBA_MODES)
            feats.append(Feature(
                "toshiba_mode", "Backlight mode", "choice", value=fsroot.read(p),
                choices=[[str(n), self.TOSHIBA_MODES.get(n, hex(n))] for n in nums],
                description="On older keyboards a change takes effect after a reboot",
            ))
        p = self._attr("kbd_backlight_timeout")
        if p:
            feats.append(Feature(
                "toshiba_timeout", "Firmware timeout (seconds)", "range",
                value=fsroot.read_int(p), min=1, max=60,
            ))
        p = self._attr("kb_mode")
        if p:
            feats.append(Feature("bitland_mode", "Keyboard mode", "choice", value=fsroot.read(p),
                                 choices=self.BITLAND_MODES))
        return feats

    def set(self, feature_id: str, value) -> None:
        mapping = {
            "dell_timeout": ("stop_timeout", lambda v: str(v)),
            "dell_als": ("als_enabled", lambda v: "1" if v else "0"),
            "toshiba_mode": ("kbd_backlight_mode", lambda v: str(v)),
            "toshiba_timeout": ("kbd_backlight_timeout", lambda v: str(int(v))),
            "bitland_mode": ("kb_mode", lambda v: str(v)),
        }
        if feature_id not in mapping:
            raise KeyError(feature_id)
        attr, fmt = mapping[feature_id]
        text = fmt(value)
        p = self._attr(attr)
        if not p:
            raise KeyError(feature_id)
        try:
            fsroot.write(p, text + "\n")
        except PermissionError:
            raise AccessError(f"no permission to write {attr}", ROOT_HINT) from None
        except OSError as e:
            raise DeviceError(f"writing {attr}={text!r} failed: {e.strerror or e}") from None
