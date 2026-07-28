from lexer import Lexer
from parser import Parser
from generator import Generator


def test_generate_assignment():
    lexer = Lexer("س = 5")
    tokens = lexer.tokenize()

    parser = Parser(tokens)
    tree = parser.parse()

    generator = Generator()

    code = generator.generate(tree)

    assert "5" in code