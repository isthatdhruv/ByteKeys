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

## Performance modes, fans and battery

ByteKeys only uses controls that the laptop's firmware runs itself, so a crash can never leave a fan
stopped or stuck. It never drives fan PWM directly.

| Control | Interface | Notes |
|---|---|---|
| Performance modes | `/sys/firmware/acpi/platform_profile` (+ `_choices`) | Switched through power-profiles-daemon over D-Bus when it runs (so the desktop's power menu stays in sync), otherwise written directly. Names: low-power, cool, quiet, balanced, balanced-performance, performance, max-power, custom. ASUS offers quiet / balanced / performance. |
| Fan curves (ASUS) | hwmon `asus_custom_fan_curve`: `pwmN_auto_point[1-8]_{temp,pwm}`, `pwmN_enable` | 8 points per fan, °C and 0–255 (the firmware stores percent). Enable `1` sends the curve to the firmware, `2` returns to the firmware curve, `3` reloads the factory curve of the active mode. The kernel validates nothing, so ByteKeys does: temperatures rise, speeds never drop, at least 50 % from 80 °C and at least 70 % at the last point. |
| Full fan speed (ASUS) | hwmon `asus`: `pwm1_enable` `0` / `2` | Only on "SPEC 8.3" fans (no `pwm1` file); older AGFN fans have no full-speed switch. Turning it on or off clears custom curves, which ByteKeys re-applies afterwards. |
| Charge limit | `power_supply/BAT*/charge_control_end_threshold` (+ `_start_threshold`, `charge_types`); IdeaPad `conservation_mode`; `charge_types` `Long_Life` | Presets 60 / 80 / 100 % (LG: 80 / 100). A start threshold is kept 5 % below the end (ThinkPad, Dell, Chromebooks refuse start > end), and Dell's `charge_types` is switched to `Custom`, the only mode in which its thresholds apply. ASUS resets the limit to 100 % at every boot and some ASUS firmware only honours 60 / 80 / 100, so the service re-applies it at start and after resume. |
| Temperatures and fans | hwmon (`coretemp`, `k10temp`, `asus`, `amdgpu`...), `nvidia-smi` | The NVIDIA GPU temperature is read only while the GPU is awake (`runtime_status` = active), so monitoring never wakes it. |

**Why the service keeps re-applying fan curves.** asus-wmi forgets custom curves on *every* performance
mode write (even of the same mode, by Fn+F5, by power-profiles-daemon, or by any other program), when
another fan is switched back to the firmware curve, at boot, and it never restores them after resume.
ByteKeys stores curves per mode, writes enabled curves last, re-applies them after mode changes, boot and
resume, and checks every second that an enabled curve is still active. If something keeps resetting
them (for example asusd running alongside), it backs off and logs a warning. The service starts after
power-profiles-daemon, which rewrites its saved mode when it starts.

The firmware has its own default curve for each mode, but the kernel only reads the one of the mode it
booted in. The first time a mode is used, the service reloads that mode's factory curve once (`3`) and
remembers it, so the editor always shows the curve that is really running.

## Launch keys

The key that opens the vendor's app on Windows, as Linux reports it (kernel keymaps and systemd's
`60-keyboard.hwdb`). ByteKeys picks the default for your laptop; **Settings → Launch key → Detect key**
learns any other one. Only special keys can be learned, never letters, digits or modifiers.

| Laptop | Key | evdev code | Keysym |
|---|---|---|---|
| ASUS TUF / ROG with WMI hotkeys (e.g. TUF F15 FX507) | Armoury Crate | KEY_PROG3 (202) | XF86Launch3 |
| ASUS ROG and newer TUF with an N-KEY USB/I2C keyboard (hid-asus) | Armoury Crate / ROG | KEY_PROG1 (148) | XF86Launch1 |
| ASUS Zenbook / Vivobook | MyASUS | KEY_PROG1 (148) | XF86Launch1 |
| Acer Nitro / Predator | NitroSense / PredatorSense | KEY_PROG1 (148) | XF86Launch1 |
| HP OMEN / Victus | OMEN | KEY_PROG2 (149) | XF86Launch2 |
| MSI gaming | MSI Center | KEY_CONFIG (171) | XF86Tools |
| MSI Modern / Prestige | Creation Center | KEY_PROG1 (148) | XF86Launch1 |
| Samsung Galaxy Book | Samsung Settings (Fn+F1) | KEY_PROG1 (148) | XF86Launch1 |
| Huawei MateBook | PC Manager (\|M\|) | KEY_CONFIG (171) | XF86Tools |

How it reaches ByteKeys:

- The **service** watches the input devices for that one key and tells a running control center to show
  itself. Nothing else is recorded.
- A **desktop shortcut** also starts ByteKeys when it is closed. On GNOME-based desktops ByteKeys adds a
  custom shortcut through gsettings (keys without a keysym are bound by their raw keycode on Wayland); on
  KDE Plasma it installs a shortcut file that takes effect at the next login. Other desktops need a manual
  shortcut running `bytekeys-gui`.
- XF86Tools (KEY_CONFIG, KEY_F13), XF86Calculator and XF86AudioMedia are also used by the desktop (GNOME
  opens Settings on XF86Tools). The GNOME shortcut takes such a key over and gives it back when removed.
- Codes above 247 (e.g. KEY_VENDOR) never reach X11 applications; they work with GNOME on Wayland.
