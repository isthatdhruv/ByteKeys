"""JSON-lines RPC between the ByteKeys service and its clients.

Transport: a Unix stream socket (default /run/bytekeys/bytekeysd.sock).
Each request is one line ``{"id": 1, "method": "set", "params": {...}}``
answered by ``{"id": 1, "result": ...}`` or ``{"id": 1, "error": {...}}``.
After ``subscribe`` the server also pushes ``{"event": kind, "data": ...}``.

Authorization uses the peer's credentials (SO_PEERCRED): anybody may read,
but changing lighting is reserved to root, members of the ``bytekeys``
group, and users sitting at an active local session - the same people
logind lets change screen brightness.

When no service is running, :class:`LocalClient` hosts an engine inside the
calling process ("portable mode") behind the very same interface.
"""

from __future__ import annotations

import grp
import json
import logging
import os
import pwd
import queue
import socket
import socketserver
import struct
import threading
from typing import Any, Callable

from .hw.base import AccessError, DeviceError

log = logging.getLogger(__name__)

SOCKET_PATH = os.environ.get("BYTEKEYS_SOCKET", "/run/bytekeys/bytekeysd.sock")
MAX_LINE = 4 * 1024 * 1024
MAX_CLIENTS = 64
ADMIN_GROUP = "bytekeys"

READ_METHODS = {"hello", "system", "devices", "device", "rules", "rule_catalog", "profiles",
                "settings", "sensors", "report"}
WRITE_METHODS = {"set", "toggle", "nudge", "feature", "rules_set", "profile_save", "profile_apply",
                 "profile_delete", "profile_rename", "settings_set", "flash", "rescan"}


class ServiceError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def dispatch(engine, method: str, p: dict) -> Any:
    """Route one RPC call to the engine."""
    table: dict[str, Callable[[dict], Any]] = {
        "hello": lambda p: engine.hello(),
        "system": lambda p: engine.system(),
        "devices": lambda p: engine.device_list(),
        "device": lambda p: engine.device(p["device"]),
        "set": lambda p: engine.set(p.get("device"), p.get("changes") or {}),
        "toggle": lambda p: engine.toggle(p.get("device")),
        "nudge": lambda p: engine.nudge(p.get("device"), int(p.get("step", 1))),
        "feature": lambda p: engine.set_feature(p["device"], p["feature"], p.get("value")),
        "rules": lambda p: engine.get_rules(),
        "rules_set": lambda p: engine.set_rules(p["rules"]),
        "rule_catalog": lambda p: engine.rule_catalog(),
        "profiles": lambda p: engine.profile_list(),
        "profile_save": lambda p: engine.profile_save(p["name"]),
        "profile_apply": lambda p: engine.profile_apply(p["name"]),
        "profile_delete": lambda p: engine.profile_delete(p["name"]),
        "profile_rename": lambda p: engine.profile_rename(p["old"], p["new"]),
        "settings": lambda p: engine.get_settings(),
        "settings_set": lambda p: engine.set_settings(p.get("changes") or {}),
        "sensors": lambda p: engine.sensor_readings(),
        "flash": lambda p: engine.flash(p.get("device"), p.get("color", "#ffffff"),
                                        p.get("count", 3), p.get("period", 0.5)),
        "rescan": lambda p: engine.rescan(),
        "report": lambda p: engine.report(),
    }
    fn = table.get(method)
    if fn is None:
        raise ServiceError("unknown_method", f"unknown method {method!r}")
    if not isinstance(p, dict):
        raise ServiceError("invalid", "params must be an object")
    try:
        return fn(p)
    except ServiceError:
        raise
    except KeyError as e:
        raise ServiceError("not_found", str(e.args[0]) if e.args else "not found") from None
    except (ValueError, TypeError) as e:
        raise ServiceError("invalid", str(e)) from None
    except AccessError as e:
        raise ServiceError("access", f"{e}. {e.hint}" if e.hint else str(e)) from None
    except DeviceError as e:
        raise ServiceError("device", str(e)) from None


# ===================================================================== server
def peer_credentials(sock: socket.socket) -> tuple[int, int, int]:
    data = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    return struct.unpack("3i", data)


def _active_local_session(uid: int, sessions_dir: str = "/run/systemd/sessions") -> bool | None:
    """True/False from logind's session files; None when logind is not in use."""
    try:
        names = os.listdir(sessions_dir)
    except OSError:
        return None
    for name in names:
        if name.endswith(".ref"):
            continue
        fields = {}
        try:
            with open(os.path.join(sessions_dir, name), encoding="utf-8") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.rstrip("\n").split("=", 1)
                        fields[k] = v
        except OSError:
            continue
        if (fields.get("UID") == str(uid) and fields.get("ACTIVE") == "1"
                and fields.get("REMOTE") != "1" and fields.get("CLASS", "user").startswith("user")):
            return True
    return False


def authorized(uid: int) -> bool:
    if uid == 0 or uid == os.getuid():
        return True
    try:
        group = grp.getgrnam(ADMIN_GROUP)
        user = pwd.getpwuid(uid)
        if user.pw_gid == group.gr_gid or user.pw_name in group.gr_mem:
            return True
    except KeyError:
        pass
    active = _active_local_session(uid)
    return True if active is None else active


class _Handler(socketserver.StreamRequestHandler):
    server: "_UnixServer"

    def setup(self) -> None:
        super().setup()
        self._wlock = threading.Lock()
        self._queue: queue.Queue = queue.Queue(maxsize=2000)
        self._subscribed = False
        try:
            self.pid, self.uid, self.gid = peer_credentials(self.request)
        except OSError:
            self.pid, self.uid, self.gid = -1, -1, -1

    def _send(self, obj: dict) -> None:
        data = (json.dumps(obj, separators=(",", ":"), default=str) + "\n").encode()
        with self._wlock:
            self.wfile.write(data)
            self.wfile.flush()

    def _on_event(self, kind: str, data: dict) -> None:
        try:
            self._queue.put_nowait({"event": kind, "data": data})
        except queue.Full:
            pass  # a stalled client misses events rather than stalling the engine

    def _sender(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            try:
                self._send(item)
            except OSError:
                return

    def handle(self) -> None:
        engine = self.server.engine
        while True:
            try:
                line = self.rfile.readline(MAX_LINE + 1)
            except OSError:
                return
            if not line:
                return
            if len(line) > MAX_LINE:
                self._send({"id": None, "error": {"code": "invalid", "message": "request too large"}})
                return
            try:
                req = json.loads(line)
                rid, method = req.get("id"), req.get("method")
                params = req.get("params") or {}
            except (ValueError, AttributeError):
                self._send({"id": None, "error": {"code": "invalid", "message": "malformed request"}})
                continue
            if method == "subscribe":
                if not self._subscribed:
                    self._subscribed = True
                    threading.Thread(target=self._sender, daemon=True).start()
                    engine.subscribe(self._on_event)
                self._send({"id": rid, "result": True})
                continue
            if method in WRITE_METHODS and not authorized(self.uid):
                self._send({"id": rid, "error": {
                    "code": "forbidden",
                    "message": "Only the user at the active local session (or the 'bytekeys' "
                               "group) may change the lighting.",
                }})
                continue
            try:
                result = dispatch(engine, method, params)
                self._send({"id": rid, "result": result})
            except ServiceError as e:
                self._send({"id": rid, "error": {"code": e.code, "message": e.message}})
            except OSError:
                return
            except Exception as e:
                log.exception("request %r failed", method)
                self._send({"id": rid, "error": {"code": "internal", "message": str(e)}})

    def finish(self) -> None:
        if self._subscribed:
            self.server.engine.unsubscribe(self._on_event)
            self._queue.put(None)
        try:
            super().finish()
        except OSError:
            pass


class _UnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, path: str, engine):
        self.engine = engine
        self.slots = threading.BoundedSemaphore(MAX_CLIENTS)
        super().__init__(path, _Handler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)       # too many clients: refuse instead of piling up threads
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


class Server:
    def __init__(self, engine, path: str = SOCKET_PATH):
        self.engine = engine
        self.path = path
        self._server: _UnixServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass
        self._server = _UnixServer(self.path, self.engine)
        os.chmod(self.path, 0o666)   # authorization happens per request
        self._thread = threading.Thread(target=self._server.serve_forever, name="bytekeys-ipc", daemon=True)
        self._thread.start()
        log.info("listening on %s", self.path)

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        try:
            os.unlink(self.path)
        except OSError:
            pass


# ===================================================================== clients
class SocketClient:
    """Talks to a running ByteKeys service."""

    mode = "service"

    def __init__(self, path: str = SOCKET_PATH, timeout: float = 15.0):
        self.path = path
        self.timeout = timeout
        self._lock = threading.Lock()
        self._next = 0
        self._sock = self._connect()
        self._rfile = self._sock.makefile("rb")
        self._subs: list[socket.socket] = []

    def _connect(self) -> socket.socket:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect(self.path)
        except OSError:
            sock.close()
            raise
        return sock

    def call(self, method: str, **params) -> Any:
        with self._lock:
            self._next += 1
            rid = self._next
            msg = json.dumps({"id": rid, "method": method, "params": params}) + "\n"
            try:
                self._sock.sendall(msg.encode())
                while True:
                    line = self._rfile.readline(MAX_LINE + 1)
                    if not line:
                        raise ServiceError("disconnected", "the ByteKeys service closed the connection")
                    reply = json.loads(line)
                    if reply.get("id") == rid:
                        break
            except OSError as e:
                raise ServiceError("disconnected", f"lost connection to the ByteKeys service: {e}") from None
        if "error" in reply:
            err = reply["error"]
            raise ServiceError(err.get("code", "error"), err.get("message", "error"))
        return reply.get("result")

    def subscribe(self, callback: Callable[[str, dict], None]) -> None:
        sock = self._connect()
        sock.sendall(b'{"id":0,"method":"subscribe"}\n')
        rfile = sock.makefile("rb")
        # Wait for the acknowledgement so no event after this call can be missed.
        while True:
            line = rfile.readline(MAX_LINE + 1)
            if not line:
                raise ServiceError("disconnected", "the ByteKeys service closed the connection")
            if json.loads(line).get("id") == 0:
                break
        sock.settimeout(None)
        self._subs.append(sock)

        def reader():
            try:
                for line in rfile:
                    try:
                        msg = json.loads(line)
                    except ValueError:
                        continue
                    if "event" in msg:
                        callback(msg["event"], msg.get("data") or {})
            except OSError:
                pass
            callback("disconnected", {})

        threading.Thread(target=reader, name="bytekeys-events", daemon=True).start()

    def close(self) -> None:
        for sock in [self._sock, *self._subs]:
            try:
                sock.close()
            except OSError:
                pass


class LocalClient:
    """Runs the engine in-process when no service is available."""

    mode = "portable"

    def __init__(self, engine):
        self.engine = engine

    @staticmethod
    def _copy(value):
        return json.loads(json.dumps(value, default=str))

    def call(self, method: str, **params) -> Any:
        if method == "subscribe":
            return True
        return self._copy(dispatch(self.engine, method, self._copy(params)))

    def subscribe(self, callback: Callable[[str, dict], None]) -> None:
        self.engine.subscribe(lambda kind, data: callback(kind, self._copy(data)))

    def close(self) -> None:
        self.engine.stop()


def user_state_dir() -> str:
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return os.path.join(base, "bytekeys")


def service_available(path: str = SOCKET_PATH) -> bool:
    try:
        SocketClient(path, timeout=2).close()
        return True
    except OSError:
        return False


def connect(*, path: str = SOCKET_PATH, local: bool = False, demo: bool = False,
            state_dir: str | None = None, restore: bool = True):
    """A client for the service, falling back to an in-process engine."""
    if not local:
        try:
            client = SocketClient(path)
            client.call("hello")
            return client
        except (OSError, ServiceError):
            pass
    from .engine import Engine
    engine = Engine(state_dir or user_state_dir(), privileged=os.geteuid() == 0,
                    demo=demo, mode="portable", restore=restore)
    engine.start()
    return LocalClient(engine)
