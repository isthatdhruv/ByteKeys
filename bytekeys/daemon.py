"""bytekeysd: the ByteKeys system service."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
import sys
import threading

from . import __version__
from .engine import Engine
from .ipc import SOCKET_PATH, Server

log = logging.getLogger("bytekeysd")


def sd_notify(state: str) -> None:
    """Tell systemd about our state (Type=notify) without libsystemd."""
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return
    if addr.startswith("@"):
        addr = "\0" + addr[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
            s.connect(addr)
            s.sendall(state.encode())
    except OSError as e:
        log.debug("sd_notify failed: %s", e)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bytekeysd", description="ByteKeys keyboard lighting service")
    ap.add_argument("--socket", default=SOCKET_PATH, help="control socket path (default: %(default)s)")
    ap.add_argument("--state-dir", default=os.environ.get("STATE_DIRECTORY", "/var/lib/bytekeys"),
                    help="where settings are stored (default: %(default)s)")
    ap.add_argument("--demo", action="store_true", help="add simulated keyboards")
    ap.add_argument("--no-input", action="store_true",
                    help="do not watch input devices (disables idle rules and Reactive)")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--version", action="version", version=f"bytekeysd {__version__}")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    privileged = os.geteuid() == 0
    if not privileged:
        log.warning("not running as root: only devices this user can access will work")

    engine = Engine(args.state_dir, privileged=privileged, demo=args.demo, mode="service",
                    watch_input=privileged and not args.no_input)
    engine.start()
    server = Server(engine, args.socket)
    try:
        server.start()
    except OSError as e:
        log.error("cannot listen on %s: %s", args.socket, e)
        engine.stop()
        return 1

    stop = threading.Event()

    def on_signal(signum, _frame):
        log.info("received signal %d, shutting down", signum)
        stop.set()

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    sd_notify("READY=1")
    log.info("ByteKeys %s ready (%d device(s))", __version__, len(engine.devices))
    stop.wait()
    sd_notify("STOPPING=1")
    server.stop()
    engine.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
