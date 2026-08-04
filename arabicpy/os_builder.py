"""Project editor for future Ubuntu-based OS builds.

This module intentionally contains no ISO, WSL, live-build, or package-install
logic.  It only owns the builder's UI and its portable JSON project format.
"""

from dataclasses import asdict, dataclass, field
import json
import os

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)


BUILT_IN_APPLICATIONS = (
    ("al_baa_ide", "Al-Baa IDE"),
    ("python", "Python"),
    ("git", "Git"),
    ("rust", "Rust"),
    ("docker", "Docker"),
    ("ollama", "Ollama"),
    ("vscode", "VS Code (optional)"),
)


@dataclass
class OSBuilderProject:
    """Versioned, build-tool-agnostic OS project configuration."""

    format_version: int = 1
    distribution_name: str = "Al-Baa OS"
    logo_path: str = ""
    wallpaper_path: str = ""
    login_background_path: str = ""
    accent_color: str = "#6C8CFF"
    applications: dict[str, bool] = field(default_factory=lambda: {
        key: key != "vscode" for key, _label in BUILT_IN_APPLICATIONS
    })
    additional_packages: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data):
        project = cls()
        if not isinstance(data, dict):
            raise ValueError("The OS Builder project must contain a JSON object.")
        project.format_version = int(data.get("format_version", 1))
        project.distribution_name = str(data.get("distribution_name", project.distribution_name))
        project.logo_path = str(data.get("logo_path", ""))
        project.wallpaper_path = str(data.get("wallpaper_path", ""))
        project.login_background_path = str(data.get("login_background_path", ""))
        project.accent_color = str(data.get("accent_color", project.accent_color))
        saved_apps = data.get("applications", {})
        if isinstance(saved_apps, dict):
            project.applications.update({key: bool(value) for key, value in saved_apps.items()})
        packages = data.get("additional_packages", [])
        if isinstance(packages, list):
            project.additional_packages = [str(item) for item in packages if str(item).strip()]
        return project


class OSBuilderProjectStore:
    """Read and write `.albaa-os.json` project files."""

    @staticmethod
    def save(path, project):
        with open(path, "w", encoding="utf-8") as project_file:
            json.dump(asdict(project), project_file, ensure_ascii=False, indent=2)
            project_file.write("\n")

    @staticmethod
    def load(path):
        with open(path, "r", encoding="utf-8") as project_file:
            return OSBuilderProject.from_dict(json.load(project_file))


class BuilderSection(QFrame):
    """Shared card shell used by every settings section."""

    def __init__(self, title, description, parent=None):
        super().__init__(parent)
        self.setObjectName("osBuilderSection")
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(18, 16, 18, 18)
        self.content_layout.setSpacing(10)
        self.content_layout.addWidget(QLabel(title, objectName="osBuilderSectionTitle"))
        subtitle = QLabel(description, objectName="osBuilderSectionDescription")
        subtitle.setWordWrap(True)
        self.content_layout.addWidget(subtitle)


class AssetPathField(QWidget):
    """A read-only path field with an image picker."""

    changed = Signal()

    def __init__(self, label, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(QLabel(label, objectName="osBuilderFieldLabel"))
        row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("No image selected")
        row.addWidget(self.path_edit, 1)
        choose = QPushButton("Choose…", objectName="secondaryButton")
        choose.clicked.connect(self.choose_image)
        row.addWidget(choose)
        clear = QPushButton("Clear", objectName="secondaryButton")
        clear.clicked.connect(self.clear)
        row.addWidget(clear)
        layout.addLayout(row)

    def choose_image(self):
        path, _selected_filter = QFileDialog.getOpenFileName(
            self, "Choose Image", "", "Images (*.png *.jpg *.jpeg *.webp *.svg);;All Files (*)"
        )
        if path:
            self.set_path(path)

    def set_path(self, path):
        self.path_edit.setText(os.path.normpath(path) if path else "")
        self.changed.emit()

    def path(self):
        return self.path_edit.text().strip()

    def clear(self):
        self.set_path("")


class BrandingSection(BuilderSection):
    def __init__(self, parent=None):
        super().__init__("Branding", "Choose the identity and visual assets for the distribution.", parent)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Al-Baa OS")
        self.content_layout.addWidget(QLabel("Distribution name", objectName="osBuilderFieldLabel"))
        self.content_layout.addWidget(self.name_edit)
        self.logo_field = AssetPathField("Logo")
        self.wallpaper_field = AssetPathField("Desktop wallpaper")
        self.login_field = AssetPathField("Login background")
        self.content_layout.addWidget(self.logo_field)
        self.content_layout.addWidget(self.wallpaper_field)
        self.content_layout.addWidget(self.login_field)
        self.content_layout.addWidget(QLabel("Accent color", objectName="osBuilderFieldLabel"))
        color_row = QHBoxLayout()
        self.color_edit = QLineEdit()
        self.color_edit.setPlaceholderText("#6C8CFF")
        color_row.addWidget(self.color_edit, 1)
        self.color_button = QPushButton("Choose color…", objectName="secondaryButton")
        self.color_button.clicked.connect(self.choose_color)
        color_row.addWidget(self.color_button)
        self.content_layout.addLayout(color_row)

    def choose_color(self):
        color = QColorDialog.getColor(QColor(self.color_edit.text()), self, "Choose Accent Color")
        if color.isValid():
            self.color_edit.setText(color.name().upper())

    def apply_project(self, project):
        self.name_edit.setText(project.distribution_name)
        self.logo_field.set_path(project.logo_path)
        self.wallpaper_field.set_path(project.wallpaper_path)
        self.login_field.set_path(project.login_background_path)
        self.color_edit.setText(project.accent_color)

    def update_project(self, project):
        project.distribution_name = self.name_edit.text().strip() or "Al-Baa OS"
        project.logo_path = self.logo_field.path()
        project.wallpaper_path = self.wallpaper_field.path()
        project.login_background_path = self.login_field.path()
        color = QColor(self.color_edit.text().strip())
        project.accent_color = color.name().upper() if color.isValid() else "#6C8CFF"


class ApplicationsSection(BuilderSection):
    def __init__(self, parent=None):
        super().__init__("Preinstalled applications", "Select software to include when ISO building is implemented.", parent)
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(9)
        self.checkboxes = {}
        for index, (key, label) in enumerate(BUILT_IN_APPLICATIONS):
            checkbox = QCheckBox(label)
            self.checkboxes[key] = checkbox
            grid.addWidget(checkbox, index // 2, index % 2)
        self.content_layout.addLayout(grid)

    def apply_project(self, project):
        for key, checkbox in self.checkboxes.items():
            checkbox.setChecked(project.applications.get(key, False))

    def update_project(self, project):
        project.applications = {key: checkbox.isChecked() for key, checkbox in self.checkboxes.items()}


class PackagesSection(BuilderSection):
    def __init__(self, parent=None):
        super().__init__(
            "Additional Ubuntu packages",
            "Enter package names separated by spaces, commas, or new lines. They are saved only; nothing is installed.",
            parent,
        )
        self.packages_edit = QPlainTextEdit()
        self.packages_edit.setPlaceholderText("curl\nhtop\nfonts-noto")
        self.packages_edit.setFixedHeight(105)
        self.content_layout.addWidget(self.packages_edit)

    def apply_project(self, project):
        self.packages_edit.setPlainText("\n".join(project.additional_packages))

    def update_project(self, project):
        raw = self.packages_edit.toPlainText().replace(",", " ")
        project.additional_packages = list(dict.fromkeys(raw.split()))


class OSBuilderPage(QWidget):
    """Complete project editor, composed from independent settings sections."""

    projectChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("osBuilderPage")
        self.project_path = ""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QWidget(objectName="osBuilderHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(22, 14, 22, 14)
        title_box = QVBoxLayout()
        title_box.addWidget(QLabel("OS Builder", objectName="osBuilderTitle"))
        self.path_label = QLabel("Unsaved project", objectName="osBuilderProjectPath")
        title_box.addWidget(self.path_label)
        header_layout.addLayout(title_box)
        header_layout.addStretch()
        new_button = QPushButton("New", objectName="secondaryButton")
        new_button.clicked.connect(self.new_project)
        header_layout.addWidget(new_button)
        open_button = QPushButton("Open…", objectName="secondaryButton")
        open_button.clicked.connect(self.open_project)
        header_layout.addWidget(open_button)
        save_button = QPushButton("Save Project", objectName="primaryButton")
        save_button.clicked.connect(self.save_project)
        header_layout.addWidget(save_button)
        outer.addWidget(header)
        notice = QLabel(
            "Configuration only — ISO generation will be added in a future version.",
            objectName="osBuilderNotice",
        )
        notice.setWordWrap(True)
        outer.addWidget(notice)
        scroll = QScrollArea(objectName="osBuilderScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(22, 18, 22, 24)
        content_layout.setSpacing(14)
        self.branding = BrandingSection()
        self.applications = ApplicationsSection()
        self.packages = PackagesSection()
        content_layout.addWidget(self.branding)
        content_layout.addWidget(self.applications)
        content_layout.addWidget(self.packages)
        content_layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        self.apply_project(OSBuilderProject())

    def current_project(self):
        project = OSBuilderProject()
        self.branding.update_project(project)
        self.applications.update_project(project)
        self.packages.update_project(project)
        return project

    def apply_project(self, project):
        self.branding.apply_project(project)
        self.applications.apply_project(project)
        self.packages.apply_project(project)

    def new_project(self):
        self.project_path = ""
        self.path_label.setText("Unsaved project")
        self.apply_project(OSBuilderProject())

    def open_project(self):
        path, _selected_filter = QFileDialog.getOpenFileName(
            self, "Open OS Builder Project", "", "Al-Baa OS Projects (*.albaa-os.json);;JSON (*.json)"
        )
        if not path:
            return
        try:
            self.apply_project(OSBuilderProjectStore.load(path))
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
            QMessageBox.critical(self, "Could Not Open Project", str(error))
            return
        self.project_path = path
        self.path_label.setText(path)
        self.projectChanged.emit(path)

    def save_project(self):
        path = self.project_path
        if not path:
            path, _selected_filter = QFileDialog.getSaveFileName(
                self, "Save OS Builder Project", "Al-Baa-OS.albaa-os.json",
                "Al-Baa OS Projects (*.albaa-os.json);;JSON (*.json)",
            )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".albaa-os.json"
        try:
            OSBuilderProjectStore.save(path, self.current_project())
        except OSError as error:
            QMessageBox.critical(self, "Could Not Save Project", str(error))
            return
        self.project_path = path
        self.path_label.setText(path)
        self.projectChanged.emit(path)
        QMessageBox.information(self, "Project Saved", f"OS Builder project saved to:\n{path}")
