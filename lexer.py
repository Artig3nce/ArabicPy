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
    "دالة": "DEF",
    "ارجع": "RETURN",
}


class Lexer:
    def __init__(self, text):
        self.text = text
        self.position = 0

    def tokenize(self):
        tokens = []

        while self.position < len(self.text):
            current = self.text[self.position]

            # Skip spaces
            if current.isspace():
                self.position += 1
                continue

            # Numbers
            if current.isdigit():
                number = ""

                while (
                    self.position < len(self.text)
                    and self.text[self.position].isdigit()
                ):
                    number += self.text[self.position]
                    self.position += 1

                tokens.append(Token("NUMBER", int(number)))
                continue

            # Strings
            if current == '"':
                self.position += 1
                string = ""

                while (
                    self.position < len(self.text)
                    and self.text[self.position] != '"'
                ):
                    string += self.text[self.position]
                    self.position += 1

                self.position += 1
                tokens.append(Token("STRING", string))
                continue
                        # Words (Arabic identifiers and keywords)
            if current.isalpha():
                word = ""

                while (
                    self.position < len(self.text)
                    and (
                        self.text[self.position].isalpha()
                        or self.text[self.position].isdigit()
                        or self.text[self.position] == "_"
                    )
                ):
                    word += self.text[self.position]
                    self.position += 1

                if word in KEYWORDS:
                    tokens.append(Token(KEYWORDS[word], word))
                else:
                    tokens.append(Token("IDENTIFIER", word))

                continue
            # Two-character operators
            if current == ">" and self.position + 1 < len(self.text) and self.text[self.position + 1] == "=":
                tokens.append(Token("GREATER_EQUAL", ">="))
                self.position += 2
                continue

            if current == "<" and self.position + 1 < len(self.text) and self.text[self.position + 1] == "=":
                tokens.append(Token("LESS_EQUAL", "<="))
                self.position += 2
                continue

            if current == "=" and self.position + 1 < len(self.text) and self.text[self.position + 1] == "=":
                tokens.append(Token("EQUAL_EQUAL", "=="))
                self.position += 2
                continue

            if current == "!" and self.position + 1 < len(self.text) and self.text[self.position + 1] == "=":
                tokens.append(Token("NOT_EQUAL", "!="))
                self.position += 2
                continue

            # Single-character operators
            if current == ">":
                tokens.append(Token("GREATER", ">"))
                self.position += 1
                continue

            if current == "<":
                tokens.append(Token("LESS", "<"))
                self.position += 1
                continue

            if current == "+":
                tokens.append(Token("PLUS", "+"))
                self.position += 1
                continue

            if current == "-":
                tokens.append(Token("MINUS", "-"))
                self.position += 1
                continue

            if current == "*":
                tokens.append(Token("MULTIPLY", "*"))
                self.position += 1
                continue

            if current == "/":
                tokens.append(Token("DIVIDE", "/"))
                self.position += 1
                continue

            if current == "=":
                tokens.append(Token("EQUALS", "="))
                self.position += 1
                continue

            if current == "(":
                tokens.append(Token("LPAREN", "("))
                self.position += 1
                continue

            if current == ")":
                tokens.append(Token("RPAREN", ")"))
                self.position += 1
                continue

            if current == ":":
                tokens.append(Token("COLON", ":"))
                self.position += 1
                continue
            # Arabic comma
            if current == "،":
                tokens.append(Token("COMMA", "،"))
                self.position += 1
                continue
            # Unknown character
            raise Exception(
                f"Unknown character: {repr(current)} (Unicode: U+{ord(current):04X}) at position {self.position}"
            )
        return tokens
