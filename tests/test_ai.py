from arabicpy.ai import reply
from arabicpy.generator import Generator
from arabicpy.lexer import Lexer
from arabicpy.parser import Parser


def test_ask_builtin_generates_runtime_helper():
    source = '\u0627\u0637\u0628\u0639(\u0627\u0633\u0623\u0644("\u0645\u0631\u062d\u0628\u0627"))'
    code = Generator().generate(Parser(Lexer(source).tokenize()).parse())

    assert code.startswith("print(arabicpy_ai_reply(")


def test_offline_ai_reply_is_available():
    assert "مساعد" in reply("مرحبا")


def test_arabic_input_builtin_uses_standard_input():
    source = "\u0631\u0633\u0627\u0644\u0629 = \u0627\u062f\u062e\u0644()"
    code = Generator().generate(Parser(Lexer(source).tokenize()).parse())

    assert "input()" in code
