"""ByteKeys control center: main window and entry point."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys

from .. import APP_ID, APP_NAME, __version__, service
from . import icons, theme
from .bridge import Bridge
from .prefs import Prefs, autostart_enabled
from .qt import API, QtCore, QtGui, QtNetwork, QtWidgets, Qt, Signal
from .tray import Tray
from .widgets.sidebar import Sidebar

log = logging.getLogger(__name__)
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
INSTANCE_NAME = f"bytekeys-gui-{os.getuid()}"

# (key, icon, label)
PAGES = [
    ("home", "home", "Home"),
    ("lighting", "keyboard", "Lighting"),
    ("performance", "fan", "Performance"),
    ("automation", "bolt", "Automation"),
    ("profiles", "layers", "Profiles"),
    ("settings", "gear", "Settings"),
]
PAGE_KEYS = [key for key, _icon, _label in PAGES]


def app_icon() -> QtGui.QIcon:
    icon = QtGui.QIcon()
    for size in (32, 64, 128, 256):
        path = os.path.join(ASSETS, f"bytekeys-{size}.png")
        if os.path.exists(path):
            icon.addFile(path, QtCore.QSize(size, size))
    if icon.isNull():
        icon = QtGui.QIcon.fromTheme(APP_ID)
    return icon


class Toast(QtWidgets.QWidget):
    """Short message that fades in at the bottom of the window."""

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.text = ""
        self.error = False
        self._effect = QtWidgets.QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)
        self._anim = QtCore.QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(180)
        self._anim.finished.connect(self._finished)
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(lambda: self._fade(0.0))
        self.hide()

    def show_message(self, text: str, error: bool = False, left: int = 0) -> None:
        self.text, self.error = text, error
        parent = self.parentWidget()
        fm = QtGui.QFontMetrics(theme.font(10, 600))
        width = min(fm.horizontalAdvance(text) + 76, parent.width() - left - 48)
        self.resize(max(220, width), 46)
        self.move(left + (parent.width() - left - self.width()) // 2, parent.height() - self.height() - 26)
        self.raise_()
        self.show()
        self.update()
        self._fade(1.0)
        self._timer.start(4800 if error else 2600)

    def _fade(self, target: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(target)
        self._anim.start()

    def _finished(self) -> None:
        if self._effect.opacity() < 0.05:
            self.hide()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        r = QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QtGui.QPen(theme.c("bad" if self.error else "border_hi"), 1))
        p.setBrush(theme.c("surface2"))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        tone = theme.c("bad") if self.error else theme.c("glow")
        icons.paint(p, "warning" if self.error else "check", QtCore.QRectF(r.left() + 16, r.center().y() - 9, 18, 18),
                    tone, 2.2)
        p.setPen(theme.c("text"))
        f = theme.font(10, 600)
        p.setFont(f)
        text = QtGui.QFontMetrics(f).elidedText(self.text, Qt.TextElideMode.ElideRight, int(r.width() - 64))
        p.drawText(r.adjusted(44, 0, -18, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)


class MainWindow(QtWidgets.QMainWindow):
    deviceSelected = Signal(str)

    def __init__(self, bridge: Bridge, prefs: Prefs, app: QtWidgets.QApplication, start_page: str | None = None):
        super().__init__()
        self.bridge = bridge
        self.prefs = prefs
        self.app = app
        self._device_id: str | None = prefs["last_device"]
        self._service_status = service.status()
        self._quitting = False
        self.pages: dict = {}
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.setMinimumSize(1040, 700)

        self.tray = Tray(self)
        self.tray.set_visible(bool(prefs["tray"]) and Tray.available())
        self._build()

        bridge.devicesChanged.connect(self._on_devices)
        bridge.connectionChanged.connect(self._on_connection)
        bridge.errorOccurred.connect(lambda msg: self.toast(msg, error=True))
        bridge.profileApplied.connect(lambda name: self.toast(f"Profile “{name}” applied"))
        bridge.launchRequested.connect(self.on_launch_key)

        geometry = prefs["geometry"]
        if geometry:
            self.restoreGeometry(QtCore.QByteArray.fromBase64(geometry.encode()))
        else:
            self.resize(1240, 840)
        self._on_devices()
        self._on_connection()
        self.go(start_page or prefs["last_page"])

    # ---------------------------------------------------------------- build
    def _build(self) -> None:
        from .pages.automation import AutomationPage
        from .pages.home import HomePage
        from .pages.lighting import LightingPage
        from .pages.performance import PerformancePage
        from .pages.profiles import ProfilesPage
        from .pages.settings import SettingsPage

        root = QtWidgets.QWidget()
        root.setObjectName("root")
        h = QtWidgets.QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        self.sidebar = Sidebar(self.windowIcon(), [(icon, label) for _key, icon, label in PAGES])
        self.sidebar.pageSelected.connect(self._on_nav)
        self.sidebar.statusClicked.connect(lambda: self.go("settings"))
        h.addWidget(self.sidebar)
        self.stack = QtWidgets.QStackedWidget()
        h.addWidget(self.stack, 1)
        classes = {"home": HomePage, "lighting": LightingPage, "performance": PerformancePage,
                   "automation": AutomationPage, "profiles": ProfilesPage, "settings": SettingsPage}
        self.pages = {}
        for key in PAGE_KEYS:
            self.pages[key] = classes[key](self)
            self.stack.addWidget(self.pages[key])
        self.setCentralWidget(root)
        self.toast_widget = Toast(root)

    def rebuild(self) -> None:
        """Recreate every page (after a theme change)."""
        current = self.current_page_key()
        for page in self.pages.values():
            page.on_hide()
            page.detach()
        self._build()
        self._on_devices()
        self._on_connection()
        self.go(current)

    # ---------------------------------------------------------- navigation
    def current_page_key(self) -> str:
        idx = self.stack.currentIndex()
        return PAGE_KEYS[idx] if 0 <= idx < len(PAGE_KEYS) else "home"

    def go(self, key) -> None:
        if key not in self.pages:
            key = "home"
        self._on_nav(PAGE_KEYS.index(key))

    def _on_nav(self, index: int) -> None:
        if not 0 <= index < len(PAGE_KEYS):
            return
        new = self.pages[PAGE_KEYS[index]]
        old = self.stack.currentWidget()
        if old is not None and old is not new:
            old.on_hide()
        self.stack.setCurrentIndex(index)
        self.sidebar.set_current(index)
        self.prefs["last_page"] = PAGE_KEYS[index]
        if self.isVisible():
            new.on_show()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        page = self.stack.currentWidget()
        if page is not None:
            page.on_show()

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)
        page = self.stack.currentWidget()
        if page is not None:
            page.on_hide()

    # --------------------------------------------------------------- state
    def current_device(self) -> dict | None:
        devices = self.bridge.devices
        if self._device_id in devices:
            return devices[self._device_id]
        if self.bridge.order:
            return devices[self.bridge.order[0]]
        return None

    def select_device(self, dev_id: str) -> None:
        if dev_id and dev_id != self._device_id and dev_id in self.bridge.devices:
            self._device_id = dev_id
            self.prefs["last_device"] = dev_id
            self.deviceSelected.emit(dev_id)

    def keyboard_layout(self) -> str:
        choice = self.prefs["keyboard_layout"]
        if choice in ("compact", "full"):
            return choice
        return self.bridge.system.get("layout", "compact")

    def service_status(self) -> dict:
        return self._service_status

    def _on_devices(self) -> None:
        dev = self.current_device()
        if dev:
            self._device_id = dev["id"]
        for page in self.pages.values():
            page.refresh()

    def _on_connection(self) -> None:
        self._service_status = service.status()
        self.sidebar.model.setText(self.bridge.system.get("model", ""))
        if self.bridge.mode == "service":
            text, tone = "Service running", "good"
        else:
            text, tone = "Portable mode", "warn"
        if self.bridge.demo:
            text += " · demo"
        self.sidebar.set_status(text, tone)
        for page in self.pages.values():
            page.refresh()

    # ------------------------------------------------------------ settings
    def set_theme(self, mode: str) -> None:
        self.prefs["theme"] = mode
        theme.apply(self.app, mode)
        self.rebuild()

    def set_keyboard_layout(self, choice: str) -> None:
        self.prefs["keyboard_layout"] = choice
        for page in self.pages.values():
            page.layout_changed()

    def set_tray_enabled(self, on: bool) -> None:
        self.prefs["tray"] = on
        self.tray.set_visible(on and Tray.available())

    def runs_in_background(self) -> bool:
        """Closing the window keeps ByteKeys running (tray icon or launch key)."""
        launch = bool(self.bridge.settings.get("launch_key")) and self.bridge.mode == "service"
        return bool(self.prefs["close_to_tray"]) and (self.tray.icon.isVisible() or launch)

    # ------------------------------------------------------------ launch key
    def on_launch_key(self) -> None:
        self.show_window()

    # -------------------------------------------------------------- service
    def install_service(self) -> None:
        status = service.status()
        env = QtCore.QProcessEnvironment.systemEnvironment()
        proc = QtCore.QProcess(self)
        if status.get("managed_by_package"):
            proc.setProgram("pkexec")
            proc.setArguments(["systemctl", "restart", "bytekeysd.service"] if self.bridge.outdated
                              else ["systemctl", "enable", "--now", "bytekeysd.service"])
        else:
            pkg_parent = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            env.insert("PYTHONPATH", pkg_parent + os.pathsep + env.value("PYTHONPATH", ""))
            proc.setProgram(sys.executable)
            proc.setArguments(["-m", "bytekeys.service", "install", "--graphical"])
        proc.setProcessEnvironment(env)
        verb = "Updating" if self.bridge.outdated else "Installing"
        dialog = QtWidgets.QProgressDialog(f"{verb} the ByteKeys service…\n"
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
        if self.bridge.switch_to_service() and not self.bridge.outdated:
            self._service_status = service.status()
            self.toast("Service ready: full control enabled")
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
        self.toast_widget.show_message(message, error, left=self.sidebar.width())

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
        if not self._quitting and self.runs_in_background():
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


def _single_instance(app, message: bytes):
    """Return a server when we are the first instance, None when another one was told to show."""
    if QtNetwork is None:
        return False   # cannot tell; just run
    sock = QtNetwork.QLocalSocket()
    sock.connectToServer(INSTANCE_NAME)
    if sock.waitForConnected(300):
        sock.write(message + b"\n")
        sock.flush()
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        return None
    QtNetwork.QLocalServer.removeServer(INSTANCE_NAME)
    server = QtNetwork.QLocalServer(app)
    server.listen(INSTANCE_NAME)
    return server


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bytekeys-gui", description=f"{APP_NAME} control center")
    ap.add_argument("--minimized", action="store_true", help="start hidden (in the tray)")
    ap.add_argument("--page", choices=PAGE_KEYS, help="open this page")
    ap.add_argument("--demo", action="store_true", help="add simulated keyboards and fans")
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
    server = _single_instance(app, f"show {args.page or ''}".strip().encode())
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
    window = MainWindow(bridge, prefs, app, args.page)

    def on_message(conn):
        words = bytes(conn.readAll()).decode(errors="replace").split()
        if len(words) > 1 and words[0] == "show":
            window.go(words[1])
        window.show_window()

    def on_connection():
        conn = server.nextPendingConnection()
        if conn is not None:
            conn.readyRead.connect(lambda: on_message(conn))
    if server:
        server.newConnection.connect(on_connection)

    hidden_ok = window.tray.icon.isVisible() or autostart_enabled()
    if not (args.minimized and hidden_ok):
        window.show()
    log.debug("Qt binding: %s", API)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
