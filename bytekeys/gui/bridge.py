"""Keeps the GUI in sync with the engine (service or in-process)."""

from __future__ import annotations

import logging

from .. import __version__, ipc
from ..ipc import ServiceError
from .qt import QtCore, Signal

log = logging.getLogger(__name__)


class Bridge(QtCore.QObject):
    devicesChanged = Signal()
    deviceChanged = Signal(str)
    rulesChanged = Signal()
    profilesChanged = Signal()
    settingsChanged = Signal()
    automationChanged = Signal()
    connectionChanged = Signal()
    errorOccurred = Signal(str)
    profileApplied = Signal(str)
    powerChanged = Signal()
    monitorUpdated = Signal(dict)
    launchRequested = Signal()
    _incoming = Signal(str, object)

    def __init__(self, *, demo: bool = False, local: bool = False, parent=None):
        super().__init__(parent)
        self.demo = demo
        self.local = local
        self.client = None
        self.hello: dict = {}
        self.system: dict = {}
        self.devices: dict[str, dict] = {}
        self.order: list[str] = []
        self.rules: list[dict] = []
        self.profiles: list[dict] = []
        self.settings: dict = {}
        self.catalog: dict = {}
        self.power: dict = {}
        self.monitor: dict = {}
        self.active_rules: set[str] = set()
        self.outdated = False           # the service is an older version without some methods
        self._monitor_timer = QtCore.QTimer(self)
        self._monitor_timer.setInterval(1500)
        self._monitor_timer.timeout.connect(self.poll_monitor)
        self._monitor_users = 0
        self._incoming.connect(self._on_event, QtCore.Qt.ConnectionType.QueuedConnection)
        self._retry = QtCore.QTimer(self)
        self._retry.setInterval(1500)
        self._retry.timeout.connect(self._try_reconnect)
        self._retries = 0

    # ------------------------------------------------------------ connection
    @property
    def mode(self) -> str:
        return getattr(self.client, "mode", "none")

    def start(self) -> None:
        self.client = ipc.connect(local=self.local, demo=self.demo, restore=True)
        self.client.subscribe(lambda kind, data: self._incoming.emit(kind, data))
        self.refresh_all()

    def switch_to_service(self) -> bool:
        """After installing the service: drop the in-process engine and use the service."""
        try:
            client = ipc.SocketClient()
            client.call("hello")
        except (OSError, ServiceError):
            return False
        old, self.client = self.client, client
        if old is not None:
            old.close()
        self.client.subscribe(lambda kind, data: self._incoming.emit(kind, data))
        self.refresh_all()
        return True

    def _try_reconnect(self) -> None:
        self._retries += 1
        if self.switch_to_service():
            self._retry.stop()
            self._retries = 0
            return
        if self._retries >= 8:   # the service is gone; keep working in portable mode
            self._retry.stop()
            self._retries = 0
            self.local = True
            self.start()

    def close(self) -> None:
        if self.client is not None:
            self.client.close()

    # ----------------------------------------------------------------- calls
    def call(self, method: str, **params):
        if self.client is None:
            return None
        try:
            return self.client.call(method, **params)
        except ServiceError as e:
            if e.code == "disconnected":
                self._retry.start()
            if e.code == "unknown_method":
                if not self.outdated:
                    self.outdated = True
                    self.errorOccurred.emit("The ByteKeys service is older than this app. Update it in Settings.")
                return None
            self.errorOccurred.emit(e.message)
            return None

    @property
    def service_version(self) -> str:
        return str(self.hello.get("version", ""))

    def refresh_all(self) -> None:
        self.hello = self.call("hello") or {}
        self.outdated = self.mode == "service" and self.service_version not in ("", __version__)
        self.system = self.call("system") or {}
        self._set_devices(self.call("devices") or [])
        self.rules = self.call("rules") or []
        self.profiles = self.call("profiles") or []
        self.settings = self.call("settings") or {}
        self.catalog = self.call("rule_catalog") or {}
        self.power = (self.call("power") or {}) if not self.outdated else {}
        self.connectionChanged.emit()
        self.devicesChanged.emit()
        self.rulesChanged.emit()
        self.profilesChanged.emit()
        self.settingsChanged.emit()
        self.powerChanged.emit()

    # --------------------------------------------------------------- power
    def start_monitoring(self) -> None:
        self._monitor_users += 1
        if not self._monitor_timer.isActive():
            self.poll_monitor()
            self._monitor_timer.start()

    def stop_monitoring(self) -> None:
        self._monitor_users = max(0, self._monitor_users - 1)
        if not self._monitor_users:
            self._monitor_timer.stop()

    def poll_monitor(self) -> None:
        if self.outdated:
            self._monitor_timer.stop()
            return
        data = self.call("monitor")
        if data is not None:
            self.monitor = data
            if data.get("profile") != self.power.get("profile") and self.power:
                # changed elsewhere (Fn key, desktop settings) and the event was missed
                self.power = self.call("power") or self.power
                self.powerChanged.emit()
            self.monitorUpdated.emit(data)

    def _power_result(self, result) -> None:
        if result is not None:
            self.power = result
            self.powerChanged.emit()

    def set_power_profile(self, profile: str) -> None:
        self._power_result(self.call("power_profile", profile=profile))

    def set_fan_curve(self, fan: str, points, enabled: bool) -> None:
        self._power_result(self.call("fan_curve", fan=fan, points=points, enabled=enabled))

    def reset_fan_curve(self, fan: str) -> None:
        self._power_result(self.call("fan_curve_reset", fan=fan))

    def set_fan_boost(self, on: bool) -> None:
        self._power_result(self.call("fan_boost", on=on))

    def set_charge_limit(self, limit: int) -> None:
        self._power_result(self.call("charge_limit", limit=limit))

    def refresh_system(self) -> None:
        self.system = self.call("system") or self.system
        self.connectionChanged.emit()

    def _set_devices(self, views: list[dict]) -> None:
        self.devices = {v["id"]: v for v in views}
        self.order = [v["id"] for v in views]
        self.active_rules = {r for v in views for r in v.get("rules_active", [])}

    def _merge(self, views) -> None:
        for v in views or []:
            self.devices[v["id"]] = v
            self.deviceChanged.emit(v["id"])

    def set_state(self, device: str, changes: dict) -> None:
        self._merge(self.call("set", device=device, changes=changes))

    def toggle(self, device: str | None = None) -> None:
        self._merge(self.call("toggle", device=device))

    def set_feature(self, device: str, feature: str, value) -> None:
        view = self.call("feature", device=device, feature=feature, value=value)
        if view:
            self._merge([view])

    def set_rules(self, rules: list[dict]) -> bool:
        result = self.call("rules_set", rules=rules)
        if result is not None:
            self.rules = result
            self.rulesChanged.emit()
            return True
        return False

    def apply_profile(self, name: str) -> None:
        self._merge(self.call("profile_apply", name=name))

    def save_profile(self, name: str) -> None:
        result = self.call("profile_save", name=name)
        if result is not None:
            self.profiles = result
            self.profilesChanged.emit()

    def delete_profile(self, name: str) -> None:
        result = self.call("profile_delete", name=name)
        if result is not None:
            self.profiles = result
            self.profilesChanged.emit()

    def rename_profile(self, old: str, new: str) -> None:
        result = self.call("profile_rename", old=old, new=new)
        if result is not None:
            self.profiles = result
            self.profilesChanged.emit()

    def set_settings(self, changes: dict) -> None:
        result = self.call("settings_set", changes=changes)
        if result is not None:
            self.settings = result
            self.settingsChanged.emit()

    def rescan(self) -> None:
        views = self.call("rescan")
        if views is not None:
            self._set_devices(views)
            self.devicesChanged.emit()
            self.refresh_system()

    # ---------------------------------------------------------------- events
    def _on_event(self, kind: str, data: dict) -> None:
        if kind == "state":
            dev = self.devices.get(data.get("device"))
            if dev is not None:
                dev["state"] = data["state"]
                dev["effective"] = data["effective"]
                dev["rules_active"] = data.get("rules_active", [])
                self.deviceChanged.emit(dev["id"])
        elif kind == "device":
            view = data.get("device")
            if view:
                self.devices[view["id"]] = view
                if view["id"] not in self.order:
                    self.order.append(view["id"])
                self.deviceChanged.emit(view["id"])
        elif kind == "devices":
            self._set_devices(data.get("devices", []))
            self.devicesChanged.emit()
        elif kind == "rules":
            self.rules = data.get("rules", [])
            self.rulesChanged.emit()
        elif kind == "profiles":
            self.profiles = data.get("profiles", [])
            self.profilesChanged.emit()
        elif kind == "settings":
            self.settings = data.get("settings", {})
            self.settingsChanged.emit()
        elif kind == "automation":
            self.active_rules = set(data.get("active", []))
            self.automationChanged.emit()
        elif kind == "profile_applied":
            self.profileApplied.emit(data.get("name", ""))
        elif kind == "power":
            self.power = data
            self.powerChanged.emit()
        elif kind == "launch":
            self.launchRequested.emit()
        elif kind == "disconnected" and self.mode == "service":
            try:
                self.client.call("hello")
                return      # a stale event from a connection we already replaced
            except (OSError, ServiceError):
                pass
            log.warning("lost connection to the ByteKeys service; reconnecting")
            self._retry.start()
