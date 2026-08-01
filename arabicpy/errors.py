import re


class ArabicPyError(Exception):
    """A language error that can point to a place in ArabicPy source code."""

    def __init__(self, message, line=None, column=None):
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column


def format_error(error, source):
    """Render a compact Arabic diagnostic for the IDE and command line."""
    if not isinstance(error, ArabicPyError):
        if isinstance(error, NameError):
            match = re.search(r"name '([^']+)' is not defined", str(error))
            name = match.group(1) if match else "غير معروف"
            hint = ""
            if name == "اطب":
                hint = "\nهل تقصد: اطبع(...) ؟"
            return f"خطأ أثناء التشغيل:\nالاسم غير معرّف: {name}{hint}"
        if isinstance(error, ZeroDivisionError):
            return "خطأ أثناء التشغيل:\nلا يمكن القسمة على صفر."
        if isinstance(error, TypeError):
            return f"خطأ أثناء التشغيل:\nاستخدام غير صحيح للقيمة أو العملية: {error}"
        return f"خطأ أثناء التشغيل:\nحدث خطأ غير متوقع: {error}"

    header = "خطأ في الباء"
    if error.line is None:
        return f"{header}: {error.message}"

    lines = source.splitlines()
    code_line = lines[error.line - 1] if error.line <= len(lines) else ""
    column = max(1, error.column or 1)
    pointer = " " * (column - 1) + "^"
    return f"{header} في السطر {error.line}، العمود {column}:\n{code_line}\n{pointer}\n{error.message}"
