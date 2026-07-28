class Program:
    def __init__(self, statements):
        self.statements = statements

class Block:
    def __init__(self, statements):
        self.statements = statements

    def __repr__(self):
        return f"Block({self.statements})"
class Block:
    def __init__(self, statements):
        self.statements = statements


class PrintStatement:
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"PrintStatement({self.value})"


class Assignment:
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def __repr__(self):
        return f"Assignment({self.name}, {self.value})"


class IfStatement:
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body

    def __repr__(self):
        return f"IfStatement({self.condition}, {self.body})"


class BinaryOperation:
    def __init__(self, left, operator, right):
        self.left = left
        self.operator = operator
        self.right = right

    def __repr__(self):
        return f"BinaryOperation({self.left}, {self.operator}, {self.right})"


class Number:
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"Number({self.value})"


class String:
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"String({self.value})"


class Identifier:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"Identifier({self.name})"


class Boolean:
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"Boolean({self.value})"