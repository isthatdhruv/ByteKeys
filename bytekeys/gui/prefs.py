"""GUI-only preferences and login autostart."""

from __future__ import annotations

import json
import os
import shlex
import sys

from .. import APP_ID, APP_NAME

DEFAULTS = {
    "theme": "dark",            # dark | light | system
    "tray": True,
    "close_to_tray": True,
    "keyboard_layout": "auto",  # auto | compact | full
    "last_page": "home",
    "last_device": None,
    "geometry": None,
    "launch_key_last": 0,       # the launch key to use when it is switched back on
}


def config_dir() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "bytekeys")


class Prefs:
    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(config_dir(), "gui.json")
        self.data = dict(DEFAULTS)
        try:
            with open(self.path, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self.data.update({k: v for k, v in loaded.items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass

    def __getitem__(self, key: str):
        return self.data.get(key, DEFAULTS.get(key))

    def __setitem__(self, key: str, value) -> None:
        self.data[key] = value
        self.save()

    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=1)
            os.replace(tmp, self.path)
        except OSError:
            pass


def autostart_path() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "autostart", f"{APP_ID}.desktop")


def launch_command(minimized: bool = True) -> str:
    """The command that starts this copy of ByteKeys (AppImage, package or source tree)."""
    flag = " --minimized" if minimized else ""
    appimage = os.environ.get("APPIMAGE")
    if appimage:
        return f"{shlex.quote(appimage)}{flag}"
    for candidate in ("/usr/bin/bytekeys-gui", "/usr/local/bin/bytekeys-gui"):
        if os.path.exists(candidate):
            return f"{candidate}{flag}"
    package_parent = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return (f"env PYTHONPATH={shlex.quote(package_parent)} {shlex.quote(sys.executable)} "
            f"-m bytekeys gui{flag}")


def autostart_enabled() -> bool:
    return os.path.exists(autostart_path())


def set_autostart(enabled: bool) -> None:
    path = autostart_path()
    if not enabled:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={APP_NAME}\n"
            "Comment=Keyboard lighting control\n"
            f"Exec={launch_command()}\n"
            f"Icon={APP_ID}\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
            "X-GNOME-Autostart-Delay=3\n"
        )
