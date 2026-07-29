from lexer import Lexer

with open("examples/hello.apy", "r", encoding="utf-8") as file:
    code = file.read()

lexer = Lexer(code)

tokens = lexer.tokenize()

for token in tokens:
    print(token)