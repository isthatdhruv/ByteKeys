"""Known laptop families: what lighting they have and how to get it working.

Detection itself never depends on this table (devices are found by probing
the kernel and USB buses), but the table lets ByteKeys explain what it found
and, more importantly, what to do when it found nothing.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field


@dataclass
class Family:
    id: str
    title: str
    match: dict[str, str]               # DMI field -> regex; all must match
    lighting: str                       # what this family usually has
    expects_rgb: bool = False
    advice: list[str] = field(default_factory=list)   # shown when nothing usable was found
    tips: list[str] = field(default_factory=list)     # always shown
    layout: str = "compact"


TUXEDO_DRIVERS = (
    "Install tuxedo-drivers (DKMS), which adds keyboard lighting support for Clevo and "
    "Uniwill/Tongfang based laptops: https://github.com/tuxedocomputers/tuxedo-drivers"
)
OPENRGB = (
    "Install OpenRGB and start it with its SDK server enabled (openrgb --server); ByteKeys "
    "will then control the keyboard through it."
)

FAMILIES: list[Family] = [
    Family(
        "asus-tuf", "ASUS TUF Gaming",
        {"sys_vendor": r"ASUSTeK", "product_name|product_family": r"TUF"},
        "Single-zone RGB keyboard driven by the asus-wmi kernel driver (kbd_rgb_mode).",
        expects_rgb=True,
        advice=["Use Linux 6.1 or newer, which added TUF keyboard RGB support to asus-wmi."],
    ),
    Family(
        "asus-rog", "ASUS ROG",
        {"sys_vendor": r"ASUSTeK", "product_name|product_family": r"ROG|Strix|Zephyrus|Scar|Flow"},
        "Aura RGB keyboard over USB (0b05:xxxx); brightness also through asus-wmi.",
        expects_rgb=True,
        advice=["Most ROG keyboards are supported by asusctl (https://asus-linux.org) and OpenRGB.",
                OPENRGB],
        tips=["If asusd (asusctl) is running, let only one program control the keyboard."],
        layout="full",
    ),
    Family(
        "asus", "ASUS",
        {"sys_vendor": r"ASUSTeK"},
        "White keyboard backlight through asus-wmi (asus::kbd_backlight).",
    ),
    Family(
        "lenovo-legion", "Lenovo Legion / LOQ / IdeaPad Gaming",
        {"sys_vendor": r"LENOVO", "product_version|product_family": r"Legion|LOQ|IdeaPad Gaming"},
        "Most models have a 4-zone RGB keyboard on a USB ITE controller (048d:c9xx); "
        "Legion 7/Pro 7 models have per-key RGB.",
        expects_rgb=True,
        advice=["Per-key Legion keyboards are not natively supported yet. " + OPENRGB],
        layout="full",
    ),
    Family(
        "lenovo-thinkpad", "Lenovo ThinkPad",
        {"sys_vendor": r"LENOVO", "product_version|product_family": r"ThinkPad"},
        "White backlight with Off/Low/High levels through thinkpad_acpi.",
    ),
    Family(
        "lenovo", "Lenovo IdeaPad / Yoga / ThinkBook",
        {"sys_vendor": r"LENOVO"},
        "White backlight through ideapad-laptop (platform::kbd_backlight) when present.",
    ),
    Family(
        "dell-gaming", "Dell G-Series",
        {"sys_vendor": r"Dell", "product_name": r"\bG1[56]\b|\bG[357] 15|\bG[357]\b"},
        "4-zone RGB models use an AlienFX USB controller (187c:0550/0551); others are white.",
        expects_rgb=True,
        advice=[OPENRGB],
        layout="full",
    ),
    Family(
        "alienware", "Alienware",
        {"sys_vendor": r"Alienware|Dell", "product_name": r"Alienware"},
        "AlienFX lighting over USB (187c:xxxx) or alienware-wmi zones.",
        expects_rgb=True,
        advice=[OPENRGB],
        layout="full",
    ),
    Family(
        "dell", "Dell",
        {"sys_vendor": r"Dell"},
        "White backlight through dell-laptop, with a firmware timeout setting.",
    ),
    Family(
        "hp-omen", "HP Omen / Victus",
        {"sys_vendor": r"^HP|Hewlett", "product_name|product_family": r"OMEN|Victus"},
        "Four-zone RGB models are controlled through WMI.",
        expects_rgb=True,
        advice=["Four-zone RGB needs the hp-omen WMI driver that exposes "
                "/sys/devices/platform/hp-wmi/rgb_zones (out-of-tree or newer kernels)."],
        layout="full",
    ),
    Family(
        "hp", "HP",
        {"sys_vendor": r"^HP|Hewlett"},
        "Many HP keyboards are switched by firmware only (Fn key) and are not visible to Linux.",
    ),
    Family(
        "acer-gaming", "Acer Predator / Nitro",
        {"sys_vendor": r"Acer", "product_name|product_family": r"Predator|Nitro|Helios|Triton"},
        "Four-zone RGB through Acer's gaming WMI interface.",
        expects_rgb=True,
        advice=["Install the acer-predator-turbo-and-rgb-keyboard-linux-module (provides "
                "/dev/acer-gkbbl-0): https://github.com/JafarAkhondali/acer-predator-turbo-and-rgb-keyboard-linux-module"],
        layout="full",
    ),
    Family(
        "acer", "Acer",
        {"sys_vendor": r"Acer"},
        "Mostly firmware-controlled white backlights.",
    ),
    Family(
        "msi", "MSI",
        {"sys_vendor": r"Micro-Star|MSI"},
        "Per-key SteelSeries keyboards (USB 1038:xxxx), older 3-zone SteelSeries KLM (1770:ff00), "
        "or white backlights through msi-ec.",
        expects_rgb=True,
        advice=[OPENRGB],
        layout="full",
    ),
    Family(
        "razer", "Razer Blade",
        {"sys_vendor": r"Razer"},
        "Razer Chroma keyboard over USB (1532:xxxx).",
        expects_rgb=True,
        advice=["Install OpenRazer (https://openrazer.github.io) or " + OPENRGB],
    ),
    Family(
        "gigabyte", "Gigabyte / AORUS",
        {"sys_vendor": r"GIGABYTE|AORUS"},
        "Per-key RGB over USB.",
        expects_rgb=True,
        advice=[OPENRGB],
        layout="full",
    ),
    Family(
        "system76", "System76",
        {"sys_vendor": r"System76"},
        "White or RGB backlight through system76_acpi (color attribute).",
    ),
    Family(
        "clevo", "Clevo / TUXEDO / XMG / Tongfang family",
        {"sys_vendor|board_vendor": r"CLEVO|Notebook|TUXEDO|SchenkerTechnologiesGmbH|XMG|PCSpecialist|"
                                    r"Eluktronics|SAGER|Sager|Metabox|Uniwill|TongFang|Monster|Mechrevo|"
                                    r"Hasee|Origin|Medion|Machenike|Thunderobot"},
        "1-zone, 3-zone or per-key RGB, either through tuxedo-drivers or a USB ITE controller.",
        expects_rgb=True,
        advice=[TUXEDO_DRIVERS],
        layout="full",
    ),
    Family(
        "apple", "Apple MacBook",
        {"sys_vendor": r"Apple"},
        "White backlight through applesmc (Intel Macs) or the Asahi drivers.",
    ),
    Family(
        "framework", "Framework",
        {"sys_vendor": r"Framework"},
        "Framework 13: white backlight via the ChromeOS EC. Framework 16: QMK keyboard modules "
        "(USB 32ac:xxxx) with optional RGB.",
        advice=["RGB Framework 16 modules can be controlled with OpenRGB or VIA."],
    ),
    Family(
        "chromebook", "Chromebook",
        {"sys_vendor": r"Google"},
        "White backlight through the ChromeOS EC (chromeos::kbd_backlight).",
    ),
    Family(
        "samsung", "Samsung Galaxy Book",
        {"sys_vendor": r"SAMSUNG"},
        "White backlight through samsung-galaxybook (Linux 6.15+) or samsung-laptop.",
    ),
    Family(
        "huawei", "Huawei / Honor",
        {"sys_vendor": r"HUAWEI|HONOR"},
        "White backlight through huawei-wmi on supported models.",
    ),
    Family(
        "toshiba", "Toshiba / Dynabook",
        {"sys_vendor": r"TOSHIBA|Dynabook"},
        "White backlight with firmware modes through toshiba_acpi.",
    ),
    Family(
        "lg", "LG gram",
        {"sys_vendor": r"LG Electronics"},
        "White backlight through lg-laptop.",
    ),
]


def _field_matches(dmi: dict[str, str], fields: str, pattern: str) -> bool:
    rx = re.compile(pattern, re.IGNORECASE)
    return any(rx.search(dmi.get(f, "") or "") for f in fields.split("|"))


def family_for(dmi: dict[str, str]) -> Family | None:
    for fam in FAMILIES:
        if all(_field_matches(dmi, fields, pattern) for fields, pattern in fam.match.items()):
            return fam
    return None


def hints(dmi: dict[str, str], devices: list[dict], *, privileged: bool,
          openrgb_seen: bool = False) -> list[dict]:
    """User-facing advice derived from the machine identity and what was found."""
    out: list[dict] = []
    fam = family_for(dmi)
    if fam:
        out.append({"level": "info", "text": f"{fam.title}: {fam.lighting}"})
    real = [d for d in devices if d.get("backend") != "demo"]
    has_rgb = any(d.get("color_mode") != "none" for d in real)
    if not real and len(devices) > len(real):
        out.append({"level": "info", "text": "Demo mode: showing simulated keyboards."})
    elif not real:
        out.append({"level": "warn", "text": "No controllable keyboard light was found."})
        advice = fam.advice if fam and fam.advice else [
            "Some keyboards are switched only by the firmware (Fn key) and are invisible to Linux.",
            "Make sure your laptop's platform driver is loaded and up to date (newer kernels add support).",
            OPENRGB,
        ]
        out += [{"level": "tip", "text": a} for a in advice]
    elif fam and fam.expects_rgb and not has_rgb:
        out.append({"level": "warn", "text": "Only a single-color backlight was found, but this laptop "
                                             "family usually has RGB lighting."})
        out += [{"level": "tip", "text": a} for a in fam.advice]
    if fam:
        out += [{"level": "tip", "text": t} for t in fam.tips]
    if real and not privileged and any(d.get("access") for d in real):
        out.append({"level": "tip", "text": "Running without the ByteKeys service: some controls are "
                                            "unavailable until it is installed."})
    if not openrgb_seen and shutil.which("openrgb") and (not real or (fam and fam.expects_rgb and not has_rgb)):
        out.append({"level": "tip", "text": "OpenRGB is installed. Start it with the SDK server enabled "
                                            "(openrgb --server) and press Rescan."})
    return out


# The vendor control-center key ("launch key") by laptop family, as evdev codes.
# Sources: the kernel's asus-nb-wmi, hid-asus and hp-wmi keymaps and systemd's 60-keyboard.hwdb.
LAUNCH_KEYS = {
    "asus-tuf": 202,      # Armoury Crate key: KEY_PROG3 through asus-nb-wmi (KEY_PROG1 on N-KEY keyboards)
    "asus-rog": 202,
    "asus": 148,          # MyASUS key -> KEY_PROG1
    "acer-gaming": 148,   # NitroSense / PredatorSense key -> KEY_PROG1
    "hp-omen": 149,       # OMEN key -> KEY_PROG2
    "msi": 171,           # MSI Center key -> KEY_CONFIG
    "samsung": 148,       # Samsung Settings key (Fn+F1) -> KEY_PROG1
    "huawei": 171,        # PC Manager |M| key -> KEY_CONFIG
}
LAUNCH_KEY_NAMES = {
    "asus-tuf": "Armoury Crate key", "asus-rog": "Armoury Crate key", "asus": "MyASUS key",
    "acer-gaming": "NitroSense / PredatorSense key", "hp-omen": "OMEN key", "msi": "MSI Center key",
    "samsung": "Samsung Settings key", "huawei": "PC Manager key",
}
# Keys that the desktop itself also acts on (opening Settings, the calculator, mic mute...).
DESKTOP_KEYS = {171, 183, 140, 226}


def default_launch_key(dmi: dict[str, str], hid_keyboard: bool = False) -> int:
    """The vendor key of this laptop; *hid_keyboard*: an ASUS N-KEY (hid-asus) keyboard is present."""
    fam = family_for(dmi)
    if fam is None:
        return 0
    if fam.id in ("asus-tuf", "asus-rog") and hid_keyboard:
        return 148        # hid-asus reports the Armoury Crate / ROG key as KEY_PROG1
    if fam.id == "msi" and _field_matches(dmi, "product_name|product_family", r"Modern|Prestige|Summit|Creator"):
        return 148        # these MSI models send KEY_PROG1 (Creation Center key)
    return LAUNCH_KEYS.get(fam.id, 0)


def launch_key_name(dmi: dict[str, str], code: int) -> str:
    """A friendly name for *code*, using the vendor's name when it is that laptop's launch key."""
    fam = family_for(dmi)
    if code and fam and fam.id in LAUNCH_KEY_NAMES:
        if fam.id in ("asus-tuf", "asus-rog") and code in (148, 202):
            return LAUNCH_KEY_NAMES[fam.id]
        if code == default_launch_key(dmi):
            return "Creation Center key" if fam.id == "msi" and code == 148 else LAUNCH_KEY_NAMES[fam.id]
    return {148: "Launch key 1", 149: "Launch key 2", 202: "Launch key 3", 203: "Launch key 4",
            171: "Settings key", 156: "Bookmarks key", 140: "Calculator key", 360: "Vendor key",
            364: "Favorites key", 425: "Presentation key", 138: "Help key", 141: "Setup key", 226: "Media key",
            358: "Info key", 444: "Notification key", 579: "Control panel key", 701: "Performance key",
            **{656 + i: f"Macro key {1 + i}" for i in range(5)},
            **{183 + i: f"F{13 + i}" for i in range(12)}}.get(code, f"Key {code}" if code else "None")
