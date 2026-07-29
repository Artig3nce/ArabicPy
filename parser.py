from ast_nodes import (
    Program,
    PrintStatement,
    Assignment,
    IfStatement,
    RepeatStatement,
    WhileStatement,
    FunctionDefinition,
    ReturnStatement,
    FunctionCall,
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

    # -------------------------
    # Helpers
    # -------------------------

    def current(self):
        if self.position < len(self.tokens):
            return self.tokens[self.position]
        return None

    def advance(self):
        self.position += 1

    def expect(self, token_type):
        token = self.current()

        if token is None:
            raise Exception(f"Expected {token_type}")

        if token.type != token_type:
            raise Exception(
                f"Expected {token_type}, got {token.type}"
            )

        self.advance()
        return token

    # -------------------------
    # Primary
    # -------------------------

    def parse_primary(self):
        token = self.current()

        if token is None:
            raise Exception("Unexpected end of input")

        if token.type == "NUMBER":
            self.advance()
            return Number(token.value)

        if token.type == "STRING":
            self.advance()
            return String(token.value)

        if token.type == "IDENTIFIER":
            name = token.value
            self.advance()

            # Function Call
            if (
                self.current()
                and self.current().type == "LPAREN"
            ):
                self.advance()

                arguments = []

                if (
                    self.current()
                    and self.current().type != "RPAREN"
                ):
                    while True:
                        arguments.append(
                            self.parse_expression()
                        )

                        if (
                            self.current()
                            and self.current().type == "COMMA"
                        ):
                            self.advance()
                        else:
                            break

                self.expect("RPAREN")

                return FunctionCall(name, arguments)

            return Identifier(name)

        if token.type == "TRUE":
            self.advance()
            return Boolean(True)

        if token.type == "FALSE":
            self.advance()
            return Boolean(False)

        if token.type == "LPAREN":
            self.advance()

            expression = self.parse_expression()

            self.expect("RPAREN")

            return expression

        raise Exception(
            f"Unexpected token: {token.type}"
        )

    # -------------------------
    # * /
    # -------------------------

    def parse_factor(self):
        left = self.parse_primary()

        while (
            self.current()
            and self.current().type in (
                "MULTIPLY",
                "DIVIDE",
            )
        ):
            operator = self.current().value
            self.advance()

            right = self.parse_primary()

            left = BinaryOperation(
                left,
                operator,
                right,
            )

        return left

    # -------------------------
    # + -
    # -------------------------

    def parse_term(self):
        left = self.parse_factor()

        while (
            self.current()
            and self.current().type in (
                "PLUS",
                "MINUS",
            )
        ):
            operator = self.current().value
            self.advance()

            right = self.parse_factor()

            left = BinaryOperation(
                left,
                operator,
                right,
            )

        return left

    # -------------------------
    # Comparisons
    # -------------------------

    def parse_comparison(self):
        left = self.parse_term()

        while (
            self.current()
            and self.current().type in (
                "GREATER",
                "LESS",
                "GREATER_EQUAL",
                "LESS_EQUAL",
                "EQUAL_EQUAL",
                "NOT_EQUAL",
            )
        ):
            operator = self.current().value
            self.advance()

            right = self.parse_term()

            left = BinaryOperation(
                left,
                operator,
                right,
            )

        return left

    # -------------------------
    # Expression
    # -------------------------

    def parse_expression(self):
        return self.parse_comparison()

        # -------------------------
    # Statement
    # -------------------------

    def parse_statement(self):
        token = self.current()

        if token is None:
            return None

        # -------------------------
        # FUNCTION
        # -------------------------

        if token.type == "FUNCTION":
            self.advance()

            name = self.expect("IDENTIFIER").value

            self.expect("LPAREN")

            parameters = []

            if (
                self.current()
                and self.current().type != "RPAREN"
            ):
                while True:
                    parameters.append(
                        self.expect("IDENTIFIER").value
                    )

                    if (
                        self.current()
                        and self.current().type == "COMMA"
                    ):
                        self.advance()
                    else:
                        break

            self.expect("RPAREN")
            self.expect("COLON")

            body = self.parse_statement()

            return FunctionDefinition(
                name,
                parameters,
                body,
            )

        # -------------------------
        # RETURN
        # -------------------------

        if token.type == "RETURN":
            self.advance()

            value = self.parse_expression()

            return ReturnStatement(value)

        # -------------------------
        # IF
        # -------------------------

        if token.type == "IF":
            self.advance()

            condition = self.parse_expression()

            self.expect("COLON")

            body = self.parse_statement()

            return IfStatement(
                condition,
                body,
            )

        # -------------------------
        # REPEAT
        # -------------------------

        if token.type == "REPEAT":
            self.advance()

            count = self.parse_expression()

            self.expect("TIMES")
            self.expect("COLON")

            body = self.parse_statement()

            return RepeatStatement(
                count,
                body,
            )

        # -------------------------
        # WHILE
        # -------------------------

        if token.type == "WHILE":
            self.advance()

            condition = self.parse_expression()

            self.expect("COLON")

            body = self.parse_statement()

            return WhileStatement(
                condition,
                body,
            )

        # -------------------------
        # Assignment
        # -------------------------

        if (
            token.type == "IDENTIFIER"
            and self.position + 1 < len(self.tokens)
            and self.tokens[self.position + 1].type == "EQUALS"
        ):
            name = token.value

            self.advance()
            self.advance()

            value = self.parse_expression()

            return Assignment(
                name,
                value,
            )

        # -------------------------
        # Print
        # -------------------------

        if token.type == "PRINT":
            self.advance()

            self.expect("LPAREN")

            value = self.parse_expression()

            self.expect("RPAREN")

            return PrintStatement(value)

        return None
    # -------------------------
    # Program
    # -------------------------

    def parse(self):
        statements = []

        while self.current() is not None:

            # Skip blank lines
            if self.current().type == "NEWLINE":
                self.advance()
                continue

            statement = self.parse_statement()

            if statement is None:
                raise Exception(
                    f"Unexpected token: {self.current().type}"
                )

            statements.append(statement)

        return Program(statements)