"""A desktop keyboard shortcut for the launch key, so it opens ByteKeys even when it is closed.

The ByteKeys service reports the launch key to a running control center; a
desktop shortcut also starts ByteKeys when it is not running, without any
background process. GNOME-style desktops (GNOME, Ubuntu, Pop!_OS, Budgie,
Zorin) are set up live through gsettings; KDE Plasma reads a shortcut file
at the next login. Other desktops get instructions.
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess

from .. import APP_ID, APP_NAME

SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/bytekeys/"
ITEM = f"{SCHEMA}.custom-keybinding:{PATH}"
GNOME_DESKTOPS = ("gnome", "ubuntu", "pop", "budgie", "zorin", "unity")

# evdev code -> the xkb keysym desktops see for it (xkeyboard-config's evdev keymap).
KEYSYMS = {
    148: "XF86Launch1", 149: "XF86Launch2", 202: "XF86Launch3", 203: "XF86Launch4",
    171: "XF86Tools", 183: "XF86Tools", 140: "XF86Calculator", 226: "XF86AudioMedia",
    156: "XF86Favorites", 364: "XF86Favorites", 360: "XF86VendorLogo", 358: "XF86Info",
    **{184 + i: f"XF86Launch{5 + i}" for i in range(5)},    # F14-F18
}
# GNOME's own bindings that would take the key first (media-keys schema key).
GNOME_CONFLICTS = {"XF86Tools": "control-center-static", "XF86Calculator": "calculator-static",
                   "XF86AudioMedia": "media-static"}
# Qt's names for keysyms, as KDE writes them (Qt 6 / Plasma 6).
KDE_NAMES = {**{f"XF86Launch{n}": f"Launch ({n})" for n in range(1, 10)},
             "XF86Tools": "Tools", "XF86Favorites": "Favorites", "XF86Calculator": "Calculator",
             "XF86AudioMedia": "Launch Media"}


def desktop() -> str:
    return (os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("DESKTOP_SESSION") or "").lower()


def backend() -> str | None:
    """'gnome', 'kde' or None when the shortcut cannot be set up automatically."""
    name = desktop()
    if any(d in name for d in GNOME_DESKTOPS) and shutil.which("gsettings"):
        return "gnome"
    if "kde" in name or "plasma" in name:
        return "kde"
    return None


def supported() -> bool:
    return backend() is not None


def keysym(code: int) -> str | None:
    return KEYSYMS.get(int(code or 0))


def _wayland() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY")) or os.environ.get("XDG_SESSION_TYPE") == "wayland"


def gnome_binding(code: int) -> str | None:
    """A mutter accelerator: the keysym name, or the raw xkb keycode (evdev + 8) for keys without one."""
    sym = keysym(code)
    if sym:
        return sym
    if code and (code + 8 <= 255 or _wayland()):    # X11 keycodes stop at 255
        return f"0x{code + 8:x}"
    return None


def kde_binding(code: int) -> str | None:
    name = KDE_NAMES.get(keysym(code) or "")
    if name and name.startswith("Launch (") and os.environ.get("KDE_SESSION_VERSION") == "5":
        name = f"Launch ({int(name[8:-1]) + 2})"    # Qt 5 numbers the launch keys two higher
    return name


def binding(code: int) -> str | None:
    kind = backend()
    if kind == "gnome":
        return gnome_binding(code)
    if kind == "kde":
        return kde_binding(code)
    return None


def conflicts(code: int) -> bool:
    """The desktop itself also acts on this key (opens Settings, the calculator...)."""
    return keysym(code) in GNOME_CONFLICTS


# ------------------------------------------------------------------- GNOME
def _gsettings(*args: str) -> str | None:
    try:
        out = subprocess.run(["gsettings", *args], capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _quote(text: str) -> str:
    """A GVariant string literal."""
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _parse_list(text: str | None) -> list[str]:
    if not text:
        return []
    text = text.strip()
    if text.startswith("@as"):
        text = text[3:].strip()
    try:
        value = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return []
    return [str(v) for v in value] if isinstance(value, (list, tuple)) else []


def _format_list(items: list[str]) -> str:
    return "[" + ", ".join(_quote(i) for i in items) + "]"


def _gnome_installed() -> str | None:
    if PATH not in _parse_list(_gsettings("get", SCHEMA, "custom-keybindings")):
        return None
    value = _gsettings("get", ITEM, "binding")
    if not value:
        return None
    try:
        return str(ast.literal_eval(value)) or None
    except (ValueError, SyntaxError):
        return None


def _gnome_install(accel: str, command: str) -> tuple[bool, str]:
    for key, value in (("name", APP_NAME), ("command", command), ("binding", accel)):
        if _gsettings("set", ITEM, key, _quote(value)) is None:
            return False, "Could not change the desktop shortcuts (gsettings failed)."
    paths = _parse_list(_gsettings("get", SCHEMA, "custom-keybindings"))
    if PATH not in paths and _gsettings("set", SCHEMA, "custom-keybindings", _format_list([*paths, PATH])) is None:
        return False, "Could not change the desktop shortcuts (gsettings failed)."
    conflict = GNOME_CONFLICTS.get(accel)
    if conflict and accel in _parse_list(_gsettings("get", SCHEMA, conflict)):
        # GNOME would grab the key for itself; hand it to ByteKeys (given back on removal).
        remaining = [k for k in _parse_list(_gsettings("get", SCHEMA, conflict)) if k != accel]
        _gsettings("set", SCHEMA, conflict, _format_list(remaining))
    return True, "Desktop shortcut added: the key opens ByteKeys even when it is closed."


def _gnome_uninstall() -> None:
    accel = _gnome_installed()
    paths = _parse_list(_gsettings("get", SCHEMA, "custom-keybindings"))
    if PATH in paths:
        _gsettings("set", SCHEMA, "custom-keybindings", _format_list([p for p in paths if p != PATH]))
    for key in ("name", "command", "binding"):
        _gsettings("reset", ITEM, key)
    conflict = GNOME_CONFLICTS.get(accel or "")
    if conflict:
        _gsettings("reset", SCHEMA, conflict)   # GNOME's own binding back


# --------------------------------------------------------------------- KDE
def _kde_file() -> str:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "kglobalaccel", f"{APP_ID}.desktop")


def _kde_installed() -> str | None:
    try:
        with open(_kde_file(), encoding="utf-8") as f:
            for line in f:
                if line.startswith("X-KDE-Shortcuts="):
                    return line.split("=", 1)[1].strip() or None
    except OSError:
        pass
    return None


def _kde_install(name: str, command: str) -> tuple[bool, str]:
    path = _kde_file()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("[Desktop Entry]\nType=Application\n"
                    f"Name={APP_NAME}\nExec={command}\nIcon={APP_ID}\n"
                    "NoDisplay=true\nStartupNotify=false\n"
                    f"X-KDE-Shortcuts={name}\n")
    except OSError as e:
        return False, f"Could not write the KDE shortcut: {e.strerror or e}"
    return True, "Desktop shortcut added; KDE starts using it after you log in again."


# -------------------------------------------------------------------- public
def installed() -> str | None:
    """The key binding of our shortcut, or None."""
    kind = backend()
    if kind == "gnome":
        return _gnome_installed()
    if kind == "kde":
        return _kde_installed()
    return None


def install(code: int, command: str) -> tuple[bool, str]:
    """Bind the key with evdev *code* to *command*. Returns (ok, message)."""
    kind = backend()
    accel = binding(code)
    if kind is None:
        return False, manual_instructions(code, command)
    if accel is None:
        return False, "Your desktop cannot use this key for a shortcut."
    uninstall()
    if kind == "gnome":
        return _gnome_install(accel, command)
    return _kde_install(accel, command)


def uninstall() -> None:
    kind = backend()
    if kind == "gnome":
        _gnome_uninstall()
    elif kind == "kde":
        try:
            os.unlink(_kde_file())
        except OSError:
            pass


def manual_instructions(code: int, command: str) -> str:
    sym = keysym(code) or f"key code {code}"
    return (f"Add a custom keyboard shortcut in your desktop settings: press the launch key "
            f"(it is called {sym}) and use this command: {command}")
