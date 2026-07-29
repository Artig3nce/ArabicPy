import token

from .ast_nodes import Variable
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
    Boolean,
    List,  
    ForStatement,
    Variable,
)



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



    # =====================
    # Expressions
    # =====================

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



        if token.type == "IDENTIFIER":

            name = token.value

            self.advance()


            # function call

            if (
                self.current()
                and self.current().type == "LPAREN"
            ):

                self.advance()

                args = []


                while (
                    self.current()
                    and self.current().type != "RPAREN"
                ):

                    args.append(
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
                    args
                )


            return Variable(name)



        if token.type == "LPAREN":

            self.advance()

            expr = self.parse_expression()

            self.expect("RPAREN")

            return expr



        if token.type == "LBRACKET":

            self.advance()

            elements = []


            while (
                self.current()
                and self.current().type != "RBRACKET"
            ):

                elements.append(
                    self.parse_expression()
                )


                if (
                    self.current()
                    and self.current().type == "COMMA"
                ):

                    self.advance()

                else:
                    break


            self.expect("RBRACKET")


            return List(elements)



        raise Exception(
            f"Unexpected token {token.type}"
        )



    def parse_factor(self):

        left = self.parse_primary()


        while (
            self.current()
            and self.current().type in
            (
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
            and self.current().type in
            (
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



    def parse_expression(self):

        return self.parse_term()



    # =====================
    # Statements
    # =====================

    def parse_statement(self):

        token = self.current()


        if token is None:
            return None



        # print

        if token.type == "PRINT":

            self.advance()

            self.expect("LPAREN")

            value = self.parse_expression()

            self.expect("RPAREN")


            return PrintStatement(value)



        # assignment

        if (
            token.type == "IDENTIFIER"
            and self.peek()
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



        # normal expression

        return self.parse_expression()



    # =====================
    # Program
    # =====================

    def parse(self):

        statements = []


        while self.current():

            if self.current().type == "NEWLINE":

                self.advance()

                continue


            statement = self.parse_statement()


            if statement:

                statements.append(statement)


        return Program(statements)