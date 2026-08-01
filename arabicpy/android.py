"""Small الباء-to-Kivy translator and Android project exporter."""

import os
import re
from dataclasses import dataclass, field

from .errors import ArabicPyError


WIDGET_PATTERN = re.compile(r'^(?P<name>[\w\u0600-\u06ff]+)\s*=\s*(?P<kind>نص|زر|حقل)\("(?P<text>.*)"\)\s*$')
EVENT_PATTERN = re.compile(r'^عند_النقر\((?P<name>[\w\u0600-\u06ff]+)\):\s*$')
SET_TEXT_PATTERN = re.compile(r'^غيّر_النص\((?P<name>[\w\u0600-\u06ff]+)\s*[،,]\s*"(?P<text>.*)"\)\s*$')
COLOR_PATTERN = re.compile(
    r'^(?P<property>لون_النص|لون_الخلفية)\('
    r'(?P<name>[\w\u0600-\u06ff]+)\s*[،,]\s*"(?P<color>#[0-9a-fA-F]{6})"\)\s*$'
)
APP_PATTERN = re.compile(r'^تطبيق\s+"(?P<title>.*)"\s*$')
SCREEN_COLOR_PATTERN = re.compile(r'^لون_الشاشة\("(?P<color>#[0-9a-fA-F]{6})"\)\s*$')


@dataclass
class AndroidWidget:
    name: str
    kind: str
    text: str
    text_color: str | None = None
    background_color: str | None = None


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


def is_android_source(source):
    return any(line.strip().startswith("تطبيق ") for line in source.splitlines())


def parse_android(source):
    title = None
    widgets = []
    events = []
    background_color = None
    widget_names = set()
    lines = source.splitlines()
    index = 0

    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()
        line_number = index + 1
        if not stripped or stripped.startswith("#"):
            index += 1
            continue

        if raw_line[:1].isspace():
            raise ArabicPyError("تعليمة مزاحة خارج حدث", line_number, 1)

        app_match = APP_PATTERN.match(stripped)
        if app_match:
            if title is not None:
                raise ArabicPyError("يمكن تعريف تطبيق واحد فقط", line_number, 1)
            title = app_match.group("title")
            index += 1
            continue

        screen_color_match = SCREEN_COLOR_PATTERN.match(stripped)
        if screen_color_match:
            background_color = screen_color_match.group("color").upper()
            index += 1
            continue

        widget_match = WIDGET_PATTERN.match(stripped)
        if widget_match:
            name = widget_match.group("name")
            if name in widget_names:
                raise ArabicPyError(f"العنصر معرّف مسبقاً: {name}", line_number, 1)
            widget_names.add(name)
            widgets.append(AndroidWidget(name, widget_match.group("kind"), widget_match.group("text")))
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

        event_match = EVENT_PATTERN.match(stripped)
        if event_match:
            button = event_match.group("name")
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
        raise ArabicPyError('ابدأ البرنامج بـ: تطبيق "اسم التطبيق"', 1, 1)
    if not widgets:
        raise ArabicPyError("أضف عنصراً واحداً على الأقل إلى التطبيق", 1, 1)
    return AndroidProgram(title, widgets, events, background_color)


def generate_kivy(source):
    program = parse_android(source)
    widget_classes = {"نص": "Label", "زر": "Button", "حقل": "TextInput"}
    imports = sorted({widget_classes[widget.kind] for widget in program.widgets})
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

    for widget in program.widgets:
        widget_class = widget_classes[widget.kind]
        if widget.kind == "نص" and widget.background_color:
            widget_class = "ColoredLabel"
        option_parts = [f"text={widget.text!r}"]
        if widget.text_color:
            color_property = "foreground_color" if widget.kind == "حقل" else "color"
            option_parts.append(f"{color_property}={hex_to_rgba(widget.text_color)!r}")
        if widget.background_color:
            option_parts.append(
                f"background_color={hex_to_rgba(widget.background_color)!r}"
            )
        if widget.kind == "حقل":
            option_parts.append("multiline=False")
        options = ", ".join(option_parts)
        lines.append(f"        self.{widget.name} = {widget_class}({options})")
        lines.append(f"        root.add_widget(self.{widget.name})")

    for event_index, event in enumerate(program.events, 1):
        lines.append(
            f"        self.{event.button}.bind(on_press=self._event_{event_index})"
        )
    lines.extend(["        return root", ""])

    for event_index, event in enumerate(program.events, 1):
        lines.append(f"    def _event_{event_index}(self, _button):")
        for target, text in event.actions:
            lines.append(f"        self.{target}.text = {text!r}")
        lines.append("")

    lines.extend(["", "if __name__ == '__main__':", "    AlBaaAndroidApp().run()", ""])
    return "\n".join(lines)


def hex_to_rgba(color):
    color = color.lstrip("#")
    return [round(int(color[index:index + 2], 16) / 255, 4) for index in (0, 2, 4)] + [1]


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
