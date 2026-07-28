from lexer import Lexer
from parser import Parser
from generator import Generator

with open("examples/hello.apy", "r", encoding="utf-8") as file:
    code = file.read()

lexer = Lexer(code)
tokens = lexer.tokenize()

parser = Parser(tokens)
tree = parser.parse()

generator = Generator()
python_code = generator.generate(tree)

exec(python_code)
