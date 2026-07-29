class Program:
    def __init__(self, statements):
        self.statements = statements

    def __repr__(self):
        return f"Program({self.statements})"


class Block:
    def __init__(self, statements):
        self.statements = statements

    def __repr__(self):
        return f"Block({self.statements})"


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
        return (
            f"IfStatement("
            f"{self.condition}, "
            f"{self.body})"
        )

class RepeatStatement:
    def __init__(self, count, body):
        self.count = count
        self.body = body

    def __repr__(self):
        return f"RepeatStatement({self.count}, {self.body})"


class BinaryOperation:
    def __init__(self, left, operator, right):
        self.left = left
        self.operator = operator
        self.right = right

    def __repr__(self):
        return (
            f"BinaryOperation("
            f"{self.left}, "
            f"'{self.operator}', "
            f"{self.right})"
        )


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


class WhileStatement:
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body

    def __repr__(self):
        return f"WhileStatement({self.condition}, {self.body})"   

class FunctionDefinition:
    def __init__(self, name, parameters, body):
        self.name = name
        self.parameters = parameters
        self.body = body

    def __repr__(self):
        return (
            f"FunctionDefinition("
            f"{self.name}, "
            f"{self.parameters}, "
            f"{self.body})"
        )


class ReturnStatement:
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"ReturnStatement({self.value})"


class FunctionCall:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments

    def __repr__(self):
        return (
            f"FunctionCall("
            f"{self.name}, "
            f"{self.arguments})"
        )    


class IfStatement:
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body