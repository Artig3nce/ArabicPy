from ast_nodes import Program, PrintStatement, Assignment


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.position = 0

    def current(self):
        if self.position < len(self.tokens):
            return self.tokens[self.position]
        return None

    def advance(self):
        self.position += 1

    def parse(self):
        statements = []

        while self.current() is not None:
            statement = self.parse_statement()

            if statement:
                statements.append(statement)
            else:
                raise Exception(f"Unexpected token: {self.current()}")

        return Program(statements)

    def parse_statement(self):
        token = self.current()

        # Assignment
        if (
            token
            and token.type == "IDENTIFIER"
            and self.position + 1 < len(self.tokens)
            and self.tokens[self.position + 1] == "="
        ):
            name = token.value

            self.advance()  # identifier
            self.advance()  # =

            value = self.current()

            self.advance()  # value

            return Assignment(name, value)

        # Print
        if token and token.type == "PRINT":
            self.advance()  # PRINT
            self.advance()  # (

            value = self.current()

            self.advance()  # value
            self.advance()  # )

            return PrintStatement(value)

        return None