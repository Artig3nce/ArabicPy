import pytest

from arabicpy.errors import ArabicPyError, format_error
from arabicpy.lexer import Lexer
from arabicpy.parser import Parser


def test_unknown_character_reports_arabic_source_location():
    source = "س = 1\nاطبع(@)"

    with pytest.raises(ArabicPyError) as caught:
        Lexer(source).tokenize()

    message = format_error(caught.value, source)
    assert "السطر 2" in message
    assert "رمز غير معروف: @" in message
    assert "^" in message


def test_parser_reports_expected_token_location():
    source = "اذا صح\n    اطبع(1)"

    with pytest.raises(ArabicPyError) as caught:
        Parser(Lexer(source).tokenize()).parse()

    message = format_error(caught.value, source)
    assert "السطر 1" in message
    assert "COLON" in message


def test_runtime_name_error_is_translated_to_arabic():
    error = NameError("name 'اطب' is not defined")

    message = format_error(error, "اطب(\"مرحبا\")")

    assert "الاسم غير معرّف" in message
    assert "هل تقصد: اطبع" in message
