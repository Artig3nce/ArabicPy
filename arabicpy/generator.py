from .ast_nodes import *
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


            body = "\n".join(
                self.generate(statement)
                for statement in node.then_body
            )


            body = "\n".join(
                "    " + line
                for line in body.splitlines()
            )


            result = f"if {condition}:\n{body}"


            if node.else_body:

                else_body = "\n".join(
                    self.generate(statement)
                    for statement in node.else_body
                )


                else_body = "\n".join(
                    "    " + line
                    for line in else_body.splitlines()
                )


                result += f"\nelse:\n{else_body}"


            return result


            return result
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

            body = "\n".join(
                self.generate(statement)
                for statement in node.body
            )

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
        # While
        # -------------------------
        elif isinstance(node, WhileStatement):

            condition = self.generate(node.condition)


            body = "\n".join(
                self.generate(statement)
                for statement in node.body
            )


            body = "\n".join(
                "    " + line
                for line in body.splitlines()
            )


            return f"while {condition}:\n{body}"
                # -------------------------
        # For Loop
        # -------------------------
        elif isinstance(node, ForStatement):

            iterable = self.generate(node.iterable)

            body = "\n".join(
                self.generate(statement)
                for statement in node.body
            )

            body = "\n".join(
                "    " + line
                for line in body.splitlines()
            )

            return f"for {node.variable} in {iterable}:\n{body}"
        # -------------------------
        # Function Definition
        # -------------------------
        elif isinstance(node, FunctionDefinition):
            parameters = ", ".join(node.parameters)

            body = "\n".join(
                self.generate(statement)
                for statement in node.body
            )

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
            if node.name == "ادخل":
              return "input()"

            if node.name == "نوع":
             return f"type({self.generate(node.arguments[0])})"

            if node.name == "رقم":
                return f"int({self.generate(node.arguments[0])})"           
            if node.name == "طول":
                return f"len({arguments})"

            return f"{node.name}({arguments})"


            # Built-in functions
            if node.name == "طول":
                return f"len({arguments})"


            return f"{node.name}({arguments})"

                # -------------------------
        # List
        # -------------------------
        elif isinstance(node, List):

            return "[" + ", ".join(
                self.generate(element)
                for element in node.elements
            ) + "]"