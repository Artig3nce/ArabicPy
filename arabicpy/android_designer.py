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
    "اجتماعي داكن": {
        "screen": "#000000", "text": "#F2F2F2", "surface": "#0A0A0A",
        "button": "#F2F2F2", "button_text": "#0F1419", "navigation": True,
    },
    "نظيف ومضيء": {
        "screen": "#FFFFFF", "text": "#0F172A", "surface": "#F8FAFC",
        "button": "#0F172A", "button_text": "#FFFFFF", "navigation": True,
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
            if widget_model.kind == "كلمة_مرور":
                control.setEchoMode(QLineEdit.EchoMode.Password)

        self.control = control
        if isinstance(control, QPushButton):
            control.clicked.connect(
                lambda _checked=False: self.activated.emit(self.widget_model.name)
            )
        self.apply_colors()
        control.installEventFilter(self)
        layout.addWidget(control)
        if widget_model.kind == "كلمة_مرور":
            self.password_status = QLabel("أدخل كلمة المرور")
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
            self.password_status.setText("كلمة المرور قوية")
            self.password_status.setStyleSheet("color: #22C55E;")
        else:
            self.password_status.setText(f"استخدم {minimum} خانات مع أرقام ورموز")
            self.password_status.setStyleSheet("color: #EF4444;")

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
        self.last_error = None
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
        self.bottom_navigation = QFrame(objectName="phoneNavigation")
        self.bottom_navigation_layout = QHBoxLayout(self.bottom_navigation)
        self.bottom_navigation_layout.setContentsMargins(4, 4, 4, 4)
        self.bottom_navigation_layout.setSpacing(2)
        phone_layout.addWidget(self.bottom_navigation)
        self.page_placeholder = QLabel()
        self.page_placeholder.setAlignment(Qt.AlignCenter)
        self.page_placeholder.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.page_placeholder.hide()
        phone_layout.insertWidget(2, self.page_placeholder)
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
        properties_layout.addWidget(QLabel("قوالب التطبيق", objectName="designerTitle"))
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
        except Exception as error:
            self.last_error = error
            return False
        self.last_error = None
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
        self.phone_title.setText(page_name)
        page_items = [
            item for item in self.item_widgets.values()
            if item.widget_model.page == page_name
        ]
        for item in self.item_widgets.values():
            item.setVisible(item in page_items)
        self.page_placeholder.setText(f"صفحة {page_name}")
        self.page_placeholder.setVisible(not page_items)

    def add_widget(self, kind):
        prefixes = {"نص": "نص", "زر": "زر", "حقل": "حقل"}
        defaults = {"نص": "نص جديد", "زر": "زر جديد", "حقل": "اكتب هنا"}
        used = {widget.name for widget in self.program.widgets}
        number = 1
        while f"{prefixes[kind]}_{number}" in used:
            number += 1
        widget = AndroidWidget(f"{prefixes[kind]}_{number}", kind, defaults[kind])
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
        if theme.get("navigation") and not self.program.bottom_navigation:
            self.program.bottom_navigation = ["الرئيسية", "البحث", "التنبيهات", "الرسائل"]
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
        self.page_placeholder.hide()
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
        self.refresh_bottom_navigation()
        if self.selected_name:
            self.select_widget(self.selected_name)
        else:
            self.name_edit.clear()
            self.text_edit.clear()
            self.text_color_button.setText("لون النص")
            self.background_color_button.setText("لون الخلفية")

    def refresh_phone_color(self):
        color = self.program.background_color or "#FAFAFA"
        is_dark = QColor(color).lightness() < 128
        foreground = "#F2F2F2" if is_dark else "#0F172A"
        surface = "#050505" if is_dark else "#FFFFFF"
        border = "#2F3336" if is_dark else "#CBD5E1"
        self.phone.setStyleSheet(
            f"QFrame#phoneFrame {{ background-color: {color}; }}"
        )
        self.phone_title.setStyleSheet(
            f"background-color: {surface}; color: {foreground}; "
            f"border-bottom: 1px solid {border}; padding: 10px; font-weight: 600;"
        )
        self.bottom_navigation.setStyleSheet(
            f"background-color: {surface}; border-top: 1px solid {border};"
        )
        self.screen_color_button.setText(f"لون خلفية الشاشة: {color}")

    def refresh_bottom_navigation(self):
        while self.bottom_navigation_layout.count():
            item = self.bottom_navigation_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.bottom_navigation.setVisible(bool(self.program.bottom_navigation))
        screen_color = QColor(self.program.background_color or "#FAFAFA")
        navigation_text = "#F2F2F2" if screen_color.lightness() < 128 else "#0F172A"
        for label in self.program.bottom_navigation:
            button = QPushButton(label)
            button.setObjectName("phoneNavigationButton")
            button.setStyleSheet(
                f"background: transparent; color: {navigation_text}; border: none;"
            )
            button.clicked.connect(
                lambda _checked=False, page=label: self.show_preview_page(page)
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
            else:
                generated_names[widget.name] = widget.name
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
