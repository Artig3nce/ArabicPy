class Node:
    pass


class Statement(Node):
    pass


class Expression(Node):
    pass


class Program(Node):
    def __init__(self, statements):
        self.statements = statements

    def __repr__(self):
        return f"Program({self.statements})"


class Number(Expression):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"Number({self.value})"


class String(Expression):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"String({self.value})"


class Identifier(Expression):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"Identifier({self.name})"


class BinaryOperation(Expression):
    def __init__(self, left, operator, right):
        self.left = left
        self.operator = operator
        self.right = right

    def __repr__(self):
        return f"BinaryOperation({self.left}, {self.operator}, {self.right})"


class Assignment(Statement):
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def __repr__(self):
        return f"Assignment({self.name}, {self.value})"


class PrintStatement(Statement):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"PrintStatement({self.value})"


class IfStatement(Statement):
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body

    def __repr__(self):
        return f"IfStatement({self.condition}, {self.body})"
def parse_statement(self):
    token = self.current()

    if token is None:
        return None

    # IF
    if token.type == "IF":
        self.advance()          # IF

        condition = self.current()
        self.advance()          # condition

        self.advance()          # :

        body = self.parse_statement()

        return IfStatement(condition, body)

    # Assignment
    if (
        token.type == "IDENTIFIER"
        and self.position + 1 < len(self.tokens)
        and self.tokens[self.position + 1] == "="
    ):
        name = token.value

        self.advance()
        self.advance()

        value = self.current()
        self.advance()

        return Assignment(name, value)

    # Print
    if token.type == "PRINT":
        self.advance()
        self.advance()

        value = self.current()
        self.advance()

        self.advance()

        return PrintStatement(value)

    return None

class Number:
    def __init__(self, value):
        self.value = value


class String:
    def __init__(self, value):
        self.value = value


class Identifier:
    def __init__(self, name):
        self.name = name


class Boolean:
    def __init__(self, value):
        self.value = value