"""Common page scaffolding: a header and a scrollable body."""

from __future__ import annotations

from ..qt import QtWidgets, Qt
from ..widgets.kit import text_label


class Page(QtWidgets.QScrollArea):
    def __init__(self, window, title: str, subtitle: str = ""):
        super().__init__()
        self.window = window
        self.bridge = window.bridge
        self._connections: list[tuple] = []
        self._monitoring = False
        self.setObjectName("page")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QtWidgets.QWidget()
        inner.setObjectName("page")
        self.column = QtWidgets.QVBoxLayout(inner)
        self.column.setContentsMargins(32, 26, 32, 30)
        self.column.setSpacing(16)
        head = QtWidgets.QHBoxLayout()
        head.setSpacing(10)
        titles = QtWidgets.QVBoxLayout()
        titles.setSpacing(2)
        self.title = text_label(title, "pageTitle")
        titles.addWidget(self.title)
        self.subtitle = text_label(subtitle, "pageSubtitle", wrap=True)
        self.subtitle.setVisible(bool(subtitle))
        titles.addWidget(self.subtitle)
        head.addLayout(titles, 1)
        self.header_right = QtWidgets.QHBoxLayout()
        self.header_right.setSpacing(8)
        head.addLayout(self.header_right)
        self.column.addLayout(head)
        self.column.addSpacing(4)
        self.setWidget(inner)

    def add(self, widget, stretch: int = 0):
        if isinstance(widget, QtWidgets.QLayout):
            self.column.addLayout(widget, stretch)
        else:
            self.column.addWidget(widget, stretch)
        return widget

    def finish(self) -> None:
        self.column.addStretch(1)

    def set_subtitle(self, text: str) -> None:
        self.subtitle.setText(text)
        self.subtitle.setVisible(bool(text))

    # ------------------------------------------------------------ signals
    def listen(self, signal, slot) -> None:
        """Connect to a long-lived signal (bridge, window); undone by detach()."""
        signal.connect(slot)
        self._connections.append((signal, slot))

    def detach(self) -> None:
        for signal, slot in self._connections:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self._connections = []

    # ----------------------------------------------------------- monitoring
    def start_monitoring(self) -> None:
        if not self._monitoring:
            self._monitoring = True
            self.bridge.start_monitoring()

    def stop_monitoring(self) -> None:
        if self._monitoring:
            self._monitoring = False
            self.bridge.stop_monitoring()

    # -------------------------------------------------------------- hooks
    def device(self) -> dict | None:
        return self.window.current_device()

    def refresh(self) -> None:
        """Re-read state from the bridge."""

    def layout_changed(self) -> None:
        """The keyboard picture preference changed."""

    def on_show(self) -> None:
        """Called when the page becomes visible."""

    def on_hide(self) -> None:
        """Called when another page is shown or the window hides."""
