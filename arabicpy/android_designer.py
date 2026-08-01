"""Editable Qt mobile canvas for ArabicPy Android source files."""

import re

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from .android import AndroidEvent, AndroidProgram, AndroidWidget, parse_android


COLOR_THEMES = {
    "أزرق عصري": {
        "screen": "#F4F7FB", "text": "#172033", "surface": "#FFFFFF",
        "button": "#2563EB", "button_text": "#FFFFFF",
    },
    "داكن أنيق": {
        "screen": "#111827", "text": "#F3F4F6", "surface": "#1F2937",
        "button": "#8B5CF6", "button_text": "#FFFFFF",
    },
    "أخضر هادئ": {
        "screen": "#F0FDF4", "text": "#14532D", "surface": "#FFFFFF",
        "button": "#16A34A", "button_text": "#FFFFFF",
    },
    "غروب دافئ": {
        "screen": "#FFF7ED", "text": "#7C2D12", "surface": "#FFFBEB",
        "button": "#EA580C", "button_text": "#FFFFFF",
    },
}


class DesignerItem(QFrame):
    selected = Signal(str)
    activated = Signal(str)

    def __init__(self, widget_model, parent=None):
        super().__init__(parent)
        self.widget_model = widget_model
        self.preview_mode = False
        self.setObjectName("designerItem")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        if widget_model.kind == "نص":
            control = QLabel(widget_model.text)
            control.setAlignment(Qt.AlignCenter)
        elif widget_model.kind == "زر":
            control = QPushButton(widget_model.text)
        else:
            control = QLineEdit()
            control.setPlaceholderText(widget_model.text)

        self.control = control
        if isinstance(control, QPushButton):
            control.clicked.connect(
                lambda _checked=False: self.activated.emit(self.widget_model.name)
            )
        self.apply_colors()
        control.installEventFilter(self)
        layout.addWidget(control)

    def apply_colors(self):
        text_color = self.widget_model.text_color or (
            "#FFFFFF" if self.widget_model.kind == "زر" else "#202124"
        )
        background_color = self.widget_model.background_color or (
            "#1976D2" if self.widget_model.kind == "زر" else "#FFFFFF"
        )
        self.control.setStyleSheet(
            f"color: {text_color}; background-color: {background_color};"
        )

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


class AndroidDesigner(QWidget):
    sourceChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.program = AndroidProgram("تطبيقي العربي", [], [])
        self.selected_name = None
        self.loading = False
        self.item_widgets = {}
        self.preview_mode = False
        self.setup_ui()

    def setup_ui(self):
        self.setObjectName("androidDesigner")
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(1)

        palette = QFrame(objectName="designerPanel")
        self.palette_panel = palette
        palette.setFixedWidth(150)
        palette_layout = QVBoxLayout(palette)
        palette_layout.addWidget(QLabel("العناصر", objectName="designerTitle"))
        for kind, label in (("نص", "+ نص"), ("زر", "+ زر"), ("حقل", "+ حقل إدخال")):
            button = QPushButton(label, objectName="designerTool")
            button.clicked.connect(lambda _checked=False, value=kind: self.add_widget(value))
            palette_layout.addWidget(button)
        palette_layout.addStretch()
        root.addWidget(palette)

        canvas_scroll = QScrollArea()
        canvas_scroll.setWidgetResizable(True)
        canvas_scroll.setObjectName("designerCanvas")
        canvas_host = QWidget()
        canvas_host_layout = QVBoxLayout(canvas_host)
        canvas_host_layout.setAlignment(Qt.AlignCenter)
        self.phone = QFrame(objectName="phoneFrame")
        self.phone.setFixedSize(360, 620)
        phone_layout = QVBoxLayout(self.phone)
        phone_layout.setContentsMargins(12, 12, 12, 12)
        self.phone_title = QLabel(self.program.title, objectName="phoneTitle")
        self.phone_title.setAlignment(Qt.AlignCenter)
        phone_layout.addWidget(self.phone_title)
        self.canvas_layout = QVBoxLayout()
        self.canvas_layout.setAlignment(Qt.AlignTop)
        phone_layout.addLayout(self.canvas_layout)
        phone_layout.addStretch()
        canvas_host_layout.addWidget(self.phone)
        canvas_scroll.setWidget(canvas_host)
        root.addWidget(canvas_scroll, 1)

        properties = QFrame(objectName="designerPanel")
        self.properties_panel = properties
        properties.setFixedWidth(210)
        properties_layout = QVBoxLayout(properties)
        properties_layout.addWidget(QLabel("الخصائص", objectName="designerTitle"))
        properties_layout.addWidget(QLabel("اسم التطبيق"))
        self.app_title_edit = QLineEdit()
        self.app_title_edit.editingFinished.connect(self.apply_app_title)
        properties_layout.addWidget(self.app_title_edit)
        self.screen_color_button = QPushButton("لون خلفية الشاشة")
        self.screen_color_button.clicked.connect(self.choose_screen_color)
        properties_layout.addWidget(self.screen_color_button)
        properties_layout.addWidget(QLabel("قوالب الألوان", objectName="designerTitle"))
        for theme_name in COLOR_THEMES:
            theme_button = QPushButton(theme_name, objectName="designerTool")
            theme_button.clicked.connect(
                lambda _checked=False, name=theme_name: self.apply_color_theme(name)
            )
            properties_layout.addWidget(theme_button)
        properties_layout.addWidget(QLabel("اسم العنصر"))
        self.name_edit = QLineEdit()
        properties_layout.addWidget(self.name_edit)
        properties_layout.addWidget(QLabel("النص"))
        self.text_edit = QLineEdit()
        properties_layout.addWidget(self.text_edit)
        self.text_color_button = QPushButton("لون النص")
        self.text_color_button.clicked.connect(lambda: self.choose_color("text"))
        properties_layout.addWidget(self.text_color_button)
        self.background_color_button = QPushButton("لون الخلفية")
        self.background_color_button.clicked.connect(lambda: self.choose_color("background"))
        properties_layout.addWidget(self.background_color_button)
        reset_colors_button = QPushButton("إعادة الألوان الافتراضية")
        reset_colors_button.clicked.connect(self.reset_colors)
        properties_layout.addWidget(reset_colors_button)
        apply_button = QPushButton("تطبيق التغييرات")
        apply_button.clicked.connect(self.apply_properties)
        properties_layout.addWidget(apply_button)
        up_button = QPushButton("تحريك لأعلى")
        up_button.clicked.connect(lambda: self.move_selected(-1))
        properties_layout.addWidget(up_button)
        down_button = QPushButton("تحريك لأسفل")
        down_button.clicked.connect(lambda: self.move_selected(1))
        properties_layout.addWidget(down_button)
        delete_button = QPushButton("حذف العنصر", objectName="designerDelete")
        delete_button.clicked.connect(self.delete_selected)
        properties_layout.addWidget(delete_button)
        properties_layout.addStretch()
        root.addWidget(properties)
        self.refresh_canvas()

    def load_source(self, source):
        try:
            program = parse_android(source)
        except Exception:
            return False
        self.loading = True
        self.program = program
        self.selected_name = None
        self.refresh_canvas()
        self.loading = False
        return True

    def start_preview(self):
        """Run supported click events directly inside the phone canvas."""
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
                item = self.item_widgets.get(target)
                if item is not None:
                    item.control.setText(text)

    def add_widget(self, kind):
        prefixes = {"نص": "نص", "زر": "زر", "حقل": "حقل"}
        defaults = {"نص": "نص جديد", "زر": "زر جديد", "حقل": "اكتب هنا"}
        used = {widget.name for widget in self.program.widgets}
        number = 1
        while f"{prefixes[kind]}_{number}" in used:
            number += 1
        widget = AndroidWidget(f"{prefixes[kind]}_{number}", kind, defaults[kind])
        self.program.widgets.append(widget)
        self.selected_name = widget.name
        self.refresh_canvas()
        self.emit_source()

    def select_widget(self, name):
        self.selected_name = name
        for item_name, item in self.item_widgets.items():
            item.set_selected(item_name == name)
        widget = self.selected_widget()
        if widget:
            self.name_edit.setText(widget.name)
            self.text_edit.setText(widget.text)
            self.update_color_buttons(widget)

    def selected_widget(self):
        return next(
            (widget for widget in self.program.widgets if widget.name == self.selected_name),
            None,
        )

    def apply_app_title(self):
        title = self.app_title_edit.text().strip()
        if title and '"' not in title:
            self.program.title = title
            self.phone_title.setText(title)
            self.emit_source()

    def choose_screen_color(self):
        current = self.program.background_color or "#FAFAFA"
        color = QColorDialog.getColor(QColor(current), self, "اختر لون خلفية الشاشة")
        if not color.isValid():
            return
        self.program.background_color = color.name().upper()
        self.refresh_phone_color()
        self.emit_source()

    def apply_color_theme(self, theme_name):
        """Apply a coordinated palette to the screen and every existing widget."""
        theme = COLOR_THEMES[theme_name]
        self.program.background_color = theme["screen"]
        for widget in self.program.widgets:
            if widget.kind == "زر":
                widget.text_color = theme["button_text"]
                widget.background_color = theme["button"]
            else:
                widget.text_color = theme["text"]
                widget.background_color = theme["surface"]
        self.refresh_canvas()
        self.emit_source()

    def apply_properties(self):
        widget = self.selected_widget()
        if widget is None:
            return
        name = self.name_edit.text().strip()
        text = self.text_edit.text().strip()
        if not re.fullmatch(r"[\w\u0600-\u06ff]+", name) or name[0].isdigit():
            QMessageBox.warning(self, "اسم غير صالح", "استخدم حروفاً وأرقاماً وشرطة سفلية فقط.")
            return
        if any(item.name == name and item is not widget for item in self.program.widgets):
            QMessageBox.warning(self, "اسم مكرر", "يوجد عنصر آخر بهذا الاسم.")
            return
        if '"' in text:
            QMessageBox.warning(self, "نص غير صالح", "علامة الاقتباس المزدوجة غير مدعومة داخل النص حالياً.")
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
        color = QColorDialog.getColor(QColor(current), self, "اختر اللون")
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
        text_color = widget.text_color or "افتراضي"
        background_color = widget.background_color or "افتراضي"
        self.text_color_button.setText(f"لون النص: {text_color}")
        self.background_color_button.setText(f"لون الخلفية: {background_color}")

    def move_selected(self, offset):
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
        while self.canvas_layout.count():
            item = self.canvas_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.item_widgets = {}
        self.phone_title.setText(self.program.title)
        self.refresh_phone_color()
        self.app_title_edit.setText(self.program.title)
        for widget in self.program.widgets:
            item = DesignerItem(widget)
            item.selected.connect(self.select_widget)
            item.activated.connect(self.run_preview_event)
            self.canvas_layout.addWidget(item)
            self.item_widgets[widget.name] = item
        if self.selected_name:
            self.select_widget(self.selected_name)
        else:
            self.name_edit.clear()
            self.text_edit.clear()
            self.text_color_button.setText("لون النص")
            self.background_color_button.setText("لون الخلفية")

    def refresh_phone_color(self):
        color = self.program.background_color or "#FAFAFA"
        self.phone.setStyleSheet(f"background-color: {color};")
        self.screen_color_button.setText(f"لون خلفية الشاشة: {color}")

    def emit_source(self):
        if not self.loading:
            self.sourceChanged.emit(self.to_source())

    def to_source(self):
        lines = [f'تطبيق "{self.program.title}"', ""]
        if self.program.background_color:
            lines.extend([f'لون_الشاشة("{self.program.background_color}")', ""])
        for widget in self.program.widgets:
            lines.append(f'{widget.name} = {widget.kind}("{widget.text}")')
            if widget.text_color:
                lines.append(f'لون_النص({widget.name}، "{widget.text_color}")')
            if widget.background_color:
                lines.append(f'لون_الخلفية({widget.name}، "{widget.background_color}")')
        for event in self.program.events:
            lines.extend(["", f"عند_النقر({event.button}):"])
            for target, text in event.actions:
                lines.append(f'    غيّر_النص({target}، "{text}")')
        return "\n".join(lines).rstrip() + "\n"
