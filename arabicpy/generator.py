from .ast_nodes import *


class Generator:

    def generate(self, node):

        print("GENERATE:", type(node).__name__, node)


        if isinstance(node, Program):

            return "\n".join(
                self.generate(statement)
                for statement in node.statements
            )


        elif isinstance(node, PrintStatement):

            return f"print({self.generate(node.value)})"


        elif isinstance(node, Assignment):

            return f"{node.name} = {self.generate(node.value)}"


        elif isinstance(node, Variable):

            return node.name


        elif isinstance(node, Number):

            return str(node.value)


        elif isinstance(node, String):

            return repr(node.value)


        elif isinstance(node, Boolean):

            return "True" if node.value else "False"


        elif isinstance(node, BinaryOperation):

            return (
                f"{self.generate(node.left)} "
                f"{node.operator} "
                f"{self.generate(node.right)}"
            )


        elif isinstance(node, List):

            return "[" + ", ".join(
                self.generate(item)
                for item in node.elements
            ) + "]"

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



        elif isinstance(node, ForStatement):

            body = "\n".join(
                self.generate(statement)
                for statement in node.body
            )

            body = "\n".join(
                "    " + line
                for line in body.splitlines()
            )

            return (
                f"for {node.variable} "
                f"in {self.generate(node.iterable)}:\n"
                f"{body}"
            )



        elif isinstance(node, FunctionDefinition):
 

            params = ", ".join(node.parameters)

            body = "\n".join(
                self.generate(statement)
                for statement in node.body
            )

            body = "\n".join(
                "    " + line
                for line in body.splitlines()
            )

            return f"def {node.name}({params}):\n{body}"

        

        elif isinstance(node, ReturnStatement):

            return f"return {self.generate(node.value)}"



        elif isinstance(node, FunctionCall):

            args = ", ".join(
                self.generate(arg)
                for arg in node.arguments
            )


            if node.name == "ادخل":
                return "input()"


            if node.name == "طول":
                return f"len({args})"


            if node.name == "رقم":
                return f"int({args})"


            if node.name == "نوع":
                return f"type({args})"


            return f"{node.name}({args})"



        print("UNKNOWN NODE:", type(node))

        return ""

