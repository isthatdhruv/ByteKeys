// Everything the pages say about ByteKeys, taken from the repository: README.md, CHANGELOG.md,
// docs/*.md, the CLI (bytekeys/cli.py) and the rule catalog (bytekeys/engine/rules.py). When one of
// those changes, change it here too.

export const features = [
  {
    id: "detect",
    title: "Works with most laptops",
    body: "ByteKeys finds keyboard lights the Linux kernel already exposes, drives common USB lighting controllers itself and uses OpenRGB for everything else.",
  },
  {
    id: "setup",
    title: "Detected and set up for you",
    body: "It identifies your laptop model, picks the right driver, creates sensible profiles and tells you exactly what to install when a keyboard needs an extra kernel module.",
  },
  {
    id: "effects",
    title: "Modes and effects",
    body: "Static, Breathing, Color cycle, Wave, Strobe and more. Your keyboard's own hardware modes when it has them, and software effects that work on every keyboard, even plain white ones.",
  },
  {
    id: "zones",
    title: "Zones and per-key color",
    body: "Click or drag over keys in the live keyboard preview to color them, one zone or one key at a time.",
  },
  {
    id: "rules",
    title: "Rules",
    body: "When this happens, do that: dim on battery, turn off when idle, a night schedule, low battery and overheat warnings, a Caps Lock indicator.",
  },
  {
    id: "profiles",
    title: "Profiles",
    body: "Save a look and switch to it from the control panel, the tray, the command line or a rule.",
  },
  {
    id: "restore",
    title: "Remembers your lighting",
    body: "Your lighting comes back at boot and after sleep, and ByteKeys follows the laptop's own Fn brightness keys.",
  },
  {
    id: "cli",
    title: "Tray icon and command line",
    body: "A tray icon for quick changes and the bytekeys command for scripts and keyboard shortcuts.",
  },
  {
    id: "safe",
    title: "Safe by design",
    body: "A small root service does the hardware work and the control panel runs as you. Writes to keyboard memory are opt-in, and dangerous controller commands are never sent.",
  },
] as const;

/** Brands named in the README, for the "works with" strip. */
export const kernelBrands = [
  "ASUS",
  "ThinkPad",
  "Dell",
  "System76",
  "TUXEDO",
  "Clevo",
  "Apple",
  "Framework",
  "Chromebooks",
  "Samsung",
  "LG",
  "Toshiba",
  "Sony",
] as const;

export const usbControllers = [
  "Lenovo Legion 4-zone",
  "ITE 8291 per-key",
  "ASUS ROG Aura",
  "Dell G-series and Alienware",
  "MSI 3-zone",
  "HID LampArray",
] as const;

export const modes = ["Static", "Breathing", "Color cycle", "Wave", "Strobe"] as const;

export const softwareEffects = [
  "Breathing",
  "Blink",
  "Color cycle",
  "Wave",
  "Gradient",
  "Starlight",
  "Reactive typing",
  "Candle",
] as const;

/** The control panel's pages, with the README's description of each and its screenshot. */
export const panelPages = [
  {
    id: "lighting",
    name: "Lighting",
    shot: "lighting-zones",
    body: "Live keyboard preview, power and brightness, one-click modes, colors for the whole keyboard or selected zones and keys, and device options such as firmware timeouts or boot and sleep lighting.",
  },
  {
    id: "effects",
    name: "Effects",
    shot: "effects",
    body: "Every software and hardware effect your keyboard supports, with speed, direction and colors.",
  },
  {
    id: "rules",
    name: "Rules",
    shot: "rules",
    body: "Automations. Rules apply top to bottom, and a manual change wins until the rule stops applying.",
  },
  {
    id: "profiles",
    name: "Profiles",
    shot: "profiles",
    body: "Saved looks for all your keyboards.",
  },
  {
    id: "system",
    name: "System",
    shot: "system",
    body: "Detected hardware, hints, the service, preferences and a diagnostic report.",
  },
] as const;

/** Rule triggers and actions, named as in the rule editor (bytekeys/engine/rules.py). */
export const ruleTriggers = [
  "Power source is on battery or plugged in",
  "Battery is below a level",
  "Time is between two times",
  "No keyboard or mouse input for a while",
  "Caps Lock is on",
  "CPU is hotter than a temperature",
  "CPU load is above a level",
  "Room is darker than a light level",
] as const;

export const ruleActions = [
  "Turn the lights off",
  "Set brightness",
  "Set color",
  "Play an effect",
  "Switch to profile",
  "Flash as a warning",
  "Color by CPU temperature",
  "Color by battery level",
  "Color by CPU load",
] as const;

/** Ready-made rules offered on first run, all off until you turn them on. */
export const readyRules = [
  { id: "idle-off", name: "Turn off when idle", detail: "after 2 minutes without input" },
  { id: "battery-dim", name: "Dim on battery", detail: "to 40%" },
  { id: "night", name: "Night mode", detail: "the Night profile from 22:00 to 07:00" },
  { id: "low-battery", name: "Low battery warning", detail: "a red pulse below 15%" },
  { id: "capslock", name: "Caps Lock indicator", detail: "RGB keyboards" },
  { id: "hot-cpu", name: "Overheat warning", detail: "an orange pulse above 90 °C, RGB keyboards" },
] as const;

/** The README's command line examples. */
export const cliExamples = [
  { cmd: "bytekeys status", note: "keyboards and their lighting" },
  { cmd: "bytekeys brightness 60", note: "or: up / down" },
  { cmd: "bytekeys mode breathing", note: "static, breathing, cycle, wave, strobe" },
  { cmd: 'bytekeys color "#ff8800"', note: "whole keyboard" },
  { cmd: "bytekeys color red green blue white", note: "one color per zone" },
  { cmd: "bytekeys effect wave --speed 70", note: "" },
  { cmd: "bytekeys profile apply Night", note: "" },
  { cmd: "bytekeys rules enable battery-dim", note: "" },
  { cmd: "bytekeys flash --color red --count 3", note: "e.g. from a notification script" },
  { cmd: "bytekeys report", note: "diagnostics for bug reports" },
] as const;

/** Every command, with the help text bytekeys --help prints (bytekeys/cli.py). */
export const cliReference = [
  { cmd: "status", help: "show keyboards and lighting (default)" },
  { cmd: "list", help: "list devices" },
  { cmd: "on | off | toggle", help: "turn the lights on, off, or toggle them" },
  { cmd: "brightness VALUE", help: "set brightness: 0-100, up or down" },
  { cmd: "color COLOR...", help: "set color(s): #rrggbb, r,g,b or a name; one per zone allowed (--zone N for one zone)" },
  { cmd: "effect NAME", help: "play an effect (--speed, --direction left|right, --color, repeatable)" },
  { cmd: "mode NAME", help: "switch mode: static, breathing, cycle, wave or strobe" },
  { cmd: "effects", help: "list available effects" },
  { cmd: "profile list|save|apply|delete|rename", help: "manage profiles" },
  { cmd: "rules list|enable|disable|export|import", help: "list, enable, disable, export or import automation rules" },
  { cmd: "feature [NAME] [VALUE]", help: "show or change device specific settings" },
  { cmd: "flash", help: "blink the keyboard (--color, --count, --period)" },
  { cmd: "sensors", help: "show sensor readings used by rules" },
  { cmd: "settings [key=value...]", help: "show or change settings" },
  { cmd: "report", help: "print a diagnostic report" },
  { cmd: "rescan", help: "look for keyboards again" },
  { cmd: "gui", help: "open the control panel" },
  { cmd: "service install|uninstall|status", help: "install, remove or check the system service" },
] as const;

export type HardwareStatus = "Tested" | "Supported" | "Experimental";

export const statusNote: Record<HardwareStatus, string> = {
  Tested: "Confirmed on real hardware.",
  Supported: "A standard kernel interface or a maintained third-party driver.",
  Experimental: "Implemented from documented protocols, waiting for someone to confirm it on that hardware.",
};

/** The README's supported hardware table. */
export const hardware: {
  id: string;
  name: string;
  ids?: string;
  through: string;
  throughUrl?: string;
  lighting: string;
  status: HardwareStatus;
}[] = [
  {
    id: "asus-tuf",
    name: "ASUS TUF Gaming",
    through: "kernel asus-wmi",
    lighting: "RGB; Static, Breathing, Color cycle, Strobe, Pulse; boot, awake and sleep lighting",
    status: "Tested",
  },
  {
    id: "asus-rog",
    name: "ASUS ROG (USB Aura)",
    ids: "0b05:1854, 1866, 1869, 19b6, 1a30",
    through: "built-in driver",
    lighting: "RGB; Breathing, Color cycle, Wave, Pulse",
    status: "Experimental",
  },
  {
    id: "lenovo-legion",
    name: "Lenovo Legion, LOQ and IdeaPad Gaming 4-zone",
    ids: "048d:c955 to c995",
    through: "built-in driver",
    lighting: "4 zones; Breathing, Color cycle, Wave",
    status: "Experimental",
  },
  {
    id: "ite-8291",
    name: "Clevo, Tongfang, XMG, Eluktronics and TUXEDO per-key (ITE 8291)",
    ids: "048d:6004, 6006, 600a, 600b, ce00",
    through: "built-in driver",
    lighting: "Per-key; 9 hardware effects",
    status: "Experimental",
  },
  {
    id: "tuxedo",
    name: "TUXEDO, Clevo and Uniwill with tuxedo-drivers",
    through: "kernel, tuxedo-drivers",
    throughUrl: "https://github.com/tuxedocomputers/tuxedo-drivers",
    lighting: "1-zone, 3-zone or per-key; hardware modes",
    status: "Supported",
  },
  {
    id: "system76",
    name: "System76",
    through: "kernel system76_acpi",
    lighting: "RGB or white",
    status: "Supported",
  },
  {
    id: "dell-alienware",
    name: "Dell G15 and G16, Alienware (AW-ELC)",
    ids: "187c:0550, 0551",
    through: "built-in driver",
    lighting: "4 zones; Breathing",
    status: "Experimental",
  },
  {
    id: "alienware-legacy",
    name: "Older Alienware",
    through: "kernel alienware-wmi",
    lighting: "Zones",
    status: "Supported",
  },
  {
    id: "hp-omen",
    name: "HP Omen and Victus",
    through: "omen-rgb-keyboard or hp-omen module",
    throughUrl: "https://github.com/alessandromrc/omen-rgb-keyboard",
    lighting: "4 zones; animations",
    status: "Supported",
  },
  {
    id: "acer",
    name: "Acer Predator and Nitro",
    through: "facer module",
    throughUrl: "https://github.com/JafarAkhondali/acer-predator-turbo-and-rgb-keyboard-linux-module",
    lighting: "4 zones; effects",
    status: "Supported",
  },
  {
    id: "msi-3zone",
    name: "MSI SteelSeries 3-zone",
    ids: "1770:ff00",
    through: "built-in driver",
    lighting: "3 zones",
    status: "Experimental",
  },
  {
    id: "lamparray",
    name: "HID LampArray keyboards (Windows Dynamic Lighting)",
    through: "built-in driver",
    lighting: "Per-lamp",
    status: "Experimental",
  },
  {
    id: "white",
    name: "ThinkPad, IdeaPad, Yoga, Dell, Apple, Framework, Chromebook, Samsung, LG gram, Toshiba, Sony, MSI (msi-ec), Bitland and more",
    through: "kernel",
    lighting: "White, with levels and firmware timeouts where available",
    status: "Supported",
  },
  {
    id: "openrgb",
    name: "MSI per-key, Razer, Gigabyte and AORUS, Legion per-key and hundreds more",
    through: "OpenRGB SDK (openrgb --server)",
    throughUrl: "https://openrgb.org",
    lighting: "Whatever OpenRGB supports",
    status: "Supported",
  },
];

/** docs/SUPPORTED_HARDWARE.md: kernel interfaces. */
export const kernelInterfaces = [
  { driver: "asus-wmi (TUF)", path: "asus::kbd_backlight, kbd_rgb_mode, kbd_rgb_state", notes: "Brightness 0 to 3; static, breathing, color cycle, strobe and pulse. Use kernel 6.5 or later (not 6.10.0): 6.1 to 6.4 and 6.10 had bugs here." },
  { driver: "thinkpad_acpi", path: "tpacpi::kbd_backlight", notes: "Off, Low, High." },
  { driver: "dell-laptop", path: "dell::kbd_backlight, stop_timeout, als_enabled", notes: "Firmware timeout and the ambient light switch as device settings." },
  { driver: "ideapad-laptop", path: "platform::kbd_backlight", notes: "On and off, or Off, Low, High." },
  { driver: "system76_acpi", path: "system76_acpi::kbd_backlight, color", notes: "RGB or white." },
  { driver: "tuxedo-drivers", path: "rgb:kbd_backlight, white:kbd_backlight", notes: "Multicolor 3-zone and per-key, grouped into one keyboard, with hardware modes." },
  { driver: "uniwill-laptop (7.3+)", path: "uniwill:*:kbd_backlight", notes: "Uses multi_max_intensity." },
  { driver: "applesmc, applespi, hid-apple, Asahi", path: "smc::, spi::, apple::kbd_backlight", notes: "Default triggers are switched off when ByteKeys takes control." },
  { driver: "cros_kbd_led_backlight", path: "chromeos::kbd_backlight", notes: "Chromebooks and Framework 13." },
  { driver: "samsung-galaxybook, samsung-laptop, toshiba_acpi, lg-laptop, msi-ec, bitland-mifs-wmi", path: "various", notes: "LG gram maps to Off, Low, High. Toshiba exposes its mode and timeout." },
  { driver: "sony-laptop", path: "/sys/devices/platform/sony-laptop/kbd_backlight", notes: "Off, automatic or on, plus a timeout." },
  { driver: "omen-rgb-keyboard, hp-omen-linux-module", path: "…/rgb_zones/zone0N", notes: "HP Omen and Victus four zones; animations with omen-rgb-keyboard." },
  { driver: "alienware-wmi (legacy)", path: "/sys/devices/platform/alienware-wmi/rgb_zones", notes: "4 bits per channel." },
  { driver: "facer (Acer)", path: "/dev/acer-gkbbl-0, /dev/acer-gkbbl-static-0", notes: "Effects and static zones." },
] as const;

/** docs/SUPPORTED_HARDWARE.md: USB and HID controllers with built-in drivers. */
export const usbDrivers = [
  { name: "Lenovo 4-zone (ITE)", ids: "048d:c955, c963, c965, c973, c975, c983, c984, c985, c993, c994, c995", flash: "No save command" },
  { name: "ITE 8291 rev 0.03", ids: "048d:6004, 6006, 600a, 600b, ce00", flash: "Only when you save explicitly" },
  { name: "ASUS ROG Aura", ids: "0b05:1854, 1866, 1869, 19b6, 1a30", flash: "Only when you save explicitly" },
  { name: "Dell and Alienware AW-ELC", ids: "187c:0550, 0551", flash: "Never" },
  { name: "MSI SteelSeries KLM", ids: "1770:ff00", flash: "No" },
  { name: "HID LampArray", ids: "Usage page 0x59", flash: "No" },
] as const;

export const homeFaq = [
  {
    q: "Is ByteKeys free?",
    a: "Yes. ByteKeys is free and open-source software, released under the GNU General Public License v3.0 or later. The source is on GitHub.",
  },
  {
    q: "Which laptops does ByteKeys support?",
    a: "Any laptop whose keyboard light the Linux kernel exposes (ThinkPad, Dell, ASUS, System76, TUXEDO, Apple, Framework, Chromebooks, Samsung, LG, Toshiba, Sony and more), common USB lighting controllers such as Lenovo Legion 4-zone, ITE 8291 per-key, ASUS ROG Aura, Dell G-series and Alienware, MSI 3-zone and HID LampArray, and anything OpenRGB supports.",
  },
  {
    q: "Which Linux distributions does it run on?",
    a: "The .deb package is for Debian, Ubuntu, Linux Mint, Pop!_OS and Zorin. The AppImage runs on any x86_64 distribution. From source it needs Python 3.10 or later and PyQt6 or PySide6.",
  },
  {
    q: "Why does ByteKeys install a service?",
    a: "Changing keyboard lighting needs root. A small service, bytekeysd, does the hardware work so the control panel can run as your normal user. Without it, ByteKeys runs in portable mode: brightness still works for the active desktop user, but colors, modes and background rules need the service.",
  },
  {
    q: "Is it safe for my keyboard?",
    a: "Writes to keyboard memory are opt-in and only happen once a look has stayed the same for a few seconds, never during animations. Drivers never send commands they don't understand, such as firmware update, erase or reset.",
  },
  {
    q: "Does ByteKeys record what I type?",
    a: "No. To detect idle time and run the Reactive effect, it notes when an input event happened, never which key it was. Key codes are never stored or logged.",
  },
  {
    q: "My keyboard isn't detected. What now?",
    a: "Open System and copy the report (or run bytekeys report), then open a Device support issue on GitHub with it. ByteKeys also tells you when a missing kernel module is the problem.",
  },
] as const;
