import pytest

from arabicpy.android import export_android_project, generate_kivy, is_android_source
from arabicpy.errors import ArabicPyError


ANDROID_SOURCE = """تطبيق "تطبيق الاختبار"

رسالة = نص("مرحباً")
الاسم = حقل("اكتب اسمك")
زر_الترحيب = زر("اضغط")

عند_النقر(زر_الترحيب):
    غيّر_النص(رسالة، "أهلاً بك")
"""


def test_detects_and_generates_kivy_application():
    assert is_android_source(ANDROID_SOURCE)

    python_code = generate_kivy(ANDROID_SOURCE)

    assert "class AlBaaAndroidApp(App):" in python_code
    assert "self.رسالة = Label(text='مرحباً')" in python_code
    assert "self.الاسم = TextInput(text='اكتب اسمك', multiline=False)" in python_code
    assert "self.زر_الترحيب.bind(on_press=self._event_1)" in python_code
    assert "self.رسالة.text = 'أهلاً بك'" in python_code


def test_rejects_unknown_event_target():
    source = """تطبيق "خطأ"
زر_أول = زر("اضغط")
عند_النقر(زر_مفقود):
    غيّر_النص(زر_أول، "تم")
"""

    with pytest.raises(ArabicPyError, match="زر غير معروف"):
        generate_kivy(source)


def test_exports_main_and_buildozer_spec(tmp_path):
    main_path, spec_path = export_android_project(ANDROID_SOURCE, tmp_path)

    assert main_path == str(tmp_path / "main.py")
    assert spec_path == str(tmp_path / "buildozer.spec")
    assert "AlBaaAndroidApp().run()" in (tmp_path / "main.py").read_text(encoding="utf-8")
    spec = (tmp_path / "buildozer.spec").read_text(encoding="utf-8")
    assert "requirements = python3,kivy" in spec
    assert "title = تطبيق الاختبار" in spec


def test_element_colors_are_generated_for_kivy():
    source = """تطبيق "ألوان"
رسالة = نص("مرحباً")
لون_النص(رسالة، "#112233")
لون_الخلفية(رسالة، "#AABBCC")
زر_أول = زر("اضغط")
لون_الخلفية(زر_أول، "#FF0000")
"""

    python_code = generate_kivy(source)

    assert "class ColoredLabel(Label):" in python_code
    assert "color=[0.0667, 0.1333, 0.2, 1]" in python_code
    assert "background_color=[0.6667, 0.7333, 0.8, 1]" in python_code
    assert "background_color=[1.0, 0.0, 0.0, 1]" in python_code


def test_screen_background_color_is_generated_for_kivy():
    source = """تطبيق "خلفية"
لون_الشاشة("#123456")
رسالة = نص("مرحباً")
"""

    python_code = generate_kivy(source)

    assert "from kivy.core.window import Window" in python_code
    assert "Window.clearcolor = [0.0706, 0.2039, 0.3373, 1]" in python_code
