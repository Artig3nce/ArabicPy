import re


class ArabicPyError(Exception):
    """A language error that can point to a place in ArabicPy source code."""

    def __init__(self, message, line=None, column=None):
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column


def format_error(error, source):
    """Render a compact diagnostic for the IDE and command line."""
    if not isinstance(error, ArabicPyError):
        if isinstance(error, NameError):
            match = re.search(r"name '([^']+)' is not defined", str(error))
            name = match.group(1) if match else "unknown"
            hint = ""
            if name == "اطب":
                hint = "\nDid you mean: اطبع(...) ?"
            return f"Runtime error:\nName not defined: {name}{hint}"
        if isinstance(error, ZeroDivisionError):
            return "Runtime error:\nCannot divide by zero."
        if isinstance(error, TypeError):
            return f"Runtime error:\nIncorrect use of a value or operation: {error}"
        return f"Runtime error:\nAn unexpected error occurred: {error}"

    header = "Al-Baa Error"
    if error.line is None:
        return f"{header}: {error.message}"

    lines = source.splitlines()
    code_line = lines[error.line - 1] if error.line <= len(lines) else ""
    column = max(1, error.column or 1)
    pointer = " " * (column - 1) + "^"
    return f"{header} on line {error.line}, column {column}:\n{code_line}\n{pointer}\n{error.message}"
