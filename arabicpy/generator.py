#from .ast_nodes import *


class Generator:

    def generate(self, node):

        print("GENERATE:", type(node).__name__, node)


        if isinstance(node, Program):

            code = []

            for statement in node.statements:
                result = self.generate(statement)

                if result:
                    code.append(result)

            return "\n\n".join(code)



        elif isinstance(node, Block):

            return "\n".join(
                self.generate(statement)
                for statement in node.statements
            )



        elif isinstance(node, PrintStatement):

            return f"print({self.generate(node.value)})"



        elif isinstance(node, Assignment):

            return (
                f"{node.name} = "
                f"{self.generate(node.value)}"
            )



        elif isinstance(node, Variable):

            return node.name



        elif isinstance(node, Number):

            return str(node.value)



        elif isinstance(node, String):

            return repr(node.value)



        elif isinstance(node, Boolean):

            return "True" if node.value else "False"



        elif isinstance(node, List):

            return "[" + ", ".join(
                self.generate(x)
                for x in node.elements
            ) + "]"



        elif isinstance(node, BinaryOperation):

            return (
                f"{self.generate(node.left)} "
                f"{node.operator} "
                f"{self.generate(node.right)}"
            )



        elif isinstance(node, IfStatement):

            body = self.generate(node.then_body)

            body = "\n".join(
                "    " + line
                for line in body.splitlines()
            )


            result = (
                f"if {self.generate(node.condition)}:\n"
                f"{body}"
            )


            if node.else_body:

                else_body = self.generate(node.else_body)

                else_body = "\n".join(
                    "    " + line
                    for line in else_body.splitlines()
                )

                result += (
                    f"\nelse:\n"
                    f"{else_body}"
                )


            return result



        elif isinstance(node, WhileStatement):

            body = self.generate(node.body)

            body = "\n".join(
                "    " + line
                for line in body.splitlines()
            )


            return (
                f"while {self.generate(node.condition)}:\n"
                f"{body}"
            )



        elif isinstance(node, RepeatStatement):

            body = self.generate(node.body)

            body = "\n".join(
                "    " + line
                for line in body.splitlines()
            )


            return (
                f"for _ in range({self.generate(node.count)}):\n"
                f"{body}"
            )



        elif isinstance(node, ForStatement):

            body = self.generate(node.body)

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

            body = self.generate(node.body)

            body = "\n".join(
                "    " + line
                for line in body.splitlines()
            )


            return (
                f"def {node.name}():\n"
                f"{body}"
            )
        elif isinstance(node, FunctionCall):

            args = ", ".join(
                self.generate(arg)
                for arg in node.arguments
            )

            return f"{node.name}({args})"



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



        elif isinstance(node, ReturnStatement):

            return (
                f"return "
                f"{self.generate(node.value)}"
            )



        return ""