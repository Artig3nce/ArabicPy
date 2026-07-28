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

            # Words
            if current.isalpha():
                word = ""

                while (
                    self.position < len(self.text)
                    and self.text[self.position].isalpha()
                ):
                    word += self.text[self.position]
                    self.position += 1

                if word in KEYWORDS:
                    tokens.append(Token(KEYWORDS[word], word))
                else:
                    tokens.append(Token("IDENTIFIER", word))

                continue

            # >=
            if current == ">" and self.position + 1 < len(self.text) and self.text[self.position + 1] == "=":
                tokens.append(Token("GREATER_EQUAL", ">="))
                self.position += 2
                continue

            # <=
            if current == "<" and self.position + 1 < len(self.text) and self.text[self.position + 1] == "=":
                tokens.append(Token("LESS_EQUAL", "<="))
                self.position += 2
                continue

            # ==
            if current == "=" and self.position + 1 < len(self.text) and self.text[self.position + 1] == "=":
                tokens.append(Token("EQUAL_EQUAL", "=="))
                self.position += 2
                continue

            # !=
            if current == "!" and self.position + 1 < len(self.text) and self.text[self.position + 1] == "=":
                tokens.append(Token("NOT_EQUAL", "!="))
                self.position += 2
                continue

            # Single characters
            # >=
            if current == ">" and self.position + 1 < len(self.text) and self.text[self.position + 1] == "=":
                tokens.append(Token("GREATER_EQUAL", ">="))
                self.position += 2
                continue

            # <=
            if current == "<" and self.position + 1 < len(self.text) and self.text[self.position + 1] == "=":
                tokens.append(Token("LESS_EQUAL", "<="))
                self.position += 2
                continue

            # ==
            if current == "=" and self.position + 1 < len(self.text) and self.text[self.position + 1] == "=":
                tokens.append(Token("EQUAL_EQUAL", "=="))
                self.position += 2
                continue

            # !=
            if current == "!" and self.position + 1 < len(self.text) and self.text[self.position + 1] == "=":
                tokens.append(Token("NOT_EQUAL", "!="))
                self.position += 2
                continue

            # Single-character tokens
            tokens.append(Token(current, current))
            self.position += 1

        return tokens
