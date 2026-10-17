"""Colors, fonts and the application style sheet (dark control-center look, plus light)."""

from __future__ import annotations

import shutil
import subprocess

from .qt import QT_VERSION, QtGui, QtWidgets, Qt

# Graphite, silver and warm light, after the ByteKeys logo.
DARK = {
    "bg": "#0b0b0d",
    "bg2": "#101012",
    "sidebar": "#08080a",
    "card": "#161619",
    "card2": "#111113",
    "border": "#25252a",
    "border_hi": "#3a3a42",
    "surface": "#1b1b1f",
    "surface2": "#232328",
    "surface3": "#2f2f36",
    "text": "#f5f5f7",
    "dim": "#9d9da7",
    "faint": "#5d5d66",
    "accent": "#f1e7d6",
    "accent2": "#a9a9b3",
    "accent3": "#ffd49a",
    "accent_text": "#121214",
    "good": "#5fd8a0",
    "warn": "#f2b45a",
    "bad": "#ff6b6b",
    "key": "#19191d",
    "key_edge": "#2e2e35",
    "chassis": "#0c0c0e",
    "glow": "#ffd49a",
}

LIGHT = {
    "bg": "#f3f3f5",
    "bg2": "#ececf0",
    "sidebar": "#e8e8ed",
    "card": "#ffffff",
    "card2": "#fafafb",
    "border": "#dedee5",
    "border_hi": "#c4c4ce",
    "surface": "#f1f1f4",
    "surface2": "#e7e7ec",
    "surface3": "#dadae2",
    "text": "#141416",
    "dim": "#5c5c67",
    "faint": "#a0a0aa",
    "accent": "#1d1d21",
    "accent2": "#64646e",
    "accent3": "#c4823a",
    "accent_text": "#ffffff",
    "good": "#0f9f6e",
    "warn": "#b7791f",
    "bad": "#d64545",
    "key": "#232328",
    "key_edge": "#3a3a42",
    "chassis": "#1a1a1e",
    "glow": "#c4823a",
}

colors: dict[str, str] = dict(DARK)
dark_mode = True


def c(name: str, alpha: float | None = None) -> QtGui.QColor:
    """A theme color as QColor, optionally with alpha (0-1)."""
    color = QtGui.QColor(colors[name])
    if alpha is not None:
        color.setAlphaF(max(0.0, min(1.0, alpha)))
    return color


def font(size: float = 10.5, weight: int = 400, spacing: float = 0.0) -> QtGui.QFont:
    f = QtGui.QFont(QtWidgets.QApplication.font())
    f.setPointSizeF(size)
    f.setWeight(QtGui.QFont.Weight(weight))
    if spacing:
        f.setLetterSpacing(QtGui.QFont.SpacingType.AbsoluteSpacing, spacing)
    return f


def system_prefers_dark() -> bool:
    app = QtWidgets.QApplication.instance()
    if QT_VERSION >= (6, 5) and app is not None:
        scheme = app.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    if shutil.which("gsettings"):
        try:
            out = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                                 capture_output=True, text=True, timeout=2).stdout
            if "dark" in out:
                return True
            if "default" in out or "light" in out:
                return False
        except (OSError, subprocess.SubprocessError):
            pass
    return True


def apply(app: QtWidgets.QApplication, mode: str = "dark") -> None:
    global dark_mode
    dark_mode = system_prefers_dark() if mode == "system" else mode != "light"
    colors.clear()
    colors.update(DARK if dark_mode else LIGHT)
    app.setStyle("Fusion")
    t = colors
    pal = QtGui.QPalette()
    role = QtGui.QPalette.ColorRole
    for r, key in ((role.Window, "bg"), (role.WindowText, "text"), (role.Base, "surface"),
                   (role.AlternateBase, "card"), (role.Text, "text"), (role.Button, "surface"),
                   (role.ButtonText, "text"), (role.Highlight, "accent"), (role.HighlightedText, "accent_text"),
                   (role.ToolTipBase, "surface2"), (role.ToolTipText, "text"), (role.PlaceholderText, "faint"),
                   (role.Link, "accent3")):
        pal.setColor(r, QtGui.QColor(t[key]))
    for r in (role.Text, role.ButtonText, role.WindowText):
        pal.setColor(QtGui.QPalette.ColorGroup.Disabled, r, QtGui.QColor(t["faint"]))
    app.setPalette(pal)
    app.setStyleSheet(STYLE.format(**t))


STYLE = """
QWidget {{ color: {text}; font-size: 10.5pt; }}
QMainWindow, #root {{ background: {bg}; }}
QToolTip {{ background: {surface2}; color: {text}; border: 1px solid {border_hi}; padding: 6px 9px;
           border-radius: 8px; }}
QScrollArea, #page, #transparent {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

#pageTitle {{ font-size: 21pt; font-weight: 800; }}
#pageSubtitle {{ color: {dim}; }}
#caption {{ color: {dim}; font-size: 8.5pt; font-weight: 700; letter-spacing: 1.2px; }}
#dim, #cardHint {{ color: {dim}; }}
#faint {{ color: {faint}; }}
#rowTitle {{ font-weight: 600; }}
#big {{ font-size: 24pt; font-weight: 800; }}
#value {{ font-size: 15pt; font-weight: 750; }}

QPushButton {{ background: {surface}; border: 1px solid {border}; border-radius: 10px; padding: 8px 16px;
              font-weight: 600; }}
QPushButton:hover {{ background: {surface2}; border-color: {border_hi}; }}
QPushButton:pressed {{ background: {surface3}; }}
QPushButton:disabled {{ color: {faint}; }}
QPushButton#primary {{ border: none; color: {accent_text};
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {accent}, stop:1 {accent2}); }}
QPushButton#primary:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {accent}, stop:1 {accent3}); }}
QPushButton#primary:disabled {{ background: {surface2}; color: {faint}; border: 1px solid {border}; }}
QPushButton#ghost {{ background: transparent; border: 1px solid transparent; color: {dim}; padding: 6px 10px; }}
QPushButton#ghost:hover {{ color: {text}; background: {surface}; }}
QPushButton#danger {{ color: {bad}; }}
QPushButton#link {{ background: transparent; border: none; color: {accent}; padding: 4px 2px; font-weight: 600; }}
QPushButton#link:hover {{ color: {text}; }}
QPushButton::menu-indicator {{ image: none; width: 0px; }}
QPushButton#segment {{ border-radius: 10px; padding: 7px 15px; }}
QPushButton#segment:checked {{ border: none; color: {accent_text};
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {accent}, stop:1 {accent2}); }}

QLineEdit, QComboBox, QSpinBox, QTimeEdit, QPlainTextEdit {{
    background: {surface}; border: 1px solid {border}; border-radius: 9px; padding: 7px 10px;
    selection-background-color: {accent}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTimeEdit:focus {{ border-color: {accent}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{ background: {surface}; border: 1px solid {border_hi}; padding: 4px;
                              selection-background-color: {surface3}; outline: none; }}
QSpinBox::up-button, QSpinBox::down-button, QTimeEdit::up-button, QTimeEdit::down-button {{ width: 0px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: {surface3}; border-radius: 3px; min-height: 40px; }}
QScrollBar::handle:vertical:hover {{ background: {border_hi}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar:horizontal {{ height: 0px; }}

QMenu {{ background: {card}; border: 1px solid {border_hi}; padding: 6px; border-radius: 10px; }}
QMenu::item {{ padding: 7px 24px 7px 14px; border-radius: 7px; }}
QMenu::item:selected {{ background: {surface2}; }}
QMenu::item:disabled {{ color: {faint}; }}
QMenu::separator {{ height: 1px; background: {border}; margin: 5px 8px; }}
QDialog {{ background: {bg2}; }}
QCheckBox::indicator {{ width: 16px; height: 16px; }}
QSlider {{ background: transparent; }}
"""
