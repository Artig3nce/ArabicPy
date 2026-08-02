import contextlib
import base64
import html
import io
import math
import os
import re
import secrets
import shutil
import json
import socket
from datetime import datetime

from PySide6.QtCore import QPointF, QProcess, QSettings, QTimer, QRect, QSize, Qt, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtGui import (
    QColor, QDesktopServices, QFont, QKeySequence, QPainter, QPen, QPolygonF, QTextBlockFormat, QTextCharFormat, QTextCursor,
    QTextFormat,
)
from PySide6.QtWidgets import (
    QApplication, QBoxLayout, QComboBox, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLineEdit,
    QLabel, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QMenu, QProgressBar, QScrollArea, QSizePolicy, QSplitter, QTabBar, QTabWidget,
    QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

from .generator import Generator
from .highlighter import ArabicPyHighlighter
from .lexer import Lexer
from .parser import Parser
from .android import export_android_project, generate_kivy, is_android_source
from .android_designer import AndroidDesigner
from .tauri_export import export_tauri_project
from .ai import DEFAULT_MODEL, SYSTEM_PROMPT, reply as albaa_ai_reply
from .ai_server import AlBaaAIServer
from .embedded_ai import EMBEDDED_BASE_URL, MODELS, llama_server_path, model_path, server_arguments
from .errors import format_error
from .rag import context_for as rag_context, import_document


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_line_numbers(event)


class AIChatInput(QTextEdit):
    """Chat input where Enter sends and Shift+Enter inserts a new line."""

    submitted = Signal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            self.submitted.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class SettingsIconButton(QPushButton):
    """Small monochrome settings glyph that never falls back to an emoji."""

    def __init__(self, callback):
        super().__init__()
        self.setObjectName("settingsButton")
        self.setToolTip("الإعدادات")
        self.setFixedHeight(44)
        self.icon_color = QColor("#ffffff")
        self.clicked.connect(callback)

    def set_dark_theme(self, dark):
        self.icon_color = QColor("#ffffff" if dark else "#000000")
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(self.icon_color, 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        center_x, center_y = self.width() // 2, self.height() // 2
        # A continuous toothed outline reads as a cog, unlike separate radial
        # strokes which resemble a sun icon.
        points = QPolygonF()
        radii = (8.0, 8.0, 10.5, 10.5)
        for index in range(32):
            angle = math.radians(-90 + index * 11.25)
            radius = radii[index % 4]
            points.append(QPointF(
                center_x + math.cos(angle) * radius,
                center_y + math.sin(angle) * radius,
            ))
        painter.drawPolygon(points)
        painter.drawEllipse(QPointF(center_x, center_y), 3.2, 3.2)


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
        self.current_line_color = "#2a2d2e"
        self.gutter_background = "#1e1e1e"
        self.gutter_current = "#c6c6c6"
        self.gutter_text = "#858585"
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.update_line_number_area_width(0)
        self.highlight_current_line()
        self.apply_line_spacing()

    def keyPressEvent(self, event):
        """Support both common Windows redo shortcuts in every editor tab."""
        if event.matches(QKeySequence.Undo):
            self.undo()
            event.accept()
            return
        if event.matches(QKeySequence.Redo) or (
            event.key() == Qt.Key_Z
            and event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier)
        ):
            self.redo()
            event.accept()
            return
        super().keyPressEvent(event)
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
        current_line.format.setBackground(QColor(self.current_line_color))
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

    def set_theme(self, dark):
        self.current_line_color = "#2a2d2e" if dark else "#e8f2fb"
        self.gutter_background = "#1e1e1e" if dark else "#f3f6f9"
        self.gutter_current = "#c6c6c6" if dark else "#1f2937"
        self.gutter_text = "#858585" if dark else "#64748b"
        self.highlight_current_line()
        self.line_number_area.update()

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
        painter.fillRect(event.rect(), QColor(self.gutter_background))
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                color = self.gutter_current if block == self.textCursor().block() else self.gutter_text
                painter.setPen(QColor(color))
                painter.drawText(0, top, self.line_number_area.width() - 6,
                                 self.fontMetrics().height(), Qt.AlignRight, str(number + 1))
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            number += 1


class FindInput(QLineEdit):
    escapePressed = Signal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.escapePressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class WindowControlButton(QPushButton):
    """Font-independent Windows-style minimize, maximize and close button."""

    def __init__(self, control, window):
        super().__init__()
        self.control = control
        self.window = window
        self.setObjectName("closeButton" if control == "close" else "windowButton")
        self.setFixedSize(46, 35)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setPen(QPen(self.palette().buttonText().color(), 1.0))
        center_x, center_y = self.width() // 2, self.height() // 2
        if self.control == "minimize":
            painter.drawLine(center_x - 5, center_y + 4, center_x + 5, center_y + 4)
        elif self.control == "maximize":
            if self.window.isMaximized():
                # Windows restore icon: only the exposed top/right edges of
                # the rear window are visible behind the front window.
                painter.drawLine(center_x - 2, center_y - 4, center_x + 5, center_y - 4)
                painter.drawLine(center_x + 5, center_y - 4, center_x + 5, center_y + 3)
                painter.drawLine(center_x - 2, center_y - 4, center_x - 2, center_y - 2)
                painter.drawRect(center_x - 4, center_y - 2, 7, 7)
            else:
                painter.drawRect(center_x - 4, center_y - 4, 8, 8)
        else:
            painter.drawLine(center_x - 5, center_y - 5, center_x + 5, center_y + 5)
            painter.drawLine(center_x + 5, center_y - 5, center_x - 5, center_y + 5)


class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.old_pos = None
        self.setObjectName("titleBar")
        self.setFixedHeight(35)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(7)

        logo = QLabel("ب")
        logo.setObjectName("titleLogo")
        logo.setAlignment(Qt.AlignCenter)
        logo.setFixedSize(30, 26)
        brand = QLabel("الباء")
        brand.setObjectName("brand")
        separator = QLabel("|")
        separator.setObjectName("titleSeparator")
        document = QLabel("لغة البرمجة العربية")
        document.setObjectName("titleDocument")
        layout.addWidget(logo)
        layout.addWidget(brand)
        layout.addWidget(separator)
        layout.addWidget(document)
        layout.addStretch()
        for control, action in (
            ("minimize", parent.showMinimized),
            ("maximize", parent.toggle_maximized),
            ("close", parent.close),
        ):
            button = WindowControlButton(control, parent)
            button.clicked.connect(action)
            layout.addWidget(button)
            if control == "maximize":
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

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.parent.toggle_maximized()
            event.accept()


class ArabicPyIDE(QMainWindow):
    def __init__(self):
        super().__init__()
        settings = QSettings("AlBaa", "AlBaaIDE")
        self.ai_server_token = settings.value("ai_server_token", "") or secrets.token_urlsafe(24)
        settings.setValue("ai_server_token", self.ai_server_token)
        self.ai_model = str(settings.value("ai_model", DEFAULT_MODEL) or DEFAULT_MODEL).strip()
        self.ide_dark = settings.value("ide_dark", settings.value("ai_chat_dark", True, type=bool), type=bool)
        self.ai_chat_dark = self.ide_dark
        self.ai_messages = []
        self.ai_server = None
        self.current_file = None
        self.autosave_timers = {}
        self.syncing_code_views = False
        self.output_was_visible_before_designer = True
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowTitle("الباء")
        self.resize(1400, 900)
        self.setStyleSheet(self.stylesheet(self.ide_dark))
        self.setup_ui()
        for editor in self.findChildren(CodeEditor):
            editor.set_theme(self.ide_dark)
        for highlighter in self.findChildren(ArabicPyHighlighter):
            highlighter.set_theme(self.ide_dark)
        self.settings_button.set_dark_theme(self.ide_dark)

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
        if hasattr(self, "maximize_button"):
            self.maximize_button.update()

    def stylesheet(self, dark=True):
        base = """
        QMainWindow, QWidget { background: #1e1e1e; color: #cccccc; font-family: 'Tahoma'; font-size: 13px; }
        #titleBar { background: #181818; border-bottom: 1px solid #2b2b2b; }
        #titleLogo { background: #1d9bf0; color: white; border-radius: 7px; font-weight: 800; font-size: 16px; }
        #brand { color: #ffffff; font-weight: 600; font-size: 14px; }
        #titleSeparator { color: #505050; padding: 0 2px; }
        #titleDocument { color: #969696; }
        #windowButton, #closeButton { border: none; border-radius: 0; background: transparent; color: #c8c8c8; font-size: 17px; }
        #windowButton:hover { background: #333333; } #closeButton:hover { background: #c42b1c; color: white; }
        #menuBar, #commandBar { background: #252526; border-bottom: 1px solid #333333; }
        #menuItem { background: transparent; border: none; padding: 4px 10px; color: #d4d4d4; }
        #menuItem:hover, #toolButton:hover { background: #37373d; }
        #toolButton { background: transparent; border: none; border-radius: 3px; padding: 6px 10px; color: #d4d4d4; }
        #runButton { background: #16825d; color: white; border: none; border-radius: 3px; padding: 6px 14px; font-weight: 600; }
        #runButton:hover { background: #1a9b70; }
        #aiButton { background: #007ACC; color: white; border: none; border-radius: 3px; padding: 6px 12px; font-weight: 600; }
        #aiButton:hover { background: #1594E8; }
        #aiChatPanel { background: #000000; border-left: 1px solid #2f3336; }
        #aiChatHeader { background: #000000; border-bottom: 1px solid #2f3336; }
        #aiChatAvatar { background: #1d9bf0; color: #ffffff; border-radius: 7px; font-size: 16px; font-weight: 800; }
        #aiChatTitle { color: #ffffff; font-size: 14px; font-weight: 700; padding: 4px; }
        #aiChatSubtitle { color: #d9f1ff; font-size: 10px; }
        #aiChatHistory { background: #101820; border: none; color: #e9edef; padding: 5px; }
        #aiChatInput { background: #1d2a34; color: #e9edef; border: 1px solid #344550; border-radius: 18px; padding: 9px 12px; }
        #aiChatInput:focus { border: 1px solid #168bd2; }
        #aiThinking { color: #8696a0; padding: 2px 8px; font-size: 11px; }
        #aiSendButton { background: #168bd2; color: white; border: none; border-radius: 21px; font-size: 18px; font-weight: 700; }
        #aiSendButton:hover { background: #27a4ed; }
        #themeButton, #aiCloseButton { background: transparent; color: white; border: none; border-radius: 4px; font-size: 15px; padding: 5px 9px; }
        #themeButton:hover, #aiCloseButton:hover { background: rgba(255,255,255,35); }
        #activityBar { background: #333333; min-width: 48px; max-width: 48px; }
        #activityButton { background: transparent; color: #bdbdbd; border: none; border-radius: 0; font-size: 20px; padding: 11px; }
        #activityButton:hover { background: #454545; color: white; } #activityButton:checked { border-left: 2px solid #007acc; color: white; }
        #settingsButton { background:transparent; color:#ffffff; border:none; font-size:19px; padding:11px; }
        #settingsButton:hover { background:#454545; }
        #sideBar { background: #252526; } #panelTitle { color: #bbbbbb; font-size: 11px; font-weight: 600; padding: 12px 14px 5px; }
        #fileList { background: #252526; border: none; outline: none; color: #cccccc; padding: 2px 6px; }
        #fileList::item { padding: 6px 8px; border-radius: 3px; } #fileList::item:selected { background: #37373d; color: white; }
        #tabBar { background: #252526; border-bottom: 1px solid #1e1e1e; } #activeTab { background: #1e1e1e; color: #ffffff; border-top: 1px solid #007acc; padding: 10px 16px; }
        #pythonTabSpacer { background: #1e1e1e; border-bottom: 1px solid #1e1e1e; }
        #codeEditor { background: #1e1e1e; color: #d4d4d4; border: none; selection-background-color: #264f78; font-family: 'Segoe UI'; font-size: 15px; }
        #codePaneTitle { background: #252526; color: #cccccc; border-bottom: 1px solid #333333; padding: 7px 12px; font-weight: 600; }
        #findBar { background: #252526; border-bottom: 1px solid #333333; }
        #findInput { background: #1e1e1e; color: #ffffff; border: 1px solid #555555; border-radius: 4px; padding: 5px 8px; selection-background-color: #007acc; }
        #findInput:focus { border-color: #007acc; }
        #findStatus { background: transparent; color: #aaaaaa; padding: 0 5px; }
        #pythonPreview { background: #1e1e1e; color: #d4d4d4; border: none; selection-background-color: #264f78; font-family: 'Segoe UI'; font-size: 15px; }
        #outputHeader { background: #252526; border-top: 1px solid #333333; } #outputTitle { background: transparent; border: none; color: #cccccc; font-weight: 600; padding: 7px 12px; }
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
        #phoneNavigation { background: #050505; border-top: 1px solid #2f3336; min-height: 48px; max-height: 48px; }
        #phoneNavigationButton { background: transparent; color: #f2f2f2; border: none; padding: 6px 2px; font-size: 10px; }
        #phoneNavigationButton:hover { background: #16181c; border-radius: 12px; }
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
        if dark:
            return base
        return base + """
        QMainWindow, QWidget { background:#f5f7fa; color:#1f2937; }
        #titleBar { background:#ffffff; border-bottom:1px solid #d7dde5; }
        #brand { color:#111827; } #titleSeparator { color:#9ca3af; } #titleDocument { color:#667085; }
        #windowButton { color:#374151; } #windowButton:hover { background:#e5e7eb; }
        #closeButton { color:#111827; } #closeButton:hover { background:#c42b1c; color:#ffffff; }
        #menuBar, #commandBar { background:#ffffff; border-bottom:1px solid #d7dde5; }
        #menuItem, #toolButton, #themeButton { background:transparent; color:#27364a; }
        #menuItem:hover, #toolButton:hover, #themeButton:hover { background:#e8eef5; }
        #activityBar { background:#eef2f6; } #activityButton { color:#536273; }
        #activityButton:hover { background:#dde5ee; color:#111827; }
        #settingsButton { background:transparent; color:#000000; border:none; }
        #settingsButton:hover { background:#dde5ee; color:#000000; }
        #sideBar, #fileList { background:#f3f6f9; color:#263445; }
        #panelTitle { color:#526173; } #fileList::item:selected { background:#dce8f5; color:#111827; }
        #tabBar, QTabWidget QTabBar { background:#edf1f5; border-bottom:1px solid #d7dde5; }
        #activeTab, QTabWidget QTabBar::tab:selected { background:#ffffff; color:#111827; border-top-color:#007acc; }
        QTabWidget QTabBar::tab { background:#e9eef3; color:#526173; }
        QTabWidget QTabBar::tab:hover { background:#dce5ee; color:#111827; }
        #pythonTabSpacer, #codeEditor, #pythonPreview, #output { background:#ffffff; color:#1f2937; }
        #codeEditor, #pythonPreview { selection-background-color:#b9dcf5; }
        #codePaneTitle, #outputHeader { background:#f3f6f9; color:#334155; border-color:#d7dde5; }
        #findBar { background:#f3f6f9; border-bottom:1px solid #d7dde5; }
        #findInput { background:#ffffff; color:#111827; border:1px solid #aeb8c4; selection-background-color:#007acc; selection-color:#ffffff; }
        #findStatus { color:#667085; }
        #outputTitle { background:transparent; border:none; color:#334155; } QSplitter::handle { background:#d7dde5; }
        #androidDesigner, #designerCanvas { background:#e8edf2; }
        #designerPanel { background:#f3f6f9; } #designerTitle { color:#111827; }
        #designerTool { background:#ffffff; color:#27364a; border-color:#cbd5e1; }
        #designerTool:hover { background:#e8f2fb; border-color:#007acc; }
        #tabCloseButton { color:#526173; }
        QMenu { background:#ffffff; color:#1f2937; border:1px solid #d7dde5; }
        QMenu::item:selected { background:#dceeff; color:#111827; }
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
            ("تصدير مشروع لكل المنصات...", self.export_cross_platform),
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
            ("إعداد GitHub", self.setup_github),
            ("رفع التطبيق إلى GitHub", self.upload_to_github),
            ("إنشاء APK عبر GitHub", self.build_apk_with_github),
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
        self.undo_button = self.make_button("↶ تراجع", lambda: self.editor.undo())
        self.undo_button.setToolTip("تراجع (Ctrl+Z)")
        self.undo_button.setEnabled(False)
        command_layout.addWidget(self.undo_button)
        self.redo_button = self.make_button("↷ إعادة", lambda: self.editor.redo())
        self.redo_button.setToolTip("إعادة (Ctrl+Y أو Ctrl+Shift+Z)")
        self.redo_button.setEnabled(False)
        command_layout.addWidget(self.redo_button)
        command_layout.addWidget(self.make_button("⌕ بحث", self.find_text))
        self.ai_button = self.make_button("✦ مساعد ذكي", self.ask_local_ai, "aiButton")
        self.ai_button.setCheckable(True)
        command_layout.addWidget(self.ai_button)
        self.ai_server_button = self.make_button("شبكة AI", self.toggle_ai_server)
        command_layout.addWidget(self.ai_server_button)
        command_layout.addWidget(self.make_button("مستندات RAG", self.add_rag_documents))
        self.python_toggle_button = self.make_button("◀", self.toggle_python_preview)
        self.python_toggle_button.setFixedWidth(34)
        self.python_toggle_button.setToolTip("إظهار كود Python")
        command_layout.addWidget(self.python_toggle_button)
        command_layout.addStretch()
        self.apk_progress = QProgressBar()
        self.apk_progress.setRange(0, 0)
        self.apk_progress.setFixedWidth(150)
        self.apk_progress.setFixedHeight(18)
        self.apk_progress.setFormat("%p%")
        self.apk_progress.setTextVisible(False)
        self.apk_progress.hide()
        command_layout.addWidget(self.apk_progress)
        self.github_status_label = QLabel("")
        self.github_status_label.setFixedWidth(260)
        self.github_status_label.setAlignment(Qt.AlignCenter)
        self.github_status_label.setStyleSheet(
            "color: #D8DEE9; background: #2A2D2E; border-radius: 4px; padding: 3px 8px;"
        )
        self.github_status_label.hide()
        command_layout.addWidget(self.github_status_label)
        self.github_cancel_button = self.make_button("إلغاء", self.cancel_github_operation)
        self.github_cancel_button.setFixedWidth(58)
        self.github_cancel_button.hide()
        command_layout.addWidget(self.github_cancel_button)
        self.theme_button = self.make_button("☀ المظهر", self.toggle_ide_theme, "themeButton")
        self.theme_button.setToolTip("تبديل مظهر الباء بالكامل")
        command_layout.addWidget(self.theme_button)
        self.github_setup_button = self.make_button("إعداد GitHub", self.setup_github)
        command_layout.addWidget(self.github_setup_button)
        self.github_upload_button = self.make_button("↑ رفع إلى GitHub", self.upload_to_github)
        command_layout.addWidget(self.github_upload_button)
        self.github_apk_button = self.make_button("▣ إنشاء APK", self.build_apk_with_github)
        self.github_apk_button.setToolTip("إنشاء APK سحابيًا عبر GitHub Actions")
        command_layout.addWidget(self.github_apk_button)
        self.package_button = self.make_button("▣ حزم المنصات", self.export_cross_platform)
        self.package_button.setToolTip("توليد مشروع للمتصفح وWindows وLinux وmacOS وAndroid وiOS")
        command_layout.addWidget(self.package_button)
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
        self.settings_button = SettingsIconButton(self.show_about)
        activity_layout.addWidget(self.settings_button)
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
        project = QLabel("⌄  مشاريعي", objectName="panelTitle")
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
        self.tab_widget.tabBarDoubleClicked.connect(self.rename_tab)
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
        self.find_bar = QWidget(objectName="findBar")
        find_layout = QHBoxLayout(self.find_bar)
        find_layout.setDirection(QBoxLayout.RightToLeft)
        find_layout.setContentsMargins(8, 5, 8, 5)
        find_layout.setSpacing(5)
        self.find_input = FindInput(objectName="findInput")
        self.find_input.setPlaceholderText("ابحث في الملف…")
        self.find_input.setClearButtonEnabled(True)
        self.find_input.setMaximumWidth(320)
        self.find_input.returnPressed.connect(self.find_next)
        self.find_input.escapePressed.connect(self.hide_find_bar)
        find_layout.addWidget(self.find_input)
        find_next_button = self.make_button("التالي", self.find_next)
        find_next_button.setToolTip("النتيجة التالية (Enter)")
        find_layout.addWidget(find_next_button)
        self.find_status = QLabel("", objectName="findStatus")
        find_layout.addWidget(self.find_status)
        find_close_button = self.make_button("×", self.hide_find_bar)
        find_close_button.setFixedWidth(30)
        find_close_button.setToolTip("إغلاق (Escape)")
        find_layout.addWidget(find_close_button)
        find_layout.addStretch()
        self.find_bar.hide()
        source_layout.addWidget(self.find_bar)
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
        self.enable_autosave(self.editor)
        self.editor.undoAvailable.connect(self.update_undo_redo_buttons)
        self.editor.redoAvailable.connect(self.update_undo_redo_buttons)
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
        self.editor.display_name = "غير محفوظ.apy"
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

        self.ai_chat_panel = QWidget(objectName="aiChatPanel")
        self.ai_chat_panel.setFixedWidth(360)
        chat_layout = QVBoxLayout(self.ai_chat_panel)
        chat_layout.setContentsMargins(10, 8, 10, 10)
        chat_layout.setSpacing(8)
        self.ai_chat_header = QWidget(objectName="aiChatHeader")
        chat_header = QHBoxLayout(self.ai_chat_header)
        chat_header.setContentsMargins(8, 7, 8, 7)
        self.ai_chat_avatar = QLabel("ب", objectName="aiChatAvatar")
        self.ai_chat_avatar.setAlignment(Qt.AlignCenter)
        self.ai_chat_avatar.setFixedSize(30, 26)
        chat_header.addWidget(self.ai_chat_avatar)
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        self.ai_chat_title = QLabel("مساعد الباء", objectName="aiChatTitle")
        self.ai_chat_subtitle = QLabel("متصل الآن", objectName="aiChatSubtitle")
        title_box.addWidget(self.ai_chat_title)
        title_box.addWidget(self.ai_chat_subtitle)
        chat_header.addLayout(title_box)
        chat_header.addStretch()
        close_chat = self.make_button("×", self.toggle_ai_chat, "aiCloseButton")
        close_chat.setFixedSize(28, 28)
        chat_header.addWidget(close_chat)
        chat_layout.addWidget(self.ai_chat_header)
        model_row = QHBoxLayout()
        model_row.setContentsMargins(8, 0, 8, 0)
        model_row.addWidget(QLabel("النموذج:"))
        self.ai_model_selector = QComboBox(objectName="aiModelSelector")
        self.ai_model_selector.setEditable(True)
        self.ai_model_selector.addItems([
            "qwen3:1.7b",
            "qwen3:8b",
        ])
        if self.ai_model_selector.findText(self.ai_model) < 0:
            self.ai_model_selector.addItem(self.ai_model)
        self.ai_model_selector.setCurrentText(self.ai_model)
        self.ai_model_selector.setToolTip("اختر نموذج Ollama لهذا الجهاز أو اكتب اسمه")
        self.ai_model_selector.currentTextChanged.connect(self.save_ai_model)
        model_row.addWidget(self.ai_model_selector, 1)
        chat_layout.addLayout(model_row)
        self.ai_download_progress = QProgressBar(objectName="aiDownloadProgress")
        self.ai_download_progress.setRange(0, 100)
        self.ai_download_progress.setFormat("تنزيل النموذج: %p%")
        self.ai_download_progress.setTextVisible(True)
        self.ai_download_progress.hide()
        download_row = QHBoxLayout()
        download_row.setContentsMargins(0, 0, 0, 0)
        download_row.addWidget(self.ai_download_progress, 1)
        self.ai_download_pause_button = self.make_button("إيقاف", self.toggle_ai_model_download)
        self.ai_download_pause_button.setFixedWidth(62)
        self.ai_download_pause_button.hide()
        download_row.addWidget(self.ai_download_pause_button)
        chat_layout.addLayout(download_row)
        self.ai_chat_history = QScrollArea(objectName="aiChatHistory")
        self.ai_chat_history.setWidgetResizable(True)
        self.ai_chat_history.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ai_chat_content = QWidget(objectName="aiChatContent")
        self.ai_chat_messages_layout = QVBoxLayout(self.ai_chat_content)
        self.ai_chat_messages_layout.setContentsMargins(4, 10, 4, 10)
        self.ai_chat_messages_layout.setSpacing(7)
        self.ai_chat_messages_layout.addStretch(1)
        self.ai_chat_history.setWidget(self.ai_chat_content)
        chat_layout.addWidget(self.ai_chat_history)
        self.ai_thinking_label = QLabel("مساعد الباء يكتب الآن…", objectName="aiThinking")
        self.ai_thinking_label.setAlignment(Qt.AlignRight)
        self.ai_thinking_label.hide()
        chat_layout.addWidget(self.ai_thinking_label)
        self.ai_composer = QWidget(objectName="aiComposer")
        self.ai_composer.setFixedHeight(58)
        self.ai_composer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        composer_layout = QHBoxLayout(self.ai_composer)
        composer_layout.setContentsMargins(0, 5, 0, 5)
        composer_layout.setSpacing(7)
        self.ai_chat_input = AIChatInput(objectName="aiChatInput")
        self.ai_chat_input.setPlaceholderText("اكتب رسالتك هنا...")
        self.ai_chat_input.setToolTip("Enter للإرسال — Shift+Enter لسطر جديد")
        self.ai_chat_input.setFixedHeight(48)
        self.ai_chat_input.submitted.connect(self.send_ai_message)
        composer_layout.addWidget(self.ai_chat_input)
        self.ai_send_button = self.make_button("➤", self.send_ai_message, "aiSendButton")
        self.ai_send_button.setToolTip("إرسال")
        self.ai_send_button.setFixedSize(44, 44)
        composer_layout.addWidget(self.ai_send_button)
        chat_layout.addWidget(self.ai_composer)
        self.apply_ai_chat_theme()
        self.ai_chat_panel.hide()
        workspace.addWidget(self.ai_chat_panel)
        layout.addLayout(workspace)

        status = QWidget(objectName="statusBar")
        status_layout = QHBoxLayout(status)
        status_layout.setDirection(QBoxLayout.RightToLeft)
        status_layout.setContentsMargins(4, 0, 4, 0)
        status_layout.addWidget(QLabel("◉  الباء", objectName="statusLabel"))
        self.autosave_status_label = QLabel("الحفظ التلقائي مفعّل", objectName="statusLabel")
        status_layout.addWidget(self.autosave_status_label)
        status_layout.addStretch()
        self.position_label = QLabel("السطر 1، العمود 1", objectName="statusLabel")
        status_layout.addWidget(self.position_label)
        status_layout.addWidget(QLabel("UTF-8     العربية", objectName="statusLabel"))
        self.editor.cursorPositionChanged.connect(self.update_position)
        layout.addWidget(status)
        self.setCentralWidget(root)
        self.android_project_path = None
        self.android_build_process = None
        self.apk_install_process = None
        self.apk_install_stage = None
        self.github_process = None
        self.github_project_path = None
        self.github_operation = None
        self.github_repo_name = None
        self.github_download_path = None
        self.github_elapsed_seconds = 0
        self.github_phase_label = ""
        self.github_cancel_requested = False
        self.ai_process = None
        self.embedded_ai_process = None
        self.pending_ai_payload = None
        self.pending_ai_engine = None
        self.pending_ai_model = None
        self.ai_download_manager = QNetworkAccessManager(self)
        self.ai_download_reply = None
        self.ai_download_stream = None
        self.ai_download_offset = 0
        self.ai_download_paused = False
        self.ai_download_profile = None
        self.ai_download_destination = None
        self.ai_backend = "ollama"
        self.ai_engine_wait_attempts = 0
        self.ai_response_buffer = bytearray()
        self.github_elapsed_timer = QTimer(self)
        self.github_elapsed_timer.timeout.connect(self.update_github_elapsed_time)
        self.updating_from_designer = False
        self.refresh_file_list()

    def refresh_file_list(self):
        self.file_list.clear()
        settings = QSettings("AlBaa", "AlBaaIDE")
        paths = settings.value("project_files", [], type=list)
        existing_paths = []
        for path in paths:
            path = os.path.abspath(str(path))
            if os.path.isfile(path) and path.endswith((".apy", ".py")):
                existing_paths.append(path)
                item = QListWidgetItem(f"  ◇  {os.path.basename(path)}")
                item.setToolTip(path)
                item.setData(Qt.UserRole, path)
                self.file_list.addItem(item)
        if existing_paths != list(paths):
            settings.setValue("project_files", existing_paths)

    def remember_project_file(self, path):
        """Keep only files the user explicitly opened or saved in My Projects."""
        path = os.path.abspath(path)
        settings = QSettings("AlBaa", "AlBaaIDE")
        paths = [os.path.abspath(str(item)) for item in settings.value("project_files", [], type=list)]
        paths = [item for item in paths if item != path]
        paths.insert(0, path)
        settings.setValue("project_files", paths)
        self.refresh_file_list()

    def align_code_pane_headers(self):
        """Match Python's header height to ArabicPy's document-tab row."""
        self.python_tab_spacer.setFixedHeight(self.tab_widget.tabBar().height())

    def update_tab_title(self, modified=False):
        index = self.tab_widget.indexOf(self.editor)
        if index >= 0:
            name = os.path.basename(
                getattr(self.editor, "file_path", "")
                or getattr(self.editor, "display_name", "غير محفوظ.apy")
            )
            marker = "● " if modified else ""
            self.tab_widget.setTabText(index, marker + name)
        return
        name = os.path.basename(self.current_file) if self.current_file else "غير محفوظ.apy"
        self.active_tab.setText(f"  {'●' if modified else '◇'}  {name}    ×")

    def switch_tab(self, index):
        if index >= 0:
            self.editor = self.tab_widget.widget(index)
            self.current_file = getattr(self.editor, "file_path", None)
            self.update_undo_redo_buttons()
            self.update_position()
            self.update_python_preview()
            if self.android_designer.isVisible():
                if is_android_source(self.editor.toPlainText()):
                    self.android_designer.load_source(self.editor.toPlainText())
                else:
                    self.hide_android_designer()

    def add_editor_tab(self, content="", path=None):
        editor = CodeEditor()
        editor.set_theme(self.ide_dark)
        editor.file_path = path
        editor.display_name = os.path.basename(path) if path else "غير محفوظ.apy"
        editor.highlighter = ArabicPyHighlighter(editor.document())
        editor.highlighter.set_theme(self.ide_dark)
        editor.setPlainText(content)
        editor.document().setModified(False)
        editor.document().modificationChanged.connect(lambda changed: self.update_tab_title(changed))
        self.enable_autosave(editor)
        editor.undoAvailable.connect(self.update_undo_redo_buttons)
        editor.redoAvailable.connect(self.update_undo_redo_buttons)
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

    def enable_autosave(self, editor):
        """Attach an independent, debounced autosave timer to an editor tab."""
        timer = QTimer(editor)
        timer.setSingleShot(True)
        timer.setInterval(1000)
        timer.timeout.connect(lambda source=editor: self.autosave_editor(source))
        self.autosave_timers[editor] = timer
        editor.textChanged.connect(lambda source=editor: self.schedule_autosave(source))

    def schedule_autosave(self, editor):
        timer = self.autosave_timers.get(editor)
        if timer is not None:
            timer.start()
        if hasattr(self, "autosave_status_label"):
            if getattr(editor, "file_path", None):
                self.autosave_status_label.setText("بانتظار الحفظ التلقائي…")
            else:
                self.autosave_status_label.setText("احفظ الملف أول مرة لتفعيل الحفظ التلقائي")

    def autosave_editor(self, editor):
        """Atomically save a named, modified document without interrupting typing."""
        path = getattr(editor, "file_path", None)
        if not path or not editor.document().isModified():
            return
        temporary = path + ".autosave.tmp"
        try:
            with open(temporary, "w", encoding="utf-8") as file:
                file.write(editor.toPlainText())
            os.replace(temporary, path)
            editor.document().setModified(False)
            if editor is self.editor:
                self.current_file = path
                self.update_tab_title(False)
            self.remember_project_file(path)
            if hasattr(self, "autosave_status_label"):
                self.autosave_status_label.setText("تم الحفظ تلقائيًا")
        except OSError as error:
            with contextlib.suppress(OSError):
                os.remove(temporary)
            if hasattr(self, "autosave_status_label"):
                self.autosave_status_label.setText("تعذر الحفظ التلقائي")
                self.autosave_status_label.setToolTip(str(error))

    def update_undo_redo_buttons(self, *_):
        """Keep toolbar actions in sync with the active document's history."""
        editor = getattr(self, "editor", None)
        if editor is None:
            return
        self.undo_button.setEnabled(editor.document().isUndoAvailable())
        self.redo_button.setEnabled(editor.document().isRedoAvailable())

    def rename_tab(self, index):
        if index < 0:
            return
        editor = self.tab_widget.widget(index)
        old_path = getattr(editor, "file_path", None)
        current_name = os.path.basename(old_path or getattr(editor, "display_name", "غير محفوظ.apy"))
        name, accepted = QInputDialog.getText(
            self, "تغيير اسم الملف", "الاسم الجديد:", text=current_name
        )
        if not accepted:
            return
        name = name.strip()
        if not name:
            return
        if os.path.basename(name) != name or any(character in name for character in '<>:"/\\|?*'):
            QMessageBox.warning(self, "اسم غير صالح", "اكتب اسم ملف فقط بدون مسار أو رموز غير مسموحة.")
            return
        if not os.path.splitext(name)[1]:
            name += ".apy"
        if old_path:
            new_path = os.path.join(os.path.dirname(old_path), name)
            if os.path.normcase(new_path) != os.path.normcase(old_path):
                if os.path.exists(new_path):
                    QMessageBox.warning(self, "الاسم مستخدم", "يوجد ملف بهذا الاسم بالفعل.")
                    return
                try:
                    os.rename(old_path, new_path)
                except OSError as error:
                    QMessageBox.critical(self, "تعذر تغيير الاسم", str(error))
                    return
                editor.file_path = new_path
                self.current_file = new_path
                settings = QSettings("AlBaa", "AlBaaIDE")
                paths = settings.value("project_files", [], type=list)
                settings.setValue("project_files", [path for path in paths if os.path.abspath(str(path)) != os.path.abspath(old_path)])
                self.remember_project_file(new_path)
        editor.display_name = name
        self.tab_widget.setTabText(index, ("● " if editor.document().isModified() else "") + name)

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

    def add_rag_documents(self):
        paths, _filter = QFileDialog.getOpenFileNames(
            self,
            "إضافة مستندات إلى معرفة RAG",
            "",
            "المستندات المدعومة (*.txt *.md *.apy *.py *.json *.csv *.pdf *.docx)",
        )
        if not paths:
            return
        added, errors = [], []
        for path in paths:
            self.output.setPlainText(f"جارٍ استخراج وفهرسة:\n{os.path.basename(path)}\n\nقد يستغرق OCR بعض الوقت في أول استخدام.")
            QApplication.processEvents()
            try:
                added.append(import_document(path).name)
            except Exception as error:
                errors.append(f"{os.path.basename(path)}: {error}")
        self.main_splitter.widget(1).show()
        message = f"تمت إضافة {len(added)} مستند إلى مكتبة RAG."
        if added:
            message += "\n\n" + "\n".join(f"✓ {name}" for name in added)
        if errors:
            message += "\n\nتعذر إضافة:\n" + "\n".join(errors)
        self.output.setPlainText(message)

    def ask_local_ai(self, _checked=False):
        self.toggle_ai_chat(show=True)
        self.ai_chat_input.setFocus()

    def save_ai_model(self, model):
        """Persist the Ollama model independently on each device."""
        model = str(model).strip()
        if not model:
            return
        self.ai_model = model
        QSettings("AlBaa", "AlBaaIDE").setValue("ai_model", model)

    def toggle_ai_chat(self, _checked=False, show=None):
        visible = not self.ai_chat_panel.isVisible() if show is None else show
        self.ai_chat_panel.setVisible(visible)
        self.ai_button.setChecked(visible)
        if visible:
            self.ai_chat_input.setFocus()

    def toggle_ide_theme(self, _checked=False):
        self.ide_dark = not self.ide_dark
        self.ai_chat_dark = self.ide_dark
        settings = QSettings("AlBaa", "AlBaaIDE")
        settings.setValue("ide_dark", self.ide_dark)
        settings.setValue("ai_chat_dark", self.ide_dark)
        self.setStyleSheet(self.stylesheet(self.ide_dark))
        for editor in self.findChildren(CodeEditor):
            editor.set_theme(self.ide_dark)
        for highlighter in self.findChildren(ArabicPyHighlighter):
            highlighter.set_theme(self.ide_dark)
        self.settings_button.set_dark_theme(self.ide_dark)
        self.apply_ai_chat_theme()
        self.render_ai_messages()

    def toggle_ai_chat_theme(self, _checked=False):
        """Compatibility alias: themes now apply to the entire IDE."""
        self.toggle_ide_theme()

    def apply_ai_chat_theme(self):
        if self.ai_chat_dark:
            panel, history, composer, text, border, muted = (
                "#000000", "#000000", "#000000", "#f2f2f2", "#2f3336", "#8b98a5"
            )
            self.theme_button.setText("☀ المظهر")
        else:
            panel, history, composer, text, border, muted = (
                "#eaf2f7", "#eaf2f7", "#ffffff", "#17212b", "#c8d4dc", "#667781"
            )
            self.theme_button.setText("☾ المظهر")
        self.ai_chat_panel.setStyleSheet(f"#aiChatPanel {{ background:{panel}; border-left:1px solid {border}; }}")
        self.ai_chat_history.setStyleSheet(f"#aiChatHistory {{ background:{history}; border:none; }}")
        self.ai_chat_content.setStyleSheet(f"#aiChatContent {{ background:{history}; }}")
        self.ai_composer.setStyleSheet(f"#aiComposer {{ background:{panel}; border:none; }}")
        self.ai_chat_header.setStyleSheet(
            f"#aiChatHeader {{ background:{panel}; border-bottom:1px solid {border}; border-radius:0; }}"
        )
        self.ai_chat_avatar.setStyleSheet(
            "#aiChatAvatar { background:#1d9bf0; color:white; border-radius:7px; font-size:16px; font-weight:800; }"
        )
        self.ai_chat_title.setStyleSheet(
            f"background:transparent; color:{text}; border:none; font-size:14px; font-weight:700;"
        )
        self.ai_chat_subtitle.setStyleSheet(
            f"background:transparent; color:{muted}; border:none; font-size:10px;"
        )
        self.ai_chat_input.setStyleSheet(
            f"#aiChatInput {{ background:{composer}; color:{text}; border:1px solid {border}; border-radius:18px; padding:9px 12px; }}"
            "#aiChatInput:focus { border:1px solid #168bd2; }"
        )
        self.ai_thinking_label.setStyleSheet(f"color:{muted}; padding:2px 8px; font-size:11px;")

    def append_ai_message(self, sender, message):
        self.ai_messages.append((sender, message, datetime.now().strftime("%H:%M")))
        self.render_ai_messages()

    def render_ai_messages(self):
        while self.ai_chat_messages_layout.count() > 1:
            item = self.ai_chat_messages_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        for sender, message, timestamp in self.ai_messages:
            self.render_ai_message(sender, message, timestamp)
        QTimer.singleShot(0, lambda: self.ai_chat_history.verticalScrollBar().setValue(
            self.ai_chat_history.verticalScrollBar().maximum()
        ))

    def render_ai_message(self, sender, message, timestamp):
        is_user = sender == "user"
        if self.ai_chat_dark:
            background = "#1d9bf0" if is_user else "#000000"
            foreground = "#ffffff" if is_user else "#f2f2f2"
            muted = "#d8efff" if is_user else "#8b98a5"
            bubble_border = "none" if is_user else "1px solid #2f3336"
        else:
            background = "#168bd2" if is_user else "#ffffff"
            foreground = "#ffffff" if is_user else "#17212b"
            muted = "#d9effc" if is_user else "#667781"
            bubble_border = "none" if is_user else "1px solid #c8d4dc"
        safe_message = html.escape(message).replace("\n", "<br>")
        row = QWidget()
        row.setStyleSheet("background:transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(3, 0, 3, 0)
        bubble = QLabel(
            f'<span style="font-size:13px;">{safe_message}</span><br><br>'
            f'<span style="color:{muted}; font-size:9px;">{timestamp}</span>'
        )
        bubble.setTextFormat(Qt.RichText)
        bubble.setLayoutDirection(Qt.RightToLeft)
        bubble.setAlignment(Qt.AlignRight | Qt.AlignTop)
        bubble.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        bubble.setWordWrap(True)
        metrics = bubble.fontMetrics()
        if is_user:
            longest_line = max(message.splitlines() or [""], key=len)
            natural_width = max(metrics.horizontalAdvance(longest_line), len(longest_line) * 7) + 28
            bubble_width = min(250, max(68, natural_width))
        else:
            bubble_width = 275
        bubble.setContentsMargins(12, 9, 12, 9)
        bubble.setStyleSheet(
            f"QLabel {{ background:{background}; color:{foreground}; border:{bubble_border}; "
            "border-radius:14px; padding:0; }"
        )
        bubble.setFixedWidth(bubble_width)
        text_rect = metrics.boundingRect(
            QRect(0, 0, max(20, bubble_width - 28), 10000),
            Qt.TextWordWrap | Qt.AlignRight,
            message,
        )
        # Some Windows Qt builds severely under-report shaped Arabic text
        # width. Keep a character-based fallback so wrapped lines are never
        # clipped even when QFontMetrics claims a paragraph fits on one line.
        chars_per_line = min(28, max(4, (bubble_width - 28) // 7))
        estimated_lines = sum(
            max(1, (len(line) + chars_per_line - 1) // chars_per_line)
            for line in (message.splitlines() or [""])
        )
        measured_height = text_rect.height() + metrics.height() + 22
        estimated_height = estimated_lines * 19 + 44
        bubble_height = max(measured_height, estimated_height)
        bubble.setFixedHeight(max(44, bubble_height))
        bubble.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        if is_user:
            row_layout.addStretch(1)
            row_layout.addWidget(bubble, 0, Qt.AlignRight)
        else:
            row_layout.addWidget(bubble, 0, Qt.AlignLeft)
            row_layout.addStretch(1)
        self.ai_chat_messages_layout.insertWidget(self.ai_chat_messages_layout.count() - 1, row)

    def send_ai_message(self):
        if self.ai_process is not None:
            QMessageBox.information(self, "المساعد الذكي", "انتظر حتى ينتهي المساعد من الإجابة الحالية.")
            return
        question = self.ai_chat_input.toPlainText().strip()
        if not question:
            return
        self.ai_chat_input.clear()
        self.append_ai_message("user", question)
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"معرفة موثقة مسترجعة من قاعدة الباء:\n{rag_context(question)}\n\n"
            f"كود الباء الحالي:\n{self.editor.toPlainText()}\n\n"
            f"سؤال المستخدم:\n{question}"
        )
        model = self.ai_model_selector.currentText().strip() or DEFAULT_MODEL
        self.save_ai_model(model)
        if shutil.which("ollama"):
            self.ai_backend = "ollama"
            payload = {
                "model": model, "prompt": prompt, "stream": False, "think": False,
            }
            self.start_ai_http_request("http://127.0.0.1:11434/api/generate", payload)
            return
        engine = llama_server_path()
        if engine is None:
            self.append_ai_message(
                "assistant",
                "محرك الذكاء المضمّن غير موجود في هذه النسخة. أعد بناء الباء لتضمين llama.cpp.",
            )
            return
        profile = MODELS.get(model)
        if profile is None:
            self.append_ai_message("assistant", "هذا النموذج غير مدعوم في المحرك المضمّن.")
            return
        settings = QSettings("AlBaa", "AlBaaIDE")
        consent_key = f"embedded_model_consent/{model}"
        if not settings.value(consent_key, False, type=bool):
            answer = QMessageBox.question(
                self, "تنزيل نموذج الذكاء",
                f"سيقوم الباء بتنزيل {profile.label_ar} بحجم يقارب {profile.download_gb:.1f} GB.\n\nهل تريد المتابعة؟",
                QMessageBox.Yes | QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            settings.setValue(consent_key, True)
        self.ai_backend = "embedded"
        self.pending_ai_payload = {
            "model": profile.id,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        local_model = model_path(model)
        if local_model.is_file() and local_model.stat().st_size > 10_000_000:
            self.start_embedded_ai(engine, model, local_model)
        else:
            self.download_embedded_model(engine, model, profile, local_model)

    def download_embedded_model(self, engine, model, profile, destination):
        """Download a selected GGUF model while showing byte-accurate progress."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_suffix(destination.suffix + ".part")
        offset = partial.stat().st_size if partial.exists() else 0
        try:
            self.ai_download_stream = open(partial, "ab" if offset else "wb")
        except OSError as error:
            self.append_ai_message("assistant", f"تعذر إنشاء ملف النموذج: {error}")
            return
        self.pending_ai_engine = engine
        self.pending_ai_model = model
        self.ai_download_profile = profile
        self.ai_download_destination = destination
        self.ai_download_offset = offset
        self.ai_download_expected_total = None
        self.ai_download_paused = False
        request = QNetworkRequest(QUrl(profile.download_url))
        # Large Hugging Face downloads can finish their bytes and then report
        # an HTTP/2 protocol error in Qt. HTTP/1.1 is slower only negligibly
        # here and is substantially more reliable for resumable GGUF files.
        request.setAttribute(QNetworkRequest.Attribute.Http2AllowedAttribute, False)
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
        )
        if offset:
            request.setRawHeader(b"Range", f"bytes={offset}-".encode("ascii"))
        reply = self.ai_download_manager.get(request)
        self.ai_download_reply = reply
        reply.readyRead.connect(self.write_ai_model_chunk)
        reply.downloadProgress.connect(self.update_ai_download_progress)
        reply.metaDataChanged.connect(self.validate_ai_download_resume)
        reply.finished.connect(lambda: self.finish_ai_model_download(partial, destination))
        estimated_total = max(1, int(profile.download_gb * (1024 ** 3)))
        self.ai_download_progress.setRange(0, 100)
        self.ai_download_progress.setValue(min(99, int(offset * 100 / estimated_total)))
        self.ai_download_progress.show()
        self.ai_download_pause_button.setText("إيقاف")
        self.ai_download_pause_button.show()
        self.ai_send_button.setEnabled(False)
        self.ai_thinking_label.setText("جارٍ تنزيل نموذج الذكاء…")
        self.ai_thinking_label.show()

    def validate_ai_download_resume(self):
        """Restart safely if the remote host ignored our Range request."""
        if self.ai_download_reply is None or not self.ai_download_offset:
            return
        status = self.ai_download_reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if status == 200:
            self.ai_download_paused = True
            self.ai_download_reply.abort()

    def toggle_ai_model_download(self):
        if self.ai_download_reply is not None:
            self.ai_download_paused = True
            self.ai_download_reply.abort()
            return
        if self.ai_download_profile is not None and self.ai_download_destination is not None:
            self.download_embedded_model(
                self.pending_ai_engine,
                self.pending_ai_model,
                self.ai_download_profile,
                self.ai_download_destination,
            )

    def write_ai_model_chunk(self):
        if self.ai_download_reply is not None and self.ai_download_stream is not None:
            self.ai_download_stream.write(bytes(self.ai_download_reply.readAll()))

    def update_ai_download_progress(self, received, total):
        if total > 0:
            accumulated = self.ai_download_offset + received
            complete_total = self.ai_download_offset + total
            self.ai_download_expected_total = complete_total
            percent = max(0, min(100, int(accumulated * 100 / complete_total)))
            received_gb = accumulated / (1024 ** 3)
            total_gb = complete_total / (1024 ** 3)
            self.ai_download_progress.setValue(percent)
            self.ai_download_progress.setFormat(
                f"تنزيل النموذج: {percent}% — {received_gb:.2f} / {total_gb:.2f} GB"
            )
        else:
            self.ai_download_progress.setRange(0, 0)
            self.ai_download_progress.setFormat("جارٍ تنزيل النموذج…")

    def finish_ai_model_download(self, partial, destination):
        reply = self.ai_download_reply
        self.write_ai_model_chunk()
        if self.ai_download_stream is not None:
            self.ai_download_stream.close()
        self.ai_download_stream = None
        self.ai_download_reply = None
        failed = reply is None or reply.error() != QNetworkReply.NetworkError.NoError
        error_text = reply.errorString() if reply is not None else "خطأ غير معروف"
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) if reply is not None else None
        if reply is not None:
            content_range = bytes(reply.rawHeader(b"Content-Range")).decode("ascii", errors="ignore")
            total_match = re.search(r"/(\d+)$", content_range)
            if total_match:
                self.ai_download_expected_total = int(total_match.group(1))
        # Some Qt versions report a protocol error after emitting 100%. Accept
        # the download only when its exact announced size and GGUF signature
        # prove that all model bytes reached disk.
        if failed and partial.is_file() and self.ai_download_expected_total:
            try:
                with open(partial, "rb") as downloaded:
                    valid_header = downloaded.read(4) == b"GGUF"
                complete_size = partial.stat().st_size == self.ai_download_expected_total
            except OSError:
                valid_header = complete_size = False
            if valid_header and complete_size:
                failed = False
        if reply is not None:
            reply.deleteLater()
        if self.ai_download_paused:
            # A 200 response after requesting a range means resume is unsupported;
            # discard the newly appended bytes and restart cleanly.
            if self.ai_download_offset and status == 200:
                try:
                    partial.unlink(missing_ok=True)
                except OSError:
                    pass
                self.ai_download_offset = 0
                self.ai_download_paused = False
                self.download_embedded_model(
                    self.pending_ai_engine, self.pending_ai_model,
                    self.ai_download_profile, self.ai_download_destination,
                )
                return
            self.ai_download_progress.setRange(0, 100)
            self.ai_download_progress.setFormat("تم إيقاف التنزيل — اضغط متابعة")
            self.ai_download_pause_button.setText("متابعة")
            self.ai_thinking_label.setText("تنزيل النموذج متوقف مؤقتًا")
            self.ai_send_button.setEnabled(False)
            return
        if failed:
            self.ai_download_progress.hide()
            self.ai_thinking_label.hide()
            self.ai_send_button.setEnabled(False)
            self.ai_download_pause_button.setText("متابعة")
            self.append_ai_message("assistant", f"تعذر تنزيل النموذج: {error_text}")
            return
        try:
            os.replace(partial, destination)
        except OSError as error:
            self.append_ai_message("assistant", f"تعذر حفظ النموذج: {error}")
            self.ai_send_button.setEnabled(True)
            return
        self.ai_download_progress.setRange(0, 100)
        self.ai_download_progress.setValue(100)
        self.ai_download_progress.setFormat("اكتمل تنزيل النموذج — 100%")
        self.ai_download_pause_button.hide()
        self.ai_download_profile = None
        self.ai_download_destination = None
        engine, model = self.pending_ai_engine, self.pending_ai_model
        self.pending_ai_engine = self.pending_ai_model = None
        self.start_embedded_ai(engine, model, destination)

    def start_embedded_ai(self, engine, model, local_model=None):
        """Start the bundled llama.cpp server and wait without blocking the UI."""
        if self.embedded_ai_process is None:
            process = QProcess(self)
            process.setProgram(str(engine))
            process.setArguments(server_arguments(model, local_model))
            process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            process.finished.connect(self.embedded_ai_stopped)
            process.start()
            self.embedded_ai_process = process
        self.ai_thinking_label.setText("جارٍ تنزيل أو تحميل نموذج الذكاء…")
        self.ai_thinking_label.show()
        self.ai_send_button.setEnabled(False)
        self.ai_engine_wait_attempts = 0
        QTimer.singleShot(500, self.wait_for_embedded_ai)

    def wait_for_embedded_ai(self):
        """Poll the loopback server until the model is ready."""
        self.ai_engine_wait_attempts += 1
        try:
            connection = socket.create_connection(("127.0.0.1", 11435), timeout=0.15)
            connection.close()
        except OSError:
            if self.embedded_ai_process is None or self.ai_engine_wait_attempts >= 3600:
                self.ai_thinking_label.hide()
                self.ai_send_button.setEnabled(True)
                self.append_ai_message("assistant", "تعذر تشغيل محرك الذكاء المضمّن.")
                return
            QTimer.singleShot(500, self.wait_for_embedded_ai)
            return
        payload = self.pending_ai_payload
        self.pending_ai_payload = None
        self.ai_download_progress.hide()
        self.ai_download_pause_button.hide()
        self.ai_thinking_label.setText("مساعد الباء يكتب الآن…")
        self.start_ai_http_request(f"{EMBEDDED_BASE_URL}/v1/chat/completions", payload)

    def embedded_ai_stopped(self, _exit_code, _status):
        if self.embedded_ai_process is not None:
            self.embedded_ai_process.deleteLater()
        self.embedded_ai_process = None

    def start_ai_http_request(self, endpoint, payload):
        """Send a request to either supported local AI runtime."""
        self.ai_thinking_label.show()
        self.ai_button.setEnabled(False)
        self.ai_send_button.setEnabled(False)
        self.ai_send_button.setText("…")
        self.ai_response_buffer.clear()
        process = QProcess(self)
        self.ai_process = process
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(self.read_local_ai_output)
        process.finished.connect(self.local_ai_finished)
        process.errorOccurred.connect(self.local_ai_error)
        process.setProgram("curl.exe")
        process.setArguments([
            "-sS", "-X", "POST", endpoint,
            "-H", "Content-Type: application/json",
            "-d", json.dumps(payload, ensure_ascii=False),
        ])
        process.start()

    def read_local_ai_output(self):
        if self.ai_process is None:
            return
        data = bytes(self.ai_process.readAllStandardOutput())
        if data:
            self.ai_response_buffer.extend(data)

    def local_ai_finished(self, exit_code, _status):
        process = self.ai_process
        if process is not None:
            self.read_local_ai_output()
            process.deleteLater()
        self.ai_process = None
        self.ai_button.setEnabled(True)
        self.ai_send_button.setEnabled(True)
        self.ai_send_button.setText("➤")
        self.ai_thinking_label.hide()
        raw = bytes(self.ai_response_buffer).decode("utf-8", errors="replace")
        try:
            result = json.loads(raw)
            if self.ai_backend == "embedded":
                answer = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            else:
                answer = result.get("response", "").strip()
        except json.JSONDecodeError:
            answer = ""
        if exit_code == 0 and answer:
            self.append_ai_message("assistant", answer)
        else:
            self.append_ai_message("assistant", f"تعذر تشغيل {self.ai_model}. تأكد أن النموذج مثبت أو أعد المحاولة.")

    def local_ai_error(self, _error):
        self.ai_thinking_label.hide()
        if self.ai_process is not None:
            self.append_ai_message("assistant", "تعذر بدء الاتصال بمحرك الذكاء المحلي.")

    def ensure_ai_server(self):
        if self.ai_server is not None:
            return True
        model = self.ai_model_selector.currentText().strip() or DEFAULT_MODEL
        self.save_ai_model(model)
        server = AlBaaAIServer(self.ai_server_token, model=model)
        try:
            server.start()
        except OSError as error:
            QMessageBox.critical(
                self, "تعذر تشغيل شبكة AI",
                f"تعذر فتح المنفذ 8765 على هذا الجهاز:\n{error}",
            )
            return False
        self.ai_server = server
        self.ai_server_button.setText("إيقاف شبكة AI")
        self.main_splitter.widget(1).show()
        self.output.setPlainText(
            "خادم الذكاء يعمل على شبكة Wi-Fi المحلية.\n\n"
            f"العنوان: {server.address}\n"
            f"رمز الوصول: {self.ai_server_token}\n\n"
            "يجب أن يكون الهاتف والكمبيوتر على نفس Wi-Fi. "
            "إذا ظهرت نافذة جدار حماية Windows فاسمح بالوصول للشبكات الخاصة فقط."
        )
        return True

    def toggle_ai_server(self):
        if self.ai_server is None:
            if self.ensure_ai_server():
                QMessageBox.information(
                    self, "شبكة AI جاهزة",
                    f"العنوان: {self.ai_server.address}\n\n"
                    "اترك الباء وOllama يعملان أثناء استخدام تطبيق الهاتف.",
                )
            return
        self.ai_server.stop()
        self.ai_server = None
        self.ai_server_button.setText("شبكة AI")
        self.output.setPlainText("تم إيقاف خادم الذكاء المحلي.")

    def ai_export_credentials(self):
        if not self.ensure_ai_server():
            return None, None
        return self.ai_server.address, self.ai_server_token

    def closeEvent(self, event):
        if self.ai_server is not None:
            self.ai_server.stop()
            self.ai_server = None
        if self.embedded_ai_process is not None:
            self.embedded_ai_process.terminate()
            self.embedded_ai_process.waitForFinished(2000)
            self.embedded_ai_process = None
        if self.ai_download_reply is not None:
            self.ai_download_reply.abort()
        if self.ai_download_stream is not None:
            self.ai_download_stream.close()
            self.ai_download_stream = None
        super().closeEvent(event)

    def new_android_file(self):
        source = (
            'اسم التطبيق هو الباء\n\n'
            'في شريط السفلي ضع:\n'
            '    الرئيسية\n'
            '    البحث\n'
            '    التنبيهات\n'
            '    الرسائل\n\n'
            'اطبع "ما هو اسمك"\n\n'
            'الاسم = حقل "اكتب اسمك"\n\n'
            'اطبع الاسم\n'
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
            error = self.android_designer.last_error
            message = format_error(error, source) if error else "تعذر قراءة كود التطبيق."
            self.editor.show_error_line(getattr(error, "line", None))
            self.main_splitter.widget(1).show()
            self.main_splitter.setSizes([650, 190])
            self.output.setPlainText(message)
            QMessageBox.warning(
                self,
                "تعذر فتح التصميم",
                f"أصلح الخطأ أولاً:\n\n{getattr(error, 'message', str(error))}",
            )
            return
        self.editor.clear_error_line()
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
            ai_url, ai_token = self.ai_export_credentials()
            if not ai_url:
                return None
            export_android_project(source, directory, ai_url, ai_token)
        except Exception as error:
            self.output.setPlainText(format_error(error, source))
            return False

        self.android_project_path = directory
        self.main_splitter.widget(1).show()
        self.output.setPlainText(
            f"تم تصدير مشروع Android إلى:\n{directory}\n\n"
            "يمكنك رفعه إلى GitHub أو إنشاء APK عبر GitHub Actions."
        )
        return True

    def export_cross_platform(self):
        source = self.editor.toPlainText()
        if not is_android_source(source):
            QMessageBox.warning(self, "ليس تطبيقًا", "افتح أو أنشئ مشروع تطبيق من الباء أولًا.")
            return False
        directory = QFileDialog.getExistingDirectory(self, "اختر مجلد مشروع كل المنصات")
        if not directory:
            return False
        try:
            export_tauri_project(source, directory)
        except Exception as error:
            self.output.setPlainText(format_error(error, source))
            QMessageBox.critical(self, "تعذر التصدير", str(error))
            return False
        self.main_splitter.widget(1).show()
        self.output.setPlainText(
            "تم إنشاء مشروع Tauri 2 بنجاح.\n"
            "المنصات: المتصفح، Windows، Linux، macOS، Android، iOS.\n\n"
            f"المجلد: {directory}\n\n"
            "ملفات سطح المكتب تُبنى عبر GitHub Actions. "
            "يتطلب بناء iOS جهاز macOS وXcode، ويتطلب Android إعداد Android Studio/SDK."
        )
        QMessageBox.information(self, "تم إنشاء المشروع", "تم إنشاء مشروع متعدد المنصات بنجاح.")
        return True

    def github_cli_path(self):
        """Locate GitHub CLI, including a fresh Winget installation."""
        found = shutil.which("gh")
        if found:
            return found
        candidates = [
            os.path.join(os.environ.get("ProgramFiles", ""), "GitHub CLI", "gh.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "GitHub CLI", "gh.exe"),
        ]
        return next((path for path in candidates if path and os.path.isfile(path)), None)

    def github_is_authenticated(self):
        gh_path = self.github_cli_path()
        if not gh_path:
            return False
        check = QProcess(self)
        check.setProgram(gh_path)
        check.setArguments(["auth", "status"])
        check.start()
        return check.waitForStarted(2500) and check.waitForFinished(8000) and check.exitCode() == 0

    def github_has_workflow_scope(self):
        """Return whether the active token may create Actions workflows."""
        gh_path = self.github_cli_path()
        if not gh_path:
            return False
        check = QProcess(self)
        check.setProgram(gh_path)
        check.setArguments(["api", "-i", "user"])
        check.start()
        if not check.waitForStarted(2500) or not check.waitForFinished(8000):
            return False
        headers = bytes(check.readAllStandardOutput()).decode("utf-8", errors="replace").lower()
        return any(
            "workflow" in line for line in headers.splitlines()
            if line.startswith("x-oauth-scopes:")
        )

    def set_github_busy(self, busy, label="عملية GitHub جارية"):
        for button in (
            self.github_setup_button, self.github_upload_button,
            self.github_apk_button,
        ):
            button.setEnabled(not busy)
        if busy:
            self.github_cancel_requested = False
            self.github_elapsed_seconds = 0
            self.github_phase_label = label
            self.update_github_elapsed_time()
            self.github_status_label.show()
            self.github_cancel_button.show()
            self.github_elapsed_timer.start(1000)
            if self.github_operation in ("upload", "build_upload", "build"):
                self.apk_progress.setRange(0, 100)
                self.apk_progress.setValue(
                    10 if self.github_operation in ("upload", "build_upload") else 20
                )
                self.apk_progress.setTextVisible(True)
            else:
                self.apk_progress.setRange(0, 0)
                self.apk_progress.setTextVisible(False)
            self.apk_progress.setToolTip(label)
            self.apk_progress.show()
        else:
            self.github_elapsed_timer.stop()
            self.github_status_label.hide()
            self.github_cancel_button.hide()
            self.apk_progress.hide()

    def update_github_elapsed_time(self):
        minutes, seconds = divmod(self.github_elapsed_seconds, 60)
        phases = {
            "install": "تثبيت GitHub",
            "login": "تسجيل الدخول",
            "scope": "صلاحية Actions",
            "upload": "رفع المشروع",
            "build_upload": "رفع المشروع",
            "build": "بناء APK",
        }
        phase = phases.get(self.github_operation, "GitHub")
        remaining = ""
        if self.github_operation == "build":
            elapsed_minutes = self.github_elapsed_seconds // 60
            minimum_left = max(1, 10 - elapsed_minutes)
            maximum_left = max(minimum_left, 30 - elapsed_minutes)
            remaining = f"  •  متبقي تقريبًا {minimum_left}–{maximum_left} د"
        self.github_status_label.setText(
            f"{phase}  •  {minutes:02d}:{seconds:02d}{remaining}"
        )
        tooltip = self.github_phase_label
        if self.github_operation == "build":
            tooltip += " — يستغرق عادةً 10–30 دقيقة"
        elif self.github_operation in ("login", "scope"):
            tooltip += " — أدخل الرمز الظاهر في المتصفح"
        self.github_status_label.setToolTip(tooltip)
        self.github_elapsed_seconds += 1

    def cancel_github_operation(self):
        process = self.github_process
        if process is None:
            return
        answer = QMessageBox.question(
            self, "إلغاء العملية", "هل تريد إلغاء عملية GitHub الحالية؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.github_cancel_requested = True
        self.output.appendPlainText("\nجارٍ إلغاء عملية GitHub...")
        if self.github_operation == "build" and self.github_project_path:
            gh_path = (self.github_cli_path() or "gh").replace("'", "''")
            cancel_command = (
                f"$gh='{gh_path}'; "
                "$run=& $gh run list --workflow build-apk.yml --event workflow_dispatch "
                "--limit 1 --json databaseId --jq '.[0].databaseId'; "
                "if ($run) { & $gh run cancel $run }"
            )
            QProcess.startDetached(
                "powershell.exe", ["-NoProfile", "-Command", cancel_command],
                self.github_project_path,
            )
        process.terminate()
        QTimer.singleShot(
            3000,
            lambda: process.kill()
            if process.state() != QProcess.ProcessState.NotRunning else None,
        )

    def setup_github(self):
        if self.github_process is not None:
            QMessageBox.information(self, "GitHub", "توجد عملية GitHub جارية بالفعل.")
            return
        gh_path = self.github_cli_path()
        self.main_splitter.widget(1).show()
        if not gh_path:
            self.output.setPlainText("جارٍ تثبيت GitHub CLI عبر Winget...\n")
            process = QProcess(self)
            self.github_process = process
            self.github_operation = "install"
            self.set_github_busy(True, "جارٍ تثبيت GitHub CLI")
            process.setProgram("winget.exe")
            process.setArguments([
                "install", "--id", "GitHub.cli", "-e", "--source", "winget",
                "--accept-package-agreements", "--accept-source-agreements",
            ])
            self.connect_github_process(process)
            process.start()
            return
        if self.github_is_authenticated() and self.github_has_workflow_scope():
            message = "GitHub جاهز ومسجّل الدخول. يمكنك رفع التطبيق أو إنشاء APK."
            self.output.setPlainText(message)
            QMessageBox.information(self, "GitHub جاهز", message)
            return
        if self.github_is_authenticated():
            self.output.setPlainText(
                "الحساب متصل، لكن صلاحية workflow مطلوبة لبناء APK.\n"
                "أدخل الرمز الجديد في GitHub للموافقة على صلاحية Actions.\n\n"
            )
            process = QProcess(self)
            self.github_process = process
            self.github_operation = "scope"
            self.set_github_busy(True, "إضافة صلاحية GitHub Actions")
            QDesktopServices.openUrl(QUrl("https://github.com/login/device"))
            process.setProgram(gh_path)
            process.setArguments(["auth", "refresh", "-h", "github.com", "-s", "workflow"])
            self.connect_github_process(process)
            process.start()
            return
        self.output.setPlainText(
            "سيعرض GitHub رمزًا ويفتح المتصفح لتسجيل الدخول بأمان.\n"
            "أكمل تسجيل الدخول في المتصفح وانتظر رسالة النجاح.\n\n"
        )
        process = QProcess(self)
        self.github_process = process
        self.github_operation = "login"
        self.set_github_busy(True, "في انتظار تسجيل الدخول إلى GitHub")
        QDesktopServices.openUrl(QUrl("https://github.com/login/device"))
        process.setProgram(gh_path)
        process.setArguments(["auth", "login", "--web", "--git-protocol", "https"])
        self.connect_github_process(process)
        process.start()

    def connect_github_process(self, process):
        process.readyReadStandardOutput.connect(self.read_github_output)
        process.readyReadStandardError.connect(self.read_github_output)
        process.errorOccurred.connect(self.github_process_error)
        process.finished.connect(self.github_process_finished)

    def read_github_output(self):
        process = self.github_process
        if process is None:
            return
        data = bytes(process.readAllStandardOutput()) + bytes(process.readAllStandardError())
        if data:
            decoded = data.decode("utf-8", errors="replace").rstrip()
            self.output.appendPlainText(decoded)
            if self.github_operation == "build":
                lowered = decoded.lower()
                stages = (
                    (("queued", "waiting"), 25),
                    (("checkout project", "checkout"), 30),
                    (("set up python", "setup python"), 38),
                    (("install buildozer", "install buildozer requirements"), 48),
                    (("build apk", "buildozer android"), 62),
                    (("upload apk", "upload artifact"), 90),
                    (("completed", "success"), 98),
                )
                for markers, value in stages:
                    if any(marker in lowered for marker in markers):
                        self.apk_progress.setValue(max(self.apk_progress.value(), value))

    def github_process_error(self, _error):
        if self.github_process is None:
            return
        self.output.appendPlainText("\nتعذر بدء أداة GitHub.")

    def prepare_github_project(self):
        source = self.editor.toPlainText()
        if not is_android_source(source):
            QMessageBox.warning(self, "ليس تطبيقًا", "افتح أو أنشئ تطبيقًا قبل الرفع إلى GitHub.")
            return None
        directory = self.github_project_path
        if not directory:
            directory = QFileDialog.getExistingDirectory(
                self, "اختر مجلدًا محليًا لمشروع GitHub"
            )
            if not directory:
                return None
            self.github_project_path = directory
        try:
            ai_url, ai_token = self.ai_export_credentials()
            if not ai_url:
                return False
            export_android_project(source, directory, ai_url, ai_token)
        except Exception as error:
            self.output.setPlainText(format_error(error, source))
            QMessageBox.critical(self, "تعذر تجهيز المشروع", str(error))
            return None
        return directory

    def upload_to_github(self):
        self.start_github_upload(build_after=False)

    def build_apk_with_github(self):
        self.start_github_upload(build_after=True)

    def start_github_upload(self, build_after=False):
        if self.github_process is not None:
            QMessageBox.information(self, "GitHub", "انتظر حتى تنتهي عملية GitHub الحالية.")
            return
        if not self.github_is_authenticated():
            QMessageBox.warning(
                self, "GitHub غير جاهز",
                "اضغط «إعداد GitHub» وثبّت الأداة وسجّل الدخول أولًا."
            )
            return
        if not self.github_has_workflow_scope():
            QMessageBox.warning(
                self, "صلاحية GitHub Actions مطلوبة",
                "اضغط «إعداد GitHub» ووافق على صلاحية workflow قبل الرفع."
            )
            return
        directory = self.prepare_github_project()
        if not directory:
            return
        has_remote = self.git_has_origin(directory)
        repo_name = self.github_repo_name
        if not has_remote and not repo_name:
            default_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", os.path.basename(directory)).strip("-.") or "albaa-app"
            repo_name, accepted = QInputDialog.getText(
                self, "اسم مستودع GitHub", "اكتب اسم المستودع الخاص:", text=default_name
            )
            repo_name = repo_name.strip()
            if not accepted:
                return
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", repo_name):
                QMessageBox.warning(self, "اسم غير صالح", "استخدم حروفًا إنجليزية وأرقامًا و . _ - فقط.")
                return
            self.github_repo_name = repo_name
        gh_path = self.github_cli_path().replace("'", "''")
        repo_arg = (repo_name or "albaa-app").replace("'", "''")
        if has_remote:
            remote_command = "git push -u origin HEAD; exit $LASTEXITCODE"
        else:
            remote_command = (
                "git remote remove origin 2>$null; "
                f"$fullRepo=$login + '/{repo_arg}'; "
                "$existing=& $gh repo view $fullRepo --json name --jq .name 2>$null; "
                "if ($LASTEXITCODE -eq 0) { "
                "git remote add origin ('https://github.com/' + $fullRepo + '.git'); "
                "git push -u origin HEAD "
                f"}} else {{ & $gh repo create '{repo_arg}' --private --source=. --remote=origin --push }}; "
                "exit $LASTEXITCODE"
            )
        command = (
            f"$gh='{gh_path}'; "
            "$login=& $gh api user --jq .login; if ($LASTEXITCODE -ne 0) { exit 1 }; "
            "if (!(Test-Path '.git')) { git init -b main }; "
            "git config user.name $login; git config user.email ($login + '@users.noreply.github.com'); "
            "git config core.autocrlf true; "
            "git add .; git diff --cached --quiet; "
            "if ($LASTEXITCODE -ne 0) { git commit -m 'Update from AlBaa' }; "
            + remote_command
        )
        self.start_github_command(
            command, "build_upload" if build_after else "upload",
            directory, "جارٍ رفع التطبيق إلى GitHub...",
        )

    def git_has_origin(self, directory):
        check = QProcess(self)
        check.setWorkingDirectory(directory)
        check.setProgram("git.exe")
        check.setArguments(["remote", "get-url", "origin"])
        check.start()
        if not check.waitForStarted(2500) or not check.waitForFinished(5000) or check.exitCode() != 0:
            return False
        origin = bytes(check.readAllStandardOutput()).decode("utf-8", errors="replace").strip().lower()
        return (
            origin.startswith("https://github.com/")
            or origin.startswith("git@github.com:")
            or origin.startswith("ssh://git@github.com/")
        )

    def start_github_command(self, command, operation, directory, message):
        self.main_splitter.widget(1).show()
        self.output.setPlainText(message + "\n\n")
        self.github_operation = operation
        self.set_github_busy(True, message)
        process = QProcess(self)
        self.github_process = process
        process.setWorkingDirectory(directory)
        process.setProgram("powershell.exe")
        process.setArguments(["-NoProfile", "-Command", command])
        self.connect_github_process(process)
        process.start()

    def start_github_cloud_build(self):
        directory = self.github_project_path
        gh_path = self.github_cli_path().replace("'", "''")
        download_path = os.path.join(
            directory, "apk-output", datetime.now().strftime("%Y%m%d-%H%M%S")
        )
        self.github_download_path = download_path
        escaped_download = download_path.replace("'", "''")
        command = (
            f"$gh='{gh_path}'; & $gh workflow run build-apk.yml; "
            "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; "
            "$run=''; for ($i=0; $i -lt 20 -and !$run; $i++) { "
            "Start-Sleep -Seconds 3; "
            "$run=& $gh run list --workflow build-apk.yml --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId' }; "
            "if (!$run) { Write-Error 'لم يظهر تشغيل GitHub Actions'; exit 1 }; "
            "& $gh run watch $run --compact --exit-status; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; "
            f"& $gh run download $run --name albaa-android-apk --dir '{escaped_download}'; exit $LASTEXITCODE"
        )
        self.start_github_command(
            command, "build", directory,
            "بدأ إنشاء APK على GitHub. قد يستغرق البناء الأول عدة دقائق...",
        )

    def github_process_finished(self, exit_code, _status):
        operation = self.github_operation
        was_cancelled = self.github_cancel_requested
        process = self.github_process
        if process is not None:
            self.read_github_output()
            process.deleteLater()
        self.github_process = None
        self.github_operation = None
        self.set_github_busy(False)
        if was_cancelled:
            self.github_cancel_requested = False
            self.output.appendPlainText("\nتم إلغاء عملية GitHub.")
            QMessageBox.information(self, "تم الإلغاء", "تم إلغاء عملية GitHub.")
            return
        # Device-flow login can return a non-zero process code after the browser
        # has already authorized and stored a valid credential. Trust the real
        # authenticated state rather than that stale process result.
        if operation == "login" and self.github_is_authenticated():
            exit_code = 0
        if operation == "scope" and self.github_has_workflow_scope():
            exit_code = 0
        if exit_code != 0:
            self.main_splitter.widget(1).show()
            self.main_splitter.setSizes([650, 190])
            output_lines = [
                line.strip() for line in self.output.toPlainText().splitlines()
                if line.strip()
            ]
            details = "\n".join(output_lines[-4:])
            message = f"فشلت عملية GitHub برمز {exit_code}."
            if details:
                message += f"\n\nآخر التفاصيل:\n{details}"
            self.output.appendPlainText("\n" + message)
            QMessageBox.critical(self, "فشلت عملية GitHub", message)
            return
        if operation == "install":
            self.output.appendPlainText("\nتم تثبيت GitHub CLI. أكمل تسجيل الدخول الآن.")
            QTimer.singleShot(0, self.setup_github)
        elif operation == "login":
            QMessageBox.information(self, "تم تسجيل الدخول", "تم ربط «الباء» بحساب GitHub بنجاح.")
        elif operation == "scope":
            QMessageBox.information(
                self, "اكتملت الصلاحيات",
                "تمت إضافة صلاحية GitHub Actions. يمكنك الآن رفع التطبيق وإنشاء APK."
            )
        elif operation == "upload":
            QMessageBox.information(self, "تم الرفع", "تم رفع التطبيق إلى مستودع GitHub خاص بنجاح.")
        elif operation == "build_upload":
            self.start_github_cloud_build()
        elif operation == "build":
            apk_files = []
            if self.github_download_path and os.path.isdir(self.github_download_path):
                for root, _dirs, files in os.walk(self.github_download_path):
                    apk_files.extend(os.path.join(root, name) for name in files if name.endswith(".apk"))
            if apk_files:
                message = f"تم إنشاء وتنزيل APK بنجاح:\n{apk_files[0]}"
                self.output.appendPlainText("\n" + message)
                QMessageBox.information(self, "تم إنشاء APK", message)
            else:
                QMessageBox.warning(self, "لم يُعثر على APK", "نجح GitHub لكن ملف APK غير موجود في مجلد التنزيل.")

    def build_android_apk(self):
        if self.android_build_process is not None:
            self.output.setPlainText("يجري الآن إنشاء APK. انتظر حتى تنتهي العملية.")
            return
        if not self.apk_tools_are_ready():
            self.main_splitter.widget(1).show()
            self.output.setPlainText(
                "أدوات APK غير مكتملة. اضغط أولًا على: تثبيت أدوات APK.\n"
                "إذا ثبّت Windows نظام WSL للتو، أعد تشغيل الجهاز ثم اضغط زر التثبيت مرة أخرى."
            )
            QMessageBox.warning(
                self, "أدوات APK غير جاهزة",
                "لا يمكن إنشاء APK الآن.\n\n"
                "اضغط «تثبيت أدوات APK» وأكمل جميع المراحل أولًا. "
                "قد تحتاج إلى إعادة تشغيل Windows."
            )
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
        self.apk_button.setEnabled(False)
        self.apk_tools_button.setEnabled(False)
        self.apk_button.setText("… جارٍ إنشاء APK")
        self.apk_progress.setToolTip("جارٍ إنشاء APK")
        self.apk_progress.show()
        process.setProgram("wsl.exe")
        process.setArguments([
            "--cd", self.android_project_path,
            "bash", "-lc",
            "BUILDOZER=/opt/albaa-buildozer/bin/buildozer; "
            "if [ ! -x \"$BUILDOZER\" ]; then BUILDOZER=$(command -v buildozer); fi; "
            "if [ -z \"$BUILDOZER\" ]; then echo 'BUILD_TOOLS_MISSING'; exit 127; fi; "
            "\"$BUILDOZER\" android debug",
        ])
        process.readyReadStandardOutput.connect(self.read_android_build_output)
        process.readyReadStandardError.connect(self.read_android_build_output)
        process.errorOccurred.connect(self.android_build_error)
        process.finished.connect(self.android_build_finished)
        process.start()

    def apk_tools_are_ready(self):
        """Return True only when the dedicated Buildozer environment exists."""
        check = QProcess(self)
        check.setProgram("wsl.exe")
        check.setArguments([
            "-u", "root", "--", "test", "-x",
            "/opt/albaa-buildozer/bin/buildozer",
        ])
        check.start()
        if not check.waitForStarted(2500):
            return False
        if not check.waitForFinished(8000):
            check.kill()
            return False
        return check.exitCode() == 0

    def install_apk_tools(self):
        """Install WSL first, then the official Ubuntu Buildozer dependencies."""
        if self.apk_install_process is not None:
            self.output.setPlainText("يجري الآن تثبيت أدوات APK. انتظر حتى تنتهي العملية.")
            return
        self.main_splitter.widget(1).show()
        self.output.setPlainText("فحص WSL2 وUbuntu...\n")
        self.apk_tools_button.setEnabled(False)
        self.apk_button.setEnabled(False)
        self.apk_tools_button.setText("… جارٍ الفحص")
        self.apk_progress.setToolTip("جارٍ فحص وتثبيت أدوات APK")
        self.apk_progress.show()
        self.apk_install_stage = "check"
        process = QProcess(self)
        self.apk_install_process = process
        process.setProgram("wsl.exe")
        # `wsl --status` may exit successfully even when no distribution is
        # installed or WSL2 cannot start. Test the actual Ubuntu environment.
        process.setArguments(["-d", "Ubuntu", "-u", "root", "--", "true"])
        process.readyReadStandardOutput.connect(self.read_apk_install_output)
        process.readyReadStandardError.connect(self.read_apk_install_output)
        process.finished.connect(self.apk_install_finished)
        process.start()

    def read_apk_install_output(self):
        process = self.apk_install_process
        if process is None:
            return
        data = bytes(process.readAllStandardOutput()) + bytes(process.readAllStandardError())
        if data:
            # Windows' WSL messages can be UTF-16, while Linux output is UTF-8.
            encoding = "utf-16" if b"\x00" in data[:20] else "utf-8"
            self.output.appendPlainText(data.decode(encoding, errors="replace").rstrip())

    def apk_install_finished(self, exit_code, _status):
        process = self.apk_install_process
        if process is not None:
            self.read_apk_install_output()
            process.deleteLater()
        self.apk_install_process = None

        if self.apk_install_stage == "check":
            if exit_code != 0:
                self.start_wsl_install()
                return
            self.start_buildozer_install()
            return

        if self.apk_install_stage == "wsl":
            if exit_code == 0:
                message = (
                    "انتهت مرحلة تثبيت WSL2 وUbuntu.\n\n"
                    "أعد تشغيل Windows الآن، ثم افتح «الباء» واضغط "
                    "«تثبيت أدوات APK» مرة أخرى لإكمال Buildozer."
                )
                self.output.appendPlainText("\n" + message)
                QMessageBox.information(self, "انتهت المرحلة الأولى", message)
            else:
                message = (
                    f"فشل تثبيت WSL2 برمز {exit_code}.\n\n"
                    "إذا ظهر الخطأ 14098 (مخزن المكونات تالف)، يستطيع «الباء» "
                    "تشغيل أدوات إصلاح Windows الرسمية الآن. هل تريد بدء الإصلاح؟"
                )
                self.output.appendPlainText("\n" + message)
                answer = QMessageBox.question(
                    self, "فشل تثبيت WSL2", message,
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
                )
                if answer == QMessageBox.Yes:
                    self.start_windows_component_repair()
                    return
            self.reset_apk_install_button()
            return

        if self.apk_install_stage == "repair":
            if exit_code == 0:
                message = (
                    "انتهى إصلاح مكوّنات Windows. أعد تشغيل الجهاز، ثم اضغط "
                    "«تثبيت أدوات APK» مرة أخرى."
                )
                QMessageBox.information(self, "اكتمل إصلاح Windows", message)
            else:
                message = (
                    f"لم يكتمل إصلاح Windows (الرمز {exit_code}). راجع النتيجة في نافذة PowerShell. "
                    "قد تحتاج إلى Windows Update أو مصدر إصلاح Windows مطابق لإصدار جهازك."
                )
                QMessageBox.critical(self, "تعذر إصلاح Windows", message)
            self.output.appendPlainText("\n" + message)
            self.reset_apk_install_button()
            return

        if exit_code == 0:
            message = "اكتمل تثبيت أدوات APK بنجاح. يمكنك الآن الضغط على إنشاء APK."
            self.output.appendPlainText("\n" + message)
            QMessageBox.information(self, "اكتمل التثبيت", message)
        else:
            message = (
                f"فشل تثبيت أدوات APK برمز {exit_code}. راجع سجل المخرجات.\n\n"
                "إذا كانت Ubuntu جديدة، افتحها مرة واحدة وأكمل إعدادها ثم حاول مجددًا."
            )
            self.output.appendPlainText("\n" + message)
            QMessageBox.critical(self, "فشل تثبيت أدوات APK", message)
        self.reset_apk_install_button()

    def start_wsl_install(self):
        """Run the elevated Windows installer while keeping its lifecycle visible."""
        self.apk_install_stage = "wsl"
        self.apk_tools_button.setText("… جارٍ تثبيت WSL2")
        self.output.setPlainText(
            "سيطلب Windows صلاحية المسؤول لتثبيت WSL2 وUbuntu.\n"
            "وافق على النافذة وانتظر حتى تنتهي. لا تغلق «الباء».\n\n"
        )
        elevated_script = (
            "wsl.exe --install --web-download -d Ubuntu; "
            "$result = $LASTEXITCODE; "
            "Write-Host ''; "
            "if ($result -eq 0) { Write-Host 'WSL installation finished.' -ForegroundColor Green } "
            "else { Write-Host ('WSL installation failed. Exit code: ' + $result) -ForegroundColor Red }; "
            "Read-Host 'Press Enter to return to AlBaa'; exit $result"
        )
        encoded_script = base64.b64encode(
            elevated_script.encode("utf-16-le")
        ).decode("ascii")
        command = (
            "$p = Start-Process -FilePath powershell.exe -WindowStyle Normal "
            f"-ArgumentList '-NoProfile','-EncodedCommand','{encoded_script}' "
            "-Verb RunAs -Wait -PassThru; exit $p.ExitCode"
        )
        process = QProcess(self)
        self.apk_install_process = process
        process.setProgram("powershell.exe")
        process.setArguments(["-NoProfile", "-Command", command])
        process.readyReadStandardOutput.connect(self.read_apk_install_output)
        process.readyReadStandardError.connect(self.read_apk_install_output)
        process.finished.connect(self.apk_install_finished)
        process.start()

    def start_buildozer_install(self):
        self.apk_install_stage = "tools"
        self.output.setPlainText(
            "بدء تثبيت Java وBuildozer ومتطلبات Android داخل WSL2...\n"
            "قد يستغرق ذلك عدة دقائق حسب سرعة الإنترنت.\n\n"
        )
        self.apk_tools_button.setText("… جارٍ التثبيت")
        packages = (
            "git zip unzip openjdk-17-jdk python3-pip python3-venv "
            "autoconf libtool pkg-config zlib1g-dev libncurses-dev "
            "libncursesw5-dev cmake libffi-dev libssl-dev automake "
            "autopoint gettext rustc cargo"
        )
        command = (
            "export DEBIAN_FRONTEND=noninteractive; "
            "apt-get update && apt-get install -y " + packages + " && "
            "python3 -m venv /opt/albaa-buildozer && "
            "/opt/albaa-buildozer/bin/pip install --upgrade pip && "
            "/opt/albaa-buildozer/bin/pip install buildozer legacy-cgi setuptools 'cython==0.29.34'"
        )
        process = QProcess(self)
        self.apk_install_process = process
        process.setProgram("wsl.exe")
        process.setArguments(["-u", "root", "--", "bash", "-lc", command])
        process.readyReadStandardOutput.connect(self.read_apk_install_output)
        process.readyReadStandardError.connect(self.read_apk_install_output)
        process.finished.connect(self.apk_install_finished)
        process.start()

    def start_windows_component_repair(self):
        """Run Microsoft DISM then SFC after explicit user confirmation."""
        self.apk_install_stage = "repair"
        self.apk_tools_button.setText("… جارٍ إصلاح Windows")
        self.apk_progress.setToolTip("جارٍ إصلاح مكوّنات Windows")
        self.apk_progress.show()
        self.output.setPlainText(
            "بدء إصلاح مخزن مكوّنات Windows عبر DISM ثم SFC...\n"
            "قد تستغرق العملية وقتًا طويلًا. لا تغلق نافذة PowerShell.\n\n"
        )
        repair_script = (
            "DISM.exe /Online /Cleanup-Image /RestoreHealth; "
            "$dism = $LASTEXITCODE; "
            "if ($dism -eq 0) { sfc.exe /scannow; $result = $LASTEXITCODE } "
            "else { $result = $dism }; "
            "Write-Host ''; "
            "if ($result -eq 0) { Write-Host 'Windows repair finished.' -ForegroundColor Green } "
            "else { Write-Host ('Windows repair failed. Exit code: ' + $result) -ForegroundColor Red }; "
            "Read-Host 'Press Enter to return to AlBaa'; exit $result"
        )
        encoded_script = base64.b64encode(
            repair_script.encode("utf-16-le")
        ).decode("ascii")
        command = (
            "$p = Start-Process -FilePath powershell.exe -WindowStyle Normal "
            f"-ArgumentList '-NoProfile','-EncodedCommand','{encoded_script}' "
            "-Verb RunAs -Wait -PassThru; exit $p.ExitCode"
        )
        process = QProcess(self)
        self.apk_install_process = process
        process.setProgram("powershell.exe")
        process.setArguments(["-NoProfile", "-Command", command])
        process.readyReadStandardOutput.connect(self.read_apk_install_output)
        process.readyReadStandardError.connect(self.read_apk_install_output)
        process.finished.connect(self.apk_install_finished)
        process.start()

    def reset_apk_install_button(self):
        self.apk_install_stage = None
        self.apk_tools_button.setEnabled(True)
        self.apk_button.setEnabled(True)
        self.apk_tools_button.setText("↓ تثبيت أدوات APK")
        self.apk_progress.hide()

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
            self.android_build_process.deleteLater()
            self.android_build_process = None
        self.apk_button.setEnabled(True)
        self.apk_tools_button.setEnabled(True)
        self.apk_button.setText("▣ إنشاء APK")
        self.apk_progress.hide()
        QMessageBox.critical(
            self, "تعذر إنشاء APK",
            "تعذر تشغيل WSL2 أو Buildozer. اضغط «تثبيت أدوات APK» ثم حاول مجددًا."
        )

    def android_build_finished(self, exit_code, _status):
        if exit_code == 0:
            message = "تم إنشاء APK بنجاح. ستجده داخل مجلد bin في المشروع."
            self.output.appendPlainText("\n" + message)
            QMessageBox.information(self, "تم إنشاء APK", message)
        else:
            message = f"فشل إنشاء APK برمز خروج {exit_code}. راجع سجل Buildozer في المخرجات."
            self.output.appendPlainText("\n" + message)
            QMessageBox.critical(self, "فشل إنشاء APK", message)
        if self.android_build_process is not None:
            self.android_build_process.deleteLater()
            self.android_build_process = None
        self.apk_button.setEnabled(True)
        self.apk_tools_button.setEnabled(True)
        self.apk_button.setText("▣ إنشاء APK")
        self.apk_progress.hide()

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
            self.remember_project_file(path)
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
            suggested_name = getattr(editor, "display_name", "غير محفوظ.apy")
            path, _ = QFileDialog.getSaveFileName(self, "حفظ ملف", suggested_name, "ملفات الباء (*.apy)")
            if not path:
                return
            editor.file_path = path
        try:
            with open(editor.file_path, "w", encoding="utf-8") as file:
                file.write(editor.toPlainText())
            timer = self.autosave_timers.get(editor)
            if timer is not None:
                timer.stop()
            editor.document().setModified(False)
            self.current_file = editor.file_path
            self.update_tab_title(False)
            self.remember_project_file(editor.file_path)
            self.autosave_status_label.setText("تم الحفظ")
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
        self.find_bar.show()
        selected = self.editor.textCursor().selectedText()
        if selected:
            self.find_input.setText(selected)
        self.find_status.clear()
        self.find_input.setFocus()
        self.find_input.selectAll()

    def hide_find_bar(self):
        self.find_bar.hide()
        self.editor.setFocus()

    def find_next(self):
        text = self.find_input.text()
        if not text:
            self.find_status.setText("اكتب كلمة للبحث")
            return
        found = self.editor.document().find(text, self.editor.textCursor())
        if found.isNull():
            found = self.editor.document().find(text)
        if found.isNull():
            self.find_status.setText("لا توجد نتائج")
            return
        self.editor.setTextCursor(found)
        self.editor.ensureCursorVisible()
        self.find_status.setText("تم العثور")

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
