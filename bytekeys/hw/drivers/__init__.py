"""Native drivers for USB/I2C HID keyboard lighting controllers.

To add a controller, subclass :class:`bytekeys.hw.hid.HidKeyboard`, list its
USB IDs in ``PRODUCTS``, implement ``_show`` and add the class here.
See docs/ADDING_DEVICES.md. Raw HID access stays root-only on purpose: some
lighting controllers are also the keyboard, and raw access would expose keystrokes.
"""

from __future__ import annotations

from .asus_aura import AsusAura
from .dell import DellElc
from .ite8291 import Ite8291
from .lamparray import LampArray
from .lenovo import Lenovo4Zone
from .msi import MsiKlm

ALL_DRIVERS: list = [Lenovo4Zone, Ite8291, MsiKlm, AsusAura, DellElc, LampArray]
