# Changelog

## 1.1.0 (2026-10-17)

A control center for the whole laptop: fans, performance modes and the vendor launch key, in a new look.

- **Redesigned control center** in a graphite and warm-light look that follows the new logo, with a
  sidebar for Home, Lighting, Performance, Automation, Profiles and Settings (Effects moved into
  Lighting, Rules became Automation, System became Settings). Dark and light themes.
- **New logo**, app icon, favicon and banners (frosted glass keycaps with a warm light).
- **Home dashboard**: live CPU/GPU temperatures, fan speeds and CPU load, performance modes, quick
  keyboard controls (power, brightness, modes, colors) and the battery with its charge limit.
- **Performance and fans**: firmware performance modes (platform profile, synced with
  power-profiles-daemon); custom fan curves that the laptop's firmware runs (ASUS), with presets, safety
  limits and one curve per mode, kept active whenever the kernel drops them (mode changes, boot, resume);
  full fan speed; battery charge limit (charge thresholds, Dell custom mode, IdeaPad and "Long Life"
  conservation modes).
- **Launch key**: the vendor app key (Armoury Crate, NitroSense/PredatorSense, OMEN, MSI Center,
  MyASUS...) opens ByteKeys. The service watches only that key; a GNOME or KDE shortcut also starts
  ByteKeys when it is closed. Keys can be detected with or without the service.
- Lighting page with animated effect previews, a color wheel, effect settings and device options in one
  view.
- New `bytekeys perf`, `bytekeys fans` and `bytekeys charge-limit` commands.
- The control center notices an outdated service and offers to update it; installing the service from
  the AppImage now also restarts an older running version.
- `--demo` also simulates fans and performance modes.

## 1.0.0 (2026-10-17)

First public release.

- Control panel with live keyboard preview, one-click modes, colors for the whole keyboard, zones or
  single keys, effects, rules, profiles and a tray icon; dark and light themes.
- `bytekeys` command line tool and `bytekeysd` system service with a JSON socket API.
- Automatic detection of the laptop and its keyboard lighting, ready-made profiles and rules, and advice
  when a kernel module is missing.
- Kernel backends: LED class (white, multicolor, grouped zones and per-key), ASUS TUF RGB and power
  states, System76, Dell timeouts and ambient light, Toshiba, Sony, LG, TUXEDO hardware modes, HP Omen,
  legacy Alienware and Acer Predator/Nitro zones.
- Built-in USB drivers: Lenovo Legion/LOQ/IdeaPad Gaming 4-zone, ITE 8291 per-key, ASUS ROG Aura,
  Dell G-series/Alienware AW-ELC, MSI 3-zone, HID LampArray.
- OpenRGB SDK bridge for keyboards ByteKeys has no driver for.
- Software effects for every keyboard: Breathing, Blink, Color cycle, Wave, Gradient, Starlight,
  Reactive typing, Candle.
- Rules: power source, battery level, time of day, idle, Caps Lock, CPU temperature and load, ambient
  light; actions for brightness, color, effects, profiles, warnings and color gradients.
- Restores lighting at boot and after resume; follows Fn brightness keys.
- `.deb` and AppImage packages; the AppImage can install the service on demand.
