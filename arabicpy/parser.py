from .ast_nodes import *
from .tokens import *
(
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
    List,  
    ForStatement,
)


class Parser:

    def __init__(self, tokens):
        self.tokens = tokens
        self.position = 0


    # ==========================
    # Helpers
    # ==========================

    def current(self):
        if self.position >= len(self.tokens):
            return None

        return self.tokens[self.position]


    def peek(self):
        if self.position + 1 >= len(self.tokens):
            return None

        return self.tokens[self.position + 1]


    def advance(self):
        self.position += 1


    def expect(self, token_type):

        token = self.current()

        if token is None:
            raise Exception(
                f"Expected {token_type}, got EOF"
            )

        if token.type != token_type:
            raise Exception(
                f"Expected {token_type}, got {token.type}"
            )

        self.advance()

        return token

        # ==========================
    # Primary Expressions
    # ==========================

    def parse_primary(self):

        token = self.current()

        if token is None:
            raise Exception("Unexpected EOF")


        # Number
        if token.type == "NUMBER":

            self.advance()

            return Number(token.value)


        # String
        if token.type == "STRING":

            self.advance()

            return String(token.value)


        # Boolean
        if token.type == "TRUE":

            self.advance()

            return Boolean(True)


        if token.type == "FALSE":

            self.advance()

            return Boolean(False)


        # Identifier / Function Call
        if token.type == "IDENTIFIER":

            name = token.value

            self.advance()


            # Function call
            if (
                self.current() is not None
                and self.current().type == "LPAREN"
            ):

                self.advance()

                arguments = []


                if (
                    self.current() is not None
                    and self.current().type != "RPAREN"
                ):

                    while True:

                        arguments.append(
                            self.parse_expression()
                        )


                        if (
                            self.current() is not None
                            and self.current().type == "COMMA"
                        ):
                            self.advance()

                        else:
                            break


                self.expect("RPAREN")


                return FunctionCall(
                    name,
                    arguments
                )


            return Identifier(name)



        # Parentheses
        if token.type == "LPAREN":

            self.advance()

            expression = self.parse_expression()

            self.expect("RPAREN")

            return expression
        # List
        if token.type == "LBRACKET":

            self.advance()

            elements = []

            if (
                self.current() is not None
                and self.current().type != "RBRACKET"
            ):

                while True:

                    elements.append(
                        self.parse_expression()
                    )

                    if (
                        self.current() is not None
                        and self.current().type == "COMMA"
                    ):
                        self.advance()

                    else:
                        break


            self.expect("RBRACKET")

            return List(elements)
        # List
        if token.type == "LBRACKET":

            self.advance()

            elements = []

            if (
                self.current() is not None
                and self.current().type != "RBRACKET"
            ):

                while True:

                    elements.append(
                        self.parse_expression()
                    )

                    if (
                        self.current() is not None
                        and self.current().type == "COMMA"
                    ):
                        self.advance()
                    else:
                        break

            self.expect("RBRACKET")

            return List(elements)
        raise Exception(
            f"Unexpected token: {token.type}"
        )



    # ==========================
    # Multiplication / Division
    # ==========================

    def parse_factor(self):

        left = self.parse_primary()


        while (
            self.current() is not None
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
                right
            )


        return left



    # ==========================
    # Addition / Subtraction
    # ==========================

    def parse_term(self):

        left = self.parse_factor()


        while (
            self.current() is not None
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
                right
            )


        return left



    # ==========================
    # Comparisons
    # ==========================

    def parse_comparison(self):

        left = self.parse_term()


        while (
            self.current() is not None
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
                right
            )


        return left



    # ==========================
    # Expression
    # ==========================

    def parse_expression(self):

        return self.parse_comparison()

        # ==========================
    # Block
    # ==========================

    def parse_block(self):

        self.expect("NEWLINE")

        self.expect("INDENT")


        statements = []


        while (
            self.current() is not None
            and self.current().type != "DEDENT"
        ):

            if self.current().type == "NEWLINE":
                self.advance()
                continue


            statement = self.parse_statement()


            if statement is not None:
                statements.append(statement)



        self.expect("DEDENT")


        return statements



    # ==========================
    # Statement
    # ==========================

    def parse_statement(self):

        token = self.current()


        # Skip empty lines
         # --------------------------
        # While
        # --------------------------

        if token.type == "WHILE":

            self.advance()

            condition = self.parse_expression()

            self.expect("COLON")

            body = self.parse_block()


            return WhileStatement(
                condition,
                body
            )
        
        if token is None:
            return None
        # --------------------------
        # Repeat
        # --------------------------

        if token.type == "REPEAT":

            self.advance()

            count = self.parse_expression()

            self.expect("TIMES")

            self.expect("COLON")

            body = self.parse_block()


            return RepeatStatement(
                count,
                body
            )
        # --------------------------
        # For
        # --------------------------

        if token.type == "FOR":

            self.advance()

            variable = self.expect("IDENTIFIER").value

            self.expect("IN")

            iterable = self.parse_expression()

            self.expect("COLON")

            body = self.parse_block()


            return ForStatement(
                variable,
                iterable,
                body
            )

        # --------------------------
        # Function
        # --------------------------

        if token.type == "FUNCTION":

            self.advance()


            name = self.expect(
                "IDENTIFIER"
            ).value


            self.expect("LPAREN")


            parameters = []


            if (
                self.current() is not None
                and self.current().type != "RPAREN"
            ):

                while True:

                    parameters.append(
                        self.expect(
                            "IDENTIFIER"
                        ).value
                    )


                    if (
                        self.current() is not None
                        and self.current().type == "COMMA"
                    ):

                        self.advance()

                    else:
                        break



            self.expect("RPAREN")


            self.expect("COLON")


            body = self.parse_block()


            return FunctionDefinition(
                name,
                parameters,
                body
            )



        # --------------------------
        # Return
        # --------------------------

        if token.type == "RETURN":

            self.advance()


            value = self.parse_expression()


            return ReturnStatement(
                value
            )



        # --------------------------
        # Print
        # --------------------------

        if token.type == "PRINT":

            self.advance()


            self.expect("LPAREN")


            value = self.parse_expression()


            self.expect("RPAREN")


            return PrintStatement(
                value
            )



        # --------------------------
        # Assignment
        # --------------------------

        if (
            token.type == "IDENTIFIER"
            and self.peek() is not None
            and self.peek().type == "EQUALS"
        ):

            name = token.value


            self.advance()

            self.advance()


            value = self.parse_expression()


            return Assignment(
                name,
                value
            )



        # --------------------------
        # --------------------------
        # If
        # --------------------------

        if token.type == "IF":

            self.advance()

            condition = self.parse_expression()

            self.expect("COLON")

            body = self.parse_block()
            print("AFTER IF BLOCK:", self.current())

            else_body = None


            if (
                self.current() is not None
                and self.current().type == "ELSE"
            ):

                self.advance()

                self.expect("COLON")

                else_body = self.parse_block()


            return IfStatement(
                condition,
                body,
                else_body
            )

        # --------------------------
        # While
        # --------------------------

        if token.type == "WHILE":

            self.advance()


            condition = self.parse_expression()


            self.expect("COLON")


            body = self.parse_block()


            return WhileStatement(
                condition,
                body
            )



        # --------------------------
        # Repeat
        # --------------------------

        if token.type == "REPEAT":

            self.advance()


            count = self.parse_expression()


            self.expect("TIMES")


            self.expect("COLON")


            body = self.parse_block()


            return RepeatStatement(
                count,
                body
            )



        raise Exception(
            f"Unexpected token: {token.type}"
        )

        # ==========================
    # Program
    # ==========================

    def parse(self):

        statements = []


        while self.current() is not None:


            # Skip empty lines
            if self.current().type == "NEWLINE":

                self.advance()

                continue



            statement = self.parse_statement()



            if statement is not None:

                statements.append(statement)



        return Program(
            statements
        )