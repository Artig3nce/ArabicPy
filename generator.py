from ast_nodes import Program, PrintStatement, Assignment, IfStatement

class Generator:
    def generate(self, node):

        if isinstance(node, Program):
            return "\n".join(self.generate(stmt) for stmt in node.statements)

        elif isinstance(node, PrintStatement):
            return f"print({self.generate(node.value)})"

        elif isinstance(node, Assignment):
            return f"{node.name} = {self.generate(node.value)}"

        elif isinstance(node, IfStatement):
            condition = self.generate(node.condition)
            body = self.generate(node.body)
            return f"if {condition}:\n    {body}"

        elif hasattr(node, "type"):

            if node.type == "STRING":
                return repr(node.value)

            elif node.type == "NUMBER":
                return str(node.value)

            elif node.type == "IDENTIFIER":
                return node.value

            elif node.type == "TRUE":
                return "True"

            elif node.type == "FALSE":
                return "False"

        raise Exception(f"Unknown node: {node}")
