"""Common page scaffolding."""

from __future__ import annotations

from ..qt import QtWidgets, Qt
from ..widgets.common import label


class Page(QtWidgets.QScrollArea):
    def __init__(self, window, title: str, subtitle: str = ""):
        super().__init__()
        self.window = window
        self.bridge = window.bridge
        self.setObjectName("page")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QtWidgets.QWidget()
        inner.setObjectName("page")
        self.column = QtWidgets.QVBoxLayout(inner)
        self.column.setContentsMargins(30, 26, 30, 30)
        self.column.setSpacing(16)
        head = QtWidgets.QVBoxLayout()
        head.setSpacing(2)
        self.title = label(title, "pageTitle")
        self.subtitle = label(subtitle, "pageSubtitle", wrap=True)
        head.addWidget(self.title)
        if subtitle:
            head.addWidget(self.subtitle)
        self.column.addLayout(head)
        self.setWidget(inner)

    def add(self, widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
        self.column.addWidget(widget)
        return widget

    def finish(self) -> None:
        self.column.addStretch(1)

    def device(self) -> dict | None:
        return self.window.current_device()

    def on_show(self) -> None:
        """Called when the page becomes visible."""
