from lexer import Lexer
from parser import Parser
from generator import Generator


# Read ArabicPy file
with open("hello.apy", "r", encoding="utf-8") as file:
    code = file.read()


lexer = Lexer(code)

tokens = lexer.tokenize()

parser = Parser(tokens)

ast = parser.parse()

generator = Generator()

python_code = generator.generate(ast)


# Run the generated Python
exec(python_code)