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

print("=== GENERATED CODE ===")
print(python_code)

print("=== OUTPUT ===")

exec(
    python_code,
    {}
)

print("=== BEFORE GENERATE ===")

python_code = generator.generate(ast)

print("=== GENERATED CODE ===")
print(python_code)

exec(python_code)

with contextlib.redirect_stdout(output):

    exec(
        python_code,
        globals()
    )