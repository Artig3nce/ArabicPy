import pytest

from arabicpy.app_dsl import is_app_source, parse_app_source
from arabicpy.errors import ArabicPyError


APP_SOURCE = """تطبيق "تطبيق الاختبار"

رسالة = نص("مرحباً")
الاسم = حقل("اكتب اسمك")
زر_الترحيب = زر("اضغط")

عند_النقر(زر_الترحيب):
    غيّر_النص(رسالة، "أهلاً بك")
"""


def test_detects_and_parses_app_source():
    assert is_app_source(APP_SOURCE)

    program = parse_app_source(APP_SOURCE)

    assert program.title == "تطبيق الاختبار"
    assert [widget.kind for widget in program.widgets] == ["نص", "حقل", "زر"]
    assert program.events[0].actions == [("رسالة", "أهلاً بك")]


def test_rejects_unknown_event_target():
    source = """تطبيق "خطأ"
زر_أول = زر("اضغط")
عند_النقر(زر_مفقود):
    غيّر_النص(زر_أول، "تم")
"""

    with pytest.raises(ArabicPyError, match="زر غير معروف"):
        parse_app_source(source)


def test_video_widget_is_parsed():
    source = '''تطبيق "Video App"
intro = فيديو("media/intro.mp4")
'''

    program = parse_app_source(source)
    assert program.widgets[0].kind == "فيديو"
    assert program.widgets[0].text == "media/intro.mp4"


def test_natural_arabic_widget_text_color():
    source = '''تطبيق "ألوان النص"
الاسم = حقل("اكتب اسمك")
لون النص هو #F2F2F2
زر_الحفظ = زر("حفظ")
لون النص هو اسود
'''

    program = parse_app_source(source)

    assert program.widgets[0].text_color == "#F2F2F2"
    assert program.widgets[1].text_color == "#000000"


def test_natural_arabic_application_name():
    source = '''اسم التطبيق هو الباء
رسالة = نص("مرحباً")
'''

    assert is_app_source(source)
    assert parse_app_source(source).title == "الباء"


def test_natural_arabic_click_event():
    source = '''اسم التطبيق هو الباء
رسالة = نص("مرحباً")
زر_الترحيب = زر("اضغط")

عند النقر على زر الترحيب
    غيّر_النص(رسالة، "أهلاً")
'''

    program = parse_app_source(source)

    assert program.events[0].button == "زر_الترحيب"
    assert program.events[0].actions == [("رسالة", "أهلاً")]


def test_natural_button_text_and_page_navigation():
    source = '''اسم التطبيق هو الباء
زر_الترحيب = زر("اضغط هنا")

عند النقر على زر اضغط هنا
    اذهب الى صفحة الرئيسية
'''

    program = parse_app_source(source)

    assert program.events[0].button == "زر_الترحيب"
    assert program.events[0].actions == [("__page__", "الرئيسية")]


def test_natural_arabic_button_creation():
    source = '''اسم التطبيق هو الباء
انشئ زر اسمه اضغط هنا
لون النص هو ابيض
لون الخلفية هو #2563EB

عند النقر على زر اضغط هنا
    اذهب الى صفحة البحث
'''

    program = parse_app_source(source)

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

    program = parse_app_source(source)

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

    program = parse_app_source(source)

    assert program.widgets[0].page == "قوة كلمة المرور"
    assert program.widgets[0].text_color == "#000000"


def test_background_color_without_connector_word():
    source = '''اسم التطبيق هو الباء
انشئ زر اضغط هنا
لون الخلفية #0A0A0A
'''

    assert parse_app_source(source).widgets[0].background_color == "#0A0A0A"


def test_function_accepts_unindented_print_command():
    source = '''اسم التطبيق هو الباء
رسالة = نص("مرحبا من الباء")
انشئ زر اضغط، ازرق، دالة الطباعة

دالة الطباعة:
اطبع("مرحبا")
'''

    program = parse_app_source(source)

    assert program.events[0].function_name == "الطباعة"
    assert program.events[0].actions == [("__print__", "مرحبا")]


def test_function_button_without_color_inherits_previous_button_design():
    source = '''اسم التطبيق هو الباء
انشئ زر اضغط هنا
لون النص ابيض
لون الخلفية اسود
انشئ زر اطبع، دالة الطباعة

دالة الطباعة:
اطبع("مرحبا")
'''

    program = parse_app_source(source)

    first_button, function_button = program.widgets
    assert function_button.background_color == first_button.background_color == "#000000"
    assert function_button.text_color == first_button.text_color == "#FFFFFF"


def test_numbered_natural_text_elements():
    source = '''اسم التطبيق هو الباء
نص 1 = مرحباً بك
نص 2 = كيف حالك؟
'''

    program = parse_app_source(source)

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

    program = parse_app_source(source)

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

    program = parse_app_source(source)

    assert program.widgets[0].kind == "كلمة_مرور"


def test_simple_display_and_field_syntax():
    source = '''اسم التطبيق هو الباء
اطبع "ما هو اسمك"
الاسم = حقل "اكتب اسمك"
اطبع الاسم
'''

    program = parse_app_source(source)

    assert program.widgets[0].text == "ما هو اسمك"
    assert program.widgets[1].name == "الاسم"
    assert program.widgets[1].natural_syntax
    assert program.widgets[2].bind_to == "الاسم"
