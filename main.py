import sys
from arabicpy.lexer import Lexer
from arabicpy.parser import Parser
from arabicpy.generator import Generator


if len(sys.argv) < 2:
    print("استخدم: python main.py filename.apy")
    exit()


filename = sys.argv[1]


with open(filename, "r", encoding="utf-8") as file:
    code = file.read()


lexer = Lexer(code)

tokens = lexer.tokenize()

parser = Parser(tokens)

ast = parser.parse()

generator = Generator()

python_code = generator.generate(ast)

exec(python_code)