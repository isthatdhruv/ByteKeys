"""Install or remove the ByteKeys system service without a package manager.

The .deb ships the service itself. Source checkouts and the AppImage use
this module instead: ``bytekeys service install`` copies the (pure Python)
service to /opt/bytekeys, adds a systemd unit and starts it. When not run as root it re-executes itself through pkexec (graphical
password prompt) or sudo.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

INSTALL_ROOT = "/opt/bytekeys"
LIB_DIR = f"{INSTALL_ROOT}/lib"
UNIT_PATH = "/etc/systemd/system/bytekeysd.service"
PACKAGED_UNIT = "/usr/lib/systemd/system/bytekeysd.service"
SERVICE = "bytekeysd.service"
MIN_PYTHON = (3, 10)

UNIT_TEMPLATE = """\
# Installed by "bytekeys service install". Remove with "bytekeys service uninstall".
[Unit]
Description=ByteKeys keyboard lighting service
Documentation=https://github.com/bytekeys/bytekeys
After=systemd-udevd.service

[Service]
Type=notify
ExecStart={python} -m bytekeys.daemon
Environment=PYTHONPATH={lib}
Environment=PYTHONDONTWRITEBYTECODE=1
StateDirectory=bytekeys
RuntimeDirectory=bytekeys
Restart=on-failure
RestartSec=2
{hardening}
[Install]
WantedBy=multi-user.target
"""

# Safe for a daemon that must write /sys and open /dev/hidraw* and /dev/input/*.
HARDENING = """\
NoNewPrivileges=yes
ProtectSystem=full
ProtectHome=yes
PrivateTmp=yes
ProtectHostname=yes
ProtectClock=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
RestrictNamespaces=yes
RestrictRealtime=yes
RestrictSUIDSGID=yes
LockPersonality=yes
SystemCallArchitectures=native
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK
"""


def package_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _host_python() -> str | None:
    for candidate in ("/usr/bin/python3", "/usr/local/bin/python3"):
        if not os.path.exists(candidate):
            continue
        try:
            out = subprocess.run(
                [candidate, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
                capture_output=True, text=True, timeout=10, check=True,
            ).stdout.strip()
            if tuple(int(x) for x in out.split(".")) >= MIN_PYTHON:
                return candidate
        except (OSError, subprocess.SubprocessError, ValueError):
            continue
    return None


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def status() -> dict:
    active = False
    if shutil.which("systemctl"):
        active = _run(["systemctl", "is-active", "--quiet", SERVICE], check=False).returncode == 0
    return {
        "installed": os.path.exists(UNIT_PATH) or os.path.exists(PACKAGED_UNIT),
        "managed_by_package": os.path.exists(PACKAGED_UNIT),
        "active": active,
    }


def install(source: str) -> None:
    if os.geteuid() != 0:
        raise PermissionError("installing the service requires root")
    if os.path.exists(PACKAGED_UNIT):
        print("The ByteKeys package already provides the service; enabling it.")
        _run(["systemctl", "enable", "--now", SERVICE])
        return
    python = _host_python()
    if python is None:
        bundled = os.environ.get("BYTEKEYS_BUNDLED_PYTHON")
        if not bundled or not os.path.isdir(bundled):
            raise RuntimeError("Python 3.10 or newer is required at /usr/bin/python3")
        target = f"{INSTALL_ROOT}/python"
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(bundled, target, symlinks=True)
        python = f"{target}/bin/python3"
    dest = f"{LIB_DIR}/bytekeys"
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(LIB_DIR, exist_ok=True)
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "gui"))
    os.chmod(INSTALL_ROOT, 0o755)
    with open(UNIT_PATH, "w", encoding="utf-8") as f:
        f.write(UNIT_TEMPLATE.format(python=python, lib=LIB_DIR, hardening=HARDENING))
    _run(["systemctl", "daemon-reload"])
    _run(["systemctl", "enable", "--now", SERVICE])
    print(f"ByteKeys service installed ({python}) and started.")


def uninstall() -> None:
    if os.geteuid() != 0:
        raise PermissionError("removing the service requires root")
    if os.path.exists(PACKAGED_UNIT) and not os.path.exists(UNIT_PATH):
        print("The service belongs to the ByteKeys package; remove the package instead.")
        return
    _run(["systemctl", "disable", "--now", SERVICE], check=False)
    try:
        os.unlink(UNIT_PATH)
    except FileNotFoundError:
        pass
    shutil.rmtree(INSTALL_ROOT, ignore_errors=True)
    _run(["systemctl", "daemon-reload"], check=False)
    print("ByteKeys service removed. Settings are kept in /var/lib/bytekeys.")


def _stage() -> str:
    """Copy the package somewhere root can read (AppImage FUSE mounts are private)."""
    stage = tempfile.mkdtemp(prefix="bytekeys-install-")
    os.chmod(stage, 0o755)
    shutil.copytree(package_dir(), os.path.join(stage, "bytekeys"),
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return stage


def elevate(action: str, graphical: bool) -> int:
    """Re-run *action* as root and return its exit code."""
    stage = _stage()
    python = _host_python() or sys.executable
    code = ("import sys; sys.path.insert(0, %r); from bytekeys.service import main; "
            "sys.exit(main([%r, '--source', %r]))") % (stage, action, os.path.join(stage, "bytekeys"))
    env_python = os.environ.get("BYTEKEYS_BUNDLED_PYTHON")
    if graphical and shutil.which("pkexec"):
        cmd = ["pkexec", python, "-c", code]
    elif shutil.which("sudo"):
        cmd = ["sudo"] + (["--preserve-env=BYTEKEYS_BUNDLED_PYTHON"] if env_python else []) + [python, "-c", code]
    elif shutil.which("pkexec"):
        cmd = ["pkexec", python, "-c", code]
    else:
        print("Neither pkexec nor sudo is available; run this command as root.", file=sys.stderr)
        return 1
    try:
        return subprocess.run(cmd, check=False).returncode
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bytekeys service")
    ap.add_argument("action", choices=["install", "uninstall", "status"])
    ap.add_argument("--source", default=package_dir(), help=argparse.SUPPRESS)
    ap.add_argument("--graphical", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.action == "status":
        st = status()
        print("installed:", "yes (package)" if st["managed_by_package"] else "yes" if st["installed"] else "no")
        print("running:  ", "yes" if st["active"] else "no")
        return 0
    if os.geteuid() != 0:
        return elevate(args.action, args.graphical or not sys.stdin.isatty())
    try:
        if args.action == "install":
            install(args.source)
        else:
            uninstall()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as e:
        detail = getattr(e, "stderr", "") or ""
        print(f"bytekeys service {args.action} failed: {e} {detail}".strip(), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
