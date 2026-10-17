"""Unprivileged brightness writes through systemd-logind.

logind lets the user of the active local session set the ``brightness``
attribute of LED and backlight devices (``Session.SetBrightness``, systemd
243+). That is enough for white backlights in portable mode, before the root
service is installed. Color attributes still need the service.
"""

from __future__ import annotations

import shutil
import subprocess

_available: bool | None = None


def available() -> bool:
    global _available
    if _available is None:
        _available = shutil.which("busctl") is not None
    return _available


def set_brightness(subsystem: str, name: str, value: int) -> bool:
    """Ask logind to write *value* to /sys/class/<subsystem>/<name>/brightness."""
    if not available():
        return False
    for session in ("auto", "self"):
        try:
            result = subprocess.run(
                [
                    "busctl", "call", "--system", "--quiet",
                    "org.freedesktop.login1",
                    f"/org/freedesktop/login1/session/{session}",
                    "org.freedesktop.login1.Session",
                    "SetBrightness", "ssu", subsystem, name, str(int(value)),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        if result.returncode == 0:
            return True
    return False
