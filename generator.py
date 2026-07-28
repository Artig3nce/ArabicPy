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


class Generator:

    def generate(self, node):

        # Program
        if isinstance(node, Program):
            return "\n".join(
                self.generate(stmt)
                for stmt in node.statements
            )

        # print(...)
        elif isinstance(node, PrintStatement):
            return f"print({self.generate(node.value)})"

        # variable assignment
        elif isinstance(node, Assignment):
            return f"{node.name} = {self.generate(node.value)}"

        # if statement
        elif isinstance(node, IfStatement):
            condition = self.generate(node.condition)
            body = self.generate(node.body)
            return f"if {condition}:\n    {body}"

        # arithmetic
        elif isinstance(node, BinaryOperation):
            return (
                self.generate(node.left)
                + " "
                + node.operator
                + " "
                + self.generate(node.right)
            )

        # number
        elif isinstance(node, Number):
            return str(node.value)

        # string
        elif isinstance(node, String):
            return repr(node.value)

        # identifier
        elif isinstance(node, Identifier):
            return node.name

        # boolean
        elif isinstance(node, Boolean):
            return "True" if node.value else "False"

        raise Exception(f"Unknown node: {node}")