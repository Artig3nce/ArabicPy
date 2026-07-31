import contextlib
import io
import os

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QTextFormat
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QInputDialog,
    QLabel, QListWidget, QListWidgetItem, QMainWindow, QPlainTextEdit,
    QPushButton, QMenu, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from .generator import Generator
from .highlighter import ArabicPyHighlighter
from .lexer import Lexer
from .parser import Parser
from .ai import reply as arabicpy_ai_reply


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_line_numbers(event)


class CodeEditor(QPlainTextEdit):
    """Editor with a compact gutter, current-line cue, and Arabic-friendly defaults."""

    def __init__(self):
        super().__init__()
        self.line_number_area = LineNumberArea(self)
        self.setObjectName("codeEditor")
        self.setFont(QFont("Cascadia Code", 12))
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.setLayoutDirection(Qt.RightToLeft)
        # QTextEdit's layout direction alone does not change paragraph
        # alignment. Arabic source should start at the right-hand edge.
        text_option = self.document().defaultTextOption()
        text_option.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)
        self.document().setDefaultTextOption(text_option)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.update_line_number_area_width(0)
        self.highlight_current_line()

    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        return 16 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def highlight_current_line(self):
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor("#2a2d2e"))
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])

    def paint_line_numbers(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#1e1e1e"))
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                color = "#c6c6c6" if block == self.textCursor().block() else "#858585"
                painter.setPen(QColor(color))
                painter.drawText(0, top, self.line_number_area.width() - 6,
                                 self.fontMetrics().height(), Qt.AlignRight, str(number + 1))
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            number += 1


class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.old_pos = None
        self.setObjectName("titleBar")
        self.setFixedHeight(35)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(0)

        brand = QLabel("◈  ArabicPy")
        brand.setObjectName("brand")
        document = QLabel("  —  محرر برمجة عربي")
        document.setObjectName("titleDocument")
        layout.addWidget(brand)
        layout.addWidget(document)
        layout.addStretch()
        for label, action, name in [("—", parent.showMinimized, "windowButton"), ("□", parent.showMaximized, "windowButton"), ("×", parent.close, "closeButton")]:
            button = QPushButton(label)
            button.setObjectName(name)
            button.setFixedSize(46, 35)
            button.clicked.connect(action)
            layout.addWidget(button)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos and event.buttons() & Qt.LeftButton:
            new_pos = event.globalPosition().toPoint()
            self.parent.move(self.parent.pos() + new_pos - self.old_pos)
            self.old_pos = new_pos

    def mouseReleaseEvent(self, event):
        self.old_pos = None


class ArabicPyIDE(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowTitle("ArabicPy IDE")
        self.resize(1400, 900)
        self.setStyleSheet(self.stylesheet())
        self.setup_ui()

    def stylesheet(self):
        return """
        QMainWindow, QWidget { background: #1e1e1e; color: #cccccc; font-family: 'Segoe UI'; font-size: 13px; }
        #titleBar { background: #181818; border-bottom: 1px solid #2b2b2b; }
        #brand { color: #ffffff; font-weight: 600; font-size: 14px; }
        #titleDocument { color: #969696; }
        #windowButton, #closeButton { border: none; border-radius: 0; background: transparent; color: #c8c8c8; font-size: 17px; }
        #windowButton:hover { background: #333333; } #closeButton:hover { background: #c42b1c; color: white; }
        #menuBar, #commandBar { background: #252526; border-bottom: 1px solid #333333; }
        #menuItem { background: transparent; border: none; padding: 4px 10px; color: #d4d4d4; }
        #menuItem:hover, #toolButton:hover { background: #37373d; }
        #toolButton { background: transparent; border: none; border-radius: 3px; padding: 6px 10px; color: #d4d4d4; }
        #runButton { background: #16825d; color: white; border: none; border-radius: 3px; padding: 6px 14px; font-weight: 600; }
        #runButton:hover { background: #1a9b70; }
        #activityBar { background: #333333; min-width: 48px; max-width: 48px; }
        #activityButton { background: transparent; color: #bdbdbd; border: none; border-radius: 0; font-size: 20px; padding: 11px; }
        #activityButton:hover { background: #454545; color: white; } #activityButton:checked { border-left: 2px solid #007acc; color: white; }
        #sideBar { background: #252526; } #panelTitle { color: #bbbbbb; font-size: 11px; font-weight: 600; padding: 12px 14px 5px; }
        #fileList { background: #252526; border: none; outline: none; color: #cccccc; padding: 2px 6px; }
        #fileList::item { padding: 6px 8px; border-radius: 3px; } #fileList::item:selected { background: #37373d; color: white; }
        #tabBar { background: #252526; border-bottom: 1px solid #1e1e1e; } #activeTab { background: #1e1e1e; color: #ffffff; border-top: 1px solid #007acc; padding: 10px 16px; }
        #codeEditor { background: #1e1e1e; color: #d4d4d4; border: none; selection-background-color: #264f78; }
        #outputHeader { background: #252526; border-top: 1px solid #333333; } #outputTitle { color: #cccccc; font-weight: 600; padding: 7px 12px; }
        #output { background: #1e1e1e; color: #cccccc; border: none; font-family: 'Cascadia Mono'; font-size: 12px; padding: 7px; }
        #statusBar { background: #007acc; color: white; } #statusLabel { background: transparent; color: white; padding: 3px 10px; font-size: 12px; }
        QSplitter::handle { background: #333333; } QSplitter::handle:hover { background: #007acc; }
        """

    def make_button(self, text, callback, name="toolButton"):
        button = QPushButton(text)
        button.setObjectName(name)
        button.clicked.connect(callback)
        return button

    def make_menu_button(self, text, actions):
        """Create a real, clickable top-level menu instead of a decorative label."""
        button = QPushButton(text)
        button.setObjectName("menuItem")
        menu = QMenu(button)
        for label, callback in actions:
            menu.addAction(label, callback)
        button.setMenu(menu)
        return button

    def setup_ui(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(TitleBar(self))

        menu_bar = QWidget(objectName="menuBar")
        menu_layout = QHBoxLayout(menu_bar)
        menu_layout.setContentsMargins(8, 1, 8, 1)
        menu_layout.addWidget(self.make_menu_button("ملف", [
            ("ملف جديد", self.new_file), ("فتح ملف...", self.open_file),
            ("حفظ", self.save_file), ("تحديث المستكشف", self.refresh_file_list),
        ]))
        menu_layout.addWidget(self.make_menu_button("تحرير", [
            ("تراجع", lambda: self.editor.undo()), ("إعادة", lambda: self.editor.redo()),
            ("قص", lambda: self.editor.cut()), ("نسخ", lambda: self.editor.copy()),
            ("لصق", lambda: self.editor.paste()),
        ]))
        menu_layout.addWidget(self.make_menu_button("تحديد", [
            ("تحديد الكل", lambda: self.editor.selectAll()),
            ("بحث...", self.find_text),
        ]))
        menu_layout.addWidget(self.make_menu_button("عرض", [
            ("إظهار / إخفاء المستكشف", self.toggle_sidebar),
            ("إظهار / إخفاء المخرجات", self.toggle_output),
        ]))
        menu_layout.addWidget(self.make_menu_button("تشغيل", [
            ("تشغيل البرنامج", self.run_code), ("مسح المخرجات", self.clear_output),
        ]))
        menu_layout.addWidget(self.make_menu_button("تعليمات", [
            ("حول ArabicPy", self.show_about),
        ]))
        menu_layout.addStretch()
        layout.addWidget(menu_bar)

        command_bar = QWidget(objectName="commandBar")
        command_layout = QHBoxLayout(command_bar)
        command_layout.setContentsMargins(10, 4, 10, 4)
        command_layout.setSpacing(4)
        command_layout.addWidget(self.make_button("＋ جديد", self.new_file))
        command_layout.addWidget(self.make_button("فتح", self.open_file))
        command_layout.addWidget(self.make_button("حفظ", self.save_file))
        command_layout.addWidget(self.make_button("⌕ بحث", self.find_text))
        command_layout.addStretch()
        command_layout.addWidget(self.make_button("▶ تشغيل", self.run_code, "runButton"))
        layout.addWidget(command_bar)

        workspace = QHBoxLayout()
        workspace.setSpacing(0)
        activity = QWidget(objectName="activityBar")
        activity_layout = QVBoxLayout(activity)
        activity_layout.setContentsMargins(0, 4, 0, 0)
        self.activity_buttons = []
        for i, (icon, action) in enumerate([
            ("▱", self.show_explorer), ("⌕", self.find_text),
            ("⑂", self.show_run_panel), ("▣", self.show_about),
        ]):
            button = QPushButton(icon, objectName="activityButton")
            button.setCheckable(True)
            button.setChecked(i == 0)
            button.clicked.connect(action)
            self.activity_buttons.append(button)
            activity_layout.addWidget(button)
        activity_layout.addStretch()
        activity_layout.addWidget(self.make_button("⚙", self.show_about, "activityButton"))
        workspace.addWidget(activity)

        editor_splitter = QSplitter(Qt.Horizontal)
        sidebar = QWidget(objectName="sideBar")
        self.sidebar = sidebar
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        sidebar_layout.addWidget(QLabel("المستكشف", objectName="panelTitle"))
        project = QLabel("⌄  ARABICPY", objectName="panelTitle")
        sidebar_layout.addWidget(project)
        self.file_list = QListWidget(objectName="fileList")
        self.file_list.itemDoubleClicked.connect(self.open_project_file)
        sidebar_layout.addWidget(self.file_list)
        editor_splitter.addWidget(sidebar)

        editor_panel = QWidget()
        editor_layout = QVBoxLayout(editor_panel)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)
        tabs = QWidget(objectName="tabBar")
        tabs_layout = QHBoxLayout(tabs)
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        self.active_tab = QLabel("  ●  غير محفوظ.apy    ×", objectName="activeTab")
        tabs_layout.addWidget(self.active_tab)
        tabs_layout.addStretch()
        editor_layout.addWidget(tabs)
        self.editor = CodeEditor()
        self.highlighter = ArabicPyHighlighter(self.editor.document())
        self.editor.setPlainText(
            '# آلة حاسبة بسيطة بـ ArabicPy\n\n'
            'الرقم_الأول = 20\n'
            'الرقم_الثاني = 5\n\n'
            'جمع = الرقم_الأول + الرقم_الثاني\n'
            'الطرح = الرقم_الأول - الرقم_الثاني\n'
            'الضرب = الرقم_الأول * الرقم_الثاني\n'
            'القسمة = الرقم_الأول / الرقم_الثاني\n\n'
            'اطبع("جمع:")\n'
            'اطبع(جمع)\n'
            'اطبع("الطرح:")\n'
            'اطبع(الطرح)\n'
            'اطبع("الضرب:")\n'
            'اطبع(الضرب)\n'
            'اطبع("القسمة:")\n'
            'اطبع(القسمة)'
        )
        self.editor.document().modificationChanged.connect(self.update_tab_title)
        editor_layout.addWidget(self.editor)
        editor_splitter.addWidget(editor_panel)
        editor_splitter.setSizes([245, 1100])

        main_splitter = QSplitter(Qt.Vertical)
        self.main_splitter = main_splitter
        main_splitter.addWidget(editor_splitter)
        output_panel = QWidget()
        output_layout = QVBoxLayout(output_panel)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(0)
        header = QWidget(objectName="outputHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 8, 0)
        header_layout.addWidget(QLabel("المخرجات", objectName="outputTitle"))
        header_layout.addStretch()
        clear = self.make_button("مسح", self.clear_output)
        header_layout.addWidget(clear)
        output_layout.addWidget(header)
        self.output = QPlainTextEdit(objectName="output")
        self.output.setReadOnly(True)
        self.output.setPlainText("جاهز للتشغيل.")
        output_layout.addWidget(self.output)
        main_splitter.addWidget(output_panel)
        main_splitter.setSizes([650, 190])
        workspace.addWidget(main_splitter)
        layout.addLayout(workspace)

        status = QWidget(objectName="statusBar")
        status_layout = QHBoxLayout(status)
        status_layout.setContentsMargins(4, 0, 4, 0)
        status_layout.addWidget(QLabel("◉  ArabicPy", objectName="statusLabel"))
        status_layout.addStretch()
        self.position_label = QLabel("السطر 1، العمود 1", objectName="statusLabel")
        status_layout.addWidget(self.position_label)
        status_layout.addWidget(QLabel("UTF-8     العربية", objectName="statusLabel"))
        self.editor.cursorPositionChanged.connect(self.update_position)
        layout.addWidget(status)
        self.setCentralWidget(root)
        self.refresh_file_list()

    def refresh_file_list(self):
        self.file_list.clear()
        root = os.getcwd()
        for filename in sorted(os.listdir(root)):
            if filename.endswith((".apy", ".py")):
                item = QListWidgetItem(f"  ◇  {filename}")
                item.setData(Qt.UserRole, os.path.join(root, filename))
                self.file_list.addItem(item)

    def update_tab_title(self, modified=False):
        name = os.path.basename(self.current_file) if self.current_file else "غير محفوظ.apy"
        self.active_tab.setText(f"  {'●' if modified else '◇'}  {name}    ×")

    def update_position(self):
        cursor = self.editor.textCursor()
        self.position_label.setText(f"السطر {cursor.blockNumber() + 1}، العمود {cursor.columnNumber() + 1}")

    def clear_output(self):
        self.output.clear()

    def toggle_sidebar(self):
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def toggle_output(self):
        output_widget = self.main_splitter.widget(1)
        output_widget.setVisible(not output_widget.isVisible())

    def set_active_activity(self, active_button):
        for button in self.activity_buttons:
            button.setChecked(button is active_button)

    def show_explorer(self):
        self.sidebar.show()
        self.refresh_file_list()
        self.set_active_activity(self.activity_buttons[0])

    def show_run_panel(self):
        self.main_splitter.widget(1).show()
        self.output.setPlainText("لوحة التشغيل جاهزة. اضغط ▶ تشغيل لتشغيل البرنامج الحالي.")
        self.set_active_activity(self.activity_buttons[2])

    def show_about(self):
        self.main_splitter.widget(1).show()
        self.output.setPlainText("ArabicPy IDE\n\nمحرر بسيط لكتابة وتشغيل برامج ArabicPy.\nاستخدم ملف > فتح أو زر فتح لبدء العمل.")

    def new_file(self):
        self.current_file = None
        self.editor.clear()
        self.editor.document().setModified(False)
        self.update_tab_title()
        self.editor.setFocus()

    def open_project_file(self, item):
        self.load_file(item.data(Qt.UserRole))

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "فتح ملف", "", "ArabicPy (*.apy);;Python (*.py);;All Files (*)")
        if path:
            self.load_file(path)

    def load_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as file:
                self.editor.setPlainText(file.read())
            self.current_file = path
            self.editor.document().setModified(False)
            self.update_tab_title()
        except OSError as error:
            self.output.setPlainText(f"تعذر فتح الملف:\n{error}")

    def save_file(self):
        if not self.current_file:
            path, _ = QFileDialog.getSaveFileName(self, "حفظ ملف", "", "ArabicPy (*.apy)")
            if not path:
                return
            self.current_file = path
        try:
            with open(self.current_file, "w", encoding="utf-8") as file:
                file.write(self.editor.toPlainText())
            self.editor.document().setModified(False)
            self.update_tab_title()
            self.refresh_file_list()
        except OSError as error:
            self.output.setPlainText(f"تعذر حفظ الملف:\n{error}")

    def find_text(self):
        text, ok = QInputDialog.getText(self, "بحث", "ابحث عن:")
        if ok and text:
            found = self.editor.document().find(text, self.editor.textCursor())
            if found.isNull():
                found = self.editor.document().find(text)
            if not found.isNull():
                self.editor.setTextCursor(found)

    def run_code(self):
        source = self.editor.toPlainText()
        try:
            tokens = Lexer(source).tokenize()
            ast = Parser(tokens).parse()
            python_code = Generator().generate(ast)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exec(python_code, {
                    "__name__": "__main__",
                    "arabicpy_ai_reply": arabicpy_ai_reply,
                })
            result = output.getvalue()
            self.output.setPlainText(result if result else "تم التنفيذ بنجاح — لا توجد مخرجات.")
        except Exception as error:
            self.output.setPlainText(f"حدث خطأ أثناء التشغيل:\n{type(error).__name__}: {error}")


if __name__ == "__main__":
    app = QApplication([])
    window = ArabicPyIDE()
    window.show()
    app.exec()
