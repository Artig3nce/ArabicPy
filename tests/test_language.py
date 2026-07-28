from lexer import Lexer
from parser import Parser
from generator import Generator


def test_math():
    code = """
س = 5
ص = 7
اطبع(س + ص)
"""

    lexer = Lexer(code)
    tokens = lexer.tokenize()

    parser = Parser(tokens)
    tree = parser.parse()

    generator = Generator()

    python_code = generator.generate(tree)

    assert "print" in python_code

from lexer import Lexer
from parser import Parser
from generator import Generator


def test_if_statement():
    code = """
س = 10
ص = 5

اذا س > ص:
    اطبع("س أكبر")
"""

    lexer = Lexer(code)
    tokens = lexer.tokenize()

    parser = Parser(tokens)
    tree = parser.parse()

    generator = Generator()
    python_code = generator.generate(tree)

    assert "if" in python_code