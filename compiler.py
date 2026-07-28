from keywords import KEYWORDS

def compile(code):
    for arabic, python in KEYWORDS.items():
        code = code.replace(arabic, python)

    return code
