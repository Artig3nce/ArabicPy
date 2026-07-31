from arabicpy.generator import Generator
from arabicpy.lexer import Lexer
from arabicpy.parser import Parser


def test_generates_list_index_access():
    source = "ارقام = [10, 20, 30]\nاطبع(ارقام[0])"

    tree = Parser(Lexer(source).tokenize()).parse()
    code = Generator().generate(tree)

    assert "ارقام = [10, 20, 30]" in code
    assert "print(ارقام[0])" in code


def test_generates_chained_list_index_access():
    tree = Parser(Lexer("اطبع(بيانات[0][1])").tokenize()).parse()

    assert Generator().generate(tree) == "print(بيانات[0][1])"
