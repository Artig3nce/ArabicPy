import contextlib
import io

from arabicpy.generator import Generator
from arabicpy.lexer import Lexer
from arabicpy.parser import Parser


def compile_arabicpy(source):
    return Generator().generate(Parser(Lexer(source).tokenize()).parse())


def run_arabicpy(source):
    output = io.StringIO()
    python_code = compile_arabicpy(source)
    with contextlib.redirect_stdout(output):
        exec(python_code, {"__name__": "__main__"})
    return python_code, output.getvalue()


def test_arabic_logical_and_comparison_operators():
    source = """س = 7
اذا س >= 5 و ليس س == 8:
    اطبع("صحيح")
"""

    python_code, output = run_arabicpy(source)

    assert "if س >= 5 and not س == 8:" in python_code
    assert output == "صحيح\n"


def test_dictionary_literal_and_index_access():
    source = """بيانات = {"اسم": "سعود", "عمر": 20}
اطبع(بيانات["اسم"])
"""

    python_code, output = run_arabicpy(source)

    assert "{'اسم': 'سعود', 'عمر': 20}" in python_code
    assert output == "سعود\n"


def test_for_loop_over_list():
    source = """لكل رقم_حالي في [1، 2، 3]:
    اطبع(رقم_حالي)
"""

    python_code, output = run_arabicpy(source)

    assert "for رقم_حالي in [1, 2, 3]:" in python_code
    assert output == "1\n2\n3\n"


def test_function_definition_call_and_return():
    source = """دالة جمع_رقمين(أ، ب):
    ارجع أ + ب

اطبع(جمع_رقمين(2، 3))
"""

    python_code, output = run_arabicpy(source)

    assert "def جمع_رقمين(a, b):" in python_code
    assert output == "5\n"


def test_break_continue_and_pass():
    source = """لكل س في [1، 2، 3]:
    اذا س == 2:
        استمر
    اطبع(س)
تجاوز
"""

    python_code, output = run_arabicpy(source)

    assert "continue" in python_code
    assert python_code.endswith("pass")
    assert output == "1\n3\n"
