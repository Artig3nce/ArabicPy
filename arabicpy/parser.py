print("LOADED PARSER FILE")
from .ast_nodes import *

class Parser:

    def __init__(self, tokens):
        self.tokens = tokens
        self.position = 0
    

    # =====================
    # Helpers
    # =====================

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
    

    def parse_factor(self):

        left = self.parse_primary()

        while (
            self.current()
            and self.current() and self.current().type in (
                "MULTIPLY",
                "DIVIDE"
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



    def parse_term(self):

        left = self.parse_factor()

        while (
            self.current()
            and self.current() and self.current().type in (
                "PLUS",
                "MINUS"
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



    def parse_comparison(self):

        left = self.parse_term()

        while (
            self.current()
            and self.current() and self.current().type in (
                "GREATER",
                "LESS",
                "EQUAL_EQUAL",
                "NOT_EQUAL",
                "GREATER_EQUAL",
                "LESS_EQUAL"
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



    def parse_expression(self):

        return self.parse_comparison()

    # =====================
    # Blocks
    # =====================

    def parse_block(self):

        body = []


        if (
            self.current()
            and self.current() and self.current().type == "NEWLINE"
        ):
            self.advance()


        if (
            self.current()
            and self.current() and self.current().type == "INDENT"
        ):
            self.advance()



        while (
            self.current()
            and self.current() and self.current().type != "DEDENT"
        ):

            if self.current() and self.current().type == "NEWLINE":

                self.advance()
                continue
                        
            if self.current() and self.current().type == "FUNCTION":
                return self.parse_function()

            statement = self.parse_statement()


            if statement:

                body.append(statement)



        if (
            self.current()
            and self.current() and self.current().type == "DEDENT"
        ):

            self.advance()



        return body
        
    def parse_primary(self):

        token = self.current()

        if token is None:
            raise Exception("Unexpected EOF")


        if token.type == "NUMBER":

            self.advance()

            return Number(token.value)


        if token.type == "STRING":

            self.advance()

            return String(token.value)


        if token.type == "TRUE":

            self.advance()

            return Boolean(True)


        if token.type == "FALSE":

            self.advance()

            return Boolean(False)


        # =====================
        # Identifier
        # Variable or Function Call
        # =====================

        if token.type == "IDENTIFIER":

            name = token.value

            self.advance()


            # Function Call
            if self.current() and self.current().type == "LPAREN":

                self.advance()

                arguments = []


                while (
                    self.current()
                    and self.current().type != "RPAREN"
                ):

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


                return FunctionCall(
                    name,
                    arguments
                )


            # Normal Variable

            return Variable(name)



        # =====================
        # Parentheses
        # =====================

        if token.type == "LPAREN":

            self.advance()

            value = self.parse_expression()

            self.expect("RPAREN")

            return value



        raise Exception(
            f"Unexpected token {token.type}"
        )

        # =====================
        # Function
        # =====================
    def parse_function(self):

        self.advance()  # FUNCTION

        name = self.expect("IDENTIFIER").value

        self.expect("LPAREN")
        self.expect("RPAREN")
        self.expect("COLON")


        if self.current() and self.current().type == "NEWLINE":
            self.advance()


        if self.current() and self.current().type == "INDENT":
            self.advance()


        statements = []


        while self.current() and self.current().type != "DEDENT":

            if self.current().type == "NEWLINE":
                self.advance()
                continue


            old_position = self.position

            statement = self.parse_statement()

            if statement:
                statements.append(statement)


            if self.position == old_position:
                print("FUNCTION STUCK AT:", self.current())
                self.advance()


        if self.current() and self.current().type == "DEDENT":
            self.advance()


        return FunctionDefinition(
            name,
            [],
            Block(statements)
        )

    # =====================
    # Statements
    # =====================

    def parse_statement(self):

        token = self.current()


        if token is None:

            return None



        if token.type == "NEWLINE":

            self.advance()

            return None



        # FUNCTION

        if token.type == "FUNCTION":

            return self.parse_function()
        # PRINT

        if token.type == "PRINT":

            self.advance()


            self.expect("LPAREN")


            value = self.parse_expression()


            self.expect("RPAREN")


            return PrintStatement(
                value
            )



        # RETURN

        if token.type == "RETURN":

            self.advance()


            value = self.parse_expression()


            return ReturnStatement(
                value
            )



        # IF

        if token.type == "IF":

            self.advance()


            condition = self.parse_expression()


            self.expect("COLON")


            body = self.parse_block()


            else_body = None


            if (
                self.current()
                and self.current() and self.current().type == "ELSE"
            ):

                self.advance()


                self.expect("COLON")


                else_body = self.parse_block()



            return IfStatement(
                condition,
                body,
                else_body
            )
        
        return None
    # =====================
    # Assignment
    # =====================

    def parse_assignment(self):

        name = self.expect(
            "IDENTIFIER"
        ).value


        self.expect(
            "EQUALS"
        )


        value = self.parse_expression()


        return Assignment(
            name,
            value
        )



    # =====================
    # Program
    # =====================
    def parse(self):

        statements = []

        limit = 0

        while self.current():

            limit += 1

            if limit > 1000:
                raise Exception(
                    "Parser stuck at: " + str(self.current())
                )

            if self.current() and self.current().type in (
                "NEWLINE",
                "INDENT",
                "DEDENT"
            ):
                self.advance()
                continue

            # assignment

            if (
                self.current() and self.current().type == "IDENTIFIER"
                and self.peek()
                and self.peek().type == "EQUALS"
            ):

                statement = self.parse_assignment()


            else:

                statement = self.parse_statement()
        
            # function call

            if (
                self.current() and self.current().type == "IDENTIFIER"
                and self.peek().type == "LPAREN"
            ):

                statement = self.parse_expression()

                return statement


            if statement:

                statements.append(
                    statement
                )
        print("BEFORE RETURN")
        print(Program)
        return Program(
            statements
        )        