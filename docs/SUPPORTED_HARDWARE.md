# Supported hardware and protocol notes

Status: **Tested** = confirmed on real hardware; **Supported** = standard kernel interface;
**Experimental** = implemented from documented protocols, waiting for confirmation. Please report results
with `bytekeys report`.

## Kernel interfaces (sysfs)

| Driver / module | LED / path | Notes |
|---|---|---|
| asus-wmi (TUF) | `asus::kbd_backlight` + `kbd_rgb_mode`, `kbd_rgb_state` | Brightness 0–3. `kbd_rgb_mode` = `cmd mode R G B speed`; cmd 0 applies, cmd 1 also saves to firmware (used only with *Save to keyboard memory*). Modes 0 static, 1 breathing, 2 color cycle, 3 strobe, 10 pulse. The awake flag of `kbd_rgb_state` must stay on or the keyboard stays dark. Kernels 6.1–6.4 and 6.10 had bugs here; use 6.5+ (not 6.10.0). **Tested** on TUF F15 FX507ZC4. |
| thinkpad_acpi | `tpacpi::kbd_backlight` | Off/Low/High. |
| dell-laptop | `dell::kbd_backlight` + `stop_timeout`, `als_enabled` | Firmware timeout and ambient light switch as device settings. |
| ideapad-laptop | `platform::kbd_backlight` | On/off or Off/Low/High. |
| system76_acpi | `system76_acpi::kbd_backlight` + `color` | RGB or white. Older system76-dkms: `color_left/center/right/extra`. |
| tuxedo-drivers | `rgb:kbd_backlight[_N]`, `white:kbd_backlight` | Multicolor; 3-zone and per-key (126 LEDs = ITE 8291 6×21, 120 = ITE 829x 6×20) grouped into one keyboard. Hardware modes via `tuxedo_keyboard/kbd_backlight_mode`; per-key updates batched with `controls/buffer_input`. |
| uniwill-laptop (7.3+) | `uniwill:*:kbd_backlight` | Uses `multi_max_intensity`. |
| applesmc / applespi / hid-apple / Asahi | `smc::`, `spi::`, `apple::kbd_backlight`, `kbd_backlight` | Default triggers are switched off when ByteKeys takes control. |
| cros_kbd_led_backlight | `chromeos::kbd_backlight` | Chromebooks, Framework 13 (the out-of-tree duplicate is ignored). |
| samsung-galaxybook, samsung-laptop, toshiba_acpi, lg-laptop, msi-ec (out-of-tree), bitland-mifs-wmi | various | LG gram maps to Off/Low/High (0/127/255). Toshiba exposes its mode and timeout. |
| sony-laptop | `/sys/devices/platform/sony-laptop/kbd_backlight` | Off / automatic / on, plus timeout. |
| omen-rgb-keyboard, hp-omen-linux-module | `…/rgb_zones/zone0N` | HP Omen/Victus four zones; animations with omen-rgb-keyboard. |
| alienware-wmi (legacy) | `/sys/devices/platform/alienware-wmi/rgb_zones` | 4 bits per channel. |
| facer (Acer) | `/dev/acer-gkbbl-0`, `/dev/acer-gkbbl-static-0` | 16-byte effect packets, 4-byte static zone packets. |

Without the service, brightness still works for the active desktop user through
`org.freedesktop.login1.Session.SetBrightness`; colors and modes need the service.

## USB / HID controllers (built-in drivers)

| Controller | IDs | Protocol summary | Writes flash? |
|---|---|---|---|
| Lenovo 4-zone (ITE) | `048d:c955 c963 c965 c973 c975 c983 c984 c985 c993 c994 c995` (+ any `048d:c9xx` with the same 33-byte report) | One feature report `CC 16 effect speed brightness R G B ×4 …` | No save command |
| ITE 8291 rev 0.03 | `048d:6004 6006 600a 600b`, `ce00` (bcdDevice 0.03) | 8-byte control reports + 64-byte row data, 6×21 matrix, row 0 at the bottom | Only with the save flag (explicit save) |
| ASUS ROG Aura | `0b05:1854 1866 1869 19b6 1a30` | 64-byte reports ID 0x5D: `B3` mode, `B5` apply | `B4` only on explicit save |
| Dell / Alienware AW-ELC | `187c:0550 0551` | 33-byte commands; running animation 0xFFFF, *finish & play* | Never (save/default/startup and flash commands are not implemented) |
| MSI SteelSeries KLM | `1770:ff00` | 8-byte reports `01 02 40 region R G B EC`, commit `41` | No |
| HID LampArray | usage page `0x59` | Standard lamp attributes and range/multi updates | No |

Not built in (use OpenRGB): Lenovo per-key "Spectrum", MSI per-key SteelSeries, Gigabyte/AORUS,
Razer (or OpenRazer).
