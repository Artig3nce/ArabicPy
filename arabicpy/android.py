"""Small الباء-to-Kivy translator and Android project exporter."""

import os
import re
from dataclasses import dataclass, field

from .errors import ArabicPyError


WIDGET_PATTERN = re.compile(r'^(?P<name>[\w\u0600-\u06ff]+)\s*=\s*(?P<kind>نص|زر|حقل)\("(?P<text>.*)"\)\s*$')
NATURAL_BUTTON_PATTERN = re.compile(r'^انشئ\s+زر\s+اسمه\s+(?P<text>.+?)\s*$')
EVENT_PATTERN = re.compile(r'^عند_النقر\((?P<name>[\w\u0600-\u06ff]+)\):\s*$')
NATURAL_EVENT_PATTERN = re.compile(r'^عند\s+النقر\s+على\s+(?P<name>[\w\u0600-\u06ff ]+?)\s*:?\s*$')
SET_TEXT_PATTERN = re.compile(r'^غيّر_النص\((?P<name>[\w\u0600-\u06ff]+)\s*[،,]\s*"(?P<text>.*)"\)\s*$')
GO_PAGE_PATTERN = re.compile(r'^اذهب\s+(?:الى|إلى)\s+(?:ال)?صفحة\s+(?P<page>.+?)\s*$')
COLOR_PATTERN = re.compile(
    r'^(?P<property>لون_النص|لون_الخلفية)\('
    r'(?P<name>[\w\u0600-\u06ff]+)\s*[،,]\s*"(?P<color>#[0-9a-fA-F]{6})"\)\s*$'
)
NATURAL_TEXT_COLOR_PATTERN = re.compile(
    r'^لون\s+النص\s+(?:هو\s+)?(?P<color>أسود|اسود|أبيض|ابيض|#[0-9a-fA-F]{6})\s*$'
)
NATURAL_BACKGROUND_COLOR_PATTERN = re.compile(
    r'^لون\s+الخلفية\s+هو\s+(?P<color>أسود|اسود|أبيض|ابيض|#[0-9a-fA-F]{6})\s*$'
)
APP_PATTERN = re.compile(r'^تطبيق\s+"(?P<title>.*)"\s*$')
NATURAL_APP_PATTERN = re.compile(r'^اسم\s+التطبيق\s+هو\s+(?P<title>.+?)\s*$')
SCREEN_COLOR_PATTERN = re.compile(
    r'^لون\s+الشاشة\s+(?P<color>أسود|اسود|أبيض|ابيض|#[0-9a-fA-F]{6})\s*$'
)
LEGACY_SCREEN_COLOR_PATTERN = re.compile(r'^لون_الشاشة\("(?P<color>#[0-9a-fA-F]{6})"\)\s*$')
BOTTOM_NAV_PATTERN = re.compile(r'^شريط_سفلي\("(?P<items>.*)"\)\s*$')
NATURAL_BOTTOM_NAV_PATTERN = re.compile(r'^ضع\s+في\s+شريط\s+السفلي\s+(?P<items>.+)\s*$')
BOTTOM_NAV_BLOCK_PATTERN = re.compile(r'^في\s+شريط\s+السفلي\s+ضع\s*:?\s*$')
PAGE_BLOCK_PATTERN = re.compile(
    r'^في\s+صفحة\s+(?:"(?P<quoted_page>[^"]+)"|(?P<page>.+?)(?:\s+ضع)?)\s*:?\s*$'
)
PASSWORD_FUNCTION_PATTERN = re.compile(r'^دالة\s+كلمة\s+المرور\s*$')
NATURAL_PASSWORD_FIELD_PATTERN = re.compile(
    r'^(?:انشئ|أنشئ)\s+حقل(?:ا|ًا|اً)?\s+اسمه\s+"(?P<name>[^"]+)"\s*$'
)
PASSWORD_RULES_HEADER_PATTERN = re.compile(r'^شروط\s+كلمة\s+المرور\s*$')
PASSWORD_SUMMARY_PATTERN = re.compile(
    r'^اكبر\s+او\s+تساوي\s+(?P<length>\d+)\s+خانات\s+ويجب\s+ان\s+تحتوي\s+على\s+ارقام\s+و\s+رموز\s*$'
)
PASSWORD_FIELD_PATTERN = re.compile(
    r'^حقل\s+كلمة\s+المرور\s+يجب\s+ان\s+تكون\s+اكبر\s+او\s+تساوي\s+'
    r'(?P<length>\d+)\s+خانات\s+ويجب\s+ان\s+تحتوي\s+على\s+ارقام\s+و\s+رموز\s*$'
)


@dataclass
class AndroidWidget:
    name: str
    kind: str
    text: str
    text_color: str | None = None
    background_color: str | None = None
    page: str = "الرئيسية"
    min_length: int | None = None
    require_numbers: bool = False
    require_symbols: bool = False


@dataclass
class AndroidEvent:
    button: str
    actions: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class AndroidProgram:
    title: str
    widgets: list[AndroidWidget]
    events: list[AndroidEvent]
    background_color: str | None = None
    bottom_navigation: list[str] = field(default_factory=list)


def is_android_source(source):
    return any(
        APP_PATTERN.match(line.strip()) or NATURAL_APP_PATTERN.match(line.strip())
        for line in source.splitlines()
    )


def parse_android(source):
    title = None
    widgets = []
    events = []
    background_color = None
    bottom_navigation = []
    widget_names = set()
    last_widget = None
    last_button = None
    current_page = "الرئيسية"
    lines = source.splitlines()
    index = 0

    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()
        line_number = index + 1
        if not stripped or stripped.startswith("#"):
            index += 1
            continue

        bottom_nav_block_match = BOTTOM_NAV_BLOCK_PATTERN.match(stripped)
        if bottom_nav_block_match:
            index += 1
            bottom_navigation = []
            while index < len(lines):
                candidate = lines[index]
                if not candidate.strip():
                    index += 1
                    continue
                if not candidate[:1].isspace():
                    break
                bottom_navigation.append(candidate.strip())
                index += 1
            if not bottom_navigation:
                raise ArabicPyError("أضف صفحات تحت: في شريط السفلي ضع:", line_number, 1)
            continue

        page_block_match = PAGE_BLOCK_PATTERN.match(stripped)
        if page_block_match:
            current_page = (
                page_block_match.group("quoted_page")
                or page_block_match.group("page")
            ).strip()
            index += 1
            continue

        if PASSWORD_FUNCTION_PATTERN.match(stripped):
            index += 1
            continue

        app_match = NATURAL_APP_PATTERN.match(stripped) or APP_PATTERN.match(stripped)
        if app_match:
            if title is not None:
                raise ArabicPyError("يمكن تعريف تطبيق واحد فقط", line_number, 1)
            title = app_match.group("title")
            index += 1
            continue

        screen_color_match = (
            SCREEN_COLOR_PATTERN.match(stripped)
            or LEGACY_SCREEN_COLOR_PATTERN.match(stripped)
        )
        if screen_color_match:
            color_value = screen_color_match.group("color")
            named_colors = {
                "أسود": "#000000", "اسود": "#000000",
                "أبيض": "#FFFFFF", "ابيض": "#FFFFFF",
            }
            background_color = named_colors.get(color_value, color_value.upper())
            index += 1
            continue

        natural_bottom_nav_match = NATURAL_BOTTOM_NAV_PATTERN.match(stripped)
        bottom_nav_match = natural_bottom_nav_match or BOTTOM_NAV_PATTERN.match(stripped)
        if bottom_nav_match:
            separator = r"\s+و\s+" if natural_bottom_nav_match else r"\s*\|\s*"
            bottom_navigation = [item.strip() for item in re.split(
                separator, bottom_nav_match.group("items")
            ) if item.strip()]
            bottom_navigation = [
                re.sub(r"^[⌂⌕♢✉]\s*", "", item)
                for item in bottom_navigation
            ]
            if not bottom_navigation:
                raise ArabicPyError("أضف زرًا واحدًا على الأقل إلى الشريط السفلي", line_number, 1)
            index += 1
            continue

        natural_button_match = NATURAL_BUTTON_PATTERN.match(stripped)
        short_button_match = re.match(r'^انشئ\s+زر\s+(?!اسمه\s+)(?P<text>.+?)\s*:?\s*$', stripped)
        natural_button_match = natural_button_match or short_button_match
        widget_match = WIDGET_PATTERN.match(stripped)
        if natural_button_match:
            text = natural_button_match.group("text").rstrip(":").strip()
            name = "زر_" + re.sub(r"[^\w\u0600-\u06ff]+", "_", text).strip("_")
            if name in widget_names:
                raise ArabicPyError(f"العنصر معرّف مسبقاً: {name}", line_number, 1)
            widget_names.add(name)
            last_widget = AndroidWidget(name, "زر", text, page=current_page)
            last_button = last_widget
            widgets.append(last_widget)
            index += 1
            continue
        if widget_match:
            name = widget_match.group("name")
            if name in widget_names:
                raise ArabicPyError(f"العنصر معرّف مسبقاً: {name}", line_number, 1)
            widget_names.add(name)
            last_widget = AndroidWidget(
                name, widget_match.group("kind"), widget_match.group("text"),
                page=current_page,
            )
            widgets.append(last_widget)
            if last_widget.kind == "زر":
                last_button = last_widget
            index += 1
            continue

        password_match = PASSWORD_FIELD_PATTERN.match(stripped)
        if password_match:
            name = "حقل_كلمة_المرور"
            if name in widget_names:
                raise ArabicPyError(f"العنصر معرّف مسبقاً: {name}", line_number, 1)
            widget_names.add(name)
            last_widget = AndroidWidget(
                name, "كلمة_مرور", "كلمة المرور", page=current_page,
                min_length=int(password_match.group("length")),
                require_numbers=True, require_symbols=True,
            )
            widgets.append(last_widget)
            index += 1
            continue

        natural_password_field = NATURAL_PASSWORD_FIELD_PATTERN.match(stripped)
        if natural_password_field:
            field_label = natural_password_field.group("name")
            name = "حقل_" + re.sub(r"[^\w\u0600-\u06ff]+", "_", field_label).strip("_")
            if name in widget_names:
                raise ArabicPyError(f"العنصر معرّف مسبقاً: {name}", line_number, 1)
            widget_names.add(name)
            last_widget = AndroidWidget(
                name, "كلمة_مرور", field_label, page=current_page,
                min_length=8, require_numbers=True, require_symbols=True,
            )
            widgets.append(last_widget)
            index += 1
            continue

        rules_header = PASSWORD_RULES_HEADER_PATTERN.match(stripped)
        if rules_header:
            password_widget = next(
                (widget for widget in reversed(widgets) if widget.kind == "كلمة_مرور"),
                None,
            )
            if password_widget is None:
                raise ArabicPyError("أنشئ حقل كلمة المرور قبل كتابة شروطها", line_number, 1)
            index += 1
            while index < len(lines):
                candidate = lines[index]
                if not candidate.strip():
                    index += 1
                    continue
                if not candidate[:1].isspace():
                    break
                rule = candidate.strip()
                length_match = re.fullmatch(r"طولها\s+لا\s+يقل\s+عن\s+(\d+)", rule)
                if length_match:
                    password_widget.min_length = int(length_match.group(1))
                elif rule == "تحتوي على رقم":
                    password_widget.require_numbers = True
                elif rule == "تحتوي على رمز":
                    password_widget.require_symbols = True
                else:
                    raise ArabicPyError(f"شرط كلمة مرور غير معروف: {rule}", index + 1, 1)
                index += 1
            continue

        summary_match = PASSWORD_SUMMARY_PATTERN.match(stripped)
        if summary_match:
            # A readable summary is allowed after the click action; the detailed
            # rules below the password field remain the source of truth.
            index += 1
            continue

        natural_background_match = NATURAL_BACKGROUND_COLOR_PATTERN.match(stripped)
        if natural_background_match:
            if last_widget is None:
                raise ArabicPyError("اكتب لون الخلفية بعد العنصر الذي تريد تلوينه", line_number, 1)
            color_value = natural_background_match.group("color")
            named_colors = {
                "أسود": "#000000", "اسود": "#000000",
                "أبيض": "#FFFFFF", "ابيض": "#FFFFFF",
            }
            last_widget.background_color = named_colors.get(color_value, color_value.upper())
            index += 1
            continue

        natural_text_color_match = NATURAL_TEXT_COLOR_PATTERN.match(stripped)
        if natural_text_color_match:
            if last_widget is None:
                raise ArabicPyError("اكتب لون النص بعد العنصر الذي تريد تلوينه", line_number, 1)
            color_value = natural_text_color_match.group("color")
            named_colors = {
                "أسود": "#000000", "اسود": "#000000",
                "أبيض": "#FFFFFF", "ابيض": "#FFFFFF",
            }
            last_widget.text_color = named_colors.get(color_value, color_value.upper())
            index += 1
            continue

        color_match = COLOR_PATTERN.match(stripped)
        if color_match:
            name = color_match.group("name")
            widget = next((item for item in widgets if item.name == name), None)
            if widget is None:
                raise ArabicPyError(f"عنصر غير معروف: {name}", line_number, 1)
            if color_match.group("property") == "لون_النص":
                widget.text_color = color_match.group("color").upper()
            else:
                widget.background_color = color_match.group("color").upper()
            index += 1
            continue

        implicit_event = re.fullmatch(r"عند\s+النقر\s*:?", stripped)
        natural_event_match = NATURAL_EVENT_PATTERN.match(stripped)
        event_match = natural_event_match or EVENT_PATTERN.match(stripped)
        if event_match or implicit_event:
            if implicit_event:
                if last_button is None:
                    raise ArabicPyError("اكتب عند النقر بعد الزر المطلوب", line_number, 1)
                button = last_button.name
            else:
                button = event_match.group("name")
            if natural_event_match:
                button = re.sub(r"\s+", "_", button.strip())
                if button not in widget_names and button.startswith("زر_"):
                    visible_text = button.removeprefix("زر_").replace("_", " ")
                    visible_button = next(
                        (widget for widget in widgets
                         if widget.kind == "زر" and widget.text == visible_text),
                        None,
                    )
                    if visible_button is not None:
                        button = visible_button.name
            if button not in widget_names:
                raise ArabicPyError(f"زر غير معروف: {button}", line_number, 1)
            event = AndroidEvent(button)
            index += 1
            while index < len(lines) and (not lines[index].strip() or lines[index][:1].isspace()):
                action_line = lines[index].strip()
                if not action_line:
                    index += 1
                    continue
                action_match = SET_TEXT_PATTERN.match(action_line)
                page_match = GO_PAGE_PATTERN.match(action_line)
                if page_match:
                    event.actions.append(("__page__", page_match.group("page")))
                    index += 1
                    continue
                if not action_match:
                    raise ArabicPyError("تعليمة حدث غير مدعومة", index + 1, 1)
                target = action_match.group("name")
                if target not in widget_names:
                    raise ArabicPyError(f"عنصر غير معروف: {target}", index + 1, 1)
                event.actions.append((target, action_match.group("text")))
                index += 1
            if not event.actions:
                raise ArabicPyError("حدث النقر يحتاج إلى تعليمة واحدة على الأقل", line_number, 1)
            events.append(event)
            continue

        raise ArabicPyError(f"تعليمة Android غير معروفة: {stripped}", line_number, 1)

    if title is None:
        raise ArabicPyError("ابدأ البرنامج بـ: اسم التطبيق هو الباء", 1, 1)
    if not widgets:
        raise ArabicPyError("أضف عنصراً واحداً على الأقل إلى التطبيق", 1, 1)
    return AndroidProgram(title, widgets, events, background_color, bottom_navigation)


def generate_kivy(source):
    program = parse_android(source)
    has_page_navigation = any(
        target == "__page__"
        for event in program.events
        for target, _value in event.actions
    )
    has_pages = has_page_navigation or bool(program.bottom_navigation)
    widget_classes = {"نص": "Label", "زر": "Button", "حقل": "TextInput", "كلمة_مرور": "TextInput"}
    imports = sorted({widget_classes[widget.kind] for widget in program.widgets})
    if program.bottom_navigation and "Button" not in imports:
        imports.append("Button")
    if has_pages and "Label" not in imports:
        imports.append("Label")
    lines = [
        "from kivy.app import App",
        "from kivy.uix.boxlayout import BoxLayout",
    ]
    if program.background_color:
        lines.append("from kivy.core.window import Window")
    for widget_class in imports:
        lines.append(f"from kivy.uix.{widget_class.lower()} import {widget_class}")

    colored_labels = any(
        widget.kind == "نص" and widget.background_color
        for widget in program.widgets
    )
    if colored_labels:
        lines.extend([
            "from kivy.graphics import Color, Rectangle",
            "from kivy.properties import ListProperty",
            "",
            "",
            "class ColoredLabel(Label):",
            "    background_color = ListProperty([0, 0, 0, 0])",
            "",
            "    def __init__(self, **kwargs):",
            "        super().__init__(**kwargs)",
            "        with self.canvas.before:",
            "            self._background = Color(rgba=self.background_color)",
            "            self._background_rect = Rectangle(pos=self.pos, size=self.size)",
            "        self.bind(pos=self._sync_background, size=self._sync_background)",
            "        self.bind(background_color=self._sync_background_color)",
            "",
            "    def _sync_background(self, *_):",
            "        self._background_rect.pos = self.pos",
            "        self._background_rect.size = self.size",
            "",
            "    def _sync_background_color(self, *_):",
            "        self._background.rgba = self.background_color",
        ])

    lines.extend(["", "", "class AlBaaAndroidApp(App):", "    def build(self):"])
    lines.append(f"        self.title = {program.title!r}")
    if program.background_color:
        lines.append(f"        Window.clearcolor = {hex_to_rgba(program.background_color)!r}")
    lines.append("        root = BoxLayout(orientation='vertical', padding=24, spacing=12)")
    if has_pages:
        lines.append(
            f"        self._page_title = Label(text={program.title!r}, size_hint_y=None, height=48)"
        )
        lines.append("        root.add_widget(self._page_title)")
        lines.append("        self._content = BoxLayout(orientation='vertical', spacing=12)")
        lines.append("        self._page_widgets = {}")
        lines.append("        root.add_widget(self._content)")

    for widget in program.widgets:
        widget_class = widget_classes[widget.kind]
        if widget.kind == "نص" and widget.background_color:
            widget_class = "ColoredLabel"
        option_parts = [f"text={widget.text!r}"]
        if widget.text_color:
            color_property = "foreground_color" if widget.kind in ("حقل", "كلمة_مرور") else "color"
            option_parts.append(f"{color_property}={hex_to_rgba(widget.text_color)!r}")
        if widget.background_color:
            option_parts.append(
                f"background_color={hex_to_rgba(widget.background_color)!r}"
            )
        if widget.kind in ("حقل", "كلمة_مرور"):
            option_parts.append("multiline=False")
        if widget.kind == "كلمة_مرور":
            option_parts.append("password=True")
        options = ", ".join(option_parts)
        lines.append(f"        self.{widget.name} = {widget_class}({options})")
        if has_pages:
            lines.append(f"        self._page_widgets.setdefault({widget.page!r}, []).append(self.{widget.name})")
            if widget.page == "الرئيسية":
                lines.append(f"        self._content.add_widget(self.{widget.name})")
        else:
            lines.append(f"        root.add_widget(self.{widget.name})")
        if widget.kind == "كلمة_مرور":
            lines.append(f"        self.{widget.name}_status = Label(text='أدخل كلمة المرور', size_hint_y=None, height=36)")
            if has_pages:
                lines.append(f"        self._page_widgets.setdefault({widget.page!r}, []).append(self.{widget.name}_status)")
                if widget.page == "الرئيسية":
                    lines.append(f"        self._content.add_widget(self.{widget.name}_status)")
            else:
                lines.append(f"        root.add_widget(self.{widget.name}_status)")
            lines.append(
                f"        self.{widget.name}.bind(text=lambda _field, value: self._validate_password(value, self.{widget.name}_status, {widget.min_length or 8}))"
            )

    for event_index, event in enumerate(program.events, 1):
        lines.append(
            f"        self.{event.button}.bind(on_press=self._event_{event_index})"
        )
    if program.bottom_navigation:
        dark_screen = is_dark_hex(program.background_color or "#FAFAFA")
        navigation_background = [0.02, 0.02, 0.02, 1] if dark_screen else [1, 1, 1, 1]
        navigation_text = [1, 1, 1, 1] if dark_screen else [0.06, 0.09, 0.16, 1]
        lines.append("        bottom_navigation = BoxLayout(size_hint_y=None, height=56, spacing=4)")
        for item in program.bottom_navigation:
            lines.append(f"        navigation_button = Button(text={item!r}, background_normal='', background_color={navigation_background!r}, color={navigation_text!r})")
            lines.append(f"        navigation_button.bind(on_press=lambda _button, page={item!r}: self._go_to_page(page))")
            lines.append("        bottom_navigation.add_widget(navigation_button)")
        lines.append("        root.add_widget(bottom_navigation)")
    lines.extend(["        return root", ""])

    for event_index, event in enumerate(program.events, 1):
        lines.append(f"    def _event_{event_index}(self, _button):")
        for target, text in event.actions:
            if target == "__page__":
                lines.append(f"        self._go_to_page({text!r})")
            else:
                lines.append(f"        self.{target}.text = {text!r}")
        lines.append("")

    if has_pages:
        lines.extend([
            "    def _go_to_page(self, page_name):",
            "        self._page_title.text = page_name",
            "        self._content.clear_widgets()",
            "        widgets = self._page_widgets.get(page_name, [])",
            "        if widgets:",
            "            for widget in widgets:",
            "                self._content.add_widget(widget)",
            "        else:",
            "            self._content.add_widget(Label(text=f'صفحة {page_name}'))",
            "",
        ])
    if any(widget.kind == "كلمة_مرور" for widget in program.widgets):
        lines.extend([
            "    def _validate_password(self, value, status, minimum):",
            "        valid = len(value) >= minimum and any(char.isdigit() for char in value) and any(not char.isalnum() for char in value)",
            "        status.text = 'كلمة المرور قوية' if valid else f'استخدم {minimum} خانات مع أرقام ورموز'",
            "        status.color = [0.1, 0.8, 0.35, 1] if valid else [0.95, 0.25, 0.25, 1]",
            "",
        ])

    lines.extend(["", "if __name__ == '__main__':", "    AlBaaAndroidApp().run()", ""])
    return "\n".join(lines)


def hex_to_rgba(color):
    color = color.lstrip("#")
    return [round(int(color[index:index + 2], 16) / 255, 4) for index in (0, 2, 4)] + [1]


def is_dark_hex(color):
    color = color.lstrip("#")
    red, green, blue = (int(color[index:index + 2], 16) for index in (0, 2, 4))
    return (red * 299 + green * 587 + blue * 114) / 1000 < 128


def buildozer_spec(title):
    safe_title = title.replace("\n", " ").strip() or "تطبيق الباء"
    return f"""[app]
title = {safe_title}
package.name = albaaapp
package.domain = org.albaa
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1
requirements = python3,kivy
orientation = portrait
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1
"""


def export_android_project(source, directory):
    program = parse_android(source)
    os.makedirs(directory, exist_ok=True)
    main_path = os.path.join(directory, "main.py")
    spec_path = os.path.join(directory, "buildozer.spec")
    with open(main_path, "w", encoding="utf-8", newline="\n") as file:
        file.write(generate_kivy(source))
    with open(spec_path, "w", encoding="utf-8", newline="\n") as file:
        file.write(buildozer_spec(program.title))
    return main_path, spec_path
