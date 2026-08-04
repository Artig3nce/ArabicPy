"""Editable Qt mobile canvas for ArabicPy Android source files."""

import json
import re
import urllib.error
import urllib.request

from PySide6.QtCore import QEvent, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QColorDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from .ai import DEFAULT_MODEL, system_prompt_for
from .android import AndroidEvent, AndroidProgram, AndroidWidget, parse_android
from .i18n import TRANSLATIONS


def _t(text, language, **kwargs):
    """Standalone counterpart to ArabicPyIDE.t() -- this widget has no window reference."""
    if language == "ar":
        text = TRANSLATIONS.get(text, text)
    return text.format(**kwargs) if kwargs else text


class ChatPreviewWorker(QThread):
    """Asks the same local Ollama instance the IDE uses, off the UI thread."""

    replied = Signal(str)

    def __init__(self, question, language, parent=None):
        super().__init__(parent)
        self.question = question
        self.language = language

    def run(self):
        label = "سؤال المستخدم" if self.language == "ar" else "User's question"
        payload = json.dumps({
            "model": DEFAULT_MODEL,
            "prompt": f"{system_prompt_for(self.language)}\n\n{label}:\n{self.question}",
            "stream": False,
            "think": False,
        }).encode("utf-8")
        request = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
            text = result.get("response", "").strip() or _t(
                "The model returned no answer.", self.language
            )
        except urllib.error.HTTPError as error:
            if error.code == 404:
                text = _t(
                    "Model {model} isn't installed. Install it with: ollama pull {model}",
                    self.language, model=DEFAULT_MODEL,
                )
            else:
                text = _t("Couldn't run the local model: HTTP {code}", self.language, code=error.code)
        except (urllib.error.URLError, TimeoutError, OSError):
            text = _t("Couldn't connect to Ollama. Start Ollama and try again.", self.language)
        self.replied.emit(text)


COLOR_THEMES = {
    "Dark Social": {
        "screen": "#000000", "text": "#F2F2F2", "surface": "#0A0A0A",
        "button": "#F2F2F2", "button_text": "#0F1419", "navigation": True,
    },
    "Clean & Bright": {
        "screen": "#FFFFFF", "text": "#0F172A", "surface": "#F8FAFC",
        "button": "#0F172A", "button_text": "#FFFFFF", "navigation": True,
    },
}


class DesignerItem(QFrame):
    selected = Signal(str)
    activated = Signal(str)

    def __init__(self, widget_model, parent=None, language="en", screen_background="#FFFFFF"):
        super().__init__(parent)
        self.widget_model = widget_model
        self.language = language
        self.screen_background = screen_background
        self.preview_mode = False
        self.setObjectName("designerItem")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        if widget_model.kind == "نص":
            control = QLabel(widget_model.text)
            control.setAlignment(Qt.AlignCenter)
        elif widget_model.kind == "زر":
            control = QPushButton(widget_model.text)
        elif widget_model.kind == "دردشة":
            control = self._build_chat_preview()
            self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        elif widget_model.kind == "فيديو":
            source = widget_model.text or _t("Video source", self.language)
            control = QLabel(f"▶\n{source}")
            control.setAlignment(Qt.AlignCenter)
            control.setWordWrap(True)
            control.setMinimumHeight(140)
        else:
            control = QLineEdit()
            control.setPlaceholderText(widget_model.text)
            if widget_model.kind == "كلمة_مرور":
                control.setEchoMode(QLineEdit.EchoMode.Password)

        self.control = control
        if isinstance(control, QPushButton):
            control.clicked.connect(
                lambda _checked=False: self.activated.emit(self.widget_model.name)
            )
        if widget_model.kind != "دردشة":
            self.apply_colors()
        control.installEventFilter(self)
        layout.addWidget(control)
        if widget_model.kind == "كلمة_مرور":
            self.password_status = QLabel(_t("Enter password", self.language))
            self.password_status.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.password_status)
            control.textChanged.connect(self.validate_password)

    def validate_password(self, value):
        minimum = self.widget_model.min_length or 8
        valid = (
            len(value) >= minimum
            and any(char.isdigit() for char in value)
            and any(not char.isalnum() for char in value)
        )
        if valid:
            self.password_status.setText(_t("Strong password", self.language))
            self.password_status.setStyleSheet("color: #22C55E;")
        else:
            self.password_status.setText(_t("Use {min}+ characters with digits and symbols", self.language, min=minimum))
            self.password_status.setStyleSheet("color: #EF4444;")

    def _resolve_chat_colors(self):
        """Derive bubble/container colors from the widget's theme colors (set by App Templates)."""
        accent = QColor(self.widget_model.text_color or "#007ACC")
        container = QColor(self.widget_model.background_color or self.screen_background or "#FFFFFF")
        bubble = container.lighter(140) if container.lightness() < 128 else container.darker(108)
        # The input bar is always the opposite tone of the container so typed
        # text stays legible no matter how dark or light the chosen theme is.
        input_bg = QColor("#FFFFFF") if container.lightness() < 128 else QColor("#202124")
        input_text = QColor("#202124") if container.lightness() < 128 else QColor("#FFFFFF")
        return {
            "container": container.name(),
            "accent": accent.name(),
            "accent_text": "#FFFFFF" if accent.lightness() < 128 else "#202124",
            "bubble": bubble.name(),
            "bubble_text": "#FFFFFF" if bubble.lightness() < 128 else "#202124",
            "input_bg": input_bg.name(),
            "input_text": input_text.name(),
        }

    def _build_chat_preview(self):
        """The AI chat widget: a static mockup while editing, a live chat during Run/Preview."""
        self.chat_colors = self._resolve_chat_colors()
        container = self.chat_colors["container"]

        box = QWidget()
        box.setMinimumHeight(170)
        box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        box.setStyleSheet(f"background:{container}; border-radius:8px;")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self.chat_log_scroll = QScrollArea()
        self.chat_log_scroll.setWidgetResizable(True)
        self.chat_log_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.chat_log_scroll.setStyleSheet(f"background:{container}; border:none;")
        self.chat_log_scroll.viewport().setStyleSheet(f"background:{container};")
        log_host = QWidget()
        log_host.setStyleSheet(f"background:{container};")
        self.chat_log_layout = QVBoxLayout(log_host)
        self.chat_log_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_log_layout.setSpacing(6)
        self.chat_log_layout.addStretch(1)
        self.chat_log_scroll.setWidget(log_host)
        layout.addWidget(self.chat_log_scroll, 1)

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText(_t("Type a message...", self.language))
        self.chat_input.setEnabled(False)
        self.chat_input.setStyleSheet(
            f"background:{self.chat_colors['input_bg']}; color:{self.chat_colors['input_text']}; "
            f"border:1px solid {self.chat_colors['accent']}; border-radius:6px; padding:6px 10px;"
        )
        self.chat_input.returnPressed.connect(self._send_chat_preview_message)
        layout.addWidget(self.chat_input)

        self._add_chat_bubble(_t("Sample question", self.language), is_user=True)
        self._add_chat_bubble(_t("Sample AI answer", self.language), is_user=False)
        return box

    def _add_chat_bubble(self, text, is_user):
        colors = getattr(self, "chat_colors", None) or self._resolve_chat_colors()
        background = colors["accent"] if is_user else colors["bubble"]
        foreground = colors["accent_text"] if is_user else colors["bubble_text"]
        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setAlignment(Qt.AlignRight if is_user else Qt.AlignLeft)
        bubble.setStyleSheet(
            f"background:{background}; color:{foreground}; border-radius:8px; padding:6px 10px; border:none;"
        )
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        if is_user:
            row.addStretch(1)
            row.addWidget(bubble, 0, Qt.AlignRight)
        else:
            row.addWidget(bubble, 0, Qt.AlignLeft)
            row.addStretch(1)
        self.chat_log_layout.insertLayout(self.chat_log_layout.count() - 1, row)

    def _send_chat_preview_message(self):
        if not self.preview_mode:
            return
        question = self.chat_input.text().strip()
        if not question:
            return
        self.chat_input.clear()
        self.chat_input.setEnabled(False)
        self.chat_input.setPlaceholderText(_t("Thinking...", self.language))
        self._add_chat_bubble(question, is_user=True)
        worker = ChatPreviewWorker(question, self.language, self)
        self._chat_worker = worker
        worker.replied.connect(self._on_chat_preview_reply)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_chat_preview_reply(self, text):
        self._add_chat_bubble(text, is_user=False)
        self.chat_input.setEnabled(True)
        self.chat_input.setPlaceholderText(_t("Type a message...", self.language))
        self.chat_input.setFocus()

    def _reset_chat_preview(self, live):
        while self.chat_log_layout.count() > 1:
            item = self.chat_log_layout.takeAt(0)
            child_layout = item.layout()
            if child_layout is not None:
                while child_layout.count():
                    child_item = child_layout.takeAt(0)
                    widget = child_item.widget()
                    if widget is not None:
                        widget.deleteLater()
        self.chat_input.setEnabled(live)
        self.chat_input.clear()
        self.chat_input.setPlaceholderText(_t("Type a message...", self.language))
        if live:
            self._add_chat_bubble(
                _t("Ask me anything -- I'm your local AI.", self.language), is_user=False
            )
        else:
            self._add_chat_bubble(_t("Sample question", self.language), is_user=True)
            self._add_chat_bubble(_t("Sample AI answer", self.language), is_user=False)

    def apply_colors(self):
        text_color = self.widget_model.text_color or (
            "#FFFFFF" if self.widget_model.kind == "زر" else "#202124"
        )
        background_color = self.widget_model.background_color or (
            "#0F172A" if self.widget_model.kind == "زر" else "#F8FAFC"
        )
        pressed_color = QColor(background_color).darker(125).name()
        if isinstance(self.control, QPushButton):
            style = (
                f"QPushButton {{ color: {text_color}; background-color: {background_color}; }}"
                f"QPushButton:pressed {{ background-color: {pressed_color}; }}"
            )
        else:
            style = f"color: {text_color}; background-color: {background_color};"
        self.control.setStyleSheet(style)

    def eventFilter(self, watched, event):
        if self.preview_mode:
            return super().eventFilter(watched, event)
        if watched is self.control and event.type() in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.FocusIn,
        ):
            self.selected.emit(self.widget_model.name)
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event):
        self.selected.emit(self.widget_model.name)
        super().mousePressEvent(event)

    def set_selected(self, selected):
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_preview_mode(self, enabled):
        self.preview_mode = enabled
        self.set_selected(False)
        if self.widget_model.kind == "دردشة":
            self._reset_chat_preview(live=enabled)


class AndroidDesigner(QWidget):
    sourceChanged = Signal(str)

    def __init__(self, parent=None, language="en"):
        super().__init__(parent)
        self.language = language
        self.program = AndroidProgram(self.t("Al-Baa"), [], [], background_color="#FFFFFF")
        self.selected_name = None
        self.selected_navigation_index = None
        self.loading = False
        self.item_widgets = {}
        self.preview_mode = False
        self.last_error = None
        self.setup_ui()
        self.delete_shortcut = QShortcut(QKeySequence("Delete"), self)
        self.delete_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.delete_shortcut.activated.connect(self.delete_selected_from_keyboard)

    def t(self, text, **kwargs):
        return _t(text, self.language, **kwargs)

    def delete_selected_from_keyboard(self):
        """Delete the selected canvas item without breaking text-field editing."""
        if self.preview_mode or (
            self.selected_widget() is None and self.selected_navigation_index is None
        ):
            return
        focused = QApplication.focusWidget()
        if isinstance(focused, QLineEdit) and focused.hasFocus():
            return
        self.delete_selected()

    def setup_ui(self):
        self.setObjectName("androidDesigner")
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(1)

        palette = QFrame(objectName="designerPanel")
        self.palette_panel = palette
        palette.setFixedWidth(150)
        palette_layout = QVBoxLayout(palette)
        palette_layout.addWidget(QLabel(self.t("Elements"), objectName="designerTitle"))
        for kind, label in (
            ("نص", self.t("+ Text")), ("زر", self.t("+ Button")), ("حقل", self.t("+ Input Field")),
            ("فيديو", self.t("+ Video")),
            ("دردشة", self.t("+ AI Chat")),
        ):
            button = QPushButton(label, objectName="designerTool")
            button.clicked.connect(lambda _checked=False, value=kind: self.add_widget(value))
            palette_layout.addWidget(button)
        palette_layout.addStretch()
        root.addWidget(palette)

        canvas_scroll = QScrollArea()
        self.canvas_scroll = canvas_scroll
        canvas_scroll.setWidgetResizable(True)
        canvas_scroll.setObjectName("designerCanvas")
        canvas_scroll.viewport().installEventFilter(self)
        canvas_host = QWidget()
        canvas_host_layout = QVBoxLayout(canvas_host)
        canvas_host_layout.setContentsMargins(12, 14, 12, 12)
        canvas_host_layout.setSpacing(10)
        canvas_host_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
<<<<<<< HEAD
        self.canvas_frame = QFrame(objectName="canvasFrame")
        self.canvas_logical_size = (960, 620)
        self.canvas_frame.setFixedSize(*self.canvas_logical_size)
        canvas_frame_layout = QVBoxLayout(self.canvas_frame)
        canvas_frame_layout.setContentsMargins(12, 12, 12, 12)
        self.canvas_title = QLabel(self.program.title, objectName="canvasTitle")
        self.canvas_title.setAlignment(Qt.AlignCenter)
        canvas_frame_layout.addWidget(self.canvas_title)
        self.canvas_layout = QVBoxLayout()
        canvas_frame_layout.addLayout(self.canvas_layout, 1)
        self.bottom_navigation = QFrame(objectName="canvasNavigation")
        self.bottom_navigation_layout = QHBoxLayout(self.bottom_navigation)
        self.bottom_navigation_layout.setContentsMargins(4, 4, 4, 4)
        self.bottom_navigation_layout.setSpacing(2)
        canvas_frame_layout.addWidget(self.bottom_navigation)
=======
        device_bar = QFrame(objectName="designerPanel")
        device_bar.setFixedHeight(46)
        device_bar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        device_layout = QHBoxLayout(device_bar)
        device_layout.setContentsMargins(6, 4, 6, 4)
        device_layout.setSpacing(4)
        self.device_buttons = {}
        for key, label in (
            ("phone", self.t("Phone")),
            ("tablet", self.t("Tablet")),
            ("desktop", self.t("Desktop")),
            ("browser", self.t("Browser")),
        ):
            button = QPushButton(label, objectName="designerTool")
            button.setCheckable(True)
            button.setChecked(key == "phone")
            button.clicked.connect(lambda _checked=False, value=key: self.set_device_preview(value))
            self.device_buttons[key] = button
            device_layout.addWidget(button)
        canvas_host_layout.addWidget(device_bar, 0, Qt.AlignCenter)
        self.phone = QFrame(objectName="phoneFrame")
        self.preview_device = "phone"
        self.preview_logical_size = (360, 620)
        self.phone.setFixedSize(360, 620)
        phone_layout = QVBoxLayout(self.phone)
        phone_layout.setContentsMargins(12, 12, 12, 12)
        self.phone_title = QLabel(self.program.title, objectName="phoneTitle")
        self.phone_title.setAlignment(Qt.AlignCenter)
        phone_layout.addWidget(self.phone_title)
        self.canvas_layout = QVBoxLayout()
        phone_layout.addLayout(self.canvas_layout, 1)
        self.bottom_navigation = QFrame(objectName="phoneNavigation")
        self.bottom_navigation_layout = QHBoxLayout(self.bottom_navigation)
        self.bottom_navigation_layout.setContentsMargins(4, 4, 4, 4)
        self.bottom_navigation_layout.setSpacing(2)
        phone_layout.addWidget(self.bottom_navigation)
>>>>>>> parent of aca10fd (v8)
        self.page_placeholder = QLabel()
        self.page_placeholder.setAlignment(Qt.AlignCenter)
        self.page_placeholder.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.page_placeholder.hide()
<<<<<<< HEAD
        canvas_frame_layout.insertWidget(2, self.page_placeholder)
        canvas_host_layout.addWidget(self.canvas_frame, 0, Qt.AlignHCenter | Qt.AlignTop)
=======
        phone_layout.insertWidget(2, self.page_placeholder)
        canvas_host_layout.addWidget(self.phone, 0, Qt.AlignHCenter | Qt.AlignTop)
>>>>>>> parent of aca10fd (v8)
        canvas_scroll.setWidget(canvas_host)
        root.addWidget(canvas_scroll, 1)

        properties = QFrame(objectName="designerPanel")
        self.properties_panel = properties
        properties.setFixedWidth(210)
        properties_layout = QVBoxLayout(properties)
        properties_layout.addWidget(QLabel(self.t("Properties"), objectName="designerTitle"))
        properties_layout.addWidget(QLabel(self.t("App Name")))
        self.app_title_edit = QLineEdit()
        self.app_title_edit.editingFinished.connect(self.apply_app_title)
        properties_layout.addWidget(self.app_title_edit)
        self.screen_color_button = QPushButton(self.t("Screen Background Color"))
        self.screen_color_button.clicked.connect(self.choose_screen_color)
        properties_layout.addWidget(self.screen_color_button)
        properties_layout.addWidget(QLabel(self.t("App Templates"), objectName="designerTitle"))
        for theme_name in COLOR_THEMES:
            theme_button = QPushButton(self.t(theme_name), objectName="designerTool")
            theme_button.clicked.connect(
                lambda _checked=False, name=theme_name: self.apply_color_theme(name)
            )
            properties_layout.addWidget(theme_button)
        properties_layout.addWidget(QLabel(self.t("Element Name")))
        self.name_edit = QLineEdit()
        properties_layout.addWidget(self.name_edit)
        properties_layout.addWidget(QLabel(self.t("Text")))
        self.text_edit = QLineEdit()
        properties_layout.addWidget(self.text_edit)
        self.text_color_button = QPushButton(self.t("Text Color"))
        self.text_color_button.clicked.connect(lambda: self.choose_color("text"))
        properties_layout.addWidget(self.text_color_button)
        self.background_color_button = QPushButton(self.t("Background Color"))
        self.background_color_button.clicked.connect(lambda: self.choose_color("background"))
        properties_layout.addWidget(self.background_color_button)
        reset_colors_button = QPushButton(self.t("Reset to Default Colors"))
        reset_colors_button.clicked.connect(self.reset_colors)
        properties_layout.addWidget(reset_colors_button)
        apply_button = QPushButton(self.t("Apply Changes"))
        apply_button.clicked.connect(self.apply_properties)
        properties_layout.addWidget(apply_button)
        up_button = QPushButton(self.t("Move Up"))
        up_button.clicked.connect(lambda: self.move_selected(-1))
        properties_layout.addWidget(up_button)
        down_button = QPushButton(self.t("Move Down"))
        down_button.clicked.connect(lambda: self.move_selected(1))
        properties_layout.addWidget(down_button)
        delete_button = QPushButton(self.t("Delete Element"), objectName="designerDelete")
        delete_button.clicked.connect(self.delete_selected)
        properties_layout.addWidget(delete_button)
        properties_layout.addStretch()
        root.addWidget(properties)
        self.refresh_canvas()
<<<<<<< HEAD
        QTimer.singleShot(0, self.fit_canvas_size)

    def fit_canvas_size(self):
        """Fit the design canvas completely inside the current designer viewport."""
        if not hasattr(self, "canvas_scroll") or not hasattr(self, "canvas_frame"):
            return
        logical_width, logical_height = self.canvas_logical_size
=======
        QTimer.singleShot(0, self.fit_device_preview)

    def set_device_preview(self, device):
        """Switch the responsive design canvas without changing application data."""
        sizes = {
            "phone": (360, 620),
            "tablet": (720, 760),
            "desktop": (960, 620),
            "browser": (960, 620),
        }
        self.preview_device = device if device in sizes else "phone"
        self.preview_logical_size = sizes[self.preview_device]
        self.phone.setProperty("device", device)
        for key, button in self.device_buttons.items():
            button.setChecked(key == self.preview_device)
        self.fit_device_preview()

    def fit_device_preview(self):
        """Fit the selected device completely inside the current designer viewport."""
        if not hasattr(self, "canvas_scroll") or not hasattr(self, "phone"):
            return
        logical_width, logical_height = self.preview_logical_size
>>>>>>> parent of aca10fd (v8)
        viewport = self.canvas_scroll.viewport().size()
        available_width = max(240, viewport.width() - 40)
        available_height = max(300, viewport.height() - 72)
        scale = min(1.0, available_width / logical_width, available_height / logical_height)
<<<<<<< HEAD
        self.canvas_frame.setFixedSize(
=======
        self.phone.setFixedSize(
>>>>>>> parent of aca10fd (v8)
            max(240, round(logical_width * scale)),
            max(300, round(logical_height * scale)),
        )

    def eventFilter(self, watched, event):
        if (
            hasattr(self, "canvas_scroll")
            and watched is self.canvas_scroll.viewport()
            and event.type() == QEvent.Type.Resize
        ):
<<<<<<< HEAD
            QTimer.singleShot(0, self.fit_canvas_size)
=======
            QTimer.singleShot(0, self.fit_device_preview)
>>>>>>> parent of aca10fd (v8)
        return super().eventFilter(watched, event)

    def load_source(self, source):
        try:
            program = parse_android(source)
        except Exception as error:
            self.last_error = error
            return False
        self.last_error = None
        self.loading = True
        self.program = program
        self.selected_name = None
        self.selected_navigation_index = None
        self.refresh_canvas()
        self.loading = False
        return True

    def start_preview(self):
<<<<<<< HEAD
        """Run supported click events directly inside the design canvas."""
=======
        """Run supported click events directly inside the phone canvas."""
>>>>>>> parent of aca10fd (v8)
        self.preview_mode = True
        self.selected_name = None
        self.palette_panel.setEnabled(False)
        self.properties_panel.setEnabled(False)
        for item in self.item_widgets.values():
            item.set_preview_mode(True)

    def stop_preview(self):
        self.preview_mode = False
        self.palette_panel.setEnabled(True)
        self.properties_panel.setEnabled(True)
        self.refresh_canvas()

    def run_preview_event(self, button_name):
        if not self.preview_mode:
            return
        for event in self.program.events:
            if event.button != button_name:
                continue
            for target, text in event.actions:
                if target == "__page__":
                    self.show_preview_page(text)
                    continue
                if target == "__print__":
                    print(text)
                    continue
                item = self.item_widgets.get(target)
                if item is not None:
                    item.control.setText(text)

    def show_preview_page(self, page_name):
        if not self.preview_mode:
            return
<<<<<<< HEAD
        self.canvas_title.setText(page_name)
=======
        self.phone_title.setText(page_name)
>>>>>>> parent of aca10fd (v8)
        page_items = [
            item for item in self.item_widgets.values()
            if item.widget_model.page == page_name
        ]
        page_has_chat = any(item.widget_model.kind == "دردشة" for item in page_items)
        if page_has_chat:
            page_items = [item for item in page_items if item.widget_model.kind == "دردشة"]
        for item in self.item_widgets.values():
            item.setVisible(item in page_items)
        self.page_placeholder.setText(self.t("Page {name}", name=page_name))
        self.page_placeholder.setVisible(not page_items)

    def add_widget(self, kind):
        prefixes = {
            "نص": "Text", "زر": "Button", "حقل": "Field",
            "فيديو": "Video", "دردشة": "Chat",
        }
        defaults = {
            "نص": self.t("New Text"), "زر": self.t("New Button"), "حقل": self.t("Type here"),
            "فيديو": "video.mp4",
            "دردشة": "",
        }
        used = {widget.name for widget in self.program.widgets}
        number = 1
        while f"{prefixes[kind]}_{number}" in used:
            number += 1
        widget = AndroidWidget(f"{prefixes[kind]}_{number}", kind, defaults[kind])
        # The chat widget's colors are fixed in the generated app (matches the
        # IDE's own AI panel), so it doesn't participate in text/background
        # color inheritance the way text/button/field widgets do.
        if kind not in ("دردشة", "فيديو"):
            matching_widget = next(
                (item for item in reversed(self.program.widgets) if item.kind == kind),
                None,
            )
            if matching_widget is not None:
                widget.text_color = matching_widget.text_color
                widget.background_color = matching_widget.background_color
            else:
                dark_screen = QColor(self.program.background_color or "#FAFAFA").lightness() < 128
                if kind == "زر":
                    widget.text_color = "#0F1419" if dark_screen else "#FFFFFF"
                    widget.background_color = "#F2F2F2" if dark_screen else "#0F172A"
                else:
                    widget.text_color = "#F2F2F2" if dark_screen else "#0F172A"
                    widget.background_color = "#0A0A0A" if dark_screen else "#F8FAFC"
        self.program.widgets.append(widget)
        self.selected_name = widget.name
        self.refresh_canvas()
        self.emit_source()

    def select_widget(self, name):
        self.selected_navigation_index = None
        self.selected_name = name
        for item_name, item in self.item_widgets.items():
            item.set_selected(item_name == name)
        widget = self.selected_widget()
        if widget:
            self.name_edit.setText(widget.name)
            self.text_edit.setText(widget.text)
            self.update_color_buttons(widget)

    def select_navigation(self, index):
        if self.preview_mode or not (0 <= index < len(self.program.bottom_navigation)):
            return
        self.selected_name = None
        self.selected_navigation_index = index
        for item in self.item_widgets.values():
            item.set_selected(False)
        self.name_edit.setText(f"NavButton_{index + 1}")
        self.text_edit.setText(self.program.bottom_navigation[index])
        self.text_color_button.setText(self.t("Text Color: Auto"))
        self.background_color_button.setText(self.t("Background Color: Auto"))
        self.refresh_bottom_navigation()

    def selected_widget(self):
        return next(
            (widget for widget in self.program.widgets if widget.name == self.selected_name),
            None,
        )

    def apply_app_title(self):
        title = self.app_title_edit.text().strip()
        if title and '"' not in title:
            self.program.title = title
<<<<<<< HEAD
            self.canvas_title.setText(title)
=======
            self.phone_title.setText(title)
>>>>>>> parent of aca10fd (v8)
            self.emit_source()

    def choose_screen_color(self):
        current = self.program.background_color or "#FAFAFA"
        color = QColorDialog.getColor(QColor(current), self, self.t("Choose Screen Background Color"))
        if not color.isValid():
            return
        self.program.background_color = color.name().upper()
<<<<<<< HEAD
        self.refresh_canvas_color()
=======
        self.refresh_phone_color()
>>>>>>> parent of aca10fd (v8)
        self.emit_source()

    def apply_color_theme(self, theme_name):
        """Apply a coordinated palette to the screen and every existing widget."""
        theme = COLOR_THEMES[theme_name]
        self.program.background_color = theme["screen"]
        for widget in self.program.widgets:
            if widget.kind == "زر":
                widget.text_color = theme["button_text"]
                widget.background_color = theme["button"]
            elif widget.kind == "دردشة":
                # Chat bubbles use text_color as the "my message" accent and
                # background_color as the AI-message surface, matching the
                # theme's button/surface colors respectively.
                widget.text_color = theme["button"]
                widget.background_color = theme["surface"]
            elif widget.kind == "فيديو":
                widget.text_color = None
                widget.background_color = None
            else:
                widget.text_color = theme["text"]
                widget.background_color = theme["surface"]
        if theme.get("navigation") and not self.program.bottom_navigation:
            self.program.bottom_navigation = [
                self.t("Home"), self.t("Search"), self.t("Alerts"), self.t("Messages"),
            ]
        self.refresh_canvas()
        self.emit_source()

    def apply_properties(self):
        if self.selected_navigation_index is not None:
            text = self.text_edit.text().strip()
            if not text or '"' in text:
                QMessageBox.warning(self, self.t("Invalid Text"), self.t("Enter valid text for the bottom navigation button."))
                return
            self.program.bottom_navigation[self.selected_navigation_index] = text
            self.refresh_bottom_navigation()
            self.emit_source()
            return
        widget = self.selected_widget()
        if widget is None:
            return
        name = self.name_edit.text().strip()
        text = self.text_edit.text().strip()
        if not re.fullmatch(r"[\w\u0600-\u06ff]+", name) or name[0].isdigit():
            QMessageBox.warning(self, self.t("Invalid Name"), self.t("Use only letters, numbers, and underscores."))
            return
        if any(item.name == name and item is not widget for item in self.program.widgets):
            QMessageBox.warning(self, self.t("Duplicate Name"), self.t("Another element already has this name."))
            return
        if '"' in text:
            QMessageBox.warning(self, self.t("Invalid Text"), self.t("Double quotes aren't currently supported inside text."))
            return

        old_name = widget.name
        widget.name = name
        widget.text = text
        for event in self.program.events:
            if event.button == old_name:
                event.button = name
            event.actions = [
                (name if target == old_name else target, value)
                for target, value in event.actions
            ]
        self.selected_name = name
        self.refresh_canvas()
        self.emit_source()

    def choose_color(self, color_type):
        widget = self.selected_widget()
        if widget is None:
            return
        current = (
            widget.text_color if color_type == "text" else widget.background_color
        ) or "#FFFFFF"
        color = QColorDialog.getColor(QColor(current), self, self.t("Choose Color"))
        if not color.isValid():
            return
        if color_type == "text":
            widget.text_color = color.name().upper()
        else:
            widget.background_color = color.name().upper()
        self.refresh_canvas()
        self.emit_source()

    def reset_colors(self):
        widget = self.selected_widget()
        if widget is None:
            return
        widget.text_color = None
        widget.background_color = None
        self.refresh_canvas()
        self.emit_source()

    def update_color_buttons(self, widget):
        text_color = widget.text_color or self.t("Default")
        background_color = widget.background_color or self.t("Default")
        self.text_color_button.setText(self.t("Text Color: {color}", color=text_color))
        self.background_color_button.setText(self.t("Background Color: {color}", color=background_color))

    def move_selected(self, offset):
        if self.selected_navigation_index is not None:
            index = self.selected_navigation_index
            target = index + offset
            if 0 <= target < len(self.program.bottom_navigation):
                navigation = self.program.bottom_navigation
                navigation[index], navigation[target] = navigation[target], navigation[index]
                self.selected_navigation_index = target
                self.refresh_bottom_navigation()
                self.emit_source()
            return
        widget = self.selected_widget()
        if widget is None:
            return
        index = self.program.widgets.index(widget)
        target = index + offset
        if 0 <= target < len(self.program.widgets):
            self.program.widgets[index], self.program.widgets[target] = (
                self.program.widgets[target], self.program.widgets[index]
            )
            self.refresh_canvas()
            self.emit_source()

    def delete_selected(self):
        if self.selected_navigation_index is not None:
            del self.program.bottom_navigation[self.selected_navigation_index]
            self.selected_navigation_index = None
            self.name_edit.clear()
            self.text_edit.clear()
            self.refresh_bottom_navigation()
            self.emit_source()
            return
        widget = self.selected_widget()
        if widget is None:
            return
        self.program.widgets.remove(widget)
        self.program.events = [
            event for event in self.program.events if event.button != widget.name
        ]
        for event in self.program.events:
            event.actions = [
                action for action in event.actions if action[0] != widget.name
            ]
        self.selected_name = None
        self.refresh_canvas()
        self.emit_source()

    def refresh_canvas(self):
        self.page_placeholder.hide()
        while self.canvas_layout.count():
            item = self.canvas_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.item_widgets = {}
<<<<<<< HEAD
        self.canvas_title.setText(self.program.title)
        self.refresh_canvas_color()
=======
        self.phone_title.setText(self.program.title)
        self.refresh_phone_color()
>>>>>>> parent of aca10fd (v8)
        self.app_title_edit.setText(self.program.title)
        has_chat = any(widget.kind == "دردشة" for widget in self.program.widgets)
        # A chat widget takes over its whole page like a real messaging screen --
        # its page-mates stay defined (so nothing is deleted) but are hidden so
        # the chat fills the entire screen instead of sharing it.
        chat_pages = {widget.page for widget in self.program.widgets if widget.kind == "دردشة"}
        screen_background = self.program.background_color or "#FFFFFF"
        for widget in self.program.widgets:
            item = DesignerItem(widget, language=self.language, screen_background=screen_background)
            item.selected.connect(self.select_widget)
            item.activated.connect(self.run_preview_event)
            self.canvas_layout.addWidget(item, 1 if widget.kind == "دردشة" else 0)
            self.item_widgets[widget.name] = item
            if widget.kind != "دردشة" and widget.page in chat_pages:
                item.hide()
        if not has_chat:
            self.canvas_layout.addStretch(1)
        for widget in self.program.widgets:
            if widget.bind_to and widget.bind_to in self.item_widgets:
                source_control = self.item_widgets[widget.bind_to].control
                target_control = self.item_widgets[widget.name].control
                source_control.textChanged.connect(target_control.setText)
        self.refresh_bottom_navigation()
        if self.selected_name:
            self.select_widget(self.selected_name)
        elif self.selected_navigation_index is not None:
            self.select_navigation(self.selected_navigation_index)
        else:
            self.name_edit.clear()
            self.text_edit.clear()
            self.text_color_button.setText(self.t("Text Color"))
            self.background_color_button.setText(self.t("Background Color"))

<<<<<<< HEAD
    def refresh_canvas_color(self):
=======
    def refresh_phone_color(self):
>>>>>>> parent of aca10fd (v8)
        color = self.program.background_color or "#FAFAFA"
        is_dark = QColor(color).lightness() < 128
        foreground = "#F2F2F2" if is_dark else "#0F172A"
        surface = "#050505" if is_dark else "#FFFFFF"
        border = "#2F3336" if is_dark else "#CBD5E1"
<<<<<<< HEAD
        self.canvas_frame.setStyleSheet(
            f"QFrame#canvasFrame {{ background-color: {color}; }}"
        )
        self.canvas_title.setStyleSheet(
=======
        self.phone.setStyleSheet(
            f"QFrame#phoneFrame {{ background-color: {color}; }}"
        )
        self.phone_title.setStyleSheet(
>>>>>>> parent of aca10fd (v8)
            f"background-color: {surface}; color: {foreground}; "
            f"border-bottom: 1px solid {border}; padding: 10px; font-weight: 600;"
        )
        self.bottom_navigation.setStyleSheet(
            f"background-color: {surface}; border-top: 1px solid {border};"
        )
        self.screen_color_button.setText(self.t("Screen Background Color: {color}", color=color))

    def refresh_bottom_navigation(self):
        while self.bottom_navigation_layout.count():
            item = self.bottom_navigation_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.bottom_navigation.setVisible(bool(self.program.bottom_navigation))
        screen_color = QColor(self.program.background_color or "#FAFAFA")
        navigation_text = "#F2F2F2" if screen_color.lightness() < 128 else "#0F172A"
        for index, label in enumerate(self.program.bottom_navigation):
            button = QPushButton(label)
<<<<<<< HEAD
            button.setObjectName("canvasNavigationButton")
=======
            button.setObjectName("phoneNavigationButton")
>>>>>>> parent of aca10fd (v8)
            selected = index == self.selected_navigation_index and not self.preview_mode
            border_style = "1px solid #007ACC" if selected else "none"
            selected_background = "rgba(0,122,204,45)" if selected else "transparent"
            button.setStyleSheet(
<<<<<<< HEAD
                "QPushButton#canvasNavigationButton {"
                f"background: {selected_background}; color: {navigation_text}; "
                f"border: {border_style}; border-radius: 5px; "
                "font-size: 11px; font-weight: 600; padding: 6px 2px; }"
                "QPushButton#canvasNavigationButton:pressed { "
=======
                "QPushButton#phoneNavigationButton {"
                f"background: {selected_background}; color: {navigation_text}; "
                f"border: {border_style}; border-radius: 5px; "
                "font-size: 11px; font-weight: 600; padding: 6px 2px; }"
                "QPushButton#phoneNavigationButton:pressed { "
>>>>>>> parent of aca10fd (v8)
                "background-color: rgba(0,0,0,70); }"
            )
            button.clicked.connect(
                lambda _checked=False, page=label, item_index=index: (
                    self.show_preview_page(page)
                    if self.preview_mode else self.select_navigation(item_index)
                )
            )
            self.bottom_navigation_layout.addWidget(button)

    def emit_source(self):
        if not self.loading:
            self.sourceChanged.emit(self.to_source())

    def to_source(self):
        lines = [f"اسم التطبيق هو {self.program.title}", ""]
        if self.program.background_color:
            screen_colors = {"#000000": "اسود", "#FFFFFF": "ابيض"}
            color_value = screen_colors.get(
                self.program.background_color.upper(), self.program.background_color.upper()
            )
            lines.extend([f"لون الشاشة {color_value}", ""])
        if self.program.bottom_navigation:
            lines.append("في شريط السفلي ضع")
            lines.extend(f"    {label}" for label in self.program.bottom_navigation)
            lines.append("")
        generated_names = {}
        if any(widget.kind == "كلمة_مرور" for widget in self.program.widgets):
            lines.extend(["دالة كلمة المرور", ""])
        current_page = "الرئيسية"
        for widget in self.program.widgets:
            linked_event = None
            if widget.page != current_page:
                current_page = widget.page
                lines.extend([f"في صفحة {current_page}", ""])
            if widget.kind == "زر":
                generated_name = "زر_" + re.sub(
                    r"[^\w\u0600-\u06ff]+", "_", widget.text
                ).strip("_")
                generated_names[widget.name] = generated_name
                linked_event = next(
                    (event for event in self.program.events if event.button == widget.name),
                    None,
                )
                if linked_event:
                    function_name = linked_event.function_name
                    if not function_name:
                        page_action = next(
                            (value for target, value in linked_event.actions if target == "__page__"),
                            widget.text,
                        )
                        function_name = page_action.removeprefix("قوة ")
                    linked_event.function_name = function_name
                    previous_button = next(
                        (item for item in reversed(self.program.widgets[:self.program.widgets.index(widget)])
                         if item.kind == "زر"),
                        None,
                    )
                    if previous_button and (
                        widget.background_color == previous_button.background_color
                        and widget.text_color == previous_button.text_color
                    ):
                        lines.append(f"انشئ زر {widget.text}، دالة {function_name}")
                    else:
                        button_colors = {
                            "#000000": "اسود", "#FFFFFF": "ابيض",
                            "#1976D2": "ازرق", "#16A34A": "اخضر",
                            "#DC2626": "احمر", "#6B7280": "رمادي",
                        }
                        button_color = button_colors.get(
                            (widget.background_color or "#1976D2").upper(),
                            (widget.background_color or "#1976D2").upper(),
                        )
                        lines.append(
                            f"انشئ زر {widget.text}، {button_color}، دالة {function_name}"
                        )
                else:
                    lines.append(f"انشئ زر {widget.text}")
            elif widget.kind == "كلمة_مرور":
                generated_names[widget.name] = widget.name
                minimum = widget.min_length or 8
                lines.append(f'أنشئ حقلًا اسمه "{widget.text}"')
                lines.append("")
                lines.append("شروط كلمة المرور")
                lines.append(f"    طولها لا يقل عن {minimum}")
                if widget.require_numbers:
                    lines.append("    تحتوي على رقم")
                if widget.require_symbols:
                    lines.append("    تحتوي على رمز")
            elif widget.kind == "دردشة":
                generated_names[widget.name] = widget.name
                lines.append("انشئ صندوق دردشة")
            else:
                generated_names[widget.name] = widget.name
                if widget.kind == "نص" and widget.natural_syntax:
                    if widget.bind_to:
                        lines.append(f"اطبع {widget.bind_to}")
                    else:
                        lines.append(f'اطبع "{widget.text}"')
                elif widget.kind == "حقل" and widget.natural_syntax:
                    lines.append(f'{widget.name} = حقل "{widget.text}"')
                else:
                    numbered_text = re.fullmatch(r"نص_(\d+)", widget.name)
                    if widget.kind == "نص" and numbered_text:
                        lines.append(f"نص {numbered_text.group(1)} = {widget.text}")
                    else:
                        lines.append(f'{widget.name} = {widget.kind}("{widget.text}")')
            if widget.text_color and not (widget.kind == "زر" and linked_event):
                text_colors = {
                    "#000000": "اسود", "#0F1419": "اسود", "#0F172A": "اسود",
                    "#FFFFFF": "ابيض", "#F2F2F2": "ابيض", "#E7E9EA": "ابيض",
                }
                color_value = text_colors.get(
                    widget.text_color.upper(), widget.text_color.upper()
                )
                lines.append(f"لون النص {color_value}")
            if widget.background_color and not (widget.kind == "زر" and linked_event):
                background_colors = {"#000000": "اسود", "#FFFFFF": "ابيض"}
                color_value = background_colors.get(
                    widget.background_color.upper(), widget.background_color.upper()
                )
                lines.append(f"لون الخلفية {color_value}")
        for event in self.program.events:
            button_widget = next(
                (widget for widget in self.program.widgets if widget.name == event.button),
                None,
            )
            button_name = button_widget.text if button_widget else event.button.replace("_", " ")
            if event.function_name:
                event_line = f"دالة {event.function_name}:"
            else:
                last_button = next(
                    (widget for widget in reversed(self.program.widgets) if widget.kind == "زر"),
                    None,
                )
                event_line = "عند النقر" if last_button and last_button.name == event.button else f"عند النقر على زر {button_name}"
            lines.extend(["", event_line])
            for target, text in event.actions:
                if target == "__page__":
                    lines.append(f"    اذهب الى صفحة {text}")
                elif target == "__print__":
                    lines.append(f'    اطبع("{text}")')
                else:
                    lines.append(f'    غيّر_النص({generated_names.get(target, target)}، "{text}")')
        return "\n".join(lines).rstrip() + "\n"
