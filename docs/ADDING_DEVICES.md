# Adding support for a keyboard

First find out how your keyboard's lighting is reachable:

```bash
bytekeys report          # what ByteKeys sees: LEDs, HID devices, USB IDs, kernel modules
ls /sys/class/leds/      # kernel LED devices (look for *kbd_backlight*)
lsusb                    # USB lighting controllers
```

## 1. The kernel already exposes it

If `/sys/class/leds/` has a `*kbd_backlight*` entry, ByteKeys most likely handles it already. If the
driver adds extra attributes (modes, timeouts, colors), extend `bytekeys/hw/sysfs_leds.py`:

- color attributes: subclass `SysfsKeyboard` (see `System76Keyboard`, `AsusWmiKeyboard`),
- settings such as timeouts: add them to `_VendorExtras.features()` / `set()`.

Interfaces that are not LED class devices (platform attributes, character devices) go into
`bytekeys/hw/wmi_zones.py`.

## 2. A USB (or I2C) HID controller

Create `bytekeys/hw/drivers/<name>.py`:

```python
from ..base import ColorMode, EffectInfo, Frame, ZoneInfo
from ..hid import HidKeyboard


class MyKeyboard(HidKeyboard):
    DRIVER = "my-keyboard"
    VENDOR = "Vendor"
    PRODUCTS = {(0x1234, 0x5678): "Vendor 4-Zone Keyboard"}

    @classmethod
    def score(cls, info):
        # Pick the right interface: usage page/usage from the report descriptor.
        return 3 if (info.vid, info.pid) in cls.PRODUCTS and (0xFF00, 0x01) in info.reports.applications else 0

    def __init__(self, info, transport_factory=None):
        super().__init__(info, transport_factory)
        self.color_mode = ColorMode.ZONES
        self.zones = [ZoneInfo(i, n) for i, n in enumerate(["Left", "Center", "Right", "Numpad"])]
        self.brightness_max = 3
        self.hw_effects = [EffectInfo("breathing", "Breathing", True, [])]

    def _show(self, frame: Frame, prev: Frame | None) -> None:
        # frame.on, frame.level (0..brightness_max), frame.colors (one per zone),
        # frame.effect (None or a hw effect id), frame.params, frame.persist / frame.transient
        self._feature(bytes([0x01, ...]))    # HIDIOCSFEATURE; self._output(...) for write()
```

Then add the class to `ALL_DRIVERS` in `bytekeys/hw/drivers/__init__.py`.

Rules of thumb:

- Never send commands that write flash in `_show` unless `frame.persist and not frame.transient`.
- Never send commands you do not understand. Leave out firmware update, erase and reset commands.
- Set `max_fps` to what the controller handles comfortably; slow controllers get their own writer thread.
- Set `self.experimental = True` until someone confirms it on real hardware.
- Add a byte-exact test in `tests/test_drivers.py` using `RecordingTransport`.

## 3. Laptop family advice

`bytekeys/models.py` maps DMI identities to a short description and the advice shown when nothing usable
was found (e.g. "install tuxedo-drivers"). Add your laptop family there.

## Testing without the hardware

Tests build fake `/sys` trees with `tests/fakesys.py`. Point the whole program at a captured tree with
`BYTEKEYS_FSROOT=/path/to/tree bytekeys status`, and use `--demo` for simulated keyboards.
