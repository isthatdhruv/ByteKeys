# Changelog

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
