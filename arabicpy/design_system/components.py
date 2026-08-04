"""Al-Baa Design System -- reusable widgets.

These are deliberately small, composable pieces (not a full MainWindow):
window composition is app-specific and belongs in each generated
project's own `main_window.py`. Self-contained: standard library +
PySide6 only, no `arabicpy` imports.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QStatusBar,
    QToolBar, QVBoxLayout, QWidget,
)

from .icons import icon
from .tokens import SPACING


class Card(QFrame):
    """A padded, bordered content frame -- the base for settings rows, stat tiles, etc."""

    def __init__(self, parent=None, *, padding: int = SPACING["md"]):
        super().__init__(parent)
        self.setObjectName("card")
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(padding, padding, padding, padding)
        self.content_layout.setSpacing(SPACING["sm"])

    def set_title(self, text: str):
        label = QLabel(text, objectName="cardTitle")
        self.content_layout.insertWidget(0, label)
        return label


def primary_button(text: str, parent=None) -> QPushButton:
    return QPushButton(text, parent, objectName="primaryButton")


def secondary_button(text: str, parent=None) -> QPushButton:
    return QPushButton(text, parent, objectName="secondaryButton")


def danger_button(text: str, parent=None) -> QPushButton:
    return QPushButton(text, parent, objectName="dangerButton")


class Sidebar(QWidget):
    """A fixed-width navigation rail listing `(icon_name, label, page_key)` items."""

    navigateRequested = Signal(str)

    def __init__(self, items, parent=None, *, title: str = ""):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(210)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACING["sm"], 0, SPACING["sm"])
        layout.setSpacing(2)
        if title:
            layout.addWidget(QLabel(title, objectName="sidebarTitle"))
        self._buttons = {}
        for icon_name, label, page_key in items:
            button = QPushButton(label, objectName="sidebarButton")
            button.setIcon(icon(icon_name, color="#8891a1"))
            button.setCheckable(True)
            button.setProperty("active", False)
            button.clicked.connect(lambda _checked=False, key=page_key: self.navigateRequested.emit(key))
            layout.addWidget(button)
            self._buttons[page_key] = button
        layout.addStretch(1)

    def set_active(self, page_key: str):
        for key, button in self._buttons.items():
            active = key == page_key
            button.setChecked(active)
            button.setProperty("active", active)
            button.style().unpolish(button)
            button.style().polish(button)


class Page(QWidget):
    """Base class for a page hosted in the main window's QStackedWidget."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        if title:
            outer.addWidget(QLabel(title, objectName="pageTitle"))
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(SPACING["lg"], SPACING["sm"], SPACING["lg"], SPACING["lg"])
        self.content_layout.setSpacing(SPACING["md"])
        outer.addLayout(self.content_layout, 1)


def build_toolbar(window, actions) -> QToolBar:
    """Attach a real QToolBar with `actions` (a list of QAction) to `window`."""
    toolbar = QToolBar(window)
    toolbar.setMovable(False)
    toolbar.setIconSize(toolbar.iconSize())
    for action in actions:
        toolbar.addAction(action)
    window.addToolBar(toolbar)
    return toolbar


def build_status_bar(window) -> QStatusBar:
    """Attach a real QStatusBar to `window` with a permanent theme-mode label."""
    status_bar = window.statusBar()
    mode_label = QLabel("", objectName="statusModeLabel")
    status_bar.addPermanentWidget(mode_label)
    window.theme_mode_label = mode_label
    return status_bar


def confirm(parent, title: str, message: str, *, danger: bool = False) -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(message)
    box.setIcon(QMessageBox.Icon.Warning if danger else QMessageBox.Icon.Question)
    box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    box.setDefaultButton(QMessageBox.StandardButton.No)
    return box.exec() == QMessageBox.StandardButton.Yes
