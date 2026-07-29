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


class Generator:
    def generate(self, node):

        # -------------------------
        # Program
        # -------------------------
        if isinstance(node, Program):
            return "\n".join(
                self.generate(statement)
                for statement in node.statements
            )

        # -------------------------
        # Print
        # -------------------------
        elif isinstance(node, PrintStatement):
            return f"print({self.generate(node.value)})"

        # -------------------------
        # Assignment
        # -------------------------
        elif isinstance(node, Assignment):
            return f"{node.name} = {self.generate(node.value)}"

        # -------------------------
        # If
        # -------------------------
        elif isinstance(node, IfStatement):
            condition = self.generate(node.condition)

            body = self.generate(node.then_body)

            body = "\n".join(
                "    " + line
                for line in body.splitlines()
            )

            return f"if {condition}:\n{body}"

        # -------------------------
        # Repeat
        # -------------------------
        elif isinstance(node, RepeatStatement):
            count = self.generate(node.count)

            body = self.generate(node.body)

            body = "\n".join(
                "    " + line
                for line in body.splitlines()
            )

            return f"for _ in range({count}):\n{body}"

        # -------------------------
        # Binary Operations
        # -------------------------
        elif isinstance(node, BinaryOperation):
            left = self.generate(node.left)
            right = self.generate(node.right)

            return f"{left} {node.operator} {right}"

        # -------------------------
        # Literals
        # -------------------------
        elif isinstance(node, Number):
            return str(node.value)

        elif isinstance(node, String):
            return repr(node.value)

        elif isinstance(node, Identifier):
            return node.name

        elif isinstance(node, Boolean):
            return "True" if node.value else "False"

                # -------------------------
                        # -------------------------
        # While
        # -------------------------
        elif isinstance(node, WhileStatement):
            condition = self.generate(node.condition)

            body = self.generate(node.body)

            body = "\n".join(
                "    " + line
                for line in body.splitlines()
            )

            return f"while {condition}:\n{body}"

        # -------------------------
        # Function Definition
        # -------------------------
        elif isinstance(node, FunctionDefinition):
            parameters = ", ".join(node.parameters)

            body = self.generate(node.body)

            body = "\n".join(
                "    " + line
                for line in body.splitlines()
            )

            return f"def {node.name}({parameters}):\n{body}"

        # -------------------------
        # Return
        # -------------------------
        elif isinstance(node, ReturnStatement):
            return f"return {self.generate(node.value)}"

        # -------------------------
        # Function Call
        # -------------------------
        elif isinstance(node, FunctionCall):
            arguments = ", ".join(
                self.generate(argument)
                for argument in node.arguments
            )

            return f"{node.name}({arguments})"

        raise Exception(
            f"Unknown node type: {type(node).__name__}"
        )