import contextlib
import io
import os

from PySide6.QtCore import QProcess, QTimer, QRect, QSize, Qt
from PySide6.QtGui import (
    QColor, QFont, QPainter, QTextBlockFormat, QTextCharFormat, QTextCursor,
    QTextFormat,
)
from PySide6.QtWidgets import (
    QApplication, QBoxLayout, QFileDialog, QFrame, QHBoxLayout, QInputDialog,
    QLabel, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QMenu, QSplitter, QTabBar, QTabWidget, QTextEdit, QVBoxLayout,
    QWidget,
)

from .generator import Generator
from .highlighter import ArabicPyHighlighter
from .lexer import Lexer
from .parser import Parser
from .android import export_android_project, generate_kivy, is_android_source
from .android_designer import AndroidDesigner
from .ai import reply as albaa_ai_reply
from .errors import format_error


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
        # Segoe UI provides taller Arabic glyph metrics than Tahoma, avoiding
        # collisions between dots/diacritics on adjacent source lines.
        self.setFont(QFont("Segoe UI", 13))
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.setLayoutDirection(Qt.RightToLeft)
        # QTextEdit's layout direction alone does not change paragraph
        # alignment. Arabic source should start at the right-hand edge.
        text_option = self.document().defaultTextOption()
        text_option.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)
        self.document().setDefaultTextOption(text_option)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.error_line = None
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.update_line_number_area_width(0)
        self.highlight_current_line()
        self.apply_line_spacing()

    def setPlainText(self, text):
        """Load plain text and enforce Arabic-safe spacing on every block."""
        super().setPlainText(text)
        self.apply_line_spacing()

    def apply_line_spacing(self):
        cursor = QTextCursor(self.document())
        cursor.select(QTextCursor.Document)
        block_format = QTextBlockFormat()
        # PySide6 releases disagree on accepting the scoped enum here. The
        # stable overload is (float, int); 1 is ProportionalHeight in Qt.
        block_format.setLineHeight(145.0, 1)
        cursor.mergeBlockFormat(block_format)

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
        selections = []

        current_line = QTextEdit.ExtraSelection()
        current_line.format.setBackground(QColor("#2a2d2e"))
        current_line.format.setProperty(QTextFormat.FullWidthSelection, True)
        current_line.cursor = self.textCursor()
        current_line.cursor.clearSelection()
        selections.append(current_line)

        if self.error_line is not None:
            block = self.document().findBlockByNumber(self.error_line - 1)
            if block.isValid():
                error_selection = QTextEdit.ExtraSelection()
                error_selection.cursor = QTextCursor(block)
                error_selection.cursor.select(QTextCursor.LineUnderCursor)
                error_selection.format.setBackground(QColor("#4b2025"))
                error_selection.format.setUnderlineColor(QColor("#f14c4c"))
                error_selection.format.setUnderlineStyle(QTextCharFormat.WaveUnderline)
                error_selection.format.setProperty(QTextFormat.FullWidthSelection, True)
                selections.append(error_selection)

        self.setExtraSelections(selections)

    def show_error_line(self, line):
        """Mark a one-based source line and move the editor cursor to it."""
        if line is None or line < 1 or line > self.blockCount():
            self.error_line = None
            self.highlight_current_line()
            return

        self.error_line = line
        block = self.document().findBlockByNumber(line - 1)
        self.setTextCursor(QTextCursor(block))
        self.centerCursor()
        self.highlight_current_line()

    def clear_error_line(self):
        self.error_line = None
        self.highlight_current_line()

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

        brand = QLabel("◈  الباء")
        brand.setObjectName("brand")
        document = QLabel("  —  لغة البرمجة العربية")
        document.setObjectName("titleDocument")
        layout.addWidget(brand)
        layout.addWidget(document)
        layout.addStretch()
        for label, action, name in [("—", parent.showMinimized, "windowButton"), ("□", parent.toggle_maximized, "windowButton"), ("×", parent.close, "closeButton")]:
            button = QPushButton(label)
            button.setObjectName(name)
            button.setFixedSize(46, 35)
            button.clicked.connect(action)
            layout.addWidget(button)
            if label == "□":
                parent.maximize_button = button

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
        self.syncing_code_views = False
        self.output_was_visible_before_designer = True
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowTitle("الباء")
        self.resize(1400, 900)
        self.setStyleSheet(self.stylesheet())
        self.setup_ui()

    def show_fitted(self):
        """Open at a useful normal size while staying inside the desktop."""
        screen = QApplication.primaryScreen()
        if screen is None:
            self.show()
            return
        available = screen.availableGeometry()
        width = min(1400, max(700, available.width() - 64))
        height = min(900, max(650, available.height() - 64))
        self.resize(width, height)
        self.move(
            available.x() + (available.width() - width) // 2,
            available.y() + (available.height() - height) // 2,
        )
        self.show()

    def toggle_maximized(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def stylesheet(self):
        return """
        QMainWindow, QWidget { background: #1e1e1e; color: #cccccc; font-family: 'Tahoma'; font-size: 13px; }
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
        #pythonTabSpacer { background: #1e1e1e; border-bottom: 1px solid #1e1e1e; }
        #codeEditor { background: #1e1e1e; color: #d4d4d4; border: none; selection-background-color: #264f78; font-family: 'Segoe UI'; font-size: 15px; }
        #codePaneTitle { background: #252526; color: #cccccc; border-bottom: 1px solid #333333; padding: 7px 12px; font-weight: 600; }
        #pythonPreview { background: #1e1e1e; color: #d4d4d4; border: none; selection-background-color: #264f78; font-family: 'Segoe UI'; font-size: 15px; }
        #outputHeader { background: #252526; border-top: 1px solid #333333; } #outputTitle { color: #cccccc; font-weight: 600; padding: 7px 12px; }
        #output { background: #1e1e1e; color: #e0e0e0; border: none; font-family: 'Tahoma'; font-size: 14px; padding: 9px; }
        #statusBar { background: #007acc; color: white; } #statusLabel { background: transparent; color: white; padding: 3px 10px; font-size: 12px; }
        #androidDesigner { background: #181818; }
        #designerPanel { background: #252526; border: none; }
        #designerTitle { color: #ffffff; font-weight: 600; padding: 8px; }
        #designerTool { background: #333333; color: #eeeeee; border: 1px solid #444444; border-radius: 4px; padding: 8px; text-align: right; }
        #designerTool:hover { background: #3f3f46; border-color: #007acc; }
        #designerCanvas { background: #151515; border: none; }
        #phoneFrame { background: #fafafa; border: 8px solid #333333; border-radius: 24px; }
        #phoneTitle { background: #202124; color: white; padding: 10px; font-weight: 600; }
        #designerItem { background: transparent; border: 2px solid transparent; border-radius: 5px; }
        #designerItem[selected="true"] { border-color: #007acc; background: #e8f2fb; }
        #designerItem QLabel, #designerItem QLineEdit, #designerItem QPushButton { color: #202124; background: #ffffff; border: 1px solid #bdbdbd; border-radius: 4px; padding: 8px; }
        #designerItem QPushButton { background: #1976d2; color: white; }
        #designerDelete { background: #a1260d; color: white; border: none; border-radius: 4px; padding: 7px; }
        QSplitter::handle { background: #333333; } QSplitter::handle:hover { background: #007acc; }
        QTabWidget QTabBar { background: #252526; }
        QTabWidget QTabBar::tab { background: #2d2d2d; color: #c8c8c8; border: none; border-top: 2px solid transparent; padding: 9px 18px; }
        QTabWidget QTabBar::tab:selected { background: #1e1e1e; color: #ffffff; border-top: 2px solid #007acc; }
        QTabWidget QTabBar::tab:hover { background: #37373d; color: #ffffff; }
        #tabCloseButton { background: transparent; color: #c8c8c8; border: none; border-radius: 3px; font-size: 16px; font-weight: 600; padding: 0; }
        #tabCloseButton:hover { background: #c42b1c; color: #ffffff; }
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
        button.setLayoutDirection(Qt.RightToLeft)
        menu = QMenu(button)
        menu.setLayoutDirection(Qt.RightToLeft)
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
        menu_layout.setDirection(QBoxLayout.RightToLeft)
        menu_layout.setContentsMargins(8, 1, 8, 1)
        menu_layout.addWidget(self.make_menu_button("ملف", [
            ("ملف جديد", self.new_file), ("فتح ملف...", self.open_file),
            ("حفظ", self.save_file), ("تحديث المستكشف", self.refresh_file_list),
            ("مشروع تطبيق جديد", self.new_android_file),
            ("تصدير مشروع التطبيق...", self.export_android),
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
            ("إظهار / إخفاء كود Python", self.toggle_python_preview),
        ]))
        menu_layout.addWidget(self.make_menu_button("تشغيل", [
            ("تشغيل البرنامج", self.run_code), ("مسح المخرجات", self.clear_output),
            ("إنشاء APK عبر WSL2", self.build_android_apk),
        ]))
        menu_layout.addWidget(self.make_menu_button("تعليمات", [
            ("حول الباء", self.show_about),
        ]))
        menu_layout.addStretch()
        layout.addWidget(menu_bar)

        command_bar = QWidget(objectName="commandBar")
        command_layout = QHBoxLayout(command_bar)
        command_layout.setDirection(QBoxLayout.RightToLeft)
        command_layout.setContentsMargins(10, 4, 10, 4)
        command_layout.setSpacing(4)
        command_layout.addWidget(self.make_button("＋ جديد", self.new_file))
        command_layout.addWidget(self.make_button("فتح", self.open_file))
        command_layout.addWidget(self.make_button("حفظ", self.save_file))
        command_layout.addWidget(self.make_button("⌕ بحث", self.find_text))
        self.python_toggle_button = self.make_button("◀", self.toggle_python_preview)
        self.python_toggle_button.setFixedWidth(34)
        self.python_toggle_button.setToolTip("إظهار كود Python")
        command_layout.addWidget(self.python_toggle_button)
        command_layout.addStretch()
        self.designer_button = self.make_button("تصميم", self.toggle_android_designer)
        command_layout.addWidget(self.designer_button)
        self.run_button = self.make_button("▶ تشغيل", self.run_code, "runButton")
        command_layout.addWidget(self.run_button)
        layout.addWidget(command_bar)

        workspace = QHBoxLayout()
        workspace.setDirection(QBoxLayout.RightToLeft)
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
        editor_splitter.setLayoutDirection(Qt.RightToLeft)
        sidebar = QWidget(objectName="sideBar")
        sidebar.setLayoutDirection(Qt.RightToLeft)
        self.sidebar = sidebar
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        sidebar_layout.addWidget(QLabel("المستكشف", objectName="panelTitle"))
        project = QLabel("⌄  الباء", objectName="panelTitle")
        sidebar_layout.addWidget(project)
        self.file_list = QListWidget(objectName="fileList")
        self.file_list.setLayoutDirection(Qt.RightToLeft)
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
        tabs.hide()
        self.tab_widget = QTabWidget()
        self.tab_widget.setLayoutDirection(Qt.RightToLeft)
        self.tab_widget.setTabsClosable(False)
        self.tab_widget.setMovable(True)
        self.tab_widget.currentChanged.connect(self.switch_tab)
        add_tab = self.make_button("+", self.new_file)
        add_tab.setFixedWidth(30)
        self.tab_widget.setCornerWidget(add_tab, Qt.TopLeftCorner)

        code_splitter = QSplitter(Qt.Horizontal)
        code_splitter.setLayoutDirection(Qt.RightToLeft)
        self.code_splitter = code_splitter
        source_panel = QWidget()
        source_layout = QVBoxLayout(source_panel)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.setSpacing(0)
        source_title = QLabel("الباء — الكود العربي", objectName="codePaneTitle")
        source_title.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        source_layout.addWidget(source_title)
        source_layout.addWidget(self.tab_widget)
        code_splitter.addWidget(source_panel)

        python_panel = QWidget()
        self.python_panel = python_panel
        python_layout = QVBoxLayout(python_panel)
        python_layout.setContentsMargins(0, 0, 0, 0)
        python_layout.setSpacing(0)
        python_title = QLabel("Python — كود بايثون", objectName="codePaneTitle")
        python_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        python_layout.addWidget(python_title)
        self.python_tab_spacer = QWidget(objectName="pythonTabSpacer")
        python_layout.addWidget(self.python_tab_spacer)
        self.python_preview = CodeEditor()
        self.python_preview.setObjectName("pythonPreview")
        self.python_preview.setLayoutDirection(Qt.LeftToRight)
        python_text_option = self.python_preview.document().defaultTextOption()
        python_text_option.setAlignment(Qt.AlignLeft | Qt.AlignAbsolute)
        self.python_preview.document().setDefaultTextOption(python_text_option)
        self.python_preview.setFont(QFont("Segoe UI", 13))
        self.python_preview.setReadOnly(True)
        self.python_preview.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.python_highlighter = ArabicPyHighlighter(self.python_preview.document())
        python_layout.addWidget(self.python_preview)
        code_splitter.addWidget(python_panel)
        code_splitter.setSizes([650, 650])
        python_panel.hide()
        editor_layout.addWidget(code_splitter)
        self.android_designer = AndroidDesigner()
        self.android_designer.sourceChanged.connect(self.apply_designer_source)
        self.android_designer.hide()
        editor_layout.addWidget(self.android_designer)
        self.editor = CodeEditor()
        self.highlighter = ArabicPyHighlighter(self.editor.document())
        self.editor.setPlainText(
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
        self.editor.textChanged.connect(self.update_python_preview)
        self.editor.cursorPositionChanged.connect(self.sync_arabic_cursor_to_python)
        self.editor.verticalScrollBar().valueChanged.connect(
            lambda value, editor=self.editor: self.sync_scrollbars(editor, self.python_preview, value)
        )
        self.python_preview.cursorPositionChanged.connect(self.sync_python_cursor_to_arabic)
        self.python_preview.verticalScrollBar().valueChanged.connect(
            lambda value: self.sync_scrollbars(self.python_preview, self.editor, value)
        )
        self.editor.file_path = None
        initial_index = self.tab_widget.addTab(self.editor, "غير محفوظ.apy")
        self.add_tab_close_button(initial_index, self.editor)
        QTimer.singleShot(0, self.align_code_pane_headers)
        self.update_python_preview()
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
        header_layout.setDirection(QBoxLayout.RightToLeft)
        header_layout.setContentsMargins(0, 0, 8, 0)
        header_layout.addWidget(QLabel("المخرجات", objectName="outputTitle"))
        header_layout.addStretch()
        clear = self.make_button("مسح", self.clear_output)
        header_layout.addWidget(clear)
        output_layout.addWidget(header)
        self.output = QPlainTextEdit(objectName="output")
        self.output.setLayoutDirection(Qt.RightToLeft)
        output_text_option = self.output.document().defaultTextOption()
        output_text_option.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)
        self.output.document().setDefaultTextOption(output_text_option)
        self.output.setReadOnly(True)
        self.output.setPlainText("جاهز للتشغيل.")
        output_layout.addWidget(self.output)
        main_splitter.addWidget(output_panel)
        main_splitter.setSizes([650, 190])
        workspace.addWidget(main_splitter)
        layout.addLayout(workspace)

        status = QWidget(objectName="statusBar")
        status_layout = QHBoxLayout(status)
        status_layout.setDirection(QBoxLayout.RightToLeft)
        status_layout.setContentsMargins(4, 0, 4, 0)
        status_layout.addWidget(QLabel("◉  الباء", objectName="statusLabel"))
        status_layout.addStretch()
        self.position_label = QLabel("السطر 1، العمود 1", objectName="statusLabel")
        status_layout.addWidget(self.position_label)
        status_layout.addWidget(QLabel("UTF-8     العربية", objectName="statusLabel"))
        self.editor.cursorPositionChanged.connect(self.update_position)
        layout.addWidget(status)
        self.setCentralWidget(root)
        self.android_project_path = None
        self.android_build_process = None
        self.updating_from_designer = False
        self.refresh_file_list()

    def refresh_file_list(self):
        self.file_list.clear()
        root = os.getcwd()
        for filename in sorted(os.listdir(root)):
            if filename.endswith((".apy", ".py")):
                item = QListWidgetItem(f"  ◇  {filename}")
                item.setData(Qt.UserRole, os.path.join(root, filename))
                self.file_list.addItem(item)

    def align_code_pane_headers(self):
        """Match Python's header height to ArabicPy's document-tab row."""
        self.python_tab_spacer.setFixedHeight(self.tab_widget.tabBar().height())

    def update_tab_title(self, modified=False):
        index = self.tab_widget.indexOf(self.editor)
        if index >= 0:
            name = os.path.basename(getattr(self.editor, "file_path", "") or "غير محفوظ.apy")
            marker = "● " if modified else ""
            self.tab_widget.setTabText(index, marker + name)
        return
        name = os.path.basename(self.current_file) if self.current_file else "غير محفوظ.apy"
        self.active_tab.setText(f"  {'●' if modified else '◇'}  {name}    ×")

    def switch_tab(self, index):
        if index >= 0:
            self.editor = self.tab_widget.widget(index)
            self.current_file = getattr(self.editor, "file_path", None)
            self.update_position()
            self.update_python_preview()
            if self.android_designer.isVisible():
                if is_android_source(self.editor.toPlainText()):
                    self.android_designer.load_source(self.editor.toPlainText())
                else:
                    self.hide_android_designer()

    def add_editor_tab(self, content="", path=None):
        editor = CodeEditor()
        editor.file_path = path
        editor.highlighter = ArabicPyHighlighter(editor.document())
        editor.setPlainText(content)
        editor.document().setModified(False)
        editor.document().modificationChanged.connect(lambda changed: self.update_tab_title(changed))
        editor.cursorPositionChanged.connect(self.update_position)
        editor.cursorPositionChanged.connect(self.sync_arabic_cursor_to_python)
        editor.textChanged.connect(self.update_python_preview)
        editor.verticalScrollBar().valueChanged.connect(
            lambda value, source_editor=editor: self.sync_scrollbars(
                source_editor, self.python_preview, value
            )
        )
        name = os.path.basename(path) if path else "غير محفوظ.apy"
        index = self.tab_widget.addTab(editor, name)
        self.add_tab_close_button(index, editor)
        self.tab_widget.setCurrentWidget(editor)
        return editor

    def add_tab_close_button(self, index, editor):
        close_button = QPushButton("×")
        close_button.setObjectName("tabCloseButton")
        close_button.setFixedSize(20, 20)
        close_button.setToolTip("إغلاق")
        close_button.clicked.connect(
            lambda: self.close_tab(self.tab_widget.indexOf(editor))
        )
        self.tab_widget.tabBar().setTabButton(
            index, QTabBar.ButtonPosition.LeftSide, close_button
        )

    def close_tab(self, index):
        editor = self.tab_widget.widget(index)
        self.tab_widget.removeTab(index)
        editor.deleteLater()
        if self.tab_widget.count() == 0:
            self.add_editor_tab()

    def update_python_preview(self):
        """Translate the active ArabicPy document into a live Python preview."""
        if not hasattr(self, "python_preview") or not hasattr(self, "editor"):
            return

        source = self.editor.toPlainText()
        if not source.strip():
            self.set_python_preview_text(
                "# اكتب كود الباء في الجهة اليمنى\n"
                "# The generated Python code will appear here."
            )
            return

        try:
            if is_android_source(source):
                if self.android_designer.isVisible() and not self.updating_from_designer:
                    self.android_designer.load_source(source)
                python_code = generate_kivy(source)
            else:
                tokens = Lexer(source).tokenize()
                ast = Parser(tokens).parse()
                python_code = Generator().generate(ast)
                python_code = self.match_source_spacing(source, python_code)
            self.set_python_preview_text(
                python_code or "# No Python code has been generated yet."
            )
        except Exception as error:
            line = getattr(error, "line", None)
            column = getattr(error, "column", None)
            location = ""
            if line is not None:
                location = f"\n# Error at line {line}, column {column or 1}."
            self.set_python_preview_text(
                "# Fix or complete the Al-Baa code to generate Python."
                f"{location}"
            )

    def set_python_preview_text(self, text):
        """Refresh generated code without moving the Arabic editing cursor."""
        self.syncing_code_views = True
        try:
            self.python_preview.setPlainText(text)
        finally:
            self.syncing_code_views = False
        self.sync_cursor_line(self.editor, self.python_preview)

    @staticmethod
    def match_source_spacing(source, python_code):
        """Keep blank lines and comments aligned for one-line statements."""
        source_lines = source.splitlines()
        generated_lines = python_code.splitlines()
        source_code_lines = [
            line for line in source_lines
            if line.strip() and not line.lstrip().startswith("#")
        ]

        # Compound statements can expand into a different number of Python
        # lines. In that case, retain the generator's structurally correct
        # formatting rather than guessing at a misleading alignment.
        if len(source_code_lines) != len(generated_lines):
            return python_code

        aligned_lines = []
        generated_index = 0
        for source_line in source_lines:
            if not source_line.strip():
                aligned_lines.append("")
            elif source_line.lstrip().startswith("#"):
                aligned_lines.append(source_line)
            else:
                aligned_lines.append(generated_lines[generated_index])
                generated_index += 1

        return "\n".join(aligned_lines)

    def sync_arabic_cursor_to_python(self):
        if self.syncing_code_views or self.sender() is not self.editor:
            return
        self.sync_cursor_line(self.editor, self.python_preview)

    def sync_python_cursor_to_arabic(self):
        if self.syncing_code_views:
            return
        self.sync_cursor_line(self.python_preview, self.editor)

    def sync_cursor_line(self, source_editor, target_editor):
        """Highlight the corresponding row when both views are line-aligned."""
        if source_editor.blockCount() != target_editor.blockCount():
            return

        line = source_editor.textCursor().blockNumber()
        target_block = target_editor.document().findBlockByNumber(line)
        if not target_block.isValid():
            return

        self.syncing_code_views = True
        try:
            target_editor.setTextCursor(QTextCursor(target_block))
            target_editor.ensureCursorVisible()
        finally:
            self.syncing_code_views = False

    def sync_scrollbars(self, source_editor, target_editor, value):
        """Mirror scroll position proportionally between the two code panes."""
        if self.syncing_code_views or source_editor is not self.editor and source_editor is not self.python_preview:
            return

        source_bar = source_editor.verticalScrollBar()
        target_bar = target_editor.verticalScrollBar()
        source_range = source_bar.maximum() - source_bar.minimum()
        target_range = target_bar.maximum() - target_bar.minimum()
        target_value = target_bar.minimum()
        if source_range > 0:
            ratio = (value - source_bar.minimum()) / source_range
            target_value += round(ratio * target_range)

        self.syncing_code_views = True
        try:
            target_bar.setValue(target_value)
        finally:
            self.syncing_code_views = False

    def update_position(self):
        if not hasattr(self, "position_label"):
            return
        cursor = self.editor.textCursor()
        self.position_label.setText(f"السطر {cursor.blockNumber() + 1}، العمود {cursor.columnNumber() + 1}")

    def clear_output(self):
        self.output.clear()

    def toggle_sidebar(self):
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def toggle_output(self):
        output_widget = self.main_splitter.widget(1)
        output_widget.setVisible(not output_widget.isVisible())

    def toggle_python_preview(self):
        visible = not self.python_panel.isVisible()
        self.python_panel.setVisible(visible)
        if visible:
            self.code_splitter.setSizes([700, 700])
            self.python_toggle_button.setText("▶")
            self.python_toggle_button.setToolTip("إخفاء كود Python")
            QTimer.singleShot(0, self.align_code_pane_headers)
        else:
            self.python_toggle_button.setText("◀")
            self.python_toggle_button.setToolTip("إظهار كود Python")

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
        self.output.setPlainText("الباء\n\nلغة برمجة عربية مع محرر لكتابة البرامج وتشغيلها.\nاستخدم ملف > فتح أو زر فتح لبدء العمل.")

    def new_android_file(self):
        source = (
            'تطبيق "تطبيقي العربي"\n\n'
            'رسالة = نص("مرحباً من الباء")\n'
            'الاسم = حقل("اكتب اسمك")\n'
            'زر_الترحيب = زر("اضغط هنا")\n\n'
            'عند_النقر(زر_الترحيب):\n'
            '    غيّر_النص(رسالة، "أهلاً بك في تطبيقي")\n'
        )
        editor = self.add_editor_tab(source)
        editor.document().setModified(True)
        self.update_tab_title(True)
        editor.setFocus()
        QTimer.singleShot(0, self.show_android_designer)

    def toggle_android_designer(self):
        if self.android_designer.isVisible():
            self.hide_android_designer()
        else:
            self.show_android_designer()

    def show_android_designer(self):
        source = self.editor.toPlainText()
        if not is_android_source(source):
            self.new_android_file()
            return
        if not self.android_designer.load_source(source):
            self.output.setPlainText(
                "أصلح أخطاء ملف Android قبل فتح المصمم المرئي."
            )
            return
        self.output_was_visible_before_designer = self.main_splitter.widget(1).isVisible()
        self.main_splitter.widget(1).hide()
        self.main_splitter.setSizes([1, 0])
        self.code_splitter.hide()
        self.android_designer.show()
        self.designer_button.setText("الكود")

    def hide_android_designer(self):
        if self.android_designer.preview_mode:
            self.android_designer.stop_preview()
            self.run_button.setText("▶ تشغيل")
        self.android_designer.hide()
        self.code_splitter.show()
        if self.output_was_visible_before_designer:
            self.main_splitter.widget(1).show()
            self.main_splitter.setSizes([650, 190])
        self.designer_button.setText("تصميم")

    def apply_designer_source(self, source):
        if not is_android_source(self.editor.toPlainText()):
            return
        self.updating_from_designer = True
        try:
            self.editor.setPlainText(source)
            self.editor.document().setModified(True)
            self.update_tab_title(True)
        finally:
            self.updating_from_designer = False

    def export_android(self):
        source = self.editor.toPlainText()
        if not is_android_source(source):
            self.output.setPlainText(
                'هذا الملف ليس تطبيق Android. ابدأ بـ: تطبيق "اسم التطبيق"'
            )
            return False

        directory = QFileDialog.getExistingDirectory(
            self, "اختر مجلد مشروع Android"
        )
        if not directory:
            return False

        existing = [
            name for name in ("main.py", "buildozer.spec")
            if os.path.exists(os.path.join(directory, name))
        ]
        if existing:
            answer = QMessageBox.question(
                self,
                "استبدال ملفات المشروع",
                "سيتم استبدال main.py و buildozer.spec في المجلد المحدد. هل تريد المتابعة؟",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return False

        try:
            export_android_project(source, directory)
        except Exception as error:
            self.output.setPlainText(format_error(error, source))
            return False

        self.android_project_path = directory
        self.main_splitter.widget(1).show()
        self.output.setPlainText(
            f"تم تصدير مشروع Android إلى:\n{directory}\n\n"
            "يمكنك الآن اختيار تشغيل > إنشاء APK عبر WSL2."
        )
        return True

    def build_android_apk(self):
        if self.android_build_process is not None:
            self.output.setPlainText("يجري الآن إنشاء APK. انتظر حتى تنتهي العملية.")
            return
        if not self.android_project_path and not self.export_android():
            return

        self.main_splitter.widget(1).show()
        self.output.setPlainText(
            "بدء Buildozer داخل WSL2...\n"
            "يجب تثبيت WSL2 و Buildozer ومتطلبات Android مسبقاً.\n\n"
        )
        process = QProcess(self)
        self.android_build_process = process
        process.setProgram("wsl.exe")
        process.setArguments([
            "--cd", self.android_project_path,
            "buildozer", "android", "debug",
        ])
        process.readyReadStandardOutput.connect(self.read_android_build_output)
        process.readyReadStandardError.connect(self.read_android_build_output)
        process.errorOccurred.connect(self.android_build_error)
        process.finished.connect(self.android_build_finished)
        process.start()

    def read_android_build_output(self):
        process = self.android_build_process
        if process is None:
            return
        data = bytes(process.readAllStandardOutput()) + bytes(process.readAllStandardError())
        if data:
            self.output.appendPlainText(data.decode("utf-8", errors="replace").rstrip())

    def android_build_error(self, _error):
        if self.android_build_process is not None:
            self.output.appendPlainText(
                "\nتعذر بدء WSL2/Buildozer. تأكد من تثبيتهما وإضافتهما إلى PATH داخل WSL."
            )

    def android_build_finished(self, exit_code, _status):
        if exit_code == 0:
            self.output.appendPlainText(
                "\nتم إنشاء APK بنجاح. ستجده داخل مجلد bin في المشروع."
            )
        else:
            self.output.appendPlainText(
                f"\nفشل إنشاء APK برمز خروج {exit_code}. راجع سجل Buildozer أعلاه."
            )
        if self.android_build_process is not None:
            self.android_build_process.deleteLater()
            self.android_build_process = None

    def new_file(self):
        self.add_editor_tab().setFocus()
        return
        self.current_file = None
        self.editor.clear()
        self.editor.document().setModified(False)
        self.update_tab_title()
        self.editor.setFocus()

    def open_project_file(self, item):
        self.load_file(item.data(Qt.UserRole))

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "فتح ملف", "", "ملفات الباء (*.apy);;Python (*.py);;All Files (*)")
        if path:
            self.load_file(path)

    def load_file(self, path):
        for index in range(self.tab_widget.count()):
            editor = self.tab_widget.widget(index)
            if getattr(editor, "file_path", None) == path:
                self.tab_widget.setCurrentIndex(index)
                return
        try:
            with open(path, "r", encoding="utf-8") as file:
                self.add_editor_tab(file.read(), path)
            return
            with open(path, "r", encoding="utf-8") as file:
                self.editor.setPlainText(file.read())
            self.current_file = path
            self.editor.document().setModified(False)
            self.update_tab_title()
        except OSError as error:
            self.output.setPlainText(f"تعذر فتح الملف:\n{error}")

    def save_file(self):
        editor = self.editor
        if not getattr(editor, "file_path", None):
            path, _ = QFileDialog.getSaveFileName(self, "حفظ ملف", "", "ملفات الباء (*.apy)")
            if not path:
                return
            editor.file_path = path
        try:
            with open(editor.file_path, "w", encoding="utf-8") as file:
                file.write(editor.toPlainText())
            editor.document().setModified(False)
            self.current_file = editor.file_path
            self.update_tab_title(False)
            self.refresh_file_list()
            return
        except OSError as error:
            self.output.setPlainText(f"تعذر حفظ الملف:\n{error}")
            return
        if not self.current_file:
            path, _ = QFileDialog.getSaveFileName(self, "حفظ ملف", "", "ملفات الباء (*.apy)")
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
        if is_android_source(source):
            try:
                generate_kivy(source)
                self.editor.clear_error_line()
                if self.android_designer.isVisible():
                    if self.android_designer.preview_mode:
                        self.android_designer.stop_preview()
                        self.run_button.setText("▶ تشغيل")
                    else:
                        self.android_designer.load_source(source)
                        self.android_designer.start_preview()
                        self.run_button.setText("■ إيقاف المعاينة")
                    return
                self.output.setPlainText(
                    "تم التحقق من التطبيق بنجاح. استخدم قائمتي ملف وتشغيل للتصدير أو إنشاء APK."
                )
            except Exception as error:
                self.editor.show_error_line(getattr(error, "line", None))
                self.output.setPlainText(format_error(error, source))
            return
        try:
            tokens = Lexer(source).tokenize()
            ast = Parser(tokens).parse()
            python_code = Generator().generate(ast)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exec(python_code, {
                    "__name__": "__main__",
                    "albaa_ai_reply": albaa_ai_reply,
                })
            result = output.getvalue()
            self.editor.clear_error_line()
            self.output.setPlainText(result if result else "تم التنفيذ بنجاح — لا توجد مخرجات.")
        except Exception as error:
            line = getattr(error, "line", None)
            if line is None:
                traceback = error.__traceback__
                while traceback:
                    if traceback.tb_frame.f_code.co_filename == "<string>":
                        line = traceback.tb_lineno
                    traceback = traceback.tb_next
            self.editor.show_error_line(line)
            self.output.setPlainText(format_error(error, source))


if __name__ == "__main__":
    app = QApplication([])
    window = ArabicPyIDE()
    window.show_fitted()
    app.exec()
