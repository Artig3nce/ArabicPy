
from .ast_nodes import *

class Generator:

    def clean_name(self, name):
        return name
    def generate(self, node):
        if isinstance(node, Program):

            functions = []
            other = []


            for statement in node.statements:

                if isinstance(statement, FunctionDefinition):
                    functions.append(statement)

                else:
                    other.append(statement)


            code = []


            # functions first
            for function in functions:
                code.append(
                    self.generate(function)
                )


            # calls and normal code after
            for statement in other:
                code.append(
                    self.generate(statement)
                )


            return "\n\n".join(code)
        elif isinstance(node, Block):

            results = []

            for statement in node.statements:
                generated = self.generate(statement)
                print("BLOCK GENERATED:", generated)
                results.append(generated)

            return "\n".join(results)


        elif isinstance(node, PrintStatement):

            return f"print({self.generate(node.value)})"



        elif isinstance(node, Assignment):

            return (
                f"{node.name} = "
                f"{self.generate(node.value)}"
            )



        elif isinstance(node, Variable):

            return self.clean_name(node.name)


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
            print("FUNCTION NAME:", node.name)
            print("FUNCTION BODY:", node.body)
            print("FUNCTION BODY:", node.body.statements)

            params = ", ".join(node.parameters)
            print("PARAMS:", node.parameters)

            params = ", ".join(node.parameters)

            body = self.generate(node.body)

            body = "\n".join(
                "    " + line
                for line in body.splitlines()
            )

            return (
                f"def {self.clean_name(node.name)}({params}):\n"
                f"{body}"
            )

        elif isinstance(node, FunctionCall):

            print("FUNCTION:", node.name)
            print("ARGS:", node.arguments)

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


            return f"{self.clean_name(node.name)}({args})"

        elif isinstance(node, ReturnStatement):

            value = self.generate(node.value)

            print("RETURN:", value)

            return f"return {value}"

        def clean_name(self, name):

            replacements = {
                "أ": "a",
                "ب": "b",
                "ج": "c",
                "د": "d",
                "هـ": "h",
                "و": "w",
                "ي": "y"
            }

            return replacements.get(name, name)