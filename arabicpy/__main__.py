import sys

from .lexer import Lexer
from .parser import Parser
from .generator import Generator
from .ai import reply as albaa_ai_reply
from .errors import format_error


VERSION = "0.1.0"


def show_help():
    print("""
الباء - لغة البرمجة العربية

Usage:
    albaa <file.apy>
    albaa run <file.apy>

Commands:
    run           تشغيل برنامج الباء
    check         فحص الصياغة فقط
    --version     عرض الإصدار
    --help        عرض المساعدة
""")


def run():

    if len(sys.argv) < 2:
        show_help()
        return

    command = sys.argv[1]


    if command == "--version":
        print(f"الباء {VERSION}")
        return


    if command == "--help":
        show_help()
        return


    # albaa run hello.apy
    if command == "run":

        if len(sys.argv) < 3:
            print("الاستخدام: albaa run <file.apy>")
            return

        filename = sys.argv[2]


    # albaa hello.apy
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

        exec(python_code, {
            "__name__": "__main__",
            "albaa_ai_reply": albaa_ai_reply,
        })


    except FileNotFoundError:
        print(f"خطأ في الباء: الملف غير موجود '{filename}'")


    except Exception as e:
        print(format_error(e, code if "code" in locals() else ""))


if __name__ == "__main__":
    run()
