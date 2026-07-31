from arabicpy.lexer import Lexer
from arabicpy.parser import Parser


def test_assignment():
    lexer = Lexer("س = 5")
    tokens = lexer.tokenize()

    parser = Parser(tokens)
    tree = parser.parse()

    assert len(tree.statements) == 1
