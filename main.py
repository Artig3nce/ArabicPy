from lexer import Lexer
from parser import Parser
from generator import Generator

code = """
دالة مربع(س):
    ارجع س * س

اطبع(مربع(5))
"""

lexer = Lexer(code)
tokens = lexer.tokenize()

parser = Parser(tokens)
ast = parser.parse()

print(ast)

generator = Generator()
python_code = generator.generate(ast)

print(python_code)