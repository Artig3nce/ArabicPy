import os
import io
import contextlib
from PySide6.QtWidgets import QInputDialog

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QListWidget,
    QSplitter,
    QInputDialog,
)

from PySide6.QtCore import Qt


from .lexer import Lexer
from .parser import Parser
from .generator import Generator
from .highlighter import ArabicPyHighlighter



class ArabicPyIDE(QMainWindow):

    def __init__(self):

        super().__init__()
        self.current_file = None

        # ======================
        # Window
        # ======================

        self.setWindowTitle(
            "ArabicPy IDE"
        )

        self.resize(
            900,
            700
        )


        # ======================
        # Project
        # ======================

        self.project_path = os.path.join(
            os.getcwd(),
            "projects"
        )

        os.makedirs(
            self.project_path,
            exist_ok=True
        )
        self.current_file = None


        # ======================
        # File Explorer
        # ======================

        self.file_list = QListWidget()

        self.load_files()


        self.file_list.itemClicked.connect(
            self.open_project_file
        )


        # ======================
        # Editor
        # ======================

        self.editor = QTextEdit()

        self.editor.setLayoutDirection(
            Qt.RightToLeft
        )


        self.highlighter = ArabicPyHighlighter(
            self.editor.document()
        )


        self.editor.setPlainText(
            'اطبع("مرحبا من ArabicPy")'
        )



        # ======================
        # Buttons
        # ======================

        self.new_button = QPushButton(
            "جديد 📄"
        )

        self.open_button = QPushButton(
            "فتح 📂"
        )

        self.save_button = QPushButton(
            "حفظ 💾"
        )

        self.run_button = QPushButton(
            "تشغيل ▶"
        )
        self.find_button = QPushButton(
             "بحث 🔍"
        )


        # ======================
        # Output
        # ======================

        self.output = QTextEdit()

        self.output.setReadOnly(
            True
        )



        # ======================
        # Events
        # ======================

        self.new_button.clicked.connect(
            self.new_file
        )

        self.open_button.clicked.connect(
            self.open_file
        )

        self.save_button.clicked.connect(
            self.save_file
        )

        self.run_button.clicked.connect(
            self.run_code
        )

        self.find_button.clicked.connect(
            self.find_text
        )


        # ======================
        # Layout
        # ======================

        splitter = QSplitter()


        splitter.addWidget(
            self.file_list
        )


        splitter.addWidget(
            self.editor
        )


        layout = QVBoxLayout()


        layout.addWidget(
            self.new_button
        )

        layout.addWidget(
            self.find_button
        )

        layout.addWidget(
            self.open_button
        )

        layout.addWidget(
            self.save_button
        )


        layout.addWidget(
            splitter
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



    # ======================
    # Project Files
    # ======================


    def load_files(self):

        self.file_list.clear()


        for file in os.listdir(
            self.project_path
        ):

            if file.endswith(".apy") or file.endswith(".py"):

                self.file_list.addItem(
                    file
                )



    def open_project_file(self, item):

        path = os.path.join(
            self.project_path,
            item.text()
        )


        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            self.editor.setPlainText(
                file.read()
            )

    # ======================
    # File System
    # ======================


    def new_file(self):

        self.current_file = None

        self.editor.clear()



    def open_file(self):

        path, _ = QFileDialog.getOpenFileName(
            self,
            "فتح ملف",
            "",
            "ArabicPy Files (*.apy);;Python Files (*.py);;All Files (*)"
        )


        if path:

            self.current_file = path

            with open(
                path,
                "r",
                encoding="utf-8"
            ) as file:

                self.editor.setPlainText(
                    file.read()
                )



    def save_file(self):

        if self.current_file:

            with open(
                self.current_file,
                "w",
                encoding="utf-8"
            ) as file:

                file.write(
                    self.editor.toPlainText()
                )

            return



        path, _ = QFileDialog.getSaveFileName(
            self,
            "حفظ ملف",
            "",
            "ArabicPy Files (*.apy);;Python Files (*.py)"
        )


        if path:

            self.current_file = path

            with open(
                path,
                "w",
                encoding="utf-8"
            ) as file:

                file.write(
                    self.editor.toPlainText()
                )
    def find_text(self):

        text, ok = QInputDialog.getText(
            self,
            "بحث",
            "ابحث عن:"
        )


        if ok and text:

            cursor = self.editor.textCursor()

            found = self.editor.document().find(
                text,
                cursor
            )


            if not found.isNull():

                self.editor.setTextCursor(
                    found
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


            self.output.setPlainText(
                buffer.getvalue()
            )


        except Exception as error:

            self.output.setPlainText(
                "خطأ:\n" + str(error)
            )

# ======================
# Start
# ======================

if __name__ == "__main__":

    app = QApplication([])

    window = ArabicPyIDE()

    window.show()

    app.exec()