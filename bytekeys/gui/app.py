"""ByteKeys control panel: main window and entry point."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys

from .. import APP_ID, APP_NAME, __version__, service
from . import theme
from .bridge import Bridge
from .pages.effects import EffectsPage
from .pages.lighting import LightingPage
from .pages.profiles import ProfilesPage
from .pages.rules import RulesPage
from .pages.system import SystemPage
from .prefs import Prefs
from .qt import API, QtCore, QtGui, QtNetwork, QtWidgets, Qt, Signal
from .tray import Tray
from .widgets.common import label, repolish

log = logging.getLogger(__name__)
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
INSTANCE_NAME = f"bytekeys-gui-{os.getuid()}"

NAV = [("◐", "Lighting"), ("✦", "Effects"), ("⚡", "Rules"), ("▤", "Profiles"), ("⚙", "System")]


def app_icon() -> QtGui.QIcon:
    icon = QtGui.QIcon.fromTheme(APP_ID)
    if icon.isNull():
        icon = QtGui.QIcon()
        for size in (32, 64, 128, 256):
            path = os.path.join(ASSETS, f"bytekeys-{size}.png")
            if os.path.exists(path):
                icon.addFile(path, QtCore.QSize(size, size))
    return icon


class MainWindow(QtWidgets.QMainWindow):
    deviceSelected = Signal(str)

    def __init__(self, bridge: Bridge, prefs: Prefs, app: QtWidgets.QApplication):
        super().__init__()
        self.bridge = bridge
        self.prefs = prefs
        self.app = app
        self._device_id: str | None = prefs["last_device"]
        self._service_status = service.status()
        self._quitting = False
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.setMinimumSize(900, 620)

        root = QtWidgets.QWidget()
        root.setObjectName("root")
        h = QtWidgets.QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        self.setCentralWidget(root)

        side = QtWidgets.QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(236)
        sv = QtWidgets.QVBoxLayout(side)
        sv.setContentsMargins(16, 18, 16, 16)
        sv.setSpacing(12)
        brand = QtWidgets.QHBoxLayout()
        logo = QtWidgets.QLabel()
        logo.setPixmap(self.windowIcon().pixmap(36, 36))
        brand.addWidget(logo)
        names = QtWidgets.QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(label(APP_NAME, "brand"))
        self.model_label = label("", "brandSub", wrap=True)
        names.addWidget(self.model_label)
        brand.addLayout(names, 1)
        sv.addLayout(brand)
        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.currentIndexChanged.connect(self._on_device_combo)
        sv.addWidget(self.device_combo)
        self.nav = QtWidgets.QListWidget()
        self.nav.setObjectName("navList")
        for icon, name in NAV:
            QtWidgets.QListWidgetItem(f"{icon}   {name}", self.nav)
        self.nav.setCursor(Qt.CursorShape.PointingHandCursor)
        sv.addWidget(self.nav, 1)
        self.status_button = QtWidgets.QPushButton()
        self.status_button.setObjectName("statusButton")
        self.status_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.status_button.setToolTip("Service and system details")
        self.status_button.clicked.connect(lambda: self.nav.setCurrentRow(4))
        sv.addWidget(self.status_button)
        h.addWidget(side)

        self.stack = QtWidgets.QStackedWidget()
        h.addWidget(self.stack, 1)
        self.pages = [LightingPage(self), EffectsPage(self), RulesPage(self), ProfilesPage(self), SystemPage(self)]
        for page in self.pages:
            self.stack.addWidget(page)
        self.nav.currentRowChanged.connect(self._on_nav)

        self.toast_label = QtWidgets.QLabel(root)
        self.toast_label.setObjectName("pill")
        self.toast_label.setProperty("tone", "accent")
        self.toast_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toast_label.hide()
        self._toast_timer = QtCore.QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self.toast_label.hide)

        self.tray = Tray(self)
        self.tray.set_visible(bool(prefs["tray"]) and Tray.available())

        bridge.devicesChanged.connect(self._on_devices)
        bridge.connectionChanged.connect(self._on_connection)
        bridge.errorOccurred.connect(lambda msg: self.toast(msg, error=True))
        bridge.profileApplied.connect(lambda name: self.toast(f"Profile “{name}” applied"))

        geometry = prefs["geometry"]
        if geometry:
            self.restoreGeometry(QtCore.QByteArray.fromBase64(geometry.encode()))
        else:
            self.resize(1100, 780)
        self._on_devices()
        self._on_connection()
        self.nav.setCurrentRow(int(prefs["last_page"] or 0) if self.bridge.order else 4)

    # --------------------------------------------------------------- state
    def current_device(self) -> dict | None:
        devices = self.bridge.devices
        if self._device_id in devices:
            return devices[self._device_id]
        if self.bridge.order:
            return devices[self.bridge.order[0]]
        return None

    def keyboard_layout(self) -> str:
        choice = self.prefs["keyboard_layout"]
        if choice in ("compact", "full"):
            return choice
        return self.bridge.system.get("layout", "compact")

    def service_status(self) -> dict:
        return self._service_status

    def _on_devices(self) -> None:
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        for dev_id in self.bridge.order:
            self.device_combo.addItem(self.bridge.devices[dev_id]["name"], dev_id)
        dev = self.current_device()
        if dev:
            self._device_id = dev["id"]
            self.device_combo.setCurrentIndex(max(0, self.device_combo.findData(dev["id"])))
        self.device_combo.setVisible(len(self.bridge.order) > 1)
        self.device_combo.blockSignals(False)
        for page in self.pages:
            page.refresh()

    def _on_device_combo(self, _index: int) -> None:
        dev_id = self.device_combo.currentData()
        if dev_id and dev_id != self._device_id:
            self._device_id = dev_id
            self.prefs["last_device"] = dev_id
            self.deviceSelected.emit(dev_id)

    def _on_connection(self) -> None:
        self._service_status = service.status()
        self.model_label.setText(self.bridge.system.get("model", ""))
        if self.bridge.mode == "service":
            color, text = theme.colors["good"], "Service running"
        else:
            color, text = theme.colors["warn"], "Portable mode"
        if self.bridge.demo:
            text += " · demo"
        dot = QtGui.QPixmap(12, 12)
        dot.fill(Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(dot)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor(color))
        painter.drawEllipse(1, 1, 10, 10)
        painter.end()
        self.status_button.setIcon(QtGui.QIcon(dot))
        self.status_button.setText(" " + text)
        for page in self.pages:
            page.refresh()

    def _on_nav(self, row: int) -> None:
        if row < 0:
            return
        self.stack.setCurrentIndex(row)
        self.prefs["last_page"] = row
        self.pages[row].on_show()

    # ------------------------------------------------------------ settings
    def set_theme(self, mode: str) -> None:
        self.prefs["theme"] = mode
        theme.apply(self.app, mode)
        self._on_connection()
        for w in self.findChildren(QtWidgets.QWidget):
            w.update()

    def set_keyboard_layout(self, choice: str) -> None:
        self.prefs["keyboard_layout"] = choice
        for page in self.pages:
            if hasattr(page, "keyboard"):
                page._dev_id = None
            page.refresh()

    def set_tray_enabled(self, on: bool) -> None:
        self.prefs["tray"] = on
        self.tray.set_visible(on and Tray.available())

    # -------------------------------------------------------------- service
    def install_service(self) -> None:
        status = service.status()
        env = QtCore.QProcessEnvironment.systemEnvironment()
        proc = QtCore.QProcess(self)
        if status.get("managed_by_package"):
            proc.setProgram("pkexec")
            proc.setArguments(["systemctl", "enable", "--now", "bytekeysd.service"])
        else:
            pkg_parent = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            env.insert("PYTHONPATH", pkg_parent + os.pathsep + env.value("PYTHONPATH", ""))
            proc.setProgram(sys.executable)
            proc.setArguments(["-m", "bytekeys.service", "install", "--graphical"])
        proc.setProcessEnvironment(env)
        dialog = QtWidgets.QProgressDialog("Installing the ByteKeys service…\n"
                                           "Your system will ask for your password.", None, 0, 0, self)
        dialog.setWindowTitle(APP_NAME)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.show()

        def finished(code, _status):
            dialog.close()
            output = bytes(proc.readAllStandardError()).decode(errors="replace").strip()
            if code != 0:
                QtWidgets.QMessageBox.warning(self, APP_NAME, "The service was not installed."
                                              + (f"\n\n{output}" if output else ""))
                return
            self._wait_for_service(12)

        proc.finished.connect(finished)
        proc.start()

    def _wait_for_service(self, tries: int) -> None:
        if self.bridge.switch_to_service():
            self._service_status = service.status()
            self.toast("Service installed: full control enabled")
            self._on_connection()
            return
        if tries > 0:
            QtCore.QTimer.singleShot(500, lambda: self._wait_for_service(tries - 1))
        else:
            self.toast("The service was installed but is not answering yet", error=True)

    def uninstall_service(self) -> None:
        answer = QtWidgets.QMessageBox.question(
            self, APP_NAME, "Remove the ByteKeys background service? Lighting control will fall back "
                            "to portable mode.")
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        env = QtCore.QProcessEnvironment.systemEnvironment()
        pkg_parent = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        env.insert("PYTHONPATH", pkg_parent + os.pathsep + env.value("PYTHONPATH", ""))
        proc = QtCore.QProcess(self)
        proc.setProcessEnvironment(env)

        def finished(code, _status):
            self._service_status = service.status()
            if code == 0:
                self.bridge.local = True
                self.bridge.close()
                self.bridge.start()
                self.toast("Service removed")
            self._on_connection()

        proc.finished.connect(finished)
        proc.start(sys.executable, ["-m", "bytekeys.service", "uninstall", "--graphical"])

    # ---------------------------------------------------------------- misc
    def toast(self, message: str, error: bool = False) -> None:
        self.toast_label.setText(f"  {message}  ")
        self.toast_label.setProperty("tone", "warn" if error else "accent")
        repolish(self.toast_label)
        self.toast_label.adjustSize()
        w = min(self.toast_label.sizeHint().width() + 24, self.width() - 280)
        self.toast_label.setFixedSize(max(200, w), 34)
        self.toast_label.move(236 + (self.width() - 236 - self.toast_label.width()) // 2, self.height() - 60)
        self.toast_label.raise_()
        self.toast_label.show()
        self._toast_timer.start(4500 if error else 2600)

    def show_window(self) -> None:
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def toggle_window(self) -> None:
        if self.isVisible() and self.isActiveWindow():
            self.hide()
        else:
            self.show_window()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.prefs["geometry"] = bytes(self.saveGeometry().toBase64()).decode()
        if not self._quitting and self.prefs["close_to_tray"] and self.tray.icon.isVisible():
            event.ignore()
            self.hide()
            return
        event.accept()
        self.quit()

    def quit(self) -> None:
        self._quitting = True
        self.prefs["geometry"] = bytes(self.saveGeometry().toBase64()).decode()
        self.tray.set_visible(False)
        self.bridge.close()
        self.app.quit()


def _single_instance(app):
    """Return a server when we are the first instance, None when another one was told to show."""
    if QtNetwork is None:
        return False   # cannot tell; just run
    sock = QtNetwork.QLocalSocket()
    sock.connectToServer(INSTANCE_NAME)
    if sock.waitForConnected(300):
        sock.write(b"show\n")
        sock.flush()
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        return None
    QtNetwork.QLocalServer.removeServer(INSTANCE_NAME)
    server = QtNetwork.QLocalServer(app)
    server.listen(INSTANCE_NAME)
    return server


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bytekeys-gui", description=f"{APP_NAME} control panel")
    ap.add_argument("--minimized", action="store_true", help="start in the tray")
    ap.add_argument("--demo", action="store_true", help="add simulated keyboards")
    ap.add_argument("--local", action="store_true", help="do not use the service (portable mode)")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    args, qt_args = ap.parse_known_args(argv if argv is not None else sys.argv[1:])
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    QtGui.QGuiApplication.setDesktopFileName(APP_ID)
    app = QtWidgets.QApplication([sys.argv[0], *qt_args])
    app.setApplicationName("bytekeys")
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)
    server = _single_instance(app)
    if server is None:
        return 0   # another instance is running and was asked to show itself
    prefs = Prefs()
    theme.apply(app, prefs["theme"])
    app.setWindowIcon(app_icon())

    bridge = Bridge(demo=args.demo, local=args.local)
    try:
        bridge.start()
    except Exception as e:  # show something useful instead of a traceback
        log.exception("startup failed")
        QtWidgets.QMessageBox.critical(None, APP_NAME, f"{APP_NAME} could not start:\n\n{e}")
        return 1
    window = MainWindow(bridge, prefs, app)

    def on_connection():
        conn = server.nextPendingConnection()
        if conn is not None:
            conn.readyRead.connect(lambda: (conn.readAll(), window.show_window()))
    if server:
        server.newConnection.connect(on_connection)

    if not (args.minimized and window.tray.icon.isVisible()):
        window.show()
    log.debug("Qt binding: %s", API)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
