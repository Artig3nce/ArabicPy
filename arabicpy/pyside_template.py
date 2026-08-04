"""Scaffold a standalone PySide6 desktop app built on the Al-Baa Design System.

Mirrors the write-a-whole-project-to-disk pattern used by
`tauri_export.export_tauri_project` / `android.export_android_project`.
"""

import importlib.resources
import os
import re


def safe_identifier(name):
    value = re.sub(r"[^a-z0-9_]+", "_", name.strip().lower()).strip("_")
    if not value or value[0].isdigit():
        value = f"app_{value}" if value else "albaa_app"
    return value


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def _copy_design_system(project_dir):
    source = importlib.resources.files("arabicpy.design_system")
    for entry in source.iterdir():
        if entry.name.endswith(".py"):
            _write(os.path.join(project_dir, "design_system", entry.name), entry.read_text(encoding="utf-8"))


def _main_py(project_name):
    return f'''"""Entry point for {project_name}."""

import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from main_window import MainWindow


def main():
    QCoreApplication.setOrganizationName({project_name!r})
    QCoreApplication.setApplicationName({project_name!r})
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
'''


def _main_window_py(project_name):
    return f'''"""Main window for {project_name} -- built on the Al-Baa Design System."""

from pathlib import Path

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QSplitter, QStackedWidget

from design_system import DARK, LIGHT, PALETTES, Sidebar, build_app_stylesheet, build_status_bar, build_toolbar, icon
from pages.ai_panel import AIPanel
from pages.settings_page import SettingsPage
from pages.welcome_page import WelcomePage

OVERRIDES_PATH = Path(__file__).resolve().parent / "styles" / "overrides.qss"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle({project_name!r})
        self.resize(1080, 720)

        self.settings = QSettings({project_name!r}, "Settings")
        stored_mode = self.settings.value("theme_mode", DARK)
        self.theme_mode = stored_mode if stored_mode in (DARK, LIGHT) else DARK

        self._build_toolbar()
        self._build_body()
        build_status_bar(self)
        self.apply_theme()

    def _build_toolbar(self):
        toggle_theme = QAction(icon("settings", color="#8891a1"), "Toggle Theme", self)
        toggle_theme.triggered.connect(self.toggle_theme)
        build_toolbar(self, [toggle_theme])

    def _build_body(self):
        nav_items = [
            ("home", "Welcome", "welcome"),
            ("settings", "Settings", "settings"),
            ("chat", "AI Panel", "ai_panel"),
        ]
        self.sidebar = Sidebar(nav_items, title={project_name!r})
        self.sidebar.navigateRequested.connect(self.show_page)

        self.welcome_page = WelcomePage()
        self.settings_page = SettingsPage(self)
        self.ai_panel = AIPanel()
        self._pages = {{
            "welcome": self.welcome_page,
            "settings": self.settings_page,
            "ai_panel": self.ai_panel,
        }}
        self.stack = QStackedWidget()
        for page in self._pages.values():
            self.stack.addWidget(page)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([210, 870])
        splitter.setChildrenCollapsible(False)
        self.setCentralWidget(splitter)

        self.show_page("welcome")

    def show_page(self, page_key):
        self.stack.setCurrentWidget(self._pages[page_key])
        self.sidebar.set_active(page_key)

    def toggle_theme(self):
        self.theme_mode = LIGHT if self.theme_mode == DARK else DARK
        self.settings.setValue("theme_mode", self.theme_mode)
        self.apply_theme()

    def apply_theme(self):
        overrides = ""
        if OVERRIDES_PATH.is_file():
            overrides = OVERRIDES_PATH.read_text(encoding="utf-8")
        palette = PALETTES[self.theme_mode]
        self.setStyleSheet(build_app_stylesheet(palette, overrides=overrides))
        self.theme_mode_label.setText(self.theme_mode.capitalize())
'''


def _pages_init_py():
    return '"""Pages hosted in the main window\'s page stack."""\n'


def _welcome_page_py(project_name):
    return f'''"""Welcome page -- the first thing a user of {project_name} sees."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from design_system import Card, Page, primary_button


class WelcomePage(Page):
    def __init__(self, parent=None):
        super().__init__("Welcome", parent)
        card = Card(self)
        card.set_title({("Welcome to " + project_name)!r})
        message = QLabel(
            "This project was scaffolded by Al-Baa Code using the Al-Baa Design System.\\n"
            "Edit pages/welcome_page.py to replace this placeholder."
        )
        message.setWordWrap(True)
        card.content_layout.addWidget(message)
        get_started = primary_button("Get Started")
        card.content_layout.addWidget(get_started, alignment=Qt.AlignmentFlag.AlignLeft)
        self.content_layout.addWidget(card)
        self.content_layout.addStretch(1)
'''


def _settings_page_py(project_name):
    return f'''"""Settings page -- theme toggle and app info for {project_name}."""

from PySide6.QtWidgets import QLabel

from design_system import Card, Page, secondary_button


class SettingsPage(Page):
    def __init__(self, main_window, parent=None):
        super().__init__("Settings", parent)

        appearance = Card(self)
        appearance.set_title("Appearance")
        appearance.content_layout.addWidget(QLabel("Switch between the Al-Baa light and dark themes."))
        theme_button = secondary_button("Toggle Theme")
        theme_button.clicked.connect(main_window.toggle_theme)
        appearance.content_layout.addWidget(theme_button)
        self.content_layout.addWidget(appearance)

        about = Card(self)
        about.set_title("About")
        about.content_layout.addWidget(QLabel({(project_name + ", built with the Al-Baa Design System.")!r}))
        self.content_layout.addWidget(about)

        self.content_layout.addStretch(1)
'''


def _ai_panel_py():
    return '''"""AI Panel placeholder -- no backend wired up yet."""

from PySide6.QtWidgets import QLabel, QLineEdit

from design_system import Card, Page


class AIPanel(Page):
    def __init__(self, parent=None):
        super().__init__("AI Panel", parent)
        card = Card(self)
        card.set_title("AI Assistant")
        card.content_layout.addWidget(QLabel(
            "This is a placeholder. Wire this panel up to your own AI backend when you're ready."
        ))
        input_row = QLineEdit()
        input_row.setPlaceholderText("Ask something...")
        input_row.setEnabled(False)
        card.content_layout.addWidget(input_row)
        self.content_layout.addWidget(card)
        self.content_layout.addStretch(1)
'''


def _overrides_qss():
    return (
        "/* Add your own QSS rules below -- they're appended after the base Al-Baa\n"
        "   stylesheet and win any same-selector conflicts, so this is the easiest\n"
        "   way to override a color or style while keeping everything else default. */\n"
    )


def _pyproject_toml(slug):
    return f'''[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "{slug}"
version = "0.1.0"
description = "A PySide6 desktop app built with the Al-Baa Design System."
dependencies = [
    "PySide6>=6.5",
]

[tool.setuptools]
py-modules = ["main", "main_window"]
packages = ["design_system", "pages"]
'''


def _readme_md(project_name):
    return f'''# {project_name}

A PySide6 desktop app scaffolded by Al-Baa Code, built on the **Al-Baa Design System**.

## Structure

- `main.py` -- entry point.
- `main_window.py` -- the `MainWindow`, wiring together the toolbar, sidebar, status bar, and pages.
- `pages/` -- `welcome_page.py`, `settings_page.py`, `ai_panel.py` (a placeholder -- no AI backend wired up).
- `design_system/` -- the Al-Baa Design System: colors, typography, spacing, icons, and reusable
  widgets (`Card`, `Sidebar`, buttons, dialogs). This folder was **copied in** when the project was
  generated -- it isn't linked back to Al-Baa Code. Regenerating a project won't touch an existing one;
  create a new project if you want a newer design system.
- `styles/overrides.qss` -- your own QSS, appended after the base stylesheet.

## Overriding the default Al-Baa look

Three levers, in order of how much you want to change:

1. **`styles/overrides.qss`** -- add QSS rules here. They're appended last, so they win any
   same-selector conflicts with the base stylesheet without needing extra specificity.
2. **Pass your own tokens** -- `design_system.build_app_stylesheet(palette, radius=..., spacing=..., typography=...)`
   accepts overrides for every token category; call it with your own `Palette`/dicts in `main_window.py`.
3. **Edit `design_system/` directly** -- it's your project's own copy now, not a shared package.

## Run it

```
pip install -e .
python main.py
```
'''


def _gitignore():
    return (
        "__pycache__/\n"
        "*.pyc\n"
        ".venv/\n"
        "build/\n"
        "dist/\n"
        "*.egg-info/\n"
    )


def generate_pyside_project(directory, project_name):
    """Write a standalone PySide6 project into `directory`. Returns `directory`."""
    slug = safe_identifier(project_name)

    _copy_design_system(directory)
    _write(os.path.join(directory, "main.py"), _main_py(project_name))
    _write(os.path.join(directory, "main_window.py"), _main_window_py(project_name))
    _write(os.path.join(directory, "pages", "__init__.py"), _pages_init_py())
    _write(os.path.join(directory, "pages", "welcome_page.py"), _welcome_page_py(project_name))
    _write(os.path.join(directory, "pages", "settings_page.py"), _settings_page_py(project_name))
    _write(os.path.join(directory, "pages", "ai_panel.py"), _ai_panel_py())
    _write(os.path.join(directory, "styles", "overrides.qss"), _overrides_qss())
    _write(os.path.join(directory, "pyproject.toml"), _pyproject_toml(slug))
    _write(os.path.join(directory, "README.md"), _readme_md(project_name))
    _write(os.path.join(directory, ".gitignore"), _gitignore())
    return directory
