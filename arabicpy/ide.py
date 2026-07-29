from .lexer import Lexer
from .parser import Parser
from .generator import Generator
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from PySide6.QtCore import Qt

from lexer import Lexer
from parser import Parser
from generator import Generator

import contextlib
import io


class ArabicPyIDE(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("ArabicPy IDE")
        self.resize(900, 600)


        self.editor = QTextEdit()

        self.editor.setLayoutDirection(
            Qt.RightToLeft
        )


        self.editor.setPlainText(
"""
اطبع("مرحبا من ArabicPy")
"""
        )


        self.run_button = QPushButton(
            "تشغيل ▶"
        )


        self.output = QTextEdit()

        self.output.setReadOnly(True)



        self.run_button.clicked.connect(
            self.run_code
        )


        layout = QVBoxLayout()

        layout.addWidget(
            self.editor
        )

        layout.addWidget(
            self.run_button
        )

        layout.addWidget(
            self.output
        )


        container = QWidget()

        container.setLayout(
            layout
        )

        self.setCentralWidget(
            container
        )



    def run_code(self):

        code = self.editor.toPlainText()


        try:

            lexer = Lexer(code)

            tokens = lexer.tokenize()


            parser = Parser(tokens)

            ast = parser.parse()


            generator = Generator()

            python_code = generator.generate(ast)



            buffer = io.StringIO()


            with contextlib.redirect_stdout(buffer):

                exec(python_code)



            result = buffer.getvalue()


            self.output.setPlainText(
                result
            )



        except Exception as e:

            self.output.setPlainText(
                "Error:\n" + str(e)
            )



app = QApplication([])


window = ArabicPyIDE()

window.show()


app.exec()