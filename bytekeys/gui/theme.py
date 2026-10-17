"""Colors and the application style sheet (light and dark)."""

from __future__ import annotations

import shutil
import subprocess

from .qt import QT_VERSION, QtGui, QtWidgets, Qt

DARK = {
    "bg": "#0d1120",
    "sidebar": "#10152a",
    "surface": "#151b30",
    "surface2": "#1c233b",
    "surface3": "#262f4b",
    "border": "#242c46",
    "text": "#e9ecf7",
    "dim": "#98a2bd",
    "faint": "#5f6884",
    "accent": "#5a7dff",
    "accent_text": "#ffffff",
    "accent2": "#a06cff",
    "good": "#34d399",
    "warn": "#fbbf24",
    "bad": "#f87171",
    "key": "#1a2038",
    "key_edge": "#2c3654",
    "chassis": "#0f142a",
}

LIGHT = {
    "bg": "#f2f4fb",
    "sidebar": "#e9edf8",
    "surface": "#ffffff",
    "surface2": "#eef1f9",
    "surface3": "#e1e6f4",
    "border": "#d9deec",
    "text": "#161b2e",
    "dim": "#56607a",
    "faint": "#98a1b8",
    "accent": "#4f6dff",
    "accent_text": "#ffffff",
    "accent2": "#8b5cf6",
    "good": "#059669",
    "warn": "#b7791f",
    "bad": "#dc2626",
    "key": "#262c42",
    "key_edge": "#39415c",
    "chassis": "#1b2036",
}

colors: dict[str, str] = dict(DARK)


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
    if app is not None:
        return app.palette().color(QtGui.QPalette.ColorRole.Window).lightness() < 128
    return True


def apply(app: QtWidgets.QApplication, mode: str = "system") -> None:
    dark = system_prefers_dark() if mode == "system" else mode == "dark"
    colors.clear()
    colors.update(DARK if dark else LIGHT)
    app.setStyle("Fusion")
    c = colors
    pal = QtGui.QPalette()
    role = QtGui.QPalette.ColorRole
    pal.setColor(role.Window, QtGui.QColor(c["bg"]))
    pal.setColor(role.WindowText, QtGui.QColor(c["text"]))
    pal.setColor(role.Base, QtGui.QColor(c["surface2"]))
    pal.setColor(role.AlternateBase, QtGui.QColor(c["surface"]))
    pal.setColor(role.Text, QtGui.QColor(c["text"]))
    pal.setColor(role.Button, QtGui.QColor(c["surface2"]))
    pal.setColor(role.ButtonText, QtGui.QColor(c["text"]))
    pal.setColor(role.Highlight, QtGui.QColor(c["accent"]))
    pal.setColor(role.HighlightedText, QtGui.QColor(c["accent_text"]))
    pal.setColor(role.ToolTipBase, QtGui.QColor(c["surface3"]))
    pal.setColor(role.ToolTipText, QtGui.QColor(c["text"]))
    pal.setColor(role.PlaceholderText, QtGui.QColor(c["faint"]))
    pal.setColor(role.Link, QtGui.QColor(c["accent2"]))
    pal.setColor(QtGui.QPalette.ColorGroup.Disabled, role.Text, QtGui.QColor(c["faint"]))
    pal.setColor(QtGui.QPalette.ColorGroup.Disabled, role.ButtonText, QtGui.QColor(c["faint"]))
    pal.setColor(QtGui.QPalette.ColorGroup.Disabled, role.WindowText, QtGui.QColor(c["faint"]))
    app.setPalette(pal)
    app.setStyleSheet(STYLE.format(**c))


STYLE = """
QWidget {{ color: {text}; font-size: 10.5pt; }}
QMainWindow, #root {{ background: {bg}; }}
QToolTip {{ background: {surface3}; color: {text}; border: 1px solid {border}; padding: 6px 8px;
           border-radius: 6px; }}

#sidebar {{ background: {sidebar}; border-right: 1px solid {border}; }}
#brand {{ font-size: 15pt; font-weight: 700; }}
#brandSub {{ color: {dim}; font-size: 9pt; }}
#navList {{ background: transparent; border: none; outline: none; }}
#navList::item {{ padding: 9px 12px; margin: 2px 0; border-radius: 9px; color: {dim}; }}
#navList::item:hover {{ background: {surface2}; color: {text}; }}
#navList::item:selected {{ background: {surface3}; color: {text}; font-weight: 600; }}

#pageTitle {{ font-size: 18pt; font-weight: 700; }}
#pageSubtitle {{ color: {dim}; }}
QScrollArea, #page {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

#card {{ background: {surface}; border: 1px solid {border}; border-radius: 14px; }}
#cardTitle {{ font-size: 11.5pt; font-weight: 650; }}
#cardHint, .dim {{ color: {dim}; }}
#faint {{ color: {faint}; }}
#big {{ font-size: 22pt; font-weight: 700; }}

QPushButton {{ background: {surface2}; border: 1px solid {border}; border-radius: 9px;
              padding: 7px 14px; }}
QPushButton:hover {{ background: {surface3}; }}
QPushButton:pressed {{ background: {border}; }}
QPushButton:disabled {{ color: {faint}; }}
QPushButton#primary {{ background: {accent}; color: {accent_text}; border: none; font-weight: 600; }}
QPushButton#primary:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {accent}, stop:1 {accent2}); }}
QPushButton#danger {{ color: {bad}; }}
QPushButton#flat {{ background: transparent; border: none; padding: 5px 8px; color: {dim}; }}
QPushButton#flat:hover {{ color: {text}; background: {surface2}; }}
QPushButton#segment {{ border-radius: 8px; padding: 6px 12px; }}
QPushButton#segment:checked {{ background: {accent}; color: {accent_text}; border-color: {accent}; }}

QLineEdit, QComboBox, QSpinBox, QTimeEdit, QPlainTextEdit {{
    background: {surface2}; border: 1px solid {border}; border-radius: 8px; padding: 6px 9px;
    selection-background-color: {accent}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTimeEdit:focus {{ border-color: {accent}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {surface2}; border: 1px solid {border};
                              selection-background-color: {surface3}; padding: 4px; }}

QSlider::groove:horizontal {{ height: 6px; background: {surface3}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 {accent}, stop:1 {accent2}); border-radius: 3px; }}
QSlider::handle:horizontal {{ background: #ffffff; width: 18px; height: 18px; margin: -7px 0;
                             border-radius: 9px; border: 2px solid {accent}; }}
QSlider::groove:horizontal:disabled {{ background: {surface2}; }}
QSlider::sub-page:horizontal:disabled {{ background: {faint}; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {surface3}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

#rowTitle {{ font-weight: 500; }}
#divider {{ background: {border}; }}
QPushButton::menu-indicator {{ image: none; width: 0px; }}
#bannerIcon {{ border-radius: 11px; font-weight: 800; font-size: 9.5pt; color: {bg};
              background: {dim}; }}
#bannerIcon[level="warn"] {{ background: {warn}; }}
#bannerIcon[level="error"] {{ background: {bad}; }}
#bannerIcon[level="good"] {{ background: {good}; }}
#bannerIcon[level="info"] {{ background: {accent}; color: {accent_text}; }}
#link {{ background: transparent; border: none; color: {accent2}; padding: 4px 2px; }}
#link:hover {{ text-decoration: underline; }}
#statusButton {{ background: transparent; border: none; text-align: left; padding: 6px 4px;
                color: {dim}; }}
#statusButton:hover {{ color: {text}; }}
#banner {{ border-radius: 12px; padding: 2px; }}
#banner[level="info"] {{ background: {surface2}; border: 1px solid {border}; }}
#banner[level="warn"] {{ background: rgba(251, 191, 36, 0.12); border: 1px solid rgba(251, 191, 36, 0.45); }}
#banner[level="error"] {{ background: rgba(248, 113, 113, 0.12); border: 1px solid rgba(248, 113, 113, 0.5); }}
#banner[level="good"] {{ background: rgba(52, 211, 153, 0.12); border: 1px solid rgba(52, 211, 153, 0.45); }}

#pill {{ background: {surface3}; color: {dim}; border-radius: 8px; padding: 2px 8px; font-size: 8.5pt;
        font-weight: 600; }}
#pill[tone="accent"] {{ background: {accent}; color: {accent_text}; }}
#pill[tone="good"] {{ background: rgba(52, 211, 153, 0.18); color: {good}; }}
#pill[tone="warn"] {{ background: rgba(251, 191, 36, 0.18); color: {warn}; }}

#tile {{ background: {surface2}; border: 1px solid {border}; border-radius: 12px; text-align: left;
        padding: 10px; }}
#tile:hover {{ background: {surface3}; }}
#tile:checked {{ border: 2px solid {accent}; background: {surface3}; }}

#statusDot {{ border-radius: 5px; min-width: 10px; max-width: 10px; min-height: 10px; max-height: 10px; }}
QMenu {{ background: {surface}; border: 1px solid {border}; padding: 6px; border-radius: 8px; }}
QMenu::item {{ padding: 6px 22px 6px 14px; border-radius: 6px; }}
QMenu::item:selected {{ background: {surface3}; }}
QMenu::separator {{ height: 1px; background: {border}; margin: 5px 8px; }}
QDialog {{ background: {bg}; }}
QCheckBox::indicator {{ width: 16px; height: 16px; }}
"""
