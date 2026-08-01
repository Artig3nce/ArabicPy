from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.core.window import Window
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle
from kivy.properties import ListProperty


class ColoredLabel(Label):
    background_color = ListProperty([0, 0, 0, 0])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self._background = Color(rgba=self.background_color)
            self._background_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._sync_background, size=self._sync_background)
        self.bind(background_color=self._sync_background_color)

    def _sync_background(self, *_):
        self._background_rect.pos = self.pos
        self._background_rect.size = self.size

    def _sync_background_color(self, *_):
        self._background.rgba = self.background_color


class AlBaaAndroidApp(App):
    def build(self):
        self.title = 'الباء'
        Window.clearcolor = [0.0, 0.0, 0.0, 1]
        root = BoxLayout(orientation='vertical', padding=24, spacing=12)
        self._page_title = Label(text='الباء', size_hint_y=None, height=48)
        root.add_widget(self._page_title)
        self._content = BoxLayout(orientation='vertical', spacing=12)
        self._page_widgets = {}
        root.add_widget(self._content)
        self.نص_مطبوع_1 = ColoredLabel(text='ما هو اسمك', color=[1.0, 1.0, 1.0, 1], background_color=[0.0392, 0.0392, 0.0392, 1])
        self._page_widgets.setdefault('الرئيسية', []).append(self.نص_مطبوع_1)
        self._content.add_widget(self.نص_مطبوع_1)
        self.الاسم = TextInput(hint_text='اكتب اسمك', text='', foreground_color=[1.0, 1.0, 1.0, 1], background_color=[0.0392, 0.0392, 0.0392, 1], multiline=False)
        self._page_widgets.setdefault('الرئيسية', []).append(self.الاسم)
        self._content.add_widget(self.الاسم)
        bottom_navigation = BoxLayout(size_hint_y=None, height=56, spacing=4)
        navigation_button = Button(text='الرئيسية', background_normal='', background_color=[0.02, 0.02, 0.02, 1], color=[1, 1, 1, 1])
        navigation_button.bind(on_press=lambda _button, page='الرئيسية': self._go_to_page(page))
        bottom_navigation.add_widget(navigation_button)
        navigation_button = Button(text='البحث', background_normal='', background_color=[0.02, 0.02, 0.02, 1], color=[1, 1, 1, 1])
        navigation_button.bind(on_press=lambda _button, page='البحث': self._go_to_page(page))
        bottom_navigation.add_widget(navigation_button)
        navigation_button = Button(text='التنبيهات', background_normal='', background_color=[0.02, 0.02, 0.02, 1], color=[1, 1, 1, 1])
        navigation_button.bind(on_press=lambda _button, page='التنبيهات': self._go_to_page(page))
        bottom_navigation.add_widget(navigation_button)
        navigation_button = Button(text='الرسائل', background_normal='', background_color=[0.02, 0.02, 0.02, 1], color=[1, 1, 1, 1])
        navigation_button.bind(on_press=lambda _button, page='الرسائل': self._go_to_page(page))
        bottom_navigation.add_widget(navigation_button)
        root.add_widget(bottom_navigation)
        return root

    def _go_to_page(self, page_name):
        self._page_title.text = page_name
        self._content.clear_widgets()
        widgets = self._page_widgets.get(page_name, [])
        if widgets:
            for widget in widgets:
                self._content.add_widget(widget)
        else:
            self._content.add_widget(Label(text=f'صفحة {page_name}'))


if __name__ == '__main__':
    AlBaaAndroidApp().run()
