"""Detecting the launch key: from this window's own key events, or through the service."""

from __future__ import annotations

import threading

from .. import ipc
from ..engine.inputwatch import SPECIAL_KEYS
from ..ipc import ServiceError
from . import icons, theme
from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .widgets.kit import text_label


class _ServiceLearner(QtCore.QObject):
    """Asks the service to wait for a special key on a separate connection, off the GUI thread."""

    done = Signal(object)    # code or None

    def start(self, timeout: float) -> None:
        def work():
            code = None
            try:
                client = ipc.SocketClient(timeout=timeout + 5)
                try:
                    code = (client.call("launch_learn", timeout=timeout) or {}).get("code")
                finally:
                    client.close()
            except (OSError, ServiceError):
                pass
            self.done.emit(code)
        threading.Thread(target=work, name="bytekeys-learn", daemon=True).start()


class KeyCatcher(QtWidgets.QDialog):
    """Modal "press the key" prompt. Only vendor/special keys count, never letters or digits."""

    TIMEOUT = 15.0

    def __init__(self, parent, service: bool):
        super().__init__(parent)
        self.setWindowTitle("Detect launch key")
        self.setModal(True)
        self.setMinimumWidth(460)
        self.code: int | None = None
        self.timed_out = False
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(28, 26, 28, 22)
        lay.setSpacing(12)
        badge = QtWidgets.QLabel()
        badge.setPixmap(self._badge())
        lay.addWidget(badge, 0, Qt.AlignmentFlag.AlignHCenter)
        title = text_label("Press the launch key", "value")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(title)
        info = text_label("The key that opens Armoury Crate, NitroSense, OMEN Gaming Hub or MSI Center on "
                          "Windows. Letters, digits and other ordinary keys are ignored.", "dim", wrap=True)
        info.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(info)
        self.status = text_label("", "faint", wrap=True)
        self.status.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.status)
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        row.addStretch(1)
        lay.addLayout(row)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._timed_out)
        self._timer.start(int(self.TIMEOUT * 1000))
        if service:
            self._learner = _ServiceLearner(self)
            self._learner.done.connect(self._found)
            self._learner.start(self.TIMEOUT)

    @staticmethod
    def _badge() -> QtGui.QPixmap:
        ratio = 2
        pm = QtGui.QPixmap(72 * ratio, 72 * ratio)
        pm.fill(Qt.GlobalColor.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.scale(ratio, ratio)
        glow = QtGui.QRadialGradient(QtCore.QPointF(36, 36), 36)
        glow.setColorAt(0, theme.c("glow", 0.35))
        glow.setColorAt(1, theme.c("glow", 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QtCore.QRectF(0, 0, 72, 72))
        icons.paint(p, "key", QtCore.QRectF(18, 18, 36, 36), theme.c("text"), 1.7)
        p.end()
        pm.setDevicePixelRatio(ratio)
        return pm

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.activateWindow()
        self.setFocus()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        code = event.nativeScanCode() - 8          # xkb keycode -> evdev code (Wayland and X11)
        if code in SPECIAL_KEYS:
            self._found(code)
        elif event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            self.status.setText("That is an ordinary key. Press the laptop's app key instead.")

    def _found(self, code) -> None:
        if code and self.isVisible() and self.code is None:
            self.code = int(code)
            self.accept()

    def _timed_out(self) -> None:
        self.timed_out = True
        self.reject()
