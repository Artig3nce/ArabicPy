from .tokens import Token
from .errors import ArabicPyError


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
    "و": "AND",
    "او": "OR",
    "أو": "OR",
    "ليس": "NOT",
    "توقف": "BREAK",
    "استمر": "CONTINUE",
    "تجاوز": "PASS",
}


class Lexer:

    def __init__(self, code):
        self.code = code
        self.position = 0


    def current(self):

        if self.position >= len(self.code):
            return None

        return self.code[self.position]


    def advance(self):
        self.position += 1

    def make_token(self, token_type, value, position=None):
        position = self.position if position is None else position
        return Token(
            token_type, value,
            self.code.count("\n", 0, position) + 1,
            position - self.code.rfind("\n", 0, position),
        )



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
                        self.make_token("NEWLINE", "\\n")
                    )

                    self.advance()
                    continue


                current_indent = indent_stack[-1]


                if spaces > current_indent:

                    indent_stack.append(spaces)

                    tokens.append(
                        self.make_token("INDENT", spaces)
                    )


                elif spaces < current_indent:

                    while spaces < indent_stack[-1]:

                        indent_stack.pop()

                        tokens.append(
                            self.make_token("DEDENT", spaces)
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
                    self.make_token("NEWLINE", "\\n")
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



            # identifiers
            if (
                current.isalpha()
                or current == "_"
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



            raise ArabicPyError(f"رمز غير معروف: {current}", *self.location())



        while len(indent_stack) > 1:

            indent_stack.pop()

            tokens.append(
                self.make_token("DEDENT", 0)
            )


        return tokens





    def read_number(self):
        start = self.position
        number = ""


        while (
            self.current()
            and self.current().isdigit()
        ):

            number += self.current()

            self.advance()


        return self.make_token(
            "NUMBER",
            int(number), start
        )




    def read_string(self):
        start = self.position
        self.advance()

        value = ""


        while (
            self.current()
            and self.current() != '"'
        ):

            value += self.current()

            self.advance()


        if self.current() != '"':
            raise ArabicPyError("نص غير مغلق بعلامة اقتباس", *self.location(start))

        self.advance()


        return self.make_token(
            "STRING",
            value, start
        )





    def read_identifier(self):
        start = self.position
        word = ""


        while (
            self.current()
            and (
                self.current().isalnum()
                or self.current() == "_"
            )
        ):

            word += self.current()

            self.advance()



        if word in KEYWORDS:

            token_type = KEYWORDS[word]

        else:

            token_type = "IDENTIFIER"



        return self.make_token(
            token_type,
            word, start
        )





    def read_operator(self):
        start = self.position
        current = self.current()

        two_character_operators = {
            "==": ("EQUAL_EQUAL", "=="),
            "!=": ("NOT_EQUAL", "!="),
            ">=": ("GREATER_EQUAL", ">="),
            "<=": ("LESS_EQUAL", "<="),
        }
        pair = self.code[self.position:self.position + 2]
        if pair in two_character_operators:
            token_type, value = two_character_operators[pair]
            self.advance()
            self.advance()
            return self.make_token(token_type, value, start)


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
            "{": ("LBRACE", "{"),
            "}": ("RBRACE", "}"),
        }



        if current in operators:

            token_type, value = operators[current]

            self.advance()


            return self.make_token(
                token_type,
                value, start
            )


        return None

    def location(self, position=None):
        position = self.position if position is None else position
        return (
            self.code.count("\n", 0, position) + 1,
            position - self.code.rfind("\n", 0, position),
        )
