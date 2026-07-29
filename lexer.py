from tokens import Token

KEYWORDS = {
    "اذا": "IF",
    "والا": "ELSE",
    "اطبع": "PRINT",
    "بينما": "WHILE",
    "كرر": "REPEAT",
    "مرات": "TIMES",
    "لكل": "FOR",
    "في": "IN",
    "صح": "TRUE",
    "خطأ": "FALSE",
    "دالة": "FUNCTION",
    "ارجع": "RETURN",
}


class Lexer:

    def __init__(self, text):
        self.text = text
        self.position = 0

    def current(self):
        if self.position >= len(self.text):
            return None
        return self.text[self.position]

    def peek(self):
        if self.position + 1 >= len(self.text):
            return None
        return self.text[self.position + 1]

    def advance(self):
        self.position += 1

    def tokenize(self):
        tokens = []

        while self.current() is not None:

            current = self.current()

            # Ignore spaces
            if current in " \t\r":
                self.advance()
                continue

            # New line
            if current == "\n":
                tokens.append(Token("NEWLINE", "\\n"))
                self.advance()
                continue

            # Number
            if current.isdigit():
                tokens.append(self.read_number())
                continue

            # String
            if current == '"':
                tokens.append(self.read_string())
                continue

            # Identifier / Keyword
            if current.isalpha() or current == "_":
                tokens.append(self.read_identifier())
                continue

            # Operator
            operator = self.read_operator()

            if operator:
                tokens.append(operator)
                continue

            raise Exception(
                f"Unknown character: {repr(current)} "
                f"(U+{ord(current):04X})"
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

        while self.current() is not None and self.current() != '"':
            string += self.current()
            self.advance()

        if self.current() != '"':
            raise Exception("Unterminated string")

        self.advance()  # Skip closing quote

        return Token("STRING", string)


    def read_identifier(self):
        word = ""

        while (
            self.current() is not None
            and (
                self.current().isalnum()
                or self.current() == "_"
                or self.current().isalpha()
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
        if current == ">" and self.peek() == "=":
            self.advance()
            self.advance()
            return Token("GREATER_EQUAL", ">=")

        if current == "<" and self.peek() == "=":
            self.advance()
            self.advance()
            return Token("LESS_EQUAL", "<=")

        if current == "=" and self.peek() == "=":
            self.advance()
            self.advance()
            return Token("EQUAL_EQUAL", "==")

        if current == "!" and self.peek() == "=":
            self.advance()
            self.advance()
            return Token("NOT_EQUAL", "!=")

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
            ",": ("COMMA", ","),
            "،": ("COMMA", "،"),
        }

        if current in operators:
            token_type, value = operators[current]
            self.advance()
            return Token(token_type, value)

        return None