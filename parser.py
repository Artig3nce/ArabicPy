from astfrom ast_nodes import (
    Program,
    PrintStatement,
    Assignment,
    IfStatement,
    Number,
    String,
    Identifier,
    BinaryOperation,
)


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

    def parse_primary(self):
        token = self.current()

        if token is None:
            return None

        if token.type == "NUMBER":
            self.advance()
            return Number(token.value)

        if token.type == "STRING":
            self.advance()
            return String(token.value)

        if token.type == "IDENTIFIER":
            self.advance()
            return Identifier(token.value)

        if token.type == "TRUE":
            self.advance()
            return Identifier("True")

        if token.type == "FALSE":
            self.advance()
            return Identifier("False")

        return None

    def parse_expression(self):
        left = self.parse_primary()

        token = self.current()

        if (
            token is not None
            and hasattr(token, "value")
            and token.value in ["+", "-", "*", "/"]
        ):
            operator = token.value
            self.advance()

            right = self.parse_primary()

            return BinaryOperation(left, operator, right)

        return left

    def parse_statement(self):
        token = self.current()

        if token is None:
            return None

        # IF
        if token.type == "IF":
            self.advance()

            condition = self.parse_expression()

            if self.current() and self.current().value == ":":
                self.advance()

            body = self.parse_statement()

            return IfStatement(condition, body)

        # Assignment
        if (
            token.type == "IDENTIFIER"
            and self.position + 1 < len(self.tokens)
            and hasattr(self.tokens[self.position + 1], "value")
            and self.tokens[self.position + 1].value == "="
        ):
            name = token.value

            self.advance()
            self.advance()

            value = self.parse_expression()

            return Assignment(name, value)

        # Print
        if token.type == "PRINT":
            self.advance()

            if self.current() and self.current().value == "(":
                self.advance()

            value = self.parse_expression()

            if self.current() and self.current().value == ")":
                self.advance()

            return PrintStatement(value)

        return None

    def parse(self):
        statements = []

        while self.position < len(self.tokens):
            statement = self.parse_statement()

            if statement is not None:
                statements.append(statement)
            else:
                self.advance()

        return Program(statements)
