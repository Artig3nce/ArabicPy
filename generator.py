from ast_nodes import (
    Program,
    Block,
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

        # Block
        elif isinstance(node, Block):
            return "\n".join(
                self.generate(stmt)
                for stmt in node.statements
            )

        # Print
        elif isinstance(node, PrintStatement):
            return f"print({self.generate(node.value)})"

        # Assignment
        elif isinstance(node, Assignment):
            return f"{node.name} = {self.generate(node.value)}"

        # If statement
        elif isinstance(node, IfStatement):
            condition = self.generate(node.condition)

            body = "\n".join(
                "    " + line
                for line in self.generate(node.body).splitlines()
            )

            return f"if {condition}:\n{body}"

        # Binary operation
        elif isinstance(node, BinaryOperation):
            return (
                self.generate(node.left)
                + " "
                + node.operator
                + " "
                + self.generate(node.right)
            )

        # Number
        elif isinstance(node, Number):
            return str(node.value)

        # String
        elif isinstance(node, String):
            return repr(node.value)

        # Identifier
        elif isinstance(node, Identifier):
            return node.name

        # Boolean
        elif isinstance(node, Boolean):
            return "True" if node.value else "False"

        raise Exception(f"Unknown node: {node}")