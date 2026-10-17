# Architecture

ByteKeys is plain Python 3.10+. The service and the command line tool use only the standard library;
the control center adds Qt 6 (PySide6 or PyQt6).

```
bytekeys/
├── hw/                  hardware layer: everything that turns real hardware into Device objects
│   ├── base.py          Device, Frame, capabilities (zones, effects, features)
│   ├── sysfs_leds.py    kernel LED class: brightness, multicolor, System76, ASUS TUF, Dell, Toshiba, Sony...
│   ├── wmi_zones.py     non-LED kernel interfaces: HP Omen, legacy Alienware, Acer (facer)
│   ├── hidraw.py        /dev/hidraw I/O and a HID report descriptor parser
│   ├── hid.py           base class + discovery for USB/I2C HID controllers
│   ├── drivers/         native controller drivers (Lenovo, ITE 8291, ASUS Aura, Dell, MSI, LampArray)
│   ├── openrgb.py       OpenRGB SDK client
│   ├── logind.py        unprivileged brightness through systemd-logind
│   ├── demo.py          simulated keyboards
│   └── registry.py      runs every backend and merges the results
├── engine/              the lighting engine
│   ├── core.py          Engine: state, render loop, writer threads, persistence, profiles
│   ├── effects.py       software effects (frame generators)
│   ├── rules.py         automation rules: triggers, actions, validation
│   ├── sensors.py       power, battery, CPU temperature/load, Caps Lock, ambient light, idle
│   ├── inputwatch.py    input activity (timestamps only) for idle rules and Reactive; the launch key
│   └── state.py         validation of everything clients send
├── ipc.py               JSON-lines RPC over a Unix socket + SocketClient / LocalClient
├── daemon.py            bytekeysd
├── cli.py               bytekeys
├── service.py           install the service from a source tree or the AppImage
├── power.py             performance modes, fans, firmware fan curves, charge limit, temperatures
├── modes.py             quick modes (Static/Breathing/Color cycle...) shared by GUI and CLI
├── models.py            known laptop families, advice and vendor launch keys
└── gui/                 Qt control center
    ├── app.py           main window, sidebar navigation, toasts, single instance
    ├── bridge.py        keeps the GUI in sync with the engine (events, live monitoring)
    ├── pages/           home, lighting, performance, automation, profiles, settings
    ├── widgets/         kit (cards, gauges, tiles, sliders, color wheel), fan curve editor, keyboard preview
    ├── shortcuts.py     GNOME / KDE shortcut for the launch key
    ├── launchkey.py     "press the key" detection
    ├── icons.py, theme.py
    └── tray.py
```

## Devices and frames

A backend creates `Device` objects that describe capabilities (color mode, zones, brightness range,
hardware effects, extra features). Devices never decide what to show: the engine gives them a `Frame`
(on/off, hardware brightness level, one color per zone, optional hardware effect and parameters) and the
device puts it on the hardware, diffing against the previous frame to avoid redundant writes.

Two frame flags matter for hardware longevity:

- `transient` marks animation steps. Drivers must never store those in flash.
- `persist` asks the firmware to remember a settled look (ASUS `kbd_rgb_mode` cmd 1, Aura 0xB4, ITE save
  flag). It is only sent when the user enables *Save to keyboard memory*, and only after the look has been
  unchanged for a few seconds.

## Engine

The engine keeps, per device, the user's chosen state (`states`) and the *effective* state after rules
(`effective`). A single render thread:

1. reads the sensors that enabled rules need (about once a second, immediately on input activity),
2. evaluates rules and composes the effective state,
3. renders a frame per device (software effects at up to `fps`, capped per device by `max_fps`),
4. hands frames to one writer thread per device; the newest frame wins, so slow controllers never stall
   the others,
5. polls hardware brightness to follow Fn keys (adopting the change and pausing rules that overrode
   brightness until they stop applying),
6. notices resume from suspend (CLOCK_BOOTTIME vs CLOCK_MONOTONIC) and re-applies everything (lighting,
   fan curves, charge limit), and notices performance mode changes made elsewhere (Fn keys, the desktop),
7. rescans when LED or hidraw devices appear or disappear,
8. saves state to `/var/lib/bytekeys/state.json` (portable mode: `~/.local/state/bytekeys`).

Nothing is written to a device until the user changes something or saved state is restored, so merely
running ByteKeys never alters the lighting.

## Performance and fans

`power.py` reads and writes firmware-managed controls only: the platform profile (through
power-profiles-daemon when it runs), ASUS firmware fan curves, ASUS full fan speed and the battery charge
limit. Fan curves are validated before they reach the kernel. The engine stores curves per performance
mode in `state.json`, writes enabled curves last (switching any fan back to firmware control resets all
of them), re-applies them after mode changes, boot and resume, and checks every second that enabled
curves are still active. See [SUPPORTED_HARDWARE.md](SUPPORTED_HARDWARE.md#performance-modes-fans-and-battery).

## Launch key

`inputwatch.py` compares key presses with one configured code (`settings.launch_key`, defaulting to the
laptop's vendor key from `models.py`) and emits a `launch` event that brings the control center to the
front. While the user asks to detect a key, it accepts only an allowlist of special keys. The GUI can also
detect the key from its own key events, and adds a desktop shortcut so the key starts ByteKeys when it
is closed.

## Rules

A rule is `{trigger, action, target}`. While the trigger holds, the action's partial state is layered on
top of the user's state (later rules win). When the user changes a setting that an active rule
overrides, that rule is suspended for the device until it stops applying. Thresholds have hysteresis.

## Service and clients

`bytekeysd` listens on `/run/bytekeys/bytekeysd.sock` (mode 0666) and checks the peer's credentials
(`SO_PEERCRED`) per request: reading is open, writing is limited to root, the `bytekeys` group and users
with an active local logind session. All input is validated in `engine/state.py` and `engine/rules.py`;
device paths are never taken from clients.

Clients (`bytekeys`, the GUI) use `ipc.connect()`, which falls back to an in-process engine when no service
is running. Both clients expose the same `call()`/`subscribe()` interface, so the GUI does not care which
one it has.

## Packaging

- `packaging/stage.sh` lays out an installation tree (used by `make install` and the `.deb`).
- `packaging/deb/build-deb.sh` builds an architecture-independent `.deb` with systemd integration.
- `packaging/appimage/build-appimage.sh` bundles a relocatable CPython (python-build-standalone) and
  PySide6. The AppImage can install the service on demand (`bytekeys service install`).
- `.github/workflows/release.yml` builds both on every `v*` tag and publishes a GitHub release.
