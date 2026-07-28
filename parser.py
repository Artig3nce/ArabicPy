from ast_nodes import (
    Program,
    PrintStatement,
    Assignment,
    IfStatement,
    BinaryOperation,
    Number,
    String,
    Identifier,
    Boolean,
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
            return Boolean(True)

        if token.type == "FALSE":
            self.advance()
            return Boolean(False)

        if token.type == "LPAREN":
            self.advance()
            expr = self.parse_expression()

            if self.current() and self.current().type == "RPAREN":
                self.advance()

            return expr

        return None

    def parse_expression(self):
        left = self.parse_primary()

        while self.current() and self.current().type in (
            "PLUS",
            "MINUS",
            "MULTIPLY",
            "DIVIDE",
            "GREATER",
            "LESS",
            "GREATER_EQUAL",
            "LESS_EQUAL",
            "EQUAL_EQUAL",
            "NOT_EQUAL",
        ):
            operator = self.current().value
            self.advance()

            right = self.parse_primary()

            left = BinaryOperation(left, operator, right)

        return left

    def parse_statement(self):
        token = self.current()

        if token is None:
            return None

        # IF
        if token.type == "IF":
            self.advance()

            condition = self.parse_expression()

            if self.current() and self.current().type == "COLON":
                self.advance()

            body = self.parse_statement()

            return IfStatement(condition, body)

        # Assignment
        if (
            token.type == "IDENTIFIER"
            and self.position + 1 < len(self.tokens)
            and self.tokens[self.position + 1].type == "EQUALS"
        ):
            name = token.value

            self.advance()
            self.advance()

            value = self.parse_expression()

            return Assignment(name, value)

        # Print
        if token.type == "PRINT":
            self.advance()

            if self.current() and self.current().type == "LPAREN":
                self.advance()

            value = self.parse_expression()

            if self.current() and self.current().type == "RPAREN":
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