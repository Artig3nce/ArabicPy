from tokens import Token

KEYWORDS = {
    "اذا": "IF",
    "والا": "ELSE",
    "اطبع": "PRINT",
    "بينما": "WHILE",
    "لكل": "FOR",
    "في": "IN",
    "صح": "TRUE",
    "خطأ": "FALSE",
    "كرر": "REPEAT",
    "مرات": "TIMES",
    "دالة": "FUNCTION",
    "ارجع": "RETURN",
}


class Lexer:
    def __init__(self, text):
        self.text = text
        self.position = 0

    def current(self):
        if self.position < len(self.text):
            return self.text[self.position]
        return None

    def advance(self):
        self.position += 1

    def tokenize(self):
        tokens = []

        while self.current() is not None:
            current = self.current()

            # Spaces
            if current == " ":
                self.advance()
                continue

            # Tabs
            if current == "\t":
                self.advance()
                continue

            # New line
            if current == "\n":
                tokens.append(Token("NEWLINE", "\\n"))
                self.advance()
                continue

            # Numbers
            if current.isdigit():
                tokens.append(self.read_number())
                continue

            # Strings
            if current == '"':
                tokens.append(self.read_string())
                continue

            # Words (keywords / identifiers)
            if current.isalpha():
                tokens.append(self.read_identifier())
                continue

            # Operators
            operator = self.read_operator()

            if operator:
                tokens.append(operator)
                continue

            raise Exception(
                f"Unknown character: {repr(current)} "
                f"(Unicode: U+{ord(current):04X}) "
                f"at position {self.position}"
            )

        return tokens

    def read_number(self):
        number = ""

        while self.current() and self.current().isdigit():
            number += self.current()
            self.advance()

        return Token("NUMBER", int(number))

    def read_string(self):
        self.advance()  # Skip opening quote

        string = ""

        while self.current() and self.current() != '"':
            string += self.current()
            self.advance()

        self.advance()  # Skip closing quote

        return Token("STRING", string)

    def read_identifier(self):
        word = ""

        while (
            self.current()
            and (
                self.current().isalpha()
                or self.current().isdigit()
                or self.current() == "_"
            )
        ):
            word += self.current()
            self.advance()

        if word in KEYWORDS:
            return Token(KEYWORDS[word], word)

        return Token("IDENTIFIER", word)

    def read_operator(self):
        current = self.current()

        # Two-character operators
        if (
            current == ">"
            and self.position + 1 < len(self.text)
            and self.text[self.position + 1] == "="
        ):
            self.position += 2
            return Token("GREATER_EQUAL", ">=")

        if (
            current == "<"
            and self.position + 1 < len(self.text)
            and self.text[self.position + 1] == "="
        ):
            self.position += 2
            return Token("LESS_EQUAL", "<=")

        if (
            current == "="
            and self.position + 1 < len(self.text)
            and self.text[self.position + 1] == "="
        ):
            self.position += 2
            return Token("EQUAL_EQUAL", "==")

        if (
            current == "!"
            and self.position + 1 < len(self.text)
            and self.text[self.position + 1] == "="
        ):
            self.position += 2
            return Token("NOT_EQUAL", "!=")

        # Single-character operators
        operators = {
            ">": ("GREATER", ">"),
            "<": ("LESS", "<"),
            "+": ("PLUS", "+"),
            "-": ("MINUS", "-"),
            "*": ("MULTIPLY", "*"),
            "/": ("DIVIDE", "/"),
            "=": ("EQUALS", "="),
            "(": ("LPAREN", "("),
            ")": ("RPAREN", ")"),
            ":": ("COLON", ":"),
            "،": ("COMMA", "،"),
        }

        if current in operators:
            token_type, value = operators[current]
            self.advance()
            return Token(token_type, value)

        return None
        return tokens