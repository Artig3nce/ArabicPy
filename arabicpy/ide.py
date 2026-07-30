import os
import io
import contextlib

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QTextEdit,
    QPushButton,
    QFileDialog,
    QListWidget,
    QSplitter,
    QVBoxLayout,
    QHBoxLayout,
    QInputDialog,
    QFrame,
)

from PySide6.QtCore import Qt

from .lexer import Lexer
from .parser import Parser
from .generator import Generator
from .highlighter import ArabicPyHighlighter



# =========================
# Title Bar
# =========================

class TitleBar(QWidget):

    def __init__(self, parent):
        super().__init__(parent)

        self.parent = parent
        self.old_pos = None

        self.setFixedHeight(35)

        layout = QHBoxLayout()
        layout.setContentsMargins(10, 0, 10, 0)

        title = QPushButton("ArabicPy IDE")

        minimize = QPushButton("━")
        close = QPushButton("✕")

        minimize.setFixedWidth(40)
        close.setFixedWidth(40)

        minimize.clicked.connect(
            self.parent.showMinimized
        )

        close.clicked.connect(
            self.parent.close
        )

        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(minimize)
        layout.addWidget(close)

        self.setLayout(layout)


    def mousePressEvent(self, event):

        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPosition().toPoint()


    def mouseMoveEvent(self, event):

        if self.old_pos:

            delta = (
                event.globalPosition().toPoint()
                -
                self.old_pos
            )

            self.parent.move(
                self.parent.pos() + delta
            )

            self.old_pos = event.globalPosition().toPoint()




# =========================
# Main IDE
# =========================

class ArabicPyIDE(QMainWindow):

    def __init__(self):

        super().__init__()
        self.setWindowFlags(
        Qt.FramelessWindowHint
    )
        self.current_file = None

        self.setWindowTitle(
            "ArabicPy IDE"
        )

        self.resize(
            1400,
            900
        )


        self.setStyleSheet("""

        QMainWindow {
            background-color: #1e1e1e;
        }


        QWidget {
            background-color: #1e1e1e;
        }


        QTextEdit {
            background-color: #252526;
            color: white;
            border: none;
            outline: none;
            font-size: 16px;
            font-family: Consolas;
        }


        QListWidget {
            background-color: #181818;
            color: white;
            border: none;
        }


        QPushButton {
            background-color: #333333;
            color: white;
            border-radius: 6px;
            padding: 8px;
        }


        QPushButton:hover {
            background-color: #505050;
        }


        QSplitter {
            background-color: #1e1e1e;
        }


        QSplitter::handle {
            background-color: #444444;
        }


        QSplitter::handle:hover {
            background-color: #666666;
        }


        QSplitter::handle:horizontal {
            width: 4px;
        }


        QSplitter::handle:vertical {
            height: 4px;
        }

        """)

        self.setup_ui() 

    def setup_ui(self):

        # Widgets

        self.file_list = QListWidget()
        self.file_list.setLineWidth(0)
        self.file_list.setMidLineWidth(0)
        self.file_list.setFrameShape(
             QFrame.NoFrame
        )
        self.file_list.setFrameStyle(0)

        self.editor = QTextEdit()
        self.editor.setLineWidth(0)
        self.editor.setMidLineWidth(0)

        self.editor.setFrameShape(
            QFrame.NoFrame
        )
        self.editor.setFrameStyle(0)

        self.editor.setLayoutDirection(
            Qt.RightToLeft
        )

        self.highlighter = ArabicPyHighlighter(
            self.editor.document()
        )

        self.editor.setPlainText(
            'اطبع("مرحبا من ArabicPy")'
        )

        self.output = QTextEdit()
        self.output.setStyleSheet("""
    QTextEdit {
        border-top: 4px solid #444444;
    }
""")        
        self.output.setFrameShape(
            QFrame.NoFrame
        )
        self.output.setFrameStyle(0)
        self.output.setReadOnly(True)


        # Buttons

        self.new_button = QPushButton("جديد 📄")
        self.open_button = QPushButton("فتح 📂")
        self.save_button = QPushButton("حفظ 💾")
        self.find_button = QPushButton("بحث 🔍")
        self.run_button = QPushButton("تشغيل ▶")


        self.run_button.clicked.connect(
            self.run_code
        )

        self.new_button.clicked.connect(
            self.new_file
        )

        self.open_button.clicked.connect(
            self.open_file
        )

        self.save_button.clicked.connect(
            self.save_file
        )

        self.find_button.clicked.connect(
            self.find_text
        )


        # Main layout

        main_layout = QVBoxLayout()

        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)

        self.title_bar = TitleBar(self)

        main_layout.addWidget(
            self.title_bar
        )


        buttons = QHBoxLayout()

        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(0)

        buttons.addWidget(self.new_button)
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.find_button)

        buttons.addStretch()

        main_layout.addLayout(
            buttons
        )


        # Editor

        editor_splitter = QSplitter(
    Qt.Horizontal
)

        editor_splitter.setHandleWidth(4)
        editor_splitter.setHandleWidth(0)
        editor_splitter.setContentsMargins(0,0,0,0)
        editor_splitter.setHandleWidth(1)
        editor_splitter.setHandleWidth(0)
        editor_splitter = QSplitter(Qt.Horizontal)
        editor_splitter.setHandleWidth(0)
        editor_splitter.setHandleWidth(2)

        main_splitter = QSplitter(
          Qt.Vertical
        )

        main_splitter.setHandleWidth(4)
        main_splitter.setHandleWidth(8)
        main_splitter.setHandleWidth(0)
        main_splitter.setHandleWidth(2)

        editor_splitter.addWidget(
        self.editor
)


        # Output

        main_splitter = QSplitter(
            Qt.Vertical
        )
        main_splitter.setHandleWidth(0)

        main_splitter.addWidget(
            editor_splitter
        )

        main_splitter.addWidget(
            self.output
        )


        main_layout.addWidget(
            main_splitter
        )


        main_layout.addWidget(
            self.run_button
        )


        container = QWidget()

        container.setLayout(
            main_layout
        )


        self.setCentralWidget(
            container
        )  

    # =========================
# File System
# =========================

    def new_file(self):

        self.current_file = None

        self.editor.clear()



    def open_file(self):

        path, _ = QFileDialog.getOpenFileName(
            self,
            "فتح ملف",
            "",
            "ArabicPy (*.apy);;Python (*.py)"
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
            "ArabicPy (*.apy)"
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



    # =========================
    # Find
    # =========================

    def find_text(self):

        text, ok = QInputDialog.getText(
            self,
            "بحث",
            "ابحث عن:"
        )


        if ok and text:

            cursor = self.editor.textCursor()

            result = self.editor.document().find(
                text,
                cursor
            )


            if not result.isNull():

                self.editor.setTextCursor(
                    result
                )



    # =========================
    # Run ArabicPy
    # =========================

    def run_code(self):

        try:

            source = self.editor.toPlainText()


            lexer = Lexer(source)

            tokens = lexer.tokenize()



            parser = Parser(tokens)

            ast = parser.parse()



            generator = Generator()

            python_code = generator.generate(ast)



            output = io.StringIO()


            with contextlib.redirect_stdout(output):

                exec(
                    python_code,
                    {}
                )



            result = output.getvalue()


            if result.strip():

                self.output.setPlainText(
                    result
                )

            else:

                self.output.setPlainText(
                    python_code
                )



        except Exception as e:


            self.output.setPlainText(
                "خطأ:\n" + str(e)
            )



# =========================
# Start
# =========================

if __name__ == "__main__":


    app = QApplication([])


    window = ArabicPyIDE()


    window.show()


    app.exec()       