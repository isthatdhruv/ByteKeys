"""Qt binding shim: use PySide6 or PyQt6, whichever is installed.

The AppImage bundles PySide6; distribution packages usually depend on PyQt6
(available in Debian/Ubuntu archives). Set BYTEKEYS_QT=pyqt6 or pyside6 to
force one. The rest of the GUI only uses names exported here and fully
scoped enums, which both bindings understand.
"""

from __future__ import annotations

import importlib
import os


def _load(api: str):
    core = importlib.import_module(f"{api}.QtCore")
    gui = importlib.import_module(f"{api}.QtGui")
    widgets = importlib.import_module(f"{api}.QtWidgets")
    try:  # optional: only used to keep a single GUI instance
        network = importlib.import_module(f"{api}.QtNetwork")
    except ImportError:
        network = None
    if api == "PySide6":
        return api, core, gui, widgets, network, core.Signal, core.Slot
    return api, core, gui, widgets, network, core.pyqtSignal, core.pyqtSlot


_order = ["PyQt6", "PySide6"] if os.environ.get("BYTEKEYS_QT", "").lower() == "pyqt6" else ["PySide6", "PyQt6"]
_errors = []
for _api in _order:
    try:
        API, QtCore, QtGui, QtWidgets, QtNetwork, Signal, Slot = _load(_api)
        break
    except ImportError as e:  # try the next binding
        _errors.append(str(e))
else:
    raise ImportError(
        "ByteKeys needs PySide6 or PyQt6 for its control panel. Install one of them, e.g. "
        "'sudo apt install python3-pyqt6' or 'pip install PySide6-Essentials'. "
        f"({'; '.join(_errors)})"
    )

Qt = QtCore.Qt
QT_VERSION = tuple(int(x) for x in QtCore.qVersion().split(".")[:2])
