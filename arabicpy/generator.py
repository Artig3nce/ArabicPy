from .ast_nodes import *


class Generator:

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


            for function in functions:
                generated = self.generate(function)
                if generated is not None:
                    code.append(generated)


            for statement in other:
                generated = self.generate(statement)
                if generated is not None:
                    code.append(generated)


            # Keep generated Python visually aligned with ArabicPy: one source
            # statement should occupy one output line without an extra blank
            # line being inserted between every statement.
            return "\n".join(code)



        elif isinstance(node, Block):

            results = []

            for statement in node.statements:
                generated = self.generate(statement)
                if generated is not None:
                    results.append(generated)


            return "\n".join(results)



        elif isinstance(node, PrintStatement):

            return f"print({self.generate(node.value)})"



        elif isinstance(node, Assignment):

            return (
                f"{self.clean_name(node.name)} = "
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


        elif isinstance(node, Dictionary):

            return "{" + ", ".join(
                f"{self.generate(key)}: {self.generate(value)}"
                for key, value in node.pairs
            ) + "}"


        elif isinstance(node, UnaryOperation):

            separator = " " if node.operator == "not" else ""
            return f"{node.operator}{separator}{self.generate(node.operand)}"



        elif isinstance(node, BinaryOperation):

            return (
                f"{self.generate(node.left)} "
                f"{node.operator} "
                f"{self.generate(node.right)}"
            )



        elif isinstance(node, IfStatement):

            body = self.generate(node.then_body) or "pass"

            body = "\n".join(
                "    " + line
                for line in body.splitlines()
            )


            result = (
                f"if {self.generate(node.condition)}:\n"
                f"{body}"
            )


            if node.else_body:

                else_body = self.generate(node.else_body) or "pass"

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

            body = self.generate(node.body) or "pass"

            body = "\n".join(
                "    " + line
                for line in body.splitlines()
            )


            return (
                f"while {self.generate(node.condition)}:\n"
                f"{body}"
            )



        elif isinstance(node, ForStatement):

            body = self.generate(node.body) or "pass"

            body = "\n".join(
                "    " + line
                for line in body.splitlines()
            )


            return (
                f"for {self.clean_name(node.variable)} "
                f"in {self.generate(node.iterable)}:\n"
                f"{body}"
            )



        elif isinstance(node, FunctionDefinition):

            params = ", ".join(
                self.clean_name(x)
                for x in node.parameters
            )


            body = self.generate(node.body) or "pass"

            body = "\n".join(
                "    " + line
                for line in body.splitlines()
            )


            return (
                f"def {self.clean_name(node.name)}({params}):\n"
                f"{body}"
            )



        elif isinstance(node, FunctionCall):

            args = ", ".join(
                self.generate(arg)
                for arg in node.arguments
            )


            if node.name == "ادخل":
                return "input()"

            if node.name == "\u0627\u062f\u062e\u0644":
                return "input()"


            if node.name == "طول":
                return f"len({args})"


            if node.name == "رقم":
                return f"int({args})"


            if node.name == "نوع":
                return f"type({args})"

            # اطبع(اسأل("مرحبا")): a dependency-free, built-in AI helper.
            if node.name == "\u0627\u0633\u0623\u0644":
                return f"albaa_ai_reply({args})"


            return (
                f"{self.clean_name(node.name)}({args})"
            )



        elif isinstance(node, ReturnStatement):

            value = self.generate(node.value)

            return f"return {value}"

        elif isinstance(node, BreakStatement):

            return "break"

        elif isinstance(node, ContinueStatement):

            return "continue"

        elif isinstance(node, PassStatement):

            return "pass"

        elif isinstance(node, IndexAccess):

            return (
                f"{self.generate(node.value)}"
                f"[{self.generate(node.index)}]"
            )

        raise TypeError(f"Cannot generate Python for {type(node).__name__}")
