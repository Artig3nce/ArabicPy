from .tokens import Token


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

        indent_stack = [0]
        start_of_line = True


        while self.current() is not None:


            # indentation
            if start_of_line:

                spaces = 0

                while self.current() == " ":
                    spaces += 1
                    self.advance()


                if self.current() == "\n":

                    tokens.append(
                        Token("NEWLINE", "\\n")
                    )

                    self.advance()
                    continue


                current_indent = indent_stack[-1]


                if spaces > current_indent:

                    indent_stack.append(spaces)

                    tokens.append(
                        Token("INDENT", spaces)
                    )


                elif spaces < current_indent:


                    while spaces < indent_stack[-1]:

                        indent_stack.pop()

                        tokens.append(
                            Token("DEDENT", spaces)
                        )


                start_of_line = False



            current = self.current()



            # comments

            if current == "#":

                while (
                    self.current()
                    and self.current() != "\n"
                ):
                    self.advance()

                continue



            # newline

            if current == "\n":

                tokens.append(
                    Token("NEWLINE", "\\n")
                )

                self.advance()

                start_of_line = True

                continue



            # spaces

            if current in " \t\r":

                self.advance()

                continue



            # numbers

            if current.isdigit():

                tokens.append(
                    self.read_number()
                )

                continue



            # strings

            if current == '"':

                tokens.append(
                    self.read_string()
                )

                continue



            # identifiers / keywords

            if (
                current.isalpha()
                or current == "_"
                or "\u0600" <= current <= "\u06FF"
            ):

                tokens.append(
                    self.read_identifier()
                )

                continue



            # operators

            operator = self.read_operator()


            if operator:

                tokens.append(operator)

                continue



            raise Exception(
                f"Unknown character: {current}"
            )



        while len(indent_stack) > 1:

            indent_stack.pop()

            tokens.append(
                Token("DEDENT", 0)
            )


        return tokens




    def read_number(self):

        number = ""


        while (
            self.current()
            and self.current().isdigit()
        ):

            number += self.current()

            self.advance()


        return Token(
            "NUMBER",
            int(number)
        )




    def read_string(self):

        self.advance()

        string = ""


        while (
            self.current()
            and self.current() != '"'
        ):

            string += self.current()

            self.advance()



        if self.current() != '"':

            raise Exception(
                "Unterminated string"
            )


        self.advance()


        return Token(
            "STRING",
            string
        )




    def read_identifier(self):

        word = ""


        while (
            self.current()
            and (
                self.current().isalnum()
                or self.current() == "_"
                or "\u0600" <= self.current() <= "\u06FF"
            )
        ):

            word += self.current()

            self.advance()



        if word in KEYWORDS:

            token_type = KEYWORDS[word]

        else:

            token_type = "IDENTIFIER"



        return Token(
            token_type,
            word
        )





    def read_operator(self):

        current = self.current()



        if current == "=" and self.peek() == "=":

            self.advance()
            self.advance()

            return Token(
                "EQUAL_EQUAL",
                "=="
            )



        if current == "!" and self.peek() == "=":

            self.advance()
            self.advance()

            return Token(
                "NOT_EQUAL",
                "!="
            )



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

            "[": ("LBRACKET", "["),
            "]": ("RBRACKET", "]"),

        }



        if current in operators:

            token_type, value = operators[current]

            self.advance()

            return Token(
                token_type,
                value
            )


        return None