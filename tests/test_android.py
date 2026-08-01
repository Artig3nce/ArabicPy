import pytest

from arabicpy.android import export_android_project, generate_kivy, is_android_source, parse_android
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
    assert "requirements = python3==3.12.9,hostpython3==3.12.9,kivy" in spec
    assert "title = تطبيق الاختبار" in spec
    workflow = tmp_path / ".github" / "workflows" / "build-apk.yml"
    assert workflow.exists()
    workflow_text = workflow.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow_text
    assert "actions/upload-artifact@v4" in workflow_text
    assert "git+https://github.com/kivy/buildozer" in workflow_text
    assert "libltdl-dev" in workflow_text
    assert "actions/cache@v4" in workflow_text
    assert "android.api = 35" in spec
    assert "android.ndk = 28c" in spec
    assert "android.accept_sdk_license = True" in spec


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


def test_bottom_navigation_is_parsed_and_generated():
    source = '''تطبيق "اجتماعي"
لون_الشاشة("#000000")
شريط_سفلي("⌂ الرئيسية | ⌕ البحث | ♢ التنبيهات | ✉ الرسائل")
عنوان = نص("آخر المنشورات")
'''

    python_code = generate_kivy(source)

    assert "from kivy.uix.button import Button" in python_code
    assert "bottom_navigation = BoxLayout" in python_code
    assert "text='الرئيسية'" in python_code
    assert "text='الرسائل'" in python_code


@pytest.mark.parametrize(
    ("statement", "rgba"),
    [
        ("لون الشاشة اسود", "[0.0, 0.0, 0.0, 1]"),
        ("لون الشاشة ابيض", "[1.0, 1.0, 1.0, 1]"),
    ],
)
def test_natural_arabic_screen_colors(statement, rgba):
    source = f'''تطبيق "ألوان عربية"
{statement}
رسالة = نص("مرحباً")
'''

    assert f"Window.clearcolor = {rgba}" in generate_kivy(source)


def test_natural_arabic_bottom_navigation():
    source = '''تطبيق "اجتماعي"
ضع في شريط السفلي الرئيسية و البحث و التنبيهات و الرسائل
عنوان = نص("المنشورات")
'''

    python_code = generate_kivy(source)

    assert "text='الرئيسية'" in python_code
    assert "text='البحث'" in python_code
    assert "text='التنبيهات'" in python_code
    assert "text='الرسائل'" in python_code


def test_natural_arabic_widget_text_color():
    source = '''تطبيق "ألوان النص"
الاسم = حقل("اكتب اسمك")
لون النص هو #F2F2F2
زر_الحفظ = زر("حفظ")
لون النص هو اسود
'''

    program = parse_android(source)

    assert program.widgets[0].text_color == "#F2F2F2"
    assert program.widgets[1].text_color == "#000000"


def test_natural_arabic_application_name():
    source = '''اسم التطبيق هو الباء
رسالة = نص("مرحباً")
'''

    assert is_android_source(source)
    assert parse_android(source).title == "الباء"


def test_natural_arabic_click_event():
    source = '''اسم التطبيق هو الباء
رسالة = نص("مرحباً")
زر_الترحيب = زر("اضغط")

عند النقر على زر الترحيب
    غيّر_النص(رسالة، "أهلاً")
'''

    program = parse_android(source)

    assert program.events[0].button == "زر_الترحيب"
    assert program.events[0].actions == [("رسالة", "أهلاً")]


def test_natural_button_text_and_page_navigation():
    source = '''اسم التطبيق هو الباء
زر_الترحيب = زر("اضغط هنا")

عند النقر على زر اضغط هنا
    اذهب الى صفحة الرئيسية
'''

    program = parse_android(source)
    python_code = generate_kivy(source)

    assert program.events[0].button == "زر_الترحيب"
    assert program.events[0].actions == [("__page__", "الرئيسية")]
    assert "self._go_to_page('الرئيسية')" in python_code
    assert "navigation_button.bind(on_press=" not in python_code


def test_natural_arabic_button_creation():
    source = '''اسم التطبيق هو الباء
انشئ زر اسمه اضغط هنا
لون النص هو ابيض
لون الخلفية هو #2563EB

عند النقر على زر اضغط هنا
    اذهب الى صفحة البحث
'''

    program = parse_android(source)

    assert program.widgets[0].name == "زر_اضغط_هنا"
    assert program.widgets[0].text == "اضغط هنا"
    assert program.widgets[0].background_color == "#2563EB"
    assert program.events[0].button == "زر_اضغط_هنا"


def test_password_function_page_block_syntax():
    source = '''اسم التطبيق هو الباء

لون الشاشة اسود

في شريط السفلي ضع
    الرئيسية
    قوة كلمة المرور
    التنبيهات
    الرسائل

دالة كلمة المرور
انشئ زر اضغط هنا
عند النقر
    اذهب الى صفحة قوة كلمة المرور
اكبر او تساوي 8 خانات ويجب ان تحتوي على ارقام و رموز

في صفحة "قوة كلمة المرور"
    أنشئ حقلًا اسمه "كلمة المرور"

شروط كلمة المرور
    طولها لا يقل عن 8
    تحتوي على رقم
    تحتوي على رمز
'''

    program = parse_android(source)

    password = program.widgets[-1]
    assert password.kind == "كلمة_مرور"
    assert password.page == "قوة كلمة المرور"
    assert password.min_length == 8
    assert password.require_numbers and password.require_symbols


def test_short_text_color_and_unquoted_page():
    source = '''اسم التطبيق هو الباء
في صفحة قوة كلمة المرور
رسالة = نص("آمن")
لون النص اسود
'''

    program = parse_android(source)

    assert program.widgets[0].page == "قوة كلمة المرور"
    assert program.widgets[0].text_color == "#000000"


def test_background_color_without_connector_word():
    source = '''اسم التطبيق هو الباء
انشئ زر اضغط هنا
لون الخلفية #0A0A0A
'''

    assert parse_android(source).widgets[0].background_color == "#0A0A0A"


def test_function_accepts_unindented_print_command():
    source = '''اسم التطبيق هو الباء
رسالة = نص("مرحبا من الباء")
انشئ زر اضغط، ازرق، دالة الطباعة

دالة الطباعة:
اطبع("مرحبا")
'''

    program = parse_android(source)

    assert program.events[0].function_name == "الطباعة"
    assert program.events[0].actions == [("__print__", "مرحبا")]
    assert "print('مرحبا')" in generate_kivy(source)


def test_function_button_without_color_inherits_previous_button_design():
    source = '''اسم التطبيق هو الباء
انشئ زر اضغط هنا
لون النص ابيض
لون الخلفية اسود
انشئ زر اطبع، دالة الطباعة

دالة الطباعة:
اطبع("مرحبا")
'''

    program = parse_android(source)

    first_button, function_button = program.widgets
    assert function_button.background_color == first_button.background_color == "#000000"
    assert function_button.text_color == first_button.text_color == "#FFFFFF"


def test_numbered_natural_text_elements():
    source = '''اسم التطبيق هو الباء
نص 1 = مرحباً بك
نص 2 = كيف حالك؟
'''

    program = parse_android(source)

    assert [(widget.name, widget.kind, widget.text) for widget in program.widgets] == [
        ("نص_1", "نص", "مرحباً بك"),
        ("نص_2", "نص", "كيف حالك؟"),
    ]


def test_standalone_function_uses_latest_button_and_existing_click_event():
    source = '''اسم التطبيق هو الباء
انشئ زر اضغط هنا
عند النقر
    اذهب الى صفحة قوة كلمة المرور

دالة فحص قوة كلمة المرور:
    اطبع("تم الفحص")
'''

    program = parse_android(source)

    assert len(program.events) == 1
    assert program.events[0].button == "زر_اضغط_هنا"
    assert program.events[0].function_name == "فحص قوة كلمة المرور"
    assert program.events[0].actions == [
        ("__page__", "قوة كلمة المرور"),
        ("__print__", "تم الفحص"),
    ]


def test_comments_are_ignored_inside_password_rules():
    source = '''اسم التطبيق هو الباء
في صفحة قوة كلمة المرور
    أنشئ حقلًا اسمه "كلمة المرور"
شروط كلمة المرور
    ## طولها لا يقل عن 8
    ## تحتوي على رقم
    ## تحتوي على رمز
'''

    program = parse_android(source)

    assert program.widgets[0].kind == "كلمة_مرور"


def test_simple_display_and_field_syntax_generates_live_application_text():
    source = '''اسم التطبيق هو الباء
اطبع "ما هو اسمك"
الاسم = حقل "اكتب اسمك"
اطبع الاسم
'''

    program = parse_android(source)
    python_code = generate_kivy(source)

    assert program.widgets[0].text == "ما هو اسمك"
    assert program.widgets[1].name == "الاسم"
    assert program.widgets[1].natural_syntax
    assert program.widgets[2].bind_to == "الاسم"
    assert "hint_text='اكتب اسمك', text=''" in python_code
    assert "self.الاسم.bind(text=lambda _field, value:" in python_code
    assert "setattr(self.نص_مطبوع_2, 'text', value)" in python_code
