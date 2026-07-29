import sys

from .lexer import Lexer
from .parser import Parser
from .generator import Generator


VERSION = "0.1.0"


def show_help():
    print("""
ArabicPy - Arabic Programming Language

Usage:
    arabicpy <file.apy>
    arabicpy run <file.apy>

Commands:
    run           Run ArabicPy program
    check         Check syntax only
    --version     Show version
    --help        Show help
""")


def run():

    if len(sys.argv) < 2:
        show_help()
        return

    command = sys.argv[1]


    if command == "--version":
        print(f"ArabicPy {VERSION}")
        return


    if command == "--help":
        show_help()
        return


    # arabicpy run hello.apy
    if command == "run":

        if len(sys.argv) < 3:
            print("Usage: arabicpy run <file.apy>")
            return

        filename = sys.argv[2]


    # arabicpy hello.apy
    else:
        filename = command


    try:
        with open(filename, "r", encoding="utf-8") as file:
            code = file.read()

        lexer = Lexer(code)
        tokens = lexer.tokenize()

        parser = Parser(tokens)
        ast = parser.parse()

        generator = Generator()
        python_code = generator.generate(ast)

        exec(python_code)


    except FileNotFoundError:
        print(f"ArabicPy Error: File not found '{filename}'")


    except Exception as e:
        print("ArabicPy Error:")
        print(e)


if __name__ == "__main__":
    run()