"""Information about the machine: DMI identity, kernel modules, USB devices."""

from __future__ import annotations

import os
import platform

from . import fsroot

DMI = "/sys/class/dmi/id"

# Kernel modules that matter for keyboard lighting, with a friendly label.
RELEVANT_MODULES = {
    "asus_wmi": "ASUS WMI", "asus_nb_wmi": "ASUS notebook WMI", "asus_armoury": "ASUS Armoury",
    "thinkpad_acpi": "ThinkPad ACPI", "dell_laptop": "Dell laptop", "dell_wmi": "Dell WMI",
    "ideapad_laptop": "Lenovo IdeaPad", "legion_laptop": "Lenovo Legion (out-of-tree)",
    "lenovo_wmi_gamezone": "Lenovo WMI GameZone", "system76_acpi": "System76 ACPI",
    "tuxedo_keyboard": "TUXEDO keyboard", "clevo_wmi": "Clevo WMI", "clevo_acpi": "Clevo ACPI",
    "uniwill_wmi": "Uniwill WMI", "tuxedo_io": "TUXEDO IO", "ite_8291": "ITE 8291 (tuxedo)",
    "ite_829x": "ITE 829x (tuxedo)", "ite_8297": "ITE 8297 (tuxedo)", "clevo_xsm_wmi": "Clevo XSM WMI",
    "hp_wmi": "HP WMI", "hp_omen_wmi": "HP Omen (out-of-tree)", "alienware_wmi": "Alienware WMI",
    "acer_wmi": "Acer WMI", "facer": "Acer Predator RGB (out-of-tree)", "msi_ec": "MSI EC",
    "msi_wmi": "MSI WMI", "samsung_laptop": "Samsung laptop", "samsung_galaxybook": "Samsung Galaxy Book",
    "huawei_wmi": "Huawei WMI", "lg_laptop": "LG laptop", "toshiba_acpi": "Toshiba ACPI",
    "applesmc": "Apple SMC", "cros_kbd_led_backlight": "ChromeOS keyboard backlight",
    "cros_ec_lpcs": "ChromeOS EC", "framework_laptop": "Framework (out-of-tree)",
    "razerkbd": "OpenRazer keyboard", "hid_asus": "ASUS HID", "hid_lenovo": "Lenovo HID",
    "gigabyte_wmi": "Gigabyte WMI", "xiaomi_wmi": "Xiaomi WMI",
}


def dmi() -> dict[str, str]:
    fields = ["sys_vendor", "product_name", "product_family", "product_version", "product_sku",
              "board_vendor", "board_name", "board_version", "chassis_type", "chassis_vendor",
              "bios_vendor", "bios_version", "bios_date"]
    return {f: (fsroot.read(f"{DMI}/{f}") or "").strip() for f in fields}


def loaded_modules() -> list[str]:
    text = fsroot.read("/proc/modules") or ""
    return sorted({line.split()[0] for line in text.splitlines() if line.strip()})


def relevant_modules() -> list[str]:
    loaded = set(loaded_modules())
    return [m for m in RELEVANT_MODULES if m in loaded]


def usb_devices() -> list[dict]:
    out = []
    base = "/sys/bus/usb/devices"
    for name in fsroot.listdir(base):
        if ":" in name:
            continue
        vid = fsroot.read(f"{base}/{name}/idVendor")
        pid = fsroot.read(f"{base}/{name}/idProduct")
        if not vid or not pid:
            continue
        out.append({
            "id": f"{vid}:{pid}",
            "vid": int(vid, 16),
            "pid": int(pid, 16),
            "manufacturer": fsroot.read(f"{base}/{name}/manufacturer") or "",
            "product": fsroot.read(f"{base}/{name}/product") or "",
            "path": name,
        })
    return out


def os_release() -> str:
    text = fsroot.read("/etc/os-release") or ""
    for line in text.splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip().strip('"')
    return platform.system()


def is_laptop() -> bool:
    # SMBIOS chassis types: 8 portable, 9 laptop, 10 notebook, 14 sub notebook,
    # 30 tablet, 31 convertible, 32 detachable.
    try:
        return int(fsroot.read(f"{DMI}/chassis_type") or "0") in (8, 9, 10, 14, 30, 31, 32)
    except ValueError:
        return False


def friendly_model(info: dict[str, str] | None = None) -> str:
    info = info or dmi()
    vendor = info.get("sys_vendor", "")
    product = info.get("product_name", "")
    family = info.get("product_family", "")
    short_vendor = {
        "ASUSTeK COMPUTER INC.": "ASUS", "LENOVO": "Lenovo", "Dell Inc.": "Dell", "HP": "HP",
        "Hewlett-Packard": "HP", "Micro-Star International Co., Ltd.": "MSI",
        "Acer": "Acer", "Razer": "Razer", "Apple Inc.": "Apple", "SAMSUNG ELECTRONICS CO., LTD.": "Samsung",
        "GIGABYTE": "Gigabyte", "Framework": "Framework", "System76": "System76",
        "TUXEDO": "TUXEDO", "HUAWEI": "Huawei", "XIAOMI": "Xiaomi", "TOSHIBA": "Toshiba",
        "Dynabook Inc.": "Dynabook", "LG Electronics": "LG", "Google": "Google",
    }.get(vendor, vendor)
    # Lenovo puts the marketing name in product_version and a type code in product_name.
    version = info.get("product_version", "")
    if vendor == "LENOVO" and version and version.lower() not in ("lenovo", "none", "default string"):
        product = version
    if "_" in product:
        product = product.split("_")[0]  # "TUF Gaming F15 FX507ZC4_FX507ZC4"
    name = product or family
    if short_vendor and not name.lower().startswith(short_vendor.lower()):
        name = f"{short_vendor} {name}"
    return name.strip() or "Unknown computer"


def summary() -> dict:
    info = dmi()
    return {
        "dmi": info,
        "model": friendly_model(info),
        "laptop": is_laptop(),
        "kernel": platform.release(),
        "os": os_release(),
        "arch": platform.machine(),
        "modules": relevant_modules(),
        "appimage": bool(os.environ.get("APPIMAGE")),
    }
