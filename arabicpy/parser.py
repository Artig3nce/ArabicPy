from .ast_nodes import (
    Assignment, BinaryOperation, Block, Boolean, BreakStatement,
    ContinueStatement, Dictionary, ForStatement, FunctionCall,
    FunctionDefinition, IfStatement, IndexAccess, List, Number,
    PassStatement, PrintStatement, Program, ReturnStatement, String,
    UnaryOperation, Variable, WhileStatement,
)
from .errors import ArabicPyError


class Parser:
    """Recursive-descent parser for the supported ArabicPy grammar."""

    def __init__(self, tokens):
        self.tokens = tokens
        self.position = 0

    def current(self):
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def peek(self, distance=1):
        index = self.position + distance
        return self.tokens[index] if index < len(self.tokens) else None

    def advance(self):
        token = self.current()
        if token is not None:
            self.position += 1
        return token

    def match(self, *token_types):
        token = self.current()
        if token is not None and token.type in token_types:
            self.advance()
            return token
        return None

    def expect(self, token_type):
        token = self.current()
        if token is None:
            previous = self.tokens[-1] if self.tokens else None
            raise ArabicPyError(
                f"انتهى البرنامج قبل الرمز المتوقع: {token_type}",
                getattr(previous, "line", None), getattr(previous, "column", None),
            )
        if token.type != token_type:
            raise ArabicPyError(
                f"المتوقع: {token_type}، لكن وُجد: {token.type}",
                token.line, token.column,
            )
        return self.advance()

    def skip_newlines(self):
        while self.match("NEWLINE"):
            pass

    def parse(self):
        statements = []
        self.skip_newlines()
        while self.current() is not None:
            if self.match("INDENT", "DEDENT"):
                self.skip_newlines()
                continue
            statements.append(self.parse_statement())
            self.skip_newlines()
        return Program(statements)

    def parse_statement(self):
        token = self.current()
        if token is None:
            raise ArabicPyError("تعليمة مفقودة")

        handlers = {
            "IF": self.parse_if,
            "WHILE": self.parse_while,
            "FOR": self.parse_for,
            "FUNCTION": self.parse_function,
        }
        if token.type in handlers:
            return handlers[token.type]()
        if self.match("PRINT"):
            self.expect("LPAREN")
            value = self.parse_expression()
            self.expect("RPAREN")
            return PrintStatement(value)
        if self.match("RETURN"):
            return ReturnStatement(self.parse_expression())
        if self.match("BREAK"):
            return BreakStatement()
        if self.match("CONTINUE"):
            return ContinueStatement()
        if self.match("PASS"):
            return PassStatement()
        if token.type == "IDENTIFIER" and self.peek() and self.peek().type == "EQUALS":
            name = self.advance().value
            self.advance()
            return Assignment(name, self.parse_expression())

        if token.type in ("IDENTIFIER", "LPAREN", "LBRACKET", "LBRACE", "NUMBER", "STRING"):
            return self.parse_expression()

        raise ArabicPyError(f"تعليمة غير متوقعة: {token.value}", token.line, token.column)

    def parse_block(self):
        self.expect("NEWLINE")
        self.skip_newlines()
        self.expect("INDENT")
        statements = []
        self.skip_newlines()
        while self.current() is not None and self.current().type != "DEDENT":
            statements.append(self.parse_statement())
            self.skip_newlines()
        self.expect("DEDENT")
        return Block(statements)

    def parse_if(self):
        self.expect("IF")
        condition = self.parse_expression()
        self.expect("COLON")
        then_body = self.parse_block()
        self.skip_newlines()
        else_body = None
        if self.match("ELSE"):
            self.expect("COLON")
            else_body = self.parse_block()
        return IfStatement(condition, then_body, else_body)

    def parse_while(self):
        self.expect("WHILE")
        condition = self.parse_expression()
        self.expect("COLON")
        return WhileStatement(condition, self.parse_block())

    def parse_for(self):
        self.expect("FOR")
        variable = self.expect("IDENTIFIER").value
        self.expect("IN")
        iterable = self.parse_expression()
        self.expect("COLON")
        return ForStatement(variable, iterable, self.parse_block())

    def parse_function(self):
        self.expect("FUNCTION")
        name = self.expect("IDENTIFIER").value
        self.expect("LPAREN")
        parameters = []
        if self.current() and self.current().type != "RPAREN":
            parameters.append(self.expect("IDENTIFIER").value)
            while self.match("COMMA"):
                parameters.append(self.expect("IDENTIFIER").value)
        self.expect("RPAREN")
        self.expect("COLON")
        return FunctionDefinition(name, parameters, self.parse_block())

    def parse_expression(self):
        return self.parse_or()

    def parse_or(self):
        expression = self.parse_and()
        while self.match("OR"):
            expression = BinaryOperation(expression, "or", self.parse_and())
        return expression

    def parse_and(self):
        expression = self.parse_not()
        while self.match("AND"):
            expression = BinaryOperation(expression, "and", self.parse_not())
        return expression

    def parse_not(self):
        if self.match("NOT"):
            return UnaryOperation("not", self.parse_not())
        return self.parse_comparison()

    def parse_comparison(self):
        expression = self.parse_term()
        comparison_types = {
            "GREATER", "LESS", "EQUAL_EQUAL", "NOT_EQUAL",
            "GREATER_EQUAL", "LESS_EQUAL", "IN",
        }
        while self.current() and self.current().type in comparison_types:
            operator_token = self.advance()
            operator = "in" if operator_token.type == "IN" else operator_token.value
            expression = BinaryOperation(expression, operator, self.parse_term())
        return expression

    def parse_term(self):
        expression = self.parse_factor()
        while self.current() and self.current().type in ("PLUS", "MINUS"):
            operator = self.advance().value
            expression = BinaryOperation(expression, operator, self.parse_factor())
        return expression

    def parse_factor(self):
        expression = self.parse_unary()
        while self.current() and self.current().type in ("MULTIPLY", "DIVIDE"):
            operator = self.advance().value
            expression = BinaryOperation(expression, operator, self.parse_unary())
        return expression

    def parse_unary(self):
        if self.match("MINUS"):
            return UnaryOperation("-", self.parse_unary())
        return self.parse_primary()

    def parse_primary(self):
        token = self.current()
        if token is None:
            raise ArabicPyError("انتهى التعبير بشكل غير متوقع")

        if self.match("NUMBER"):
            value = Number(token.value)
        elif self.match("STRING"):
            value = String(token.value)
        elif self.match("TRUE"):
            value = Boolean(True)
        elif self.match("FALSE"):
            value = Boolean(False)
        elif self.match("IDENTIFIER"):
            value = Variable(token.value)
        elif self.match("LPAREN"):
            value = self.parse_expression()
            self.expect("RPAREN")
        elif self.match("LBRACKET"):
            elements = self.parse_comma_separated("RBRACKET")
            value = List(elements)
        elif self.match("LBRACE"):
            pairs = []
            if self.current() and self.current().type != "RBRACE":
                while True:
                    key = self.parse_expression()
                    self.expect("COLON")
                    pairs.append((key, self.parse_expression()))
                    if not self.match("COMMA"):
                        break
            self.expect("RBRACE")
            value = Dictionary(pairs)
        else:
            raise ArabicPyError(f"رمز غير متوقع: {token.value}", token.line, token.column)

        while True:
            if self.match("LPAREN"):
                if not isinstance(value, Variable):
                    raise ArabicPyError("يمكن استدعاء الدوال بالاسم فقط", token.line, token.column)
                arguments = self.parse_comma_separated("RPAREN")
                value = FunctionCall(value.name, arguments)
            elif self.match("LBRACKET"):
                index = self.parse_expression()
                self.expect("RBRACKET")
                value = IndexAccess(value, index)
            else:
                break
        return value

    def parse_comma_separated(self, closing_type):
        values = []
        if self.current() and self.current().type != closing_type:
            values.append(self.parse_expression())
            while self.match("COMMA"):
                values.append(self.parse_expression())
        self.expect(closing_type)
        return values
