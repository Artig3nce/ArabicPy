from arabicpy.lexer import Lexer


def test_variable_assignment():
    lexer = Lexer("س = 5")
    tokens = lexer.tokenize()

    assert len(tokens) == 3

    assert tokens[0].type == "IDENTIFIER"
    assert tokens[0].value == "س"

    assert tokens[1].type == "EQUALS"
    assert tokens[1].value == "="

    assert tokens[2].type == "NUMBER"
    assert tokens[2].value == 5


def test_print():
    lexer = Lexer('اطبع("مرحبا")')
    tokens = lexer.tokenize()

    assert tokens[0].type == "PRINT"
    assert tokens[1].type == "LPAREN"
    assert tokens[2].type == "STRING"
    assert tokens[2].value == "مرحبا"
    assert tokens[3].type == "RPAREN"


def test_comparison():
    lexer = Lexer("س > ص")
    tokens = lexer.tokenize()

    assert tokens[0].type == "IDENTIFIER"
    assert tokens[1].type == "GREATER"
    assert tokens[2].type == "IDENTIFIER"
