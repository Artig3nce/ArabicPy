import contextlib
import base64
import ctypes
import hashlib
import html
import io
import math
import os
import re
import secrets
import shutil
import json
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import subprocess
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QProcess, QRectF, QSettings, QThread, QTimer, QRect, QSize, Qt, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtGui import (
    QAction, QColor, QFont, QIcon, QKeySequence, QPainter, QPainterPath, QPen, QPolygonF, QTextBlockFormat,
    QTextCharFormat, QTextCursor, QTextDocument, QTextFormat,
)
from PySide6.QtWidgets import (
    QApplication, QBoxLayout, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QMenu, QProgressBar, QScrollArea, QSizePolicy, QSplitter, QTabBar, QTabWidget,
    QTextBrowser, QTextEdit, QToolTip, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from . import theme
from .generator import Generator
from .highlighter import ArabicPyHighlighter
from .dart_highlighter import DartHighlighter
from .keywords import KEYWORDS
from .lexer import Lexer
from .parser import Parser
from .android import export_android_project, generate_kivy, is_android_source
from .android_designer import AndroidDesigner
from .tauri_export import export_tauri_project
from .pyside_template import generate_pyside_project, safe_identifier
from . import albaa_linux
from .ai import DEFAULT_MODEL, system_prompt_for, reply as albaa_ai_reply
from .ai_server import AlBaaAIServer, local_ipv4
from .ai_providers import (
    PROVIDER_TYPES, ChatMessage, ProviderConfig, ProviderError, ProviderStore,
    create_provider, list_provider_types,
)
from .updater import installer_asset, is_newer_version
from .version import __version__
from .errors import format_error
from .rag import (
    context_for as rag_context,
    document_display_name as rag_display_name,
    import_document,
    list_documents as list_rag_documents,
    remove_document as remove_rag_document,
)
from .i18n import LANGUAGE_NAMES, TRANSLATIONS


def load_word_notes():
    raw = QSettings("AlBaa", "AlBaaIDE").value("word_notes", "{}")
    try:
        notes = json.loads(str(raw))
        return notes if isinstance(notes, dict) else {}
    except (TypeError, ValueError):
        return {}


def apply_native_dark_title_bar(widget, dark):
    """Ask Windows DWM to match a native dialog title bar to the IDE theme."""
    if os.name != "nt":
        return
    try:
        handle = int(widget.winId())
        enabled = ctypes.c_int(1 if dark else 0)
        # Attribute 20 is supported by current Windows 10/11; 19 is its older name.
        for attribute in (20, 19):
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                handle, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled)
            )
            if result == 0:
                break
    except (AttributeError, OSError, TypeError, ValueError):
        pass


class NativeDialogThemeFilter(QObject):
    """Keep every native dialog title bar synchronized with the IDE theme."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window

    def eventFilter(self, watched, event):
        if isinstance(watched, QDialog) and event.type() == QEvent.Type.Show:
            self.style_dialog(watched)
            QTimer.singleShot(
                0,
                lambda dialog=watched: self.style_dialog(dialog),
            )
        return super().eventFilter(watched, event)

    def style_dialog(self, dialog):
        apply_native_dark_title_bar(dialog, self.window.ide_dark)
        palette = theme.PALETTES.get(self.window.theme_mode, theme.PALETTES[theme.DARK])
        # Graphics effects cache a dialog's rendered pixels. Interactive text
        # fields inside that cache can leave old glyphs behind while typing.
        if dialog.property("albaaNoElevation"):
            dialog.setGraphicsEffect(None)
        else:
            theme.apply_elevation(dialog, palette, "lg", self.window.glass_effects)
        if not dialog.property("albaaDialogStyled"):
            dialog.setStyleSheet(
                dialog.styleSheet()
                + f"""
            QPushButton {{
                background-color: {palette.accent}; color: {palette.text_on_accent}; border: none;
                border-radius: 5px; padding: 7px 18px; min-width: 72px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {palette.accent_hover}; }}
            QPushButton:pressed {{ background-color: {palette.accent_pressed}; }}
            QPushButton:disabled {{ background-color: #4B5563; color: #CBD5E1; }}
            """
            )
            dialog.setProperty("albaaDialogStyled", True)


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


class SendIconButton(QPushButton):
    """A crisp vector send arrow, unlike the ➤ glyph whose look depends on font fallback.
    Swaps to a stop square (Copilot/ChatGPT-style) while a request is in flight."""

    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self.setObjectName("aiSendButton")
        self.icon_color = QColor("#ffffff")
        self.mode = "send"
        self.clicked.connect(callback)

    def set_mode(self, mode):
        """mode is "send" or "stop"."""
        if self.mode != mode:
            self.mode = mode
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.icon_color if self.isEnabled() else QColor(255, 255, 255, 110))
        center_x, center_y = self.width() / 2, self.height() / 2
        if self.mode == "stop":
            side = min(self.width(), self.height()) * 0.34
            painter.drawRoundedRect(
                QRectF(center_x - side / 2, center_y - side / 2, side, side), 2, 2
            )
            return
        size = min(self.width(), self.height()) * 0.26
        # A plain triangle instead of an arrow-with-stem: the stem shape had
        # most of its area low and narrow with a wide flared head up top,
        # so its visual weight sat off-center even though the bounding box
        # was symmetric. Nudged up slightly for optical centering, since a
        # triangle's centroid otherwise reads as sitting a touch low.
        arrow = QPolygonF([
            QPointF(center_x, center_y - size * 1.15),
            QPointF(center_x + size, center_y + size * 0.65),
            QPointF(center_x - size, center_y + size * 0.65),
        ])
        painter.drawPolygon(arrow)


class RAGImportWorker(QThread):
    """Index RAG documents without freezing the IDE."""

    progress = Signal(int, str)
    completed = Signal(list, list)

    def __init__(self, paths, parent=None):
        super().__init__(parent)
        self.paths = list(paths)

    def run(self):
        added, errors = [], []
        total = max(1, len(self.paths))
        for file_index, path in enumerate(self.paths):
            name = os.path.basename(path)

            def report(value, stage="", index=file_index, filename=name):
                overall = int(((index + max(0, min(100, value)) / 100) / total) * 100)
                self.progress.emit(overall, filename)

            try:
                added.append(import_document(path, progress=report).name)
            except Exception as error:
                errors.append(f"{name}: {error}")
            self.progress.emit(int(((file_index + 1) / total) * 100), name)
        self.completed.emit(added, errors)


class SettingsIconButton(QPushButton):
    """Small monochrome settings glyph that never falls back to an emoji."""

    def __init__(self, callback):
        super().__init__()
        self.setObjectName("settingsButton")
        self.setToolTip("Settings")
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


class LanguageCard(QFrame):
    """A big, VS-Code-Extensions-style clickable row for picking a new file's language."""

    clicked = Signal()

    def __init__(self, icon_widget, title, description, parent=None):
        super().__init__(parent)
        self.setObjectName("languageCard")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        layout.addWidget(icon_widget)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        title_label = QLabel(title, objectName="languageCardTitle")
        description_label = QLabel(description, objectName="languageCardDescription")
        description_label.setWordWrap(True)
        text_layout.addWidget(title_label)
        text_layout.addWidget(description_label)
        layout.addLayout(text_layout, 1)

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

    @staticmethod
    def letter_icon(color, letter, size=36):
        """A colored rounded-square badge showing a single letter (used for Al-Baa's ب)."""
        icon = QLabel(letter)
        icon.setFixedSize(size, size)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"background:{color}; color:white; border-radius:8px; font-weight:800; font-size:15px;"
        )
        return icon


class FlutterIconLabel(QLabel):
    """A small painted mark evoking Flutter's blue folded-ribbon logo."""

    def __init__(self, size=36, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setStyleSheet("background:#FFFFFF; border-radius:8px;")

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        side = min(self.width(), self.height())
        ribbon = QPolygonF([
            QPointF(0.30 * side, 0.08 * side), QPointF(0.62 * side, 0.08 * side),
            QPointF(0.30 * side, 0.40 * side), QPointF(0.62 * side, 0.72 * side),
            QPointF(0.30 * side, 0.92 * side), QPointF(0.14 * side, 0.76 * side),
            QPointF(0.38 * side, 0.52 * side), QPointF(0.14 * side, 0.28 * side),
        ])
        painter.setBrush(QColor("#02569B"))
        painter.drawPolygon(ribbon)
        fold = QPolygonF([
            QPointF(0.30 * side, 0.92 * side), QPointF(0.62 * side, 0.72 * side),
            QPointF(0.46 * side, 0.56 * side),
        ])
        painter.setBrush(QColor("#40C4FF"))
        painter.drawPolygon(fold)


class PythonIconLabel(QLabel):
    """A small painted mark evoking Python's two-tone interlocking-snake logo."""

    def __init__(self, size=36, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setStyleSheet("background:#FFFFFF; border-radius:8px;")

    @staticmethod
    def _snake(side, head_rect, tail_rect, radius):
        head = QPainterPath()
        head.addRoundedRect(head_rect, radius, radius)
        tail = QPainterPath()
        tail.addRoundedRect(tail_rect, radius * 0.75, radius * 0.75)
        return head.united(tail)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        side = min(self.width(), self.height())

        blue = self._snake(
            side,
            QRectF(0.12 * side, 0.08 * side, 0.44 * side, 0.44 * side),
            QRectF(0.40 * side, 0.34 * side, 0.38 * side, 0.20 * side),
            0.09 * side,
        )
        painter.setBrush(QColor("#3776AB"))
        painter.drawPath(blue)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QPointF(0.26 * side, 0.22 * side), 0.045 * side, 0.045 * side)

        yellow = self._snake(
            side,
            QRectF(0.44 * side, 0.48 * side, 0.44 * side, 0.44 * side),
            QRectF(0.22 * side, 0.46 * side, 0.38 * side, 0.20 * side),
            0.09 * side,
        )
        painter.setBrush(QColor("#FFD43B"))
        painter.drawPath(yellow)
        painter.setBrush(QColor("#2b2b2b"))
        painter.drawEllipse(QPointF(0.74 * side, 0.78 * side), 0.045 * side, 0.045 * side)


class CodeEditor(QPlainTextEdit):
    """Editor with a compact gutter, current-line cue, and Arabic-friendly defaults."""

    wordDetailsRequested = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.line_number_area = LineNumberArea(self)
        self.setObjectName("codeEditor")
        # Segoe UI provides taller Arabic glyph metrics than Tahoma, avoiding
        # collisions between dots/diacritics on adjacent source lines.
        self.setFont(QFont("Segoe UI", 13))
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.set_text_direction(Qt.LeftToRight)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.error_line = None
        self.current_line_color = "#2a2d2e"
        self.gutter_background = theme.PALETTES[theme.DARK].surface
        self.gutter_current = "#c6c6c6"
        self.gutter_text = "#858585"
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.update_line_number_area_width(0)
        self.highlight_current_line()
        self.apply_line_spacing()
        self._pending_word_card = None
        self.setMouseTracking(True)
        self._hover_word = None
        self._hover_tip = None

    def _word_at(self, pos):
        """Word under pos, or "" if pos isn't actually inside its glyphs.

        cursorForPosition() snaps to the nearest character no matter how far
        pos is from any text, so on a mostly-empty document every mouse
        position would otherwise resolve to the same lone word.
        """
        cursor = self.cursorForPosition(pos)
        cursor.select(QTextCursor.WordUnderCursor)
        if not cursor.hasSelection():
            return "", cursor
        start = QTextCursor(cursor)
        start.setPosition(cursor.selectionStart())
        end = QTextCursor(cursor)
        end.setPosition(cursor.selectionEnd())
        start_rect = self.cursorRect(start)
        end_rect = self.cursorRect(end)
        left = min(start_rect.left(), end_rect.left())
        right = max(start_rect.left(), end_rect.left())
        top = min(start_rect.top(), end_rect.top())
        bottom = max(start_rect.bottom(), end_rect.bottom())
        if not QRect(left, top, right - left, bottom - top).contains(pos):
            return "", cursor
        return cursor.selectedText(), cursor

    def _show_hover_tip(self, global_pos, content):
        tip = self._hover_tip
        if tip is None:
            tip = QLabel(self, Qt.ToolTip | Qt.FramelessWindowHint)
            tip.setObjectName("hoverWordTip")
            tip.setTextFormat(Qt.RichText)
            tip.setAttribute(Qt.WA_ShowWithoutActivating)
            tip.setStyleSheet(
                "QLabel#hoverWordTip {"
                " background:#252526; color:#d4d4d4; border:1px solid #454545;"
                " border-radius:4px; padding:6px 10px; }"
            )
            self._hover_tip = tip
        tip.setText(content)
        tip.adjustSize()
        tip.move(global_pos + QPoint(12, 20))
        tip.show()
        theme.fade_in(tip, duration=140)

    def _hide_hover_tip(self):
        if self._hover_tip is not None:
            self._hover_tip.hide()

    def mouseMoveEvent(self, event):
        source_word, _cursor = self._word_at(event.position().toPoint())
        if source_word != self._hover_word:
            self._hover_word = source_word
            saved = load_word_notes().get(source_word)
            if saved:
                fields = [
                    ("Word", saved.get("word", source_word)),
                    ("Meaning", saved.get("meaning", "")),
                    ("Example", saved.get("example", "")),
                    ("Explanation", saved.get("explanation", "")),
                ]
                content = "<br>".join(
                    f"<b>{label}:</b> {html.escape(str(value))}"
                    for label, value in fields if value
                )
                self._show_hover_tip(event.globalPosition().toPoint(), content)
            else:
                self._hide_hover_tip()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover_word = None
        self._hide_hover_tip()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Ctrl+click any programming word to open its word card."""
        if (
            event.button() == Qt.LeftButton
            and event.modifiers() & Qt.ControlModifier
        ):
            word, cursor = self._word_at(event.position().toPoint())
            if self._is_programming_word(word):
                # Don't open the modal dialog here: the left button is still
                # physically down, so this editor holds Qt's implicit mouse
                # grab until mouseReleaseEvent fires, and a dialog opened
                # before that grab clears won't accept clicks/keystrokes in
                # its fields. Stash the word and open the dialog on release.
                self._pending_word_card = (word, cursor)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        pending = self._pending_word_card
        self._pending_word_card = None
        if pending is not None:
            word, cursor = pending
            event.accept()
            QTimer.singleShot(0, lambda w=word, c=cursor: self.request_word_details(w, c))
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        word, cursor = self._word_at(event.pos())
        if self._is_programming_word(word):
            first_action = menu.actions()[0] if menu.actions() else None
            action = QAction(f"Word details: {word}", menu)
            action.triggered.connect(lambda: self.request_word_details(word, cursor))
            menu.insertAction(first_action, action)
            menu.insertSeparator(first_action)
        menu.exec(event.globalPos())
        menu.deleteLater()

    @staticmethod
    def _is_programming_word(word):
        """Accept identifiers from Python, ArabicPy, and other code tabs."""
        return bool(word and re.fullmatch(r"[^\W\d]\w*", word, re.UNICODE))

    def request_word_details(self, word, cursor):
        self.wordDetailsRequested.emit(word, cursor.block().text().strip())

    def set_text_direction(self, direction):
        """Set paragraph direction and matching alignment together -- Qt doesn't derive one from the other."""
        self.setLayoutDirection(direction)
        text_option = self.document().defaultTextOption()
        text_option.setAlignment(
            (Qt.AlignRight if direction == Qt.RightToLeft else Qt.AlignLeft) | Qt.AlignAbsolute
        )
        self.document().setDefaultTextOption(text_option)

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
        self.gutter_background = theme.PALETTES[theme.DARK if dark else theme.LIGHT].surface
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


class TerminalInput(QLineEdit):
    """A shell-style command entry with Up/Down history navigation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = []
        self.history_index = -1

    def add_to_history(self, command):
        if command.strip() and (not self.history or self.history[-1] != command):
            self.history.append(command)
        self.history_index = len(self.history)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up and self.history:
            self.history_index = max(0, self.history_index - 1)
            self.setText(self.history[self.history_index])
            return
        if event.key() == Qt.Key_Down:
            if self.history_index < len(self.history) - 1:
                self.history_index += 1
                self.setText(self.history[self.history_index])
            else:
                self.history_index = len(self.history)
                self.clear()
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
    def __init__(self, parent, menu_buttons=(), left_actions=(), right_actions=()):
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
        logo.setFixedSize(22, 20)
        layout.addWidget(logo)
        layout.addSpacing(10)
        for button in menu_buttons:
            layout.addWidget(button)
        layout.addStretch()
        for widget in left_actions:
            layout.addWidget(widget)
        layout.addStretch()
        for widget in right_actions:
            layout.addWidget(widget)
        layout.addSpacing(10)
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


class LanguagePickerDialog(QDialog):
    """First-run (and settings-triggered) prompt to choose the IDE's language."""

    def __init__(self, parent=None, dark=True):
        super().__init__(parent)
        self.setWindowTitle("Choose a Language / اختر اللغة")
        self.setModal(True)
        self.setFixedSize(360, 220)
        self.chosen_language = None
        p = theme.PALETTES[theme.DARK if dark else theme.LIGHT]
        self.setStyleSheet(f"QDialog {{ background:{p.surface}; }} QLabel {{ color:{p.text}; }}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        title = QLabel("Choose a language\nاختر اللغة")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 15px; font-weight: 700;")
        layout.addWidget(title)
        layout.addStretch(1)
        for code, label in (("en", "English"), ("ar", "العربية")):
            button = QPushButton(label)
            button.setFixedHeight(42)
            button.setStyleSheet(
                f"QPushButton {{ background:{p.accent}; color:{p.text_on_accent}; border:none; "
                f"border-radius:{theme.RADIUS['sm']}px; font-size:14px; font-weight:600; }}"
                f"QPushButton:hover {{ background:{p.accent_hover}; }}"
                f"QPushButton:pressed {{ background:{p.accent_pressed}; }}"
            )
            button.clicked.connect(lambda _checked=False, value=code: self.choose(value))
            layout.addWidget(button)
        layout.addStretch(1)
        hint = QLabel("You can change this later from Settings.\nيمكنك تغيير هذا لاحقًا من الإعدادات.")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("font-size: 10px; color: #9d9d9d;")
        layout.addWidget(hint)

    def choose(self, code):
        self.chosen_language = code
        self.accept()

    def closeEvent(self, event):
        # A first-run language choice isn't optional -- default to English
        # rather than leaving the IDE in an undefined language state.
        if self.chosen_language is None:
            self.chosen_language = "en"
        super().closeEvent(event)


class ProviderEditDialog(QDialog):
    """Add or edit one configured AI provider. Fields: label, type, base URL,
    API key, default model, plus a "Test Connection" round-trip check."""

    def __init__(self, parent=None, *, language="en", dark=True, existing=None):
        super().__init__(parent)
        self.language = language
        self._existing_id = existing.id if existing is not None else str(uuid.uuid4())
        self._config = None
        self.setWindowTitle(self.t("Edit Provider") if existing is not None else self.t("Add Provider"))
        self.setModal(True)
        self.setMinimumWidth(380)
        p = theme.PALETTES[theme.DARK if dark else theme.LIGHT]
        self.setStyleSheet(
            f"QDialog {{ background:{p.surface}; }}"
            f"QLabel {{ color:{p.text}; background:transparent; }}"
            f"QLineEdit, QComboBox {{ background:{p.surface_alt}; color:{p.text}; border:1px solid {p.border}; "
            f"border-radius:{theme.RADIUS['sm']}px; padding:5px 8px; }}"
            f"QLineEdit:focus, QComboBox:focus {{ border-color:{p.accent}; }}"
            f"QPushButton {{ background:{p.surface_alt}; color:{p.text}; border:1px solid {p.border}; "
            f"border-radius:{theme.RADIUS['sm']}px; padding:6px 14px; }}"
            f"QPushButton:hover {{ border-color:{p.accent}; }}"
        )

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        self.label_edit = QLineEdit(existing.label if existing else "")
        form.addRow(self.t("Label") + ":", self.label_edit)

        self.type_combo = QComboBox()
        for spec in list_provider_types():
            self.type_combo.addItem(spec.display_name, spec.id)
        if existing is not None:
            index = self.type_combo.findData(existing.type)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)
        self.type_combo.currentIndexChanged.connect(self._apply_type_defaults)
        form.addRow(self.t("Type") + ":", self.type_combo)

        self.base_url_edit = QLineEdit(existing.base_url if existing else "")
        form.addRow(self.t("Base URL") + ":", self.base_url_edit)

        self.api_key_edit = QLineEdit(existing.api_key if existing else "")
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(self.t("API Key") + ":", self.api_key_edit)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        if existing and existing.default_model:
            self.model_combo.addItem(existing.default_model)
        form.addRow(self.t("Default Model") + ":", self.model_combo)

        layout.addLayout(form)

        self.test_result_label = QLabel("")
        self.test_result_label.setWordWrap(True)
        layout.addWidget(self.test_result_label)

        button_row = QHBoxLayout()
        test_button = QPushButton(self.t("Test Connection"))
        test_button.clicked.connect(self._test_connection)
        button_row.addWidget(test_button)
        button_row.addStretch()
        cancel_button = QPushButton(self.t("Cancel"))
        cancel_button.clicked.connect(self.reject)
        button_row.addWidget(cancel_button)
        ok_button = QPushButton(self.t("OK"))
        ok_button.setDefault(True)
        ok_button.clicked.connect(self._accept_if_valid)
        button_row.addWidget(ok_button)
        layout.addLayout(button_row)

        if existing is None:
            self._apply_type_defaults()

    def t(self, text, **kwargs):
        if self.language == "ar":
            text = TRANSLATIONS.get(text, text)
        return text.format(**kwargs) if kwargs else text

    def _apply_type_defaults(self):
        spec = PROVIDER_TYPES.get(self.type_combo.currentData())
        if spec is None:
            return
        if not self.base_url_edit.text().strip():
            self.base_url_edit.setPlaceholderText(spec.default_base_url)
        current_model = self.model_combo.currentText().strip()
        self.model_combo.clear()
        self.model_combo.addItems(list(spec.example_models))
        if current_model:
            if self.model_combo.findText(current_model) < 0:
                self.model_combo.addItem(current_model)
            self.model_combo.setCurrentText(current_model)

    def _build_config(self):
        return ProviderConfig(
            id=self._existing_id,
            type=self.type_combo.currentData(),
            label=self.label_edit.text().strip() or self.t("Untitled Provider"),
            base_url=self.base_url_edit.text().strip(),
            api_key=self.api_key_edit.text().strip(),
            default_model=self.model_combo.currentText().strip(),
        )

    def _test_connection(self):
        try:
            provider = create_provider(self._build_config())
        except ProviderError as error:
            self.test_result_label.setText(self.t("Failed: {error}", error=str(error)))
            return
        self.test_result_label.setText(self.t("Testing…"))
        handle = provider.test_connection()
        self._test_handle = handle  # keep a reference alive until it finishes
        handle.finished.connect(lambda _text: self.test_result_label.setText(self.t("Connection succeeded.")))
        handle.failed.connect(lambda error: self.test_result_label.setText(self.t("Connection failed: {error}", error=error)))

    def _accept_if_valid(self):
        if not self.label_edit.text().strip():
            self.label_edit.setFocus()
            return
        self._config = self._build_config()
        self.accept()

    def result_config(self):
        return self._config


class ArabicPyIDE(QMainWindow):
    def __init__(self):
        super().__init__()
        settings = QSettings("AlBaa", "AlBaaIDE")
        self.ai_server_token = settings.value("ai_server_token", "") or secrets.token_urlsafe(24)
        settings.setValue("ai_server_token", self.ai_server_token)
        self.provider_store = ProviderStore()
        self.ai_providers, self.active_provider_id = self.provider_store.load()
        if not self.provider_store.exists():
            legacy_remote_url = str(settings.value("remote_ai_url", "") or "").rstrip("/")
            legacy_remote_token = str(settings.value("remote_ai_token", "") or "")
            legacy_ai_model = str(settings.value("ai_model", "") or "").strip()
            self.ai_providers, self.active_provider_id = self.provider_store.migrate_legacy_settings(
                legacy_remote_url, legacy_remote_token, legacy_ai_model, DEFAULT_MODEL,
            )
        self._active_provider_instance = None
        self._active_provider_instance_id = None
        # theme_mode replaces the old ide_dark/ai_chat_dark booleans; migrate
        # a prior install's dark/light choice into the new setting.
        stored_mode = str(settings.value("ide_theme_mode", "") or "")
        if stored_mode in theme.MODES:
            self.theme_mode = stored_mode
        else:
            legacy_dark = settings.value("ide_dark", settings.value("ai_chat_dark", True, type=bool), type=bool)
            self.theme_mode = theme.DARK if legacy_dark else theme.LIGHT
        self.glass_effects = settings.value("ide_glass_effects", True, type=bool)
        self.project_folder = None
        self.ide_dark = self.theme_mode != theme.LIGHT
        self.ai_chat_dark = self.ide_dark
        self.language = str(settings.value("ui_language", "") or "")
        if self.language not in LANGUAGE_NAMES:
            picker = LanguagePickerDialog(dark=self.ide_dark)
            picker.exec()
            self.language = picker.chosen_language or "en"
            settings.setValue("ui_language", self.language)
        self.rtl = self.language == "ar"
        self.direction = Qt.RightToLeft if self.rtl else Qt.LeftToRight
        self.box_direction = QBoxLayout.RightToLeft if self.rtl else QBoxLayout.LeftToRight
        self.ai_messages = []
        self.ai_server = None
        self.current_file = None
        self.autosave_timers = {}
        self.syncing_code_views = False
        self.output_was_visible_before_designer = True
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowTitle("Al-Baa")
        bundle_root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(__file__)))
        self.setWindowIcon(QIcon(os.path.join(bundle_root, "assets", "albaa.ico")))
        self.resize(1400, 900)
        # Qt auto-grows the window to satisfy new minimum-size demands from
        # child widgets (e.g. the build-progress bar appearing) -- that's
        # normally fine, but on a frameless window it can push the window
        # past the actual monitor edge. Capping maximumSize to the screen's
        # available geometry lets the toolbar still lay out its buttons
        # normally while making sure that growth can never go off-screen.
        active_screen = self.screen() or QApplication.primaryScreen()
        if active_screen is not None:
            self.setMaximumSize(active_screen.availableGeometry().size())
        self.native_dialog_theme_filter = NativeDialogThemeFilter(self)
        QApplication.instance().installEventFilter(self.native_dialog_theme_filter)
        self.setStyleSheet(self.stylesheet())
        self.setup_ui()
        self.ai_messages = self.load_ai_history()
        self.render_ai_messages()
        if os.name == "nt" and self.background_ai_is_running():
            self.ai_server_button.setText(self.t("Stop AI Network"))
        for editor in self.findChildren(CodeEditor):
            editor.set_theme(self.ide_dark)
        for highlighter in self.findChildren(ArabicPyHighlighter):
            highlighter.set_theme(self.ide_dark)
        self.settings_button.set_dark_theme(self.ide_dark)
        self.apply_elevation_effects()
        self.update_manager = QNetworkAccessManager(self)
        self.update_reply = None
        self.update_stream = None
        self.update_asset = None
        self.update_interactive = False
        if getattr(sys, "frozen", False) and os.name == "nt":
            QTimer.singleShot(1500, self.check_for_updates)

    def check_for_updates(self, interactive=False):
        """Check GitHub Releases in the background each time the packaged IDE starts."""
        if self.update_reply is not None:
            if interactive:
                QMessageBox.information(self, "Update Manager", "An update check or download is already running.")
            return
        self.update_interactive = bool(interactive)
        self.update_progress.setRange(0, 0)
        self.update_progress.setFormat("Checking for updates...")
        self.update_progress.show()
        request = QNetworkRequest(QUrl("https://api.github.com/repos/Artig3nce/ArabicPy/releases/latest"))
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setRawHeader(b"User-Agent", b"AlBaa-Updater")
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
        )
        self.update_reply = self.update_manager.get(request)
        self.update_reply.finished.connect(self.update_check_finished)

    def update_check_finished(self):
        reply = self.update_reply
        self.update_reply = None
        if reply is None:
            return
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                if self.update_interactive:
                    QMessageBox.warning(self, "Update Manager", f"Could not check for updates:\n{reply.errorString()}")
                self.update_progress.hide()
                return
            release = json.loads(bytes(reply.readAll()).decode("utf-8"))
            if not is_newer_version(str(release.get("tag_name", "")), __version__):
                self.update_progress.hide()
                if self.update_interactive:
                    QMessageBox.information(self, "Update Manager", f"Al-Baa {__version__} is up to date.")
                return
            asset = installer_asset(release)
            if asset and asset.get("browser_download_url"):
                self.download_update(asset)
            else:
                self.update_progress.hide()
                if self.update_interactive:
                    QMessageBox.warning(self, "Update Manager", "The latest release has no Windows installer.")
        except (TypeError, ValueError, UnicodeError):
            self.update_progress.hide()
            if self.update_interactive:
                QMessageBox.warning(self, "Update Manager", "GitHub returned an invalid update response.")
            return
        finally:
            reply.deleteLater()

    def download_update(self, asset):
        """Download a newer installer to per-user storage without blocking the UI."""
        update_dir = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "AlBaa" / "updates"
        update_dir.mkdir(parents=True, exist_ok=True)
        destination = update_dir / str(asset["name"])
        try:
            self.update_stream = destination.open("wb")
        except OSError as error:
            self.update_progress.hide()
            if self.update_interactive:
                QMessageBox.warning(self, "Update Manager", f"Could not save the update:\n{error}")
            return
        self.update_asset = {**asset, "destination": str(destination)}
        request = QNetworkRequest(QUrl(str(asset["browser_download_url"])))
        request.setRawHeader(b"User-Agent", b"AlBaa-Updater")
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
        )
        self.update_reply = self.update_manager.get(request)
        self.update_reply.readyRead.connect(self.write_update_data)
        self.update_reply.downloadProgress.connect(self.update_download_progress)
        self.update_reply.finished.connect(self.update_download_finished)

    def update_download_progress(self, received, total):
        self.update_progress.show()
        if total > 0:
            self.update_progress.setRange(0, 100)
            self.update_progress.setValue(min(100, int(received * 100 / total)))
            self.update_progress.setFormat("Downloading update: %p%")
        else:
            self.update_progress.setRange(0, 0)
            self.update_progress.setFormat("Downloading update...")

    def write_update_data(self):
        if self.update_reply is not None and self.update_stream is not None:
            self.update_stream.write(bytes(self.update_reply.readAll()))

    def update_download_finished(self):
        reply, stream, asset = self.update_reply, self.update_stream, self.update_asset
        self.update_reply = self.update_stream = self.update_asset = None
        if reply is None or stream is None or asset is None:
            return
        self.write_update_tail(reply, stream)
        destination = Path(asset["destination"])
        try:
            valid = reply.error() == QNetworkReply.NetworkError.NoError
            expected_size = int(asset.get("size", 0) or 0)
            valid = valid and (not expected_size or destination.stat().st_size == expected_size)
            digest = str(asset.get("digest", "") or "")
            if digest.startswith("sha256:"):
                actual = hashlib.sha256(destination.read_bytes()).hexdigest()
                valid = valid and actual.lower() == digest.split(":", 1)[1].lower()
            if valid:
                self.update_progress.setRange(0, 100)
                self.update_progress.setValue(100)
                self.update_progress.setFormat("Installing update...")
                self.install_downloaded_update(destination)
            else:
                self.update_progress.hide()
                destination.unlink(missing_ok=True)
                QMessageBox.warning(self, "Update Manager", "The downloaded update failed validation.")
        except OSError:
            self.update_progress.hide()
            destination.unlink(missing_ok=True)
        finally:
            reply.deleteLater()

    @staticmethod
    def write_update_tail(reply, stream):
        stream.write(bytes(reply.readAll()))
        stream.close()

    def install_downloaded_update(self, installer):
        """Start Inno Setup silently, then leave so it can replace and reopen us."""
        arguments = [
            "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
            "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS",
        ]
        started = QProcess.startDetached(str(installer), arguments)
        started_ok = started[0] if isinstance(started, tuple) else bool(started)
        if started_ok:
            QTimer.singleShot(500, QApplication.instance().quit)
        else:
            self.update_progress.hide()
            QMessageBox.warning(self, "Update Manager", "Could not start the downloaded installer.")

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

    def t(self, text, **kwargs):
        """Translate an English UI string (used as its own dict key) to the active language."""
        if self.language == "ar":
            text = TRANSLATIONS.get(text, text)
        return text.format(**kwargs) if kwargs else text

    def stylesheet(self):
        return theme.build_stylesheet(self.theme_mode, self.glass_effects)

    def make_button(self, text, callback, name="toolButton"):
        button = QPushButton(self.t(text))
        button.setObjectName(name)
        button.clicked.connect(callback)
        return button

    def make_menu_button(self, text, actions):
        """Create a real, clickable top-level menu instead of a decorative label."""
        button = QPushButton(self.t(text))
        button.setObjectName("menuItem")
        button.setLayoutDirection(self.direction)
        menu = QMenu(button)
        menu.setLayoutDirection(self.direction)
        for label, callback in actions:
            menu.addAction(self.t(label), callback)
        button.setMenu(menu)
        return button

    def make_toolbar_menu(self, text):
        """A toolbar dropdown button that groups several related actions behind one menu."""
        button = QPushButton(self.t(text))
        button.setObjectName("toolButton")
        button.setLayoutDirection(self.direction)
        menu = QMenu(button)
        menu.setLayoutDirection(self.direction)
        button.setMenu(menu)
        return button, menu

    def make_menu(self, text, actions):
        """A standalone QMenu (no button of its own) meant to be embedded as a submenu."""
        menu = QMenu(self.t(text))
        menu.setLayoutDirection(self.direction)
        for label, callback in actions:
            menu.addAction(self.t(label), callback)
        return menu

    def build_word_details_panel(self):
        panel = QWidget(objectName="wordDetailsPanel")
        panel.setFixedWidth(320)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(10, 8, 10, 10)
        panel_layout.setSpacing(8)

        header = QWidget(objectName="wordDetailsHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 5, 8, 5)
        self.word_details_avatar = QLabel("W", objectName="wordDetailsAvatar")
        self.word_details_avatar.setAlignment(Qt.AlignCenter)
        self.word_details_avatar.setFixedSize(24, 22)
        header_layout.addWidget(self.word_details_avatar)
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        self.word_details_title = QLabel("Word Details", objectName="wordDetailsTitle")
        self.word_details_subtitle = QLabel("Select a code word", objectName="wordDetailsSubtitle")
        title_box.addWidget(self.word_details_title)
        title_box.addWidget(self.word_details_subtitle)
        header_layout.addLayout(title_box)
        header_layout.addStretch()
        close_button = self.make_button("×", self.close_word_details_panel, "wordDetailsClose")
        close_button.setFixedSize(22, 22)
        header_layout.addWidget(close_button)
        panel_layout.addWidget(header)

        scroll = QScrollArea(objectName="wordDetailsScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget(objectName="wordDetailsBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(8, 8, 8, 8)
        body_layout.setSpacing(7)

        body_layout.addWidget(QLabel("Word"))
        self.word_details_word = QLineEdit(objectName="wordDetailsWord")
        body_layout.addWidget(self.word_details_word)
        body_layout.addWidget(QLabel("Meaning"))
        self.word_details_meaning = QLineEdit(objectName="wordDetailsMeaning")
        self.word_details_meaning.setPlaceholderText("Add your meaning...")
        body_layout.addWidget(self.word_details_meaning)
        body_layout.addWidget(QLabel("Example"))
        self.word_details_example = QPlainTextEdit(objectName="wordDetailsExample")
        self.word_details_example.setMinimumHeight(95)
        body_layout.addWidget(self.word_details_example)
        body_layout.addWidget(QLabel("Explanation"))
        self.word_details_explanation = QTextEdit(objectName="wordDetailsExplanation")
        self.word_details_explanation.setMinimumHeight(120)
        body_layout.addWidget(self.word_details_explanation)
        body_layout.addStretch()
        scroll.setWidget(body)
        panel_layout.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        cancel = QPushButton("Cancel", objectName="wordDetailsCancel")
        cancel.clicked.connect(self.close_word_details_panel)
        save = QPushButton("Save", objectName="wordDetailsSave")
        save.clicked.connect(self.save_word_details_panel)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        panel_layout.addLayout(buttons)
        return panel

    def setup_ui(self):
        root = QWidget(objectName="appCanvas")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        view_button, view_menu = self.make_toolbar_menu("View")
        view_button.setObjectName("menuItem")
        view_menu.addAction(self.t("Toggle Explorer"), self.toggle_sidebar)
        view_menu.addAction(self.t("Toggle Output"), self.toggle_output)
        python_toggle_arrow = "◀" if self.rtl else "▶"
        self.python_toggle_button = view_menu.addAction(f"{python_toggle_arrow} {self.t('Toggle Python Code')}", self.toggle_python_preview)
        self.python_toggle_button.setToolTip(self.t("Show Python Code"))
        view_menu.addSeparator()
        self.theme_button = view_menu.addAction(self.t("☀ Theme"), self.cycle_theme)
        self.theme_button.setToolTip(self.t("Toggle Al-Baa's theme: Dark or Light"))

        ai_menu = QMenu(self.t("AI"))
        ai_menu.setLayoutDirection(self.direction)
        self.ai_server_button = ai_menu.addAction(self.t("AI Network"), self.toggle_ai_server)
        self.manage_providers_button = ai_menu.addAction(self.t("Manage AI Providers..."), self.show_ai_providers_page)
        self.manage_providers_button.setToolTip(self.t("Add, remove, and switch between AI providers"))
        self.rag_button = ai_menu.addAction(self.t("RAG Documents"), self.add_rag_documents)
        ai_menu.addSeparator()
        ai_menu.addAction(self.t("Clear Chat History"), self.clear_ai_history)

        build_menu = QMenu(self.t("Build"))
        build_menu.setLayoutDirection(self.direction)
        self.package_button = build_menu.addAction(self.t("▣ Cross-Platform Bundle"), self.export_cross_platform)
        self.package_button.setToolTip(self.t("Generate a project for Browser, Windows, Linux, macOS, Android, and iOS"))
        self.apk_tools_button = build_menu.addAction(self.t("↓ Install APK Tools"), self.install_apk_tools)
        self.apk_tools_button.setToolTip(self.t("Install the local Android APK build requirements"))
        self.apk_button = build_menu.addAction(self.t("▣ Build APK"), self.build_android_apk)
        self.apk_button.setToolTip(self.t("Export the Android project and build a debug APK"))

        albaa_linux_menu = QMenu(self.t("Al Baa Linux"))
        albaa_linux_menu.setLayoutDirection(self.direction)
        self.linux_builder_tools_button = albaa_linux_menu.addAction(
            self.t("↓ Install Builder Tools"), self.install_linux_builder_tools
        )
        self.linux_builder_tools_button.setToolTip(self.t("Install the live-build toolchain (WSL2 + Ubuntu required)"))
        self.linux_build_iso_button = albaa_linux_menu.addAction(
            self.t("▣ Build Al Baa Linux ISO"), self.build_albaa_linux_iso
        )
        self.linux_build_iso_button.setToolTip(self.t("Build the official, Ubuntu-based Al Baa Linux ISO"))

        android_menu = self.make_menu("Android", [
            ("New Android Project", self.new_android_file),
            ("Export Android Project...", self.export_android),
            ("Install APK Tools", self.install_apk_tools),
            ("Build APK", self.build_android_apk),
        ])
        help_menu = self.make_menu("Help", [
            ("Check for Updates", lambda: self.check_for_updates(True)),
            ("About Al-Baa", self.show_about),
        ])
        overflow_button, overflow_menu = self.make_toolbar_menu("…")
        overflow_button.setObjectName("menuItem")
        overflow_button.setToolTip(self.t("Android, AI, Build, Help"))
        overflow_menu.addMenu(android_menu)
        overflow_menu.addMenu(albaa_linux_menu)
        overflow_menu.addMenu(ai_menu)
        overflow_menu.addMenu(build_menu)
        overflow_menu.addMenu(help_menu)

        edit_button, edit_menu = self.make_toolbar_menu("Edit")
        edit_button.setObjectName("menuItem")
        self.undo_button = edit_menu.addAction(self.t("Undo"), lambda: self.editor.undo())
        self.undo_button.setToolTip(self.t("Undo (Ctrl+Z)"))
        self.undo_button.setEnabled(False)
        self.redo_button = edit_menu.addAction(self.t("Redo"), lambda: self.editor.redo())
        self.redo_button.setToolTip(self.t("Redo (Ctrl+Y or Ctrl+Shift+Z)"))
        self.redo_button.setEnabled(False)
        edit_menu.addAction(self.t("Cut"), lambda: self.editor.cut())
        edit_menu.addAction(self.t("Copy"), lambda: self.editor.copy())
        edit_menu.addAction(self.t("Paste"), lambda: self.editor.paste())

        self.rag_progress = QProgressBar(objectName="ragProgress")
        self.rag_progress.setRange(0, 100)
        self.rag_progress.setValue(0)
        self.rag_progress.setFixedWidth(190)
        self.rag_progress.setFixedHeight(20)
        self.rag_progress.setTextVisible(True)
        self.rag_progress.hide()
        self.apk_progress = QProgressBar()
        self.apk_progress.setRange(0, 0)
        self.apk_progress.setFixedWidth(150)
        self.apk_progress.setFixedHeight(18)
        self.apk_progress.setFormat("%p%")
        self.apk_progress.setTextVisible(False)
        self.apk_progress.hide()
        self.linux_iso_progress = QProgressBar()
        self.linux_iso_progress.setRange(0, 0)
        self.linux_iso_progress.setFixedWidth(150)
        self.linux_iso_progress.setFixedHeight(18)
        self.linux_iso_progress.setFormat("%p%")
        self.linux_iso_progress.setTextVisible(False)
        self.linux_iso_progress.hide()
        self.update_progress = QProgressBar()
        self.update_progress.setFixedWidth(180)
        self.update_progress.setFixedHeight(18)
        self.update_progress.setTextVisible(True)
        self.update_progress.hide()
        self.designer_button = self.make_button("Designer", self.toggle_android_designer)
        self.ai_button = self.make_button("✦", self.ask_local_ai, "aiButton")
        self.ai_button.setToolTip(self.t("AI Assistant"))
        self.ai_button.setFixedSize(24, 24)
        self.ai_button.setCheckable(True)
        self.ai_button.setFocusPolicy(Qt.NoFocus)
        self.run_button = self.make_button("▶", self.run_code, "runButton")
        self.run_button.setFixedSize(24, 24)
        self.run_button.setToolTip(self.t("Run"))
        self.run_button.setFocusPolicy(Qt.NoFocus)

        self.title_search_box = QLineEdit(objectName="titleSearchBox")
        self.title_search_box.setPlaceholderText(self.t("⌕  Search"))
        self.title_search_box.setMinimumWidth(180)
        self.title_search_box.setMaximumWidth(420)
        self.title_search_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.title_search_box.returnPressed.connect(self.search_from_title_bar)

        menu_buttons = [
            self.make_menu_button("File", [
                ("New File", self.new_file), ("New Flutter File", self.new_flutter_file),
                ("New Python File", self.new_python_file),
                ("Open File...", self.open_file),
                ("Open Folder...", self.open_folder), ("Close Folder", self.close_folder),
                ("Save", self.save_file), ("Refresh Explorer", self.refresh_file_list),
                ("New Android Project", self.new_android_file),
                ("New PySide6 Project...", self.new_pyside6_project),
                ("Export Cross-Platform Project...", self.export_cross_platform),
            ]),
            edit_button,
            self.make_menu_button("Select", [
                ("Select All", lambda: self.editor.selectAll()),
                ("Find...", self.find_text),
            ]),
            view_button,
            self.make_menu_button("Run", [
                ("Run Program", self.run_code), ("Clear Output", self.clear_output),
            ]),
            overflow_button,
        ]

        left_actions = [self.update_progress, self.rag_progress, self.title_search_box]
        right_actions = [self.apk_progress, self.linux_iso_progress, self.designer_button, self.ai_button, self.run_button]
        layout.addWidget(TitleBar(self, menu_buttons, left_actions, right_actions))

        workspace = QHBoxLayout()
        workspace.setDirection(self.box_direction)
        workspace.setSpacing(0)
        activity = QWidget(objectName="activityBar")
        activity_layout = QVBoxLayout(activity)
        activity_layout.setContentsMargins(0, 4, 0, 0)
        self.activity_buttons = []
        for i, (icon, action) in enumerate([
            ("▱", self.show_explorer), ("⌕", self.find_text),
            ("⑂", self.show_run_panel), ("▤", self.show_rag_library),
            ("▣", self.show_about),
        ]):
            button = QPushButton(icon, objectName="activityButton")
            button.setCheckable(True)
            button.setChecked(i == 0)
            button.clicked.connect(action)
            self.activity_buttons.append(button)
            activity_layout.addWidget(button)
        self.new_language_button = QPushButton("⊕", objectName="activityButton")
        self.new_language_button.setToolTip(self.t("New File (choose language)"))
        self.new_language_button.setCheckable(True)
        self.new_language_button.clicked.connect(self.choose_new_file_language)
        activity_layout.addWidget(self.new_language_button)
        activity_layout.addStretch()
        self.settings_button = SettingsIconButton(self.change_language)
        self.settings_button.setToolTip(self.t("Settings"))
        activity_layout.addWidget(self.settings_button)
        workspace.addWidget(activity)

        editor_splitter = QSplitter(Qt.Horizontal)
        self.editor_splitter = editor_splitter
        editor_splitter.setLayoutDirection(self.direction)
        sidebar = QWidget(objectName="sideBar")
        sidebar.setLayoutDirection(self.direction)
        self.sidebar = sidebar
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        self.explorer_title_label = QLabel(self.t("EXPLORER"), objectName="panelTitle")
        sidebar_layout.addWidget(self.explorer_title_label)
        project_header = QWidget()
        project_header_layout = QHBoxLayout(project_header)
        project_header_layout.setContentsMargins(0, 0, 0, 0)
        project_header_layout.setSpacing(0)
        self.explorer_project_label = QLabel(self.t("⌄  My Projects"), objectName="panelTitle")
        project_header_layout.addWidget(self.explorer_project_label)
        project_header_layout.addStretch()
        self.close_folder_button = self.make_button("×", self.close_folder, "wordDetailsClose")
        self.close_folder_button.setFixedSize(22, 22)
        self.close_folder_button.setToolTip(self.t("Close Folder"))
        self.close_folder_button.hide()
        project_header_layout.addWidget(self.close_folder_button)
        sidebar_layout.addWidget(project_header)
        self.file_list = QListWidget(objectName="fileList")
        self.file_list.setLayoutDirection(self.direction)
        self.file_list.itemDoubleClicked.connect(self.open_project_file)
        sidebar_layout.addWidget(self.file_list)
        self.folder_tree = QTreeWidget(objectName="fileTree")
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.setColumnCount(1)
        self.folder_tree.setLayoutDirection(self.direction)
        self.folder_tree.itemDoubleClicked.connect(self.tree_item_double_clicked)
        self.folder_tree.itemExpanded.connect(self.expand_tree_folder)
        sidebar_layout.addWidget(self.folder_tree)
        self.folder_tree.hide()
        self.new_file_panel = self.build_new_file_panel()
        sidebar_layout.addWidget(self.new_file_panel)
        self.new_file_panel.hide()
        editor_splitter.addWidget(sidebar)

        editor_panel = QWidget()
        editor_layout = QVBoxLayout(editor_panel)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)
        tabs = QWidget(objectName="tabBar")
        tabs_layout = QHBoxLayout(tabs)
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        self.active_tab = QLabel(f"  ●  {self.t('Untitled.apy')}    ×", objectName="activeTab")
        tabs_layout.addWidget(self.active_tab)
        tabs_layout.addStretch()
        editor_layout.addWidget(tabs)
        tabs.hide()
        self.tab_widget = QTabWidget()
        self.tab_widget.setLayoutDirection(self.direction)
        self.tab_widget.setTabsClosable(False)
        self.tab_widget.setMovable(True)
        self.tab_widget.currentChanged.connect(self.switch_tab)
        self.tab_widget.tabBarDoubleClicked.connect(self.rename_tab)
        add_tab = self.make_button("+", self.new_file)
        add_tab.setFixedWidth(24)
        self.tab_widget.setCornerWidget(add_tab, Qt.TopLeftCorner)

        code_splitter = QSplitter(Qt.Horizontal)
        code_splitter.setLayoutDirection(self.direction)
        self.code_splitter = code_splitter
        source_panel = QWidget()
        source_layout = QVBoxLayout(source_panel)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.setSpacing(0)
        source_layout.addWidget(self.tab_widget)
        code_splitter.addWidget(source_panel)

        python_panel = QWidget()
        self.python_panel = python_panel
        python_layout = QVBoxLayout(python_panel)
        python_layout.setContentsMargins(0, 0, 0, 0)
        python_layout.setSpacing(0)
        python_title = QLabel(self.t("Python Code"), objectName="codePaneTitle")
        python_title.setAlignment((Qt.AlignRight if self.rtl else Qt.AlignLeft) | Qt.AlignVCenter)
        python_layout.addWidget(python_title)
        self.python_tab_spacer = QWidget(objectName="pythonTabSpacer")
        python_layout.addWidget(self.python_tab_spacer)
        self.python_preview = CodeEditor()
        self.python_preview.wordDetailsRequested.connect(self.show_word_details_panel)
        self.python_preview.setObjectName("pythonPreview")
        # Python source is always Latin-script/LTR, independent of UI language.
        self.python_preview.set_text_direction(Qt.LeftToRight)
        self.python_preview.setFont(QFont("Segoe UI", 13))
        self.python_preview.setReadOnly(True)
        self.python_preview.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.python_highlighter = ArabicPyHighlighter(self.python_preview.document())
        python_layout.addWidget(self.python_preview)
        code_splitter.addWidget(python_panel)
        code_splitter.setSizes([650, 650])
        python_panel.hide()
        editor_layout.addWidget(code_splitter)
        self.android_designer = AndroidDesigner(language=self.language)
        self.android_designer.sourceChanged.connect(self.apply_designer_source)
        self.android_designer.hide()
        editor_layout.addWidget(self.android_designer)
        self.rag_library_page = self.build_rag_library_page()
        self.rag_library_page.hide()
        editor_layout.addWidget(self.rag_library_page)
        self.ai_providers_page = self.build_ai_providers_page()
        self.ai_providers_page.hide()
        editor_layout.addWidget(self.ai_providers_page)
        self.editor = CodeEditor()
        self.editor.wordDetailsRequested.connect(self.show_word_details_panel)
        self.editor.set_text_direction(self.direction)
        self.highlighter = ArabicPyHighlighter(self.editor.document())
        self.editor.setPlainText("no")
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
        self.editor.display_name = self.t("Untitled.apy")
        initial_index = self.tab_widget.addTab(self.editor, self.t("Untitled.apy"))
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
        header_layout.setDirection(self.box_direction)
        header_layout.setContentsMargins(4, 0, 0, 0)
        self.output_tab_button = QPushButton(self.t("OUTPUT"), objectName="outputTabButton")
        self.output_tab_button.setCheckable(True)
        self.output_tab_button.setChecked(True)
        self.output_tab_button.clicked.connect(self.show_output_tab)
        header_layout.addWidget(self.output_tab_button)
        self.terminal_tab_button = QPushButton(self.t("TERMINAL"), objectName="outputTabButton")
        self.terminal_tab_button.setCheckable(True)
        self.terminal_tab_button.clicked.connect(self.show_terminal_tab)
        header_layout.addWidget(self.terminal_tab_button)
        header_layout.addStretch()
        clear = self.make_button("Clear", self.clear_output)
        header_layout.addWidget(clear)
        output_layout.addWidget(header)
        self.output = QPlainTextEdit(objectName="output")
        self.output.setLayoutDirection(self.direction)
        output_text_option = self.output.document().defaultTextOption()
        output_text_option.setAlignment((Qt.AlignRight if self.rtl else Qt.AlignLeft) | Qt.AlignAbsolute)
        self.output.document().setDefaultTextOption(output_text_option)
        self.output.setReadOnly(True)
        self.output.setPlainText(self.t("Ready to run."))
        output_layout.addWidget(self.output)
        self.terminal_panel = self.build_terminal_panel()
        output_layout.addWidget(self.terminal_panel)
        self.terminal_panel.hide()
        main_splitter.addWidget(output_panel)
        main_splitter.setSizes([650, 190])
        workspace.addWidget(main_splitter)

        self.word_details_panel = self.build_word_details_panel()
        self.word_details_panel.hide()
        workspace.addWidget(self.word_details_panel)

        self.ai_chat_panel = QWidget(objectName="aiChatPanel")
        self.ai_chat_panel.setFixedWidth(300)
        chat_layout = QVBoxLayout(self.ai_chat_panel)
        chat_layout.setContentsMargins(10, 8, 10, 10)
        chat_layout.setSpacing(8)
        self.ai_chat_header = QWidget(objectName="aiChatHeader")
        chat_header = QHBoxLayout(self.ai_chat_header)
        chat_header.setContentsMargins(8, 5, 8, 5)
        chat_header.setSpacing(6)
        self.ai_chat_avatar = QLabel("B", objectName="aiChatAvatar")
        self.ai_chat_avatar.setAlignment(Qt.AlignCenter)
        self.ai_chat_avatar.setFixedSize(24, 22)
        chat_header.addWidget(self.ai_chat_avatar)
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        self.ai_chat_title = QLabel(self.t("Al-Baa Assistant"), objectName="aiChatTitle")
        self.ai_chat_subtitle = QLabel(self.t("Connected"), objectName="aiChatSubtitle")
        title_box.addWidget(self.ai_chat_title)
        title_box.addWidget(self.ai_chat_subtitle)
        chat_header.addLayout(title_box)
        chat_header.addStretch()
        close_chat = self.make_button("×", self.toggle_ai_chat, "aiCloseButton")
        close_chat.setFixedSize(22, 22)
        chat_header.addWidget(close_chat)
        chat_layout.addWidget(self.ai_chat_header)
        model_row = QHBoxLayout()
        model_row.setContentsMargins(8, 2, 8, 6)
        model_row.setSpacing(6)
        self.ai_provider_selector = QComboBox(objectName="aiProviderSelector")
        self.ai_provider_selector.setToolTip(self.t("Choose which configured AI provider to use"))
        self.ai_provider_selector.currentIndexChanged.connect(self.on_ai_provider_selected)
        model_row.addWidget(self.ai_provider_selector)
        self.ai_model_selector = QComboBox(objectName="aiModelSelector")
        self.ai_model_selector.setEditable(True)
        self.ai_model_selector.setToolTip(self.t("Choose a model for the active provider, or type its name"))
        self.ai_model_selector.currentTextChanged.connect(self.save_ai_model)
        model_row.addWidget(self.ai_model_selector, 1)
        self.ai_manage_providers_button = self.make_button("⚙", self.show_ai_providers_page, "aiManageProvidersButton")
        self.ai_manage_providers_button.setFixedWidth(28)
        self.ai_manage_providers_button.setToolTip(self.t("Manage AI Providers"))
        model_row.addWidget(self.ai_manage_providers_button)
        chat_layout.addLayout(model_row)
        self.refresh_provider_selector()
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
        self.ai_thinking_label = QLabel(objectName="aiThinking")
        self.ai_thinking_label.setAlignment(Qt.AlignRight if self.rtl else Qt.AlignLeft)
        self.ai_thinking_label.hide()
        chat_layout.addWidget(self.ai_thinking_label)
        # A small braille-spinner cycle next to the status text, like the
        # busy indicator in VS Code/Copilot Chat, instead of a static label.
        self.ai_thinking_frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self.ai_thinking_frame_index = 0
        self.ai_thinking_animated = True
        self.set_ai_thinking_text(self.t("Al-Baa Assistant is thinking"))
        self.ai_thinking_timer = QTimer(self)
        self.ai_thinking_timer.setInterval(90)
        self.ai_thinking_timer.timeout.connect(self.animate_ai_thinking)
        self.ai_thinking_timer.start()
        self.ai_composer = QWidget(objectName="aiComposer")
        self.ai_composer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        composer_layout = QVBoxLayout(self.ai_composer)
        composer_layout.setContentsMargins(12, 8, 12, 8)
        composer_layout.setSpacing(4)
        self.ai_chat_input = AIChatInput(objectName="aiChatInput")
        self.ai_chat_input.setPlaceholderText(self.t("Type your message..."))
        self.ai_chat_input.setToolTip(self.t("Enter to send — Shift+Enter for a new line"))
        self.ai_chat_input.setFixedHeight(38)
        self.ai_chat_input.submitted.connect(self.send_ai_message)
        composer_layout.addWidget(self.ai_chat_input)
        composer_icon_row = QHBoxLayout()
        composer_icon_row.setContentsMargins(0, 0, 0, 0)
        composer_icon_row.setSpacing(6)
        self.ai_attach_button = self.make_button("+", self.add_rag_documents, "aiAttachButton")
        self.ai_attach_button.setToolTip(self.t("Add a document to the RAG knowledge base"))
        self.ai_attach_button.setFixedSize(26, 26)
        self.ai_attach_button.setFocusPolicy(Qt.NoFocus)
        composer_icon_row.addWidget(self.ai_attach_button)
        composer_icon_row.addStretch(1)
        self.ai_send_button = SendIconButton(self.on_ai_composer_button)
        self.ai_send_button.setToolTip(self.t("Send"))
        self.ai_send_button.setFixedSize(30, 30)
        self.ai_send_button.setFocusPolicy(Qt.NoFocus)
        composer_icon_row.addWidget(self.ai_send_button)
        composer_layout.addLayout(composer_icon_row)
        chat_layout.addWidget(self.ai_composer)
        self.apply_ai_chat_theme()
        self.apply_word_details_theme()
        self.ai_chat_panel.hide()
        workspace.addWidget(self.ai_chat_panel)
        QTimer.singleShot(0, lambda: self.toggle_ai_chat(show=True))
        layout.addLayout(workspace)

        status = QWidget(objectName="statusBar")
        status_layout = QHBoxLayout(status)
        status_layout.setDirection(self.box_direction)
        status_layout.setContentsMargins(4, 0, 4, 0)
        status_layout.addWidget(QLabel("◉  Al-Baa", objectName="statusLabel"))
        self.autosave_status_label = QLabel(self.t("Autosave enabled"), objectName="statusLabel")
        status_layout.addWidget(self.autosave_status_label)
        status_layout.addStretch()
        self.position_label = QLabel(self.t("Line 1, Column 1"), objectName="statusLabel")
        status_layout.addWidget(self.position_label)
        status_layout.addWidget(QLabel(self.t("UTF-8     Arabic"), objectName="statusLabel"))
        self.editor.cursorPositionChanged.connect(self.update_position)
        layout.addWidget(status)
        self.setCentralWidget(root)
        self.android_project_path = None
        self.android_build_process = None
        self.apk_install_process = None
        self.linux_iso_build_process = None
        self.linux_builder_install_process = None
        self.linux_builder_install_stage = None
        self.apk_install_stage = None
        self.python_run_process = None
        self.terminal_process = None
        self.terminal_stdout_buffer = ""
        self.ai_request_handle = None
        self.ai_message_queue = []
        self.ai_stopped_by_user = False
        self.ai_stream_row = None
        self.ai_stream_bubble = None
        self.ai_stream_text = ""
        self.updating_from_designer = False
        saved_folder = str(QSettings("AlBaa", "AlBaaIDE").value("project_folder", "") or "")
        if saved_folder and os.path.isdir(saved_folder):
            self.open_folder_path(saved_folder)
        else:
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

    def open_folder(self):
        path = QFileDialog.getExistingDirectory(self, self.t("Open Folder"), "")
        if not path:
            return
        QSettings("AlBaa", "AlBaaIDE").setValue("project_folder", path)
        self.open_folder_path(path)

    def open_folder_path(self, path):
        self.project_folder = path
        self.explorer_project_label.setText(f"⌄  {os.path.basename(path.rstrip(os.sep)) or path}")
        self.close_folder_button.show()
        self.file_list.hide()
        self.folder_tree.show()
        self.populate_folder_tree(path)

    def close_folder(self, _checked=False):
        QSettings("AlBaa", "AlBaaIDE").remove("project_folder")
        self.project_folder = None
        self.folder_tree.clear()
        self.folder_tree.hide()
        self.close_folder_button.hide()
        self.explorer_project_label.setText(self.t("⌄  My Projects"))
        self.file_list.show()
        self.refresh_file_list()

    def populate_folder_tree(self, root_path):
        self.folder_tree.clear()
        self._populate_tree_level(self.folder_tree.invisibleRootItem(), root_path)

    def _populate_tree_level(self, parent, dir_path):
        """Fill one directory level. Directories get a placeholder child so they
        show an expand arrow without recursing -- see expand_tree_folder()."""
        try:
            entries = list(os.scandir(dir_path))
        except OSError:
            return
        dirs = sorted((e for e in entries if e.is_dir()), key=lambda e: e.name.lower())
        files = sorted((e for e in entries if not e.is_dir()), key=lambda e: e.name.lower())
        for entry in dirs:
            item = QTreeWidgetItem(parent, [entry.name])
            item.setData(0, Qt.UserRole, entry.path)
            item.setData(0, Qt.UserRole + 1, "dir")
            placeholder = QTreeWidgetItem(item, ["…"])
            placeholder.setData(0, Qt.UserRole + 1, "placeholder")
        for entry in files:
            item = QTreeWidgetItem(parent, [f"◇  {entry.name}"])
            item.setData(0, Qt.UserRole, entry.path)
            item.setData(0, Qt.UserRole + 1, "file")

    def expand_tree_folder(self, item):
        if item.childCount() != 1:
            return
        child = item.child(0)
        if child.data(0, Qt.UserRole + 1) != "placeholder":
            return
        item.removeChild(child)
        self._populate_tree_level(item, item.data(0, Qt.UserRole))

    def tree_item_double_clicked(self, item, _column):
        if item.data(0, Qt.UserRole + 1) != "file":
            return
        self.load_file(item.data(0, Qt.UserRole))

    def align_code_pane_headers(self):
        """Match Python's header height to ArabicPy's document-tab row."""
        self.python_tab_spacer.setFixedHeight(self.tab_widget.tabBar().height())

    def update_tab_title(self, modified=False):
        index = self.tab_widget.indexOf(self.editor)
        if index >= 0:
            name = os.path.basename(
                getattr(self.editor, "file_path", "")
                or getattr(self.editor, "display_name", self.t("Untitled.apy"))
            )
            marker = "● " if modified else ""
            self.tab_widget.setTabText(index, marker + name)
        return
        name = os.path.basename(self.current_file) if self.current_file else self.t("Untitled.apy")
        self.active_tab.setText(f"  {'●' if modified else '◇'}  {name}    ×")

    def switch_tab(self, index):
        if index >= 0:
            self.editor = self.tab_widget.widget(index)
            self.current_file = getattr(self.editor, "file_path", None)
            self.update_undo_redo_buttons()
            self.update_position()
            self.update_python_preview()
            theme.fade_in(self.editor, duration=120)
            if self.android_designer.isVisible():
                if is_android_source(self.editor.toPlainText()):
                    self.android_designer.load_source(self.editor.toPlainText())
                else:
                    self.hide_android_designer()

    def add_editor_tab(self, content="", path=None, code_language="albaa"):
        editor = CodeEditor()
        editor.wordDetailsRequested.connect(self.show_word_details_panel)
        editor.code_language = code_language
        # Dart/Flutter and Python source are Latin-script, so they stay LTR
        # regardless of the active UI language -- same reasoning as the
        # Python preview pane.
        editor.set_text_direction(
            self.direction if code_language == "albaa" else Qt.LeftToRight
        )
        editor.set_theme(self.ide_dark)
        editor.file_path = path
        default_name = {
            "flutter": self.t("main.dart"), "python": self.t("main.py"),
        }.get(code_language, self.t("Untitled.apy"))
        editor.display_name = os.path.basename(path) if path else default_name
        highlighter_cls = DartHighlighter if code_language == "flutter" else ArabicPyHighlighter
        editor.highlighter = highlighter_cls(editor.document())
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
        name = os.path.basename(path) if path else default_name
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
                self.autosave_status_label.setText(self.t("Waiting to autosave…"))
            else:
                self.autosave_status_label.setText(self.t("Save the file once to enable autosave"))

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
                self.autosave_status_label.setText(self.t("Autosaved"))
        except OSError as error:
            with contextlib.suppress(OSError):
                os.remove(temporary)
            if hasattr(self, "autosave_status_label"):
                self.autosave_status_label.setText(self.t("Autosave failed"))
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
        current_name = os.path.basename(old_path or getattr(editor, "display_name", self.t("Untitled.apy")))
        name, accepted = QInputDialog.getText(
            self, self.t("Rename File"), self.t("New name:"), text=current_name
        )
        if not accepted:
            return
        name = name.strip()
        if not name:
            return
        if os.path.basename(name) != name or any(character in name for character in '<>:"/\\|?*'):
            QMessageBox.warning(self, self.t("Invalid Name"), self.t("Enter a filename only, without a path or disallowed characters."))
            return
        if not os.path.splitext(name)[1]:
            name += ".apy"
        if old_path:
            new_path = os.path.join(os.path.dirname(old_path), name)
            if os.path.normcase(new_path) != os.path.normcase(old_path):
                if os.path.exists(new_path):
                    QMessageBox.warning(self, self.t("Name In Use"), self.t("A file with this name already exists."))
                    return
                try:
                    os.rename(old_path, new_path)
                except OSError as error:
                    QMessageBox.critical(self, self.t("Could Not Rename"), str(error))
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
        close_button.setFixedSize(16, 16)
        close_button.setToolTip(self.t("Close"))
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

        code_language = getattr(self.editor, "code_language", "albaa")
        if code_language == "python":
            self.set_python_preview_text(
                self.t("# This tab is already Python -- there's nothing to generate.\n# Click ▶ Run to run it.")
            )
            return
        if code_language != "albaa":
            self.set_python_preview_text(
                self.t("# Python preview isn't available for Flutter/Dart files.")
            )
            return

        source = self.editor.toPlainText()
        if not source.strip():
            self.set_python_preview_text(
                self.t("# Write Al-Baa code on the left\n# The generated Python code will appear here.")
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
                python_code or self.t("# No Python code has been generated yet.")
            )
        except Exception as error:
            line = getattr(error, "line", None)
            column = getattr(error, "column", None)
            location = ""
            if line is not None:
                location = self.t("\n# Error at line {line}, column {column}.", line=line, column=column or 1)
            self.set_python_preview_text(
                self.t("# Fix or complete the Al-Baa code to generate Python.") + location
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
        self.position_label.setText(
            self.t("Line {line}, Column {column}", line=cursor.blockNumber() + 1, column=cursor.columnNumber() + 1)
        )

    def clear_output(self):
        if self.terminal_panel.isVisible():
            self.terminal_output.clear()
        else:
            self.output.clear()

    def show_output_tab(self):
        self.output_tab_button.setChecked(True)
        self.terminal_tab_button.setChecked(False)
        self.terminal_panel.hide()
        self.output.show()

    def show_terminal_tab(self):
        self.output_tab_button.setChecked(False)
        self.terminal_tab_button.setChecked(True)
        self.output.hide()
        self.terminal_panel.show()
        self.ensure_terminal_process()
        self.terminal_input.setFocus()

    def build_terminal_panel(self):
        """A real interactive shell (persistent PowerShell process), not just a log."""
        panel = QWidget(objectName="terminalPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.terminal_output = QPlainTextEdit(objectName="terminalOutput")
        self.terminal_output.setLayoutDirection(Qt.LeftToRight)
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.terminal_output.setFont(QFont("Consolas", 11))
        layout.addWidget(self.terminal_output, 1)
        input_row = QWidget(objectName="terminalInputRow")
        input_layout = QHBoxLayout(input_row)
        input_layout.setContentsMargins(8, 4, 8, 6)
        input_layout.setSpacing(6)
        self.terminal_prompt = QLabel(f"PS {os.getcwd()}>", objectName="terminalPrompt")
        self.terminal_prompt.setToolTip("PowerShell — طرفية أوامر Windows")
        input_layout.addWidget(self.terminal_prompt)
        self.terminal_input = TerminalInput()
        self.terminal_input.setObjectName("terminalInput")
        self.terminal_input.setLayoutDirection(Qt.LeftToRight)
        self.terminal_input.setFont(QFont("Consolas", 11))
        self.terminal_input.returnPressed.connect(self.send_terminal_command)
        input_layout.addWidget(self.terminal_input)
        layout.addWidget(input_row)
        return panel

    def ensure_terminal_process(self):
        if self.terminal_process is not None:
            return
        process = QProcess(self)
        self.terminal_process = process
        process.setProgram("powershell.exe")
        process.setArguments([
            "-NoLogo", "-NoProfile", "-NoExit", "-Command", "-",
        ])
        source_path = getattr(self.editor, "file_path", None)
        working_directory = os.path.dirname(source_path) if source_path else os.getcwd()
        process.setWorkingDirectory(working_directory)
        self.terminal_prompt.setText(f"PS {working_directory}>")
        self.terminal_stdout_buffer = ""
        process.readyReadStandardOutput.connect(self.read_terminal_stdout)
        process.readyReadStandardError.connect(self.read_terminal_stderr)
        process.finished.connect(self.terminal_process_finished)
        process.start()

    def append_terminal_text(self, text, color):
        cursor = self.terminal_output.textCursor()
        cursor.movePosition(QTextCursor.End)
        char_format = QTextCharFormat()
        char_format.setForeground(QColor(color))
        cursor.setCharFormat(char_format)
        cursor.insertText(text)
        self.terminal_output.setTextCursor(cursor)
        self.terminal_output.ensureCursorVisible()

    def read_terminal_stdout(self):
        process = self.terminal_process
        if process is None:
            return
        data = bytes(process.readAllStandardOutput())
        if data:
            text = self.terminal_stdout_buffer + data.decode("utf-8", errors="replace")
            lines = text.splitlines(keepends=True)
            if lines and not lines[-1].endswith(("\n", "\r")):
                self.terminal_stdout_buffer = lines.pop()
            else:
                self.terminal_stdout_buffer = ""
            visible = []
            for line in lines:
                marker = "__ALBAA_CWD__"
                if marker in line:
                    path = line.split(marker, 1)[1].strip()
                    if path:
                        self.terminal_prompt.setText(f"PS {path}>")
                    continue
                # PowerShell's stdin mode can emit continuation glyphs even
                # though Al-Baa supplies its own visible prompt.
                if re.fullmatch(r"[\s>;]+", line):
                    continue
                visible.append(line)
            if visible:
                self.append_terminal_text("".join(visible), "#d4d4d4")

    def read_terminal_stderr(self):
        process = self.terminal_process
        if process is None:
            return
        data = bytes(process.readAllStandardError())
        if data:
            self.append_terminal_text(data.decode("utf-8", errors="replace"), "#f14c4c")

    def terminal_process_finished(self, _exit_code, _status):
        self.append_terminal_text(
            "\n" + self.t("[Terminal session ended. Type a command to start a new one.]") + "\n",
            "#9d9d9d",
        )
        process = self.terminal_process
        self.terminal_process = None
        if process is not None:
            process.deleteLater()

    def send_terminal_command(self):
        command = self.terminal_input.text()
        self.terminal_input.add_to_history(command)
        self.terminal_input.clear()
        self.ensure_terminal_process()
        if self.terminal_process is None:
            return
        self.append_terminal_text(self.terminal_prompt.text() + " " + command + "\n", "#4ec9b0")
        shell_input = (
            command + "\r\n"
            "Write-Output (\"__ALBAA_CWD__\" + (Get-Location).Path)\r\n"
        )
        self.terminal_process.write(shell_input.encode("utf-8"))

    def toggle_sidebar(self):
        opening = not self.sidebar.isVisible()
        target = 245 if opening else 0  # matches the initial editor_splitter.setSizes([245, ...])
        on_finished = (lambda: theme.fade_in(self.sidebar)) if opening else None
        theme.animate_panel(self.sidebar, target, splitter=self.editor_splitter, on_finished=on_finished)

    def toggle_output(self):
        output_widget = self.main_splitter.widget(1)
        output_widget.setVisible(not output_widget.isVisible())

    def toggle_python_preview(self):
        visible = not self.python_panel.isVisible()
        self.python_panel.setVisible(visible)
        # The Python panel sits on the side opposite the Arabic source panel,
        # which flips with UI direction -- so the collapse/expand arrows must
        # flip too, always pointing toward where the hidden panel will appear.
        collapse_arrow, expand_arrow = ("▶", "◀") if self.rtl else ("◀", "▶")
        label = self.t("Toggle Python Code")
        if visible:
            self.code_splitter.setSizes([700, 700])
            self.python_toggle_button.setText(f"{collapse_arrow} {label}")
            self.python_toggle_button.setToolTip(self.t("Hide Python Code"))
            QTimer.singleShot(0, self.align_code_pane_headers)
        else:
            self.python_toggle_button.setText(f"{expand_arrow} {label}")
            self.python_toggle_button.setToolTip(self.t("Show Python Code"))

    def set_active_activity(self, active_button):
        for button in self.activity_buttons:
            button.setChecked(button is active_button)

    def show_explorer(self):
        self.restore_editor_view()
        self.restore_sidebar_explorer_content()
        self.sidebar.show()
        if self.project_folder is None:
            self.refresh_file_list()
        self.set_active_activity(self.activity_buttons[0])

    def show_run_panel(self):
        self.restore_editor_view()
        self.restore_sidebar_explorer_content()
        self.main_splitter.widget(1).show()
        self.output.setPlainText(self.t("Run panel ready. Click ▶ Run to run the current program."))
        self.set_active_activity(self.activity_buttons[2])

    def show_about(self):
        self.restore_editor_view()
        self.restore_sidebar_explorer_content()
        self.main_splitter.widget(1).show()
        self.output.setPlainText(self.t("Al-Baa\n\nAn Arabic programming language with an editor for writing and running programs.\nUse File > Open or the Open button to get started."))
        self.set_active_activity(self.activity_buttons[4])

    def restore_editor_view(self):
        """Leave the RAG library / AI providers page (if open) and bring the code editor back."""
        if self.rag_library_page.isVisible():
            self.rag_library_page.hide()
            self.code_splitter.show()
        if self.ai_providers_page.isVisible():
            self.ai_providers_page.hide()
            self.code_splitter.show()

    def restore_sidebar_explorer_content(self):
        """Leave the new-file language panel (if open) and bring the file list/tree back."""
        if self.new_file_panel.isVisible():
            self.new_file_panel.hide()
            self.explorer_title_label.show()
            self.explorer_project_label.show()
            if self.project_folder is not None:
                self.close_folder_button.show()
                self.folder_tree.show()
            else:
                self.file_list.show()
        self.new_language_button.setChecked(False)

    def build_new_file_panel(self):
        """A big, VS-Code-Extensions-style language picker shown in place of the file list."""
        panel = QWidget(objectName="newFilePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        title = QLabel(self.t("NEW FILE — CHOOSE A LANGUAGE"), objectName="panelTitle")
        layout.addWidget(title)
        languages = [
            (
                LanguageCard.letter_icon("#007ACC", "ب"), self.t("Al-Baa (.apy)"),
                self.t("The Arabic-keyword language this IDE is built for."),
                self.new_file,
            ),
            (
                FlutterIconLabel(), self.t("Flutter (.dart)"),
                self.t("Write and highlight Dart/Flutter code. Running and building are on the way."),
                self.new_flutter_file,
            ),
            (
                PythonIconLabel(), self.t("Python (.py)"),
                self.t("Plain Python code, syntax-highlighted and runnable with ▶ Run."),
                self.new_python_file,
            ),
        ]
        for icon_widget, name, description, handler in languages:
            card = LanguageCard(icon_widget, name, description)
            card.clicked.connect(lambda _checked=False, action=handler: self.pick_new_file_language(action))
            layout.addWidget(card)
        layout.addStretch()
        return panel

    def choose_new_file_language(self):
        """Show the language picker as a big sidebar panel instead of a small popup."""
        if self.new_file_panel.isVisible():
            self.show_explorer()
            return
        self.restore_editor_view()
        self.explorer_title_label.hide()
        self.explorer_project_label.hide()
        self.close_folder_button.hide()
        self.file_list.hide()
        self.folder_tree.hide()
        self.new_file_panel.show()
        self.sidebar.show()
        self.set_active_activity(None)
        self.new_language_button.setChecked(True)

    def pick_new_file_language(self, handler):
        handler()
        self.show_explorer()

    def build_rag_library_page(self):
        """A dedicated page listing every document indexed into RAG, with add/remove."""
        page = QWidget(objectName="ragLibraryPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.addWidget(QLabel(self.t("RAG Knowledge Library"), objectName="ragLibraryHeader"))
        header_row.addStretch()
        self.rag_library_count_label = QLabel("", objectName="ragLibraryCount")
        header_row.addWidget(self.rag_library_count_label)
        layout.addLayout(header_row)

        toolbar_row = QHBoxLayout()
        self.rag_library_add_button = self.make_button("+ Add Documents", self.add_rag_documents)
        toolbar_row.addWidget(self.rag_library_add_button)
        self.rag_remove_button = self.make_button("Delete Selected", self.remove_selected_rag_document, "ragRemoveButton")
        toolbar_row.addWidget(self.rag_remove_button)
        toolbar_row.addStretch()
        layout.addLayout(toolbar_row)

        self.rag_library_list = QListWidget(objectName="ragLibraryList")
        self.rag_library_list.setLayoutDirection(self.direction)
        self.rag_library_list.itemSelectionChanged.connect(self.update_rag_remove_button)
        layout.addWidget(self.rag_library_list, 1)

        self.rag_library_empty_label = QLabel(
            self.t("No documents added yet.\nClick \"+ Add Documents\" to start building your RAG knowledge base."),
            objectName="ragLibraryEmpty",
        )
        self.rag_library_empty_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.rag_library_empty_label, 1)
        return page

    def show_rag_library(self):
        self.restore_sidebar_explorer_content()
        self.android_designer.hide()
        self.code_splitter.hide()
        self.ai_providers_page.hide()
        self.rag_library_page.show()
        self.refresh_rag_library()
        self.set_active_activity(self.activity_buttons[3])

    def refresh_rag_library(self):
        self.rag_library_list.clear()
        documents = list_rag_documents()
        self.rag_library_count_label.setText(self.t("{count} document(s)", count=len(documents)) if documents else "")
        self.rag_library_list.setVisible(bool(documents))
        self.rag_library_empty_label.setVisible(not documents)
        for path in documents:
            size_kb = max(1, path.stat().st_size // 1024)
            item = QListWidgetItem(self.t("  ◇  {name}      {size} KB", name=rag_display_name(path), size=size_kb))
            item.setData(Qt.UserRole, str(path))
            self.rag_library_list.addItem(item)
        self.update_rag_remove_button()

    def update_rag_remove_button(self):
        self.rag_remove_button.setEnabled(self.rag_library_list.currentItem() is not None)

    def remove_selected_rag_document(self):
        item = self.rag_library_list.currentItem()
        if item is None:
            return
        path = Path(item.data(Qt.UserRole))
        answer = QMessageBox.question(
            self, self.t("Delete Document"),
            self.t("Delete \"{name}\" from the RAG knowledge base?", name=rag_display_name(path)),
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        remove_rag_document(path)
        self.refresh_rag_library()

    def add_rag_documents(self):
        if getattr(self, "rag_worker", None) is not None and self.rag_worker.isRunning():
            return
        paths, _filter = QFileDialog.getOpenFileNames(
            self,
            self.t("Add Documents to RAG Knowledge Base"),
            "",
            self.t("Supported Documents (*.txt *.md *.apy *.py *.json *.csv *.pdf *.docx)"),
        )
        if not paths:
            return
        self.main_splitter.widget(1).show()
        self.rag_button.setEnabled(False)
        self.rag_library_add_button.setEnabled(False)
        self.rag_progress.setValue(0)
        self.rag_progress.setFormat("RAG 0%")
        self.rag_progress.show()
        self.output.setPlainText(self.t("Extracting and indexing documents..."))
        self.rag_worker = RAGImportWorker(paths, self)
        self.rag_worker.progress.connect(self.update_rag_progress)
        self.rag_worker.completed.connect(self.finish_rag_import)
        self.rag_worker.finished.connect(self.rag_worker.deleteLater)
        self.rag_worker.start()

    def update_rag_progress(self, value, filename):
        self.rag_progress.setValue(value)
        self.rag_progress.setFormat(f"RAG {value}%")
        self.output.setPlainText(
            self.t("Extracting and indexing:\n{filename}\n\nProgress: {value}%\nOCR may take a while the first time it's used.",
                   filename=filename, value=value)
        )

    def finish_rag_import(self, added, errors):
        self.rag_progress.setValue(100)
        self.rag_progress.setFormat("RAG 100%")
        self.rag_button.setEnabled(True)
        self.rag_library_add_button.setEnabled(True)
        if added:
            self.refresh_rag_library()
        message = self.t("Added {count} document(s) to the RAG library.", count=len(added))
        if added:
            message += "\n\n" + "\n".join(f"✓ {name}" for name in added)
        if errors:
            message += "\n\n" + self.t("Could not add:") + "\n" + "\n".join(errors)
        self.output.setPlainText(message)
        QTimer.singleShot(2500, self.rag_progress.hide)
        self.rag_worker = None

    def ask_local_ai(self, _checked=False):
        self.toggle_ai_chat()

    def save_ai_model(self, model):
        """Persist the chosen model on the currently active AI provider."""
        model = str(model).strip()
        config = self.active_provider_config()
        if not model or config is None:
            return
        config.default_model = model
        self.invalidate_active_provider_cache()
        self.provider_store.save(self.ai_providers, self.active_provider_id)

    def active_provider_config(self):
        return next((config for config in self.ai_providers if config.id == self.active_provider_id), None)

    def active_provider(self):
        """Return the constructed, cached AIProvider for the active config (or None)."""
        config = self.active_provider_config()
        if config is None:
            return None
        if self._active_provider_instance is None or self._active_provider_instance_id != config.id:
            self._active_provider_instance = create_provider(config)
            self._active_provider_instance_id = config.id
        return self._active_provider_instance

    def invalidate_active_provider_cache(self):
        self._active_provider_instance = None
        self._active_provider_instance_id = None

    def refresh_provider_selector(self):
        """Repopulate the provider combo from self.ai_providers and select the active one."""
        self.ai_provider_selector.blockSignals(True)
        self.ai_provider_selector.clear()
        for config in self.ai_providers:
            self.ai_provider_selector.addItem(config.label, config.id)
        index = self.ai_provider_selector.findData(self.active_provider_id)
        if index >= 0:
            self.ai_provider_selector.setCurrentIndex(index)
        self.ai_provider_selector.blockSignals(False)
        self.refresh_model_selector_for_active_provider()

    def on_ai_provider_selected(self, index):
        provider_id = self.ai_provider_selector.itemData(index)
        if provider_id is None or provider_id == self.active_provider_id:
            return
        self.switch_active_provider(provider_id)

    def switch_active_provider(self, provider_id):
        self.active_provider_id = provider_id
        self.invalidate_active_provider_cache()
        self.provider_store.save(self.ai_providers, self.active_provider_id)
        self.refresh_model_selector_for_active_provider()

    def refresh_model_selector_for_active_provider(self):
        """Seed the model combo from the active provider's type (Ollama's
        installed-model list, or the provider type's example models)."""
        config = self.active_provider_config()
        self.ai_model_selector.blockSignals(True)
        self.ai_model_selector.clear()
        if config is None:
            self.ai_model_selector.blockSignals(False)
            return
        if config.type == "ollama":
            self.ai_model_selector.addItems(["qwen3:1.7b", "qwen3:8b"])
            installed_models = self.installed_ollama_models()
            for installed_model in installed_models:
                if self.ai_model_selector.findText(installed_model) < 0:
                    self.ai_model_selector.addItem(installed_model)
            if installed_models and config.default_model not in installed_models:
                config.default_model = self.preferred_ollama_model(installed_models)
        else:
            spec = PROVIDER_TYPES.get(config.type)
            if spec is not None:
                self.ai_model_selector.addItems(list(spec.example_models))
        if config.default_model and self.ai_model_selector.findText(config.default_model) < 0:
            self.ai_model_selector.addItem(config.default_model)
        if config.default_model:
            self.ai_model_selector.setCurrentText(config.default_model)
        self.ai_model_selector.blockSignals(False)

    @staticmethod
    def installed_ollama_models():
        """Return locally installed Ollama model names without opening a console."""
        if not shutil.which("ollama"):
            return []
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            result = subprocess.run(
                ["ollama", "list"], capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=8,
                creationflags=creationflags,
            )
        except (OSError, subprocess.SubprocessError):
            return []
        if result.returncode != 0:
            return []
        models = []
        for line in result.stdout.splitlines()[1:]:
            columns = line.split()
            if columns:
                models.append(columns[0])
        return models

    @staticmethod
    def preferred_ollama_model(models):
        """Prefer the balanced desktop model, then any installed Qwen model."""
        for preferred in (DEFAULT_MODEL, "qwen3:8b", "qwen3:14b", "qwen3:1.7b"):
            if preferred in models:
                return preferred
        return next((model for model in models if model.startswith("qwen")), models[0])

    def toggle_ai_chat(self, _checked=False, show=None):
        visible = not self.ai_chat_panel.isVisible() if show is None else show
        if visible and self.word_details_panel.isVisible():
            self.hide_panel_immediately(self.word_details_panel, 320)
        self.ai_button.setChecked(visible)
        target = 300 if visible else 0  # matches ai_chat_panel's fixed width when open

        def _on_opened():
            theme.fade_in(self.ai_chat_panel)
            self.ai_chat_input.setFocus()

        theme.animate_panel(self.ai_chat_panel, target, on_finished=_on_opened if visible else None)

    @staticmethod
    def word_notes():
        return load_word_notes()

    def show_word_details_panel(self, word, line):
        self.word_details_source_word = word
        saved = self.word_notes().get(word, {})
        python_word = KEYWORDS.get(word)
        explanation = (
            f"This ArabicPy word is equivalent to Python {python_word}."
            if python_word else
            "This is a programming word used in the current code."
        )
        self.word_details_word.setText(saved.get("word", word))
        self.word_details_meaning.setText(saved.get("meaning", ""))
        self.word_details_example.setPlainText(saved.get("example", line))
        self.word_details_explanation.setPlainText(saved.get("explanation", explanation))
        self.word_details_subtitle.setText(word)

        if self.ai_chat_panel.isVisible():
            self.hide_panel_immediately(self.ai_chat_panel, 300)
            self.ai_button.setChecked(False)

        def _on_opened():
            self.word_details_meaning.setFocus()

        if self.word_details_panel.isVisible():
            self.word_details_meaning.setFocus()
        else:
            theme.animate_panel(self.word_details_panel, 320, on_finished=_on_opened)

    def close_word_details_panel(self, _checked=False):
        theme.animate_panel(self.word_details_panel, 0)

    @staticmethod
    def hide_panel_immediately(panel, normal_width):
        animation = getattr(panel, "_albaa_panel_anim", None)
        if animation is not None:
            animation.stop()
        panel.hide()
        panel.setFixedWidth(normal_width)

    def save_word_details_panel(self, _checked=False):
        source_word = getattr(self, "word_details_source_word", "")
        if not source_word:
            return
        notes = self.word_notes()
        notes[source_word] = {
            "word": self.word_details_word.text(),
            "meaning": self.word_details_meaning.text(),
            "example": self.word_details_example.toPlainText(),
            "explanation": self.word_details_explanation.toPlainText(),
        }
        QSettings("AlBaa", "AlBaaIDE").setValue(
            "word_notes", json.dumps(notes, ensure_ascii=False)
        )
        self.word_details_subtitle.setText(f"{source_word} · Saved")

    def apply_word_details_theme(self):
        p = theme.PALETTES[self.theme_mode]
        panel = theme.glass_fill(p, self.glass_effects)
        header = theme.glass_fill(p, self.glass_effects, strong=True)
        border = p.border_glass
        self.word_details_panel.setStyleSheet(f"""
            #wordDetailsPanel {{ background:{panel}; border-left:1px solid {border}; }}
            #wordDetailsHeader {{ background:{header}; border-bottom:1px solid {border}; }}
            #wordDetailsAvatar {{ background:{p.accent}; color:{p.text_on_accent}; border-radius:6px; font-weight:800; }}
            #wordDetailsTitle {{ background:transparent; color:{p.text}; font-size:13px; font-weight:700; }}
            #wordDetailsSubtitle {{ background:transparent; color:{p.text_muted}; font-size:10px; }}
            #wordDetailsClose {{ background:transparent; color:{p.text}; border:none; font-size:15px; }}
            #wordDetailsScroll, #wordDetailsBody {{ background:transparent; border:none; }}
            #wordDetailsWord, #wordDetailsMeaning, #wordDetailsExample, #wordDetailsExplanation {{
                background:{p.surface}; color:{p.text}; border:1px solid {p.border};
                border-radius:6px; padding:7px; selection-background-color:{p.selection};
            }}
            #wordDetailsWord:focus, #wordDetailsMeaning:focus,
            #wordDetailsExample:focus, #wordDetailsExplanation:focus {{ border-color:{p.accent}; }}
            #wordDetailsCancel, #wordDetailsSave {{
                border-radius:{theme.RADIUS["sm"]}px; padding:7px 14px; font-weight:600; font-size:12px;
            }}
            #wordDetailsSave {{ background:{p.accent}; color:{p.text_on_accent}; border:none; }}
            #wordDetailsSave:hover {{ background:{p.accent_hover}; }}
            #wordDetailsSave:pressed {{ background:{p.accent_pressed}; }}
            #wordDetailsCancel {{ background:transparent; color:{p.text_muted}; border:1px solid {p.border}; }}
            #wordDetailsCancel:hover {{ background:{p.border_glass if self.glass_effects else p.border}; color:{p.text}; }}
            #wordDetailsCancel:pressed {{ background:{theme.rgba(p.text, 0.1)}; }}
        """)

    def cycle_theme(self, _checked=False):
        """Toggle between Al-Baa's Dark and Light themes."""
        next_mode = {theme.DARK: theme.LIGHT, theme.LIGHT: theme.DARK}
        self.theme_mode = next_mode[self.theme_mode]
        self.ide_dark = self.theme_mode != theme.LIGHT
        self.ai_chat_dark = self.ide_dark
        settings = QSettings("AlBaa", "AlBaaIDE")
        settings.setValue("ide_theme_mode", self.theme_mode)
        self.setStyleSheet(self.stylesheet())
        for editor in self.findChildren(CodeEditor):
            editor.set_theme(self.ide_dark)
        for highlighter in self.findChildren(ArabicPyHighlighter):
            highlighter.set_theme(self.ide_dark)
        self.settings_button.set_dark_theme(self.ide_dark)
        self.apply_ai_chat_theme()
        self.apply_word_details_theme()
        self.apply_elevation_effects()
        self.render_ai_messages()

    def apply_elevation_effects(self):
        """(Re)apply the soft depth shadows used on the sidebar, AI panel, and dialogs."""
        palette = theme.PALETTES[self.theme_mode]
        theme.apply_elevation(self.sidebar, palette, "md", self.glass_effects)
        theme.apply_elevation(self.ai_chat_panel, palette, "md", self.glass_effects)
        theme.apply_elevation(self.word_details_panel, palette, "md", self.glass_effects)

    def change_language(self):
        """Let the user switch the IDE's language; applying it needs a restart."""
        picker = LanguagePickerDialog(self, dark=self.ide_dark)
        picker.chosen_language = self.language
        if picker.exec() != QDialog.DialogCode.Accepted:
            return
        new_language = picker.chosen_language
        if new_language == self.language or new_language not in LANGUAGE_NAMES:
            return
        settings = QSettings("AlBaa", "AlBaaIDE")
        settings.setValue("ui_language", new_language)
        answer = QMessageBox.question(
            self,
            self.t("Restart Required"),
            self.t("Al-Baa needs to restart to switch to {language}. Restart now?", language=LANGUAGE_NAMES[new_language]),
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        if getattr(sys, "frozen", False):
            QProcess.startDetached(sys.executable, [])
        else:
            # sys.argv[0] under `-m` is the resolved absolute path to this
            # file, not "-m arabicpy.ide" -- relaunching with sys.argv as-is
            # runs ide.py as a bare script, which crashes instantly on its
            # relative imports ("from . import theme") and never reopens.
            QProcess.startDetached(sys.executable, ["-m", "arabicpy.ide"] + sys.argv[1:])
        self.close()

    def apply_ai_chat_theme(self):
        p = theme.PALETTES[self.theme_mode]
        theme_labels = {theme.DARK: "☀ Theme", theme.LIGHT: "☾ Theme"}
        self.theme_button.setText(self.t(theme_labels[self.theme_mode]))

        panel = theme.glass_fill(p, self.glass_effects)
        header = theme.glass_fill(p, self.glass_effects, strong=True)
        history = theme.glass_fill(p, self.glass_effects)
        composer = theme.glass_fill(p, self.glass_effects, strong=True)
        border = p.border_glass
        text, muted = p.text, p.text_muted
        hover = p.border_glass if self.glass_effects else p.border

        self.ai_chat_panel.setStyleSheet(f"#aiChatPanel {{ background:{panel}; border-left:1px solid {border}; }}")
        self.ai_chat_history.setStyleSheet(
            f"#aiChatHistory {{ background:{history}; border:1px solid {border}; border-radius:14px; }}"
        )
        self.ai_chat_content.setStyleSheet("#aiChatContent { background: transparent; }")
        self.ai_composer.setStyleSheet(
            f"#aiComposer {{ background:{composer}; border:1px solid {border}; border-radius:18px; }}"
        )
        self.ai_chat_header.setStyleSheet(
            f"#aiChatHeader {{ background:{header}; border-bottom:1px solid {border}; border-radius:0; }}"
        )
        self.ai_chat_avatar.setStyleSheet(
            f"#aiChatAvatar {{ background:{p.accent}; color:{p.text_on_accent}; border-radius:6px; font-size:13px; font-weight:800; }}"
        )
        selector_qss = (
            "{selector} {{ background:{composer}; color:{text}; border:1px solid {border}; "
            "border-radius:10px; padding:5px 10px; font-size:12px; }}"
            "{selector}:hover {{ border:1px solid {accent}; }}"
            "{selector}:focus {{ border:1px solid {accent}; outline:none; }}"
            "{selector}::drop-down {{ border:none; width:22px; }}"
            "{selector}::down-arrow {{ width:0; height:0; margin-right:8px; "
            "border-left:4px solid transparent; border-right:4px solid transparent; border-top:5px solid {muted}; }}"
            "{selector} QAbstractItemView {{ background:{surface_alt}; color:{text}; "
            "border:1px solid {qborder}; border-radius:8px; padding:4px; outline:none; "
            "selection-background-color:{hover}; selection-color:{text}; }}"
        )
        self.ai_provider_selector.setStyleSheet(selector_qss.format(
            selector="#aiProviderSelector", composer=composer, text=text, border=border,
            accent=p.accent, muted=muted, surface_alt=p.surface_alt, qborder=p.border, hover=hover,
        ))
        self.ai_model_selector.setStyleSheet(selector_qss.format(
            selector="#aiModelSelector", composer=composer, text=text, border=border,
            accent=p.accent, muted=muted, surface_alt=p.surface_alt, qborder=p.border, hover=hover,
        ))
        self.ai_manage_providers_button.setStyleSheet(
            f"#aiManageProvidersButton {{ background:{composer}; color:{text}; border:1px solid {border}; "
            "border-radius:10px; font-size:13px; }"
            f"#aiManageProvidersButton:hover {{ border:1px solid {p.accent}; }}"
        )
        self.ai_chat_title.setStyleSheet(
            f"background:transparent; color:{text}; border:none; font-size:13px; font-weight:700; padding:0;"
        )
        self.ai_chat_subtitle.setStyleSheet(
            f"background:transparent; color:{muted}; border:none; font-size:10px;"
        )
        self.ai_chat_input.setStyleSheet(
            f"#aiChatInput {{ background:transparent; color:{text}; border:none; padding:2px 2px; }}"
        )
        self.ai_attach_button.setStyleSheet(
            f"#aiAttachButton {{ background:transparent; color:{muted}; border:1px solid {p.border}; "
            "border-radius:13px; font-size:15px; font-weight:700; padding:0; outline:none; }"
            f"#aiAttachButton:hover, #aiAttachButton:pressed {{ background:{hover}; color:{text}; "
            f"border:1px solid {p.border}; outline:none; }}"
            f"#aiAttachButton:focus {{ border:1px solid {p.border}; outline:none; }}"
        )
        self.ai_thinking_label.setStyleSheet(f"color:{muted}; padding:2px 8px; font-size:11px;")
        theme.apply_elevation(self.ai_composer, p, "sm", self.glass_effects)

    def append_ai_message(self, sender, message):
        if sender == "assistant":
            message = self.clean_ai_markdown(message)
        self.ai_messages.append((sender, message, datetime.now().strftime("%H:%M")))
        self.render_ai_messages()
        self.save_ai_history()

    @staticmethod
    def ai_history_file():
        app_data = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "AlBaa")
        return os.path.join(app_data, "chat_history.json")

    def load_ai_history(self):
        path = self.ai_history_file()
        if not os.path.isfile(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as stream:
                data = json.load(stream)
            return [(entry["sender"], entry["message"], entry["time"]) for entry in data]
        except (OSError, ValueError, KeyError):
            return []

    def save_ai_history(self):
        path = self.ai_history_file()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as stream:
                json.dump(
                    [{"sender": sender, "message": message, "time": timestamp}
                     for sender, message, timestamp in self.ai_messages],
                    stream, ensure_ascii=False, indent=2,
                )
        except OSError:
            pass

    def clear_ai_history(self):
        self.ai_messages = []
        self.save_ai_history()
        self.render_ai_messages()

    @staticmethod
    def clean_ai_markdown(message):
        """Turn common model Markdown into clean plain text for chat bubbles."""
        text = str(message).replace("\r\n", "\n")
        text = re.sub(r"^\s*```[^\n]*\n?", "", text, flags=re.MULTILINE)
        text = text.replace("```", "")
        text = re.sub(r"^\s*#{1,6}\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*[-+*]\s+", "• ", text, flags=re.MULTILINE)
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text, flags=re.DOTALL)
        text = re.sub(r"__(.+?)__", r"\1", text, flags=re.DOTALL)
        text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
        text = re.sub(r"(?<!_)_([^_\n]+)_(?!_)", r"\1", text)
        text = re.sub(r"`([^`\n]+)`", r"\1", text)
        return text.strip()

    def render_ai_messages(self):
        while self.ai_chat_messages_layout.count() > 1:
            item = self.ai_chat_messages_layout.takeAt(self.ai_chat_messages_layout.count() - 1)
            if item.widget() is not None:
                item.widget().deleteLater()
        for sender, message, timestamp in self.ai_messages:
            self.render_ai_message(sender, message, timestamp)
        self.scroll_ai_chat_to_bottom()

    def scroll_ai_chat_to_bottom(self):
        # Deferred twice: showing/hiding ai_thinking_label resizes the scroll
        # viewport on the next layout pass, after a single singleShot(0) would
        # already have fired and read a stale maximum() — leaving the latest
        # bubble pushed out of view.
        QTimer.singleShot(0, lambda: QTimer.singleShot(0, lambda: (
            self.ai_chat_history.verticalScrollBar().setValue(
                self.ai_chat_history.verticalScrollBar().maximum()
            )
        )))

    def set_ai_thinking_text(self, text, animated=True):
        """Set the busy-indicator's label, with or without the spinner."""
        self.ai_thinking_base_text = text
        self.ai_thinking_animated = animated
        self.ai_thinking_label.setText(
            text if not animated else f"{text} {self.ai_thinking_frames[self.ai_thinking_frame_index]}"
        )

    def animate_ai_thinking(self):
        if not self.ai_thinking_animated or not self.ai_thinking_label.isVisible():
            return
        self.ai_thinking_frame_index = (self.ai_thinking_frame_index + 1) % len(self.ai_thinking_frames)
        self.ai_thinking_label.setText(
            f"{self.ai_thinking_base_text} {self.ai_thinking_frames[self.ai_thinking_frame_index]}"
        )

    @staticmethod
    def _measure_html_height(font, html_content, content_width):
        # QLabel.heightForWidth() doesn't fully account for QTextDocument's
        # own default document margin on top of the label's contentsMargins,
        # undershooting by ~8px for rich text and clipping the last line --
        # laying the same HTML out in a QTextDocument at the exact content
        # width gives the real height that will be needed.
        doc = QTextDocument()
        doc.setDefaultFont(font)
        doc.setHtml(html_content)
        doc.setTextWidth(content_width)
        return int(doc.size().height())

    def render_ai_message(self, sender, message, timestamp):
        # Copilot Chat-style layout: the assistant's reply is flowing text
        # with a small avatar (no bubble/border), while the user's own turn
        # sits in a subtly shaded box rather than a saturated chat bubble.
        is_user = sender == "user"
        p = theme.PALETTES[self.theme_mode]
        background = p.surface_alt if is_user else "transparent"
        foreground = p.text
        muted = p.text_muted
        bubble_border = f"1px solid {p.border}" if is_user else "none"
        safe_message = html.escape(message).replace("\n", "<br>")
        row = QWidget()
        row.setStyleSheet("background:transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(3, 0, 3, 0)
        row_layout.setSpacing(8)
        bubble_html = (
            f'<span style="font-size:13px;">{safe_message}</span><br><br>'
            f'<span style="color:{muted}; font-size:9px;">{timestamp}</span>'
        )
        bubble = QLabel(bubble_html)
        bubble.setTextFormat(Qt.RichText)
        bubble.setLayoutDirection(self.direction)
        bubble.setAlignment((Qt.AlignRight if self.rtl else Qt.AlignLeft) | Qt.AlignTop)
        bubble.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        bubble.setWordWrap(True)
        metrics = bubble.fontMetrics()
        if is_user:
            longest_line = max(message.splitlines() or [""], key=len)
            natural_width = max(metrics.horizontalAdvance(longest_line), len(longest_line) * 7) + 28
            # The history viewport is narrower than the 300 px panel after its
            # outer margins, frame, padding, and the row's own margins.  Keep
            # user bubbles inside that usable width instead of letting their
            # right edge disappear behind the viewport clip.
            bubble_width = min(238, max(68, natural_width))
        else:
            # Assistant rows also contain a 22 px avatar and an 8 px gap, so
            # their text area must be narrower than a user-only row.
            bubble_width = 208
        bubble.setContentsMargins(12, 9, 12, 9)
        bubble.setStyleSheet(
            f"QLabel {{ background:{background}; color:{foreground}; border:{bubble_border}; "
            "border-radius:10px; padding:0; }"
        )
        bubble.setFixedWidth(bubble_width)
        # QLabel.heightForWidth() doesn't fully account for QTextDocument's
        # own default document margin on top of the label's contentsMargins,
        # undershooting by ~8px for rich text and clipping the last line --
        # laying the same HTML out in a QTextDocument at the exact content
        # width gives the real height that will be needed.
        content_width = bubble_width - 12 - 12
        bubble_height = self._measure_html_height(bubble.font(), bubble_html, content_width) + 9 + 9
        bubble.setFixedHeight(max(44, bubble_height))
        bubble.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        if is_user:
            row_layout.addStretch(1)
            row_layout.addWidget(bubble, 0, Qt.AlignRight)
        else:
            avatar = QLabel("ب")
            avatar.setFixedSize(22, 22)
            avatar.setAlignment(Qt.AlignCenter)
            avatar.setStyleSheet(
                f"background:{p.accent}; color:{p.text_on_accent}; border-radius:11px; font-size:11px; font-weight:800;"
            )
            row_layout.addWidget(avatar, 0, Qt.AlignTop)
            row_layout.addWidget(bubble, 0, Qt.AlignLeft)
            row_layout.addStretch(1)
        self.ai_chat_messages_layout.addWidget(row)

    def on_ai_composer_button(self):
        """The composer's single icon button sends when idle, stops when a request is in flight."""
        if self.ai_request_handle is not None:
            self.stop_ai_request()
        else:
            self.send_ai_message()

    def stop_ai_request(self):
        """Cancel the in-flight AI request; the next queued question (if any) starts right after."""
        if self.ai_request_handle is None:
            return
        self.ai_stopped_by_user = True
        self.ai_request_handle.cancel()

    def send_ai_message(self):
        question = self.ai_chat_input.toPlainText().strip()
        if not question:
            return
        self.ai_chat_input.clear()
        self.append_ai_message("user", question)
        if self.ai_request_handle is not None:
            self.ai_message_queue.append(question)
            self.update_ai_thinking_text()
            return
        self.dispatch_ai_question(question)

    def update_ai_thinking_text(self):
        base = self.t("Al-Baa Assistant is thinking")
        if self.ai_message_queue:
            base = self.t("{base} ({count} queued)", base=base, count=len(self.ai_message_queue))
        self.set_ai_thinking_text(base)

    def dispatch_next_queued_ai_message(self):
        if not self.ai_message_queue:
            return
        next_question = self.ai_message_queue.pop(0)
        self.update_ai_thinking_text()
        QTimer.singleShot(0, lambda: self.dispatch_ai_question(next_question))

    def build_ai_messages(self, question):
        """Assemble the system + RAG + editor-context + question turns for one request."""
        if self.language == "ar":
            user_content = (
                f"معرفة موثقة مسترجعة من قاعدة الباء:\n{rag_context(question)}\n\n"
                f"الكود المفتوح حالياً في المحرر (للسياق فقط — لا علاقة له بالسؤال إلا إذا "
                f"كان السؤال عن الكود نفسه):\n{self.editor.toPlainText()}\n\n"
                f"سؤال المستخدم:\n{question}"
            )
        else:
            user_content = (
                f"Documented knowledge retrieved from the Al-Baa knowledge base:\n{rag_context(question)}\n\n"
                f"Code currently open in the editor (context only — unrelated to the "
                f"question unless it's actually about this code):\n{self.editor.toPlainText()}\n\n"
                f"User's question:\n{question}"
            )
        return [
            ChatMessage(role="system", content=system_prompt_for(self.language)),
            ChatMessage(role="user", content=user_content),
        ]

    def dispatch_ai_question(self, question):
        provider = self.active_provider()
        config = self.active_provider_config()
        if provider is None or config is None:
            self.append_ai_message(
                "assistant",
                self.t("No AI provider is configured. Add one from the AI menu."),
            )
            return
        model = self.ai_model_selector.currentText().strip() or config.default_model
        if model != config.default_model:
            self.save_ai_model(model)
        messages = self.build_ai_messages(question)
        handle = provider.send_chat(messages, model=model, stream=provider.capabilities.streaming)
        self.begin_ai_request(handle)

    def begin_ai_request(self, handle):
        self.ai_request_handle = handle
        self.update_ai_thinking_text()
        self.ai_thinking_label.show()
        self.scroll_ai_chat_to_bottom()
        self.ai_button.setEnabled(False)
        self.ai_send_button.set_mode("stop")
        self.ai_send_button.setToolTip(self.t("Stop"))
        handle.token_received.connect(self.on_ai_token)
        handle.finished.connect(self.on_ai_finished)
        handle.failed.connect(self.on_ai_failed)

    def on_ai_token(self, delta):
        if self.ai_stream_row is None:
            self._begin_ai_stream_preview()
        self.ai_stream_text += delta
        self._update_ai_stream_preview()

    def end_ai_request(self):
        if self.ai_request_handle is not None:
            self.ai_request_handle.deleteLater()
        self.ai_request_handle = None
        self.ai_button.setEnabled(True)
        self.ai_send_button.setEnabled(True)
        self.ai_send_button.set_mode("send")
        self.ai_send_button.setToolTip(self.t("Send"))
        self.ai_thinking_label.hide()

    def on_ai_finished(self, full_text):
        self._end_ai_stream_preview()
        self.end_ai_request()
        stopped = self.ai_stopped_by_user
        self.ai_stopped_by_user = False
        if not stopped:
            if full_text.strip():
                self.append_ai_message("assistant", full_text)
            else:
                config = self.active_provider_config()
                self.append_ai_message(
                    "assistant",
                    self.t(
                        "Could not get a response from {provider}. Make sure it's reachable and try again.",
                        provider=config.label if config else "",
                    ),
                )
        self.dispatch_next_queued_ai_message()

    def on_ai_failed(self, error_message):
        self._end_ai_stream_preview()
        self.end_ai_request()
        stopped = self.ai_stopped_by_user
        self.ai_stopped_by_user = False
        if not stopped:
            config = self.active_provider_config()
            self.append_ai_message(
                "assistant",
                self.t(
                    "Could not get a response from {provider}: {error}",
                    provider=config.label if config else "", error=error_message,
                ),
            )
        self.dispatch_next_queued_ai_message()

    def _begin_ai_stream_preview(self):
        """A lightweight assistant bubble that grows as streamed tokens arrive,
        replaced by a normal persisted message once the request finishes."""
        self.ai_stream_text = ""
        p = theme.PALETTES[self.theme_mode]
        row = QWidget()
        row.setStyleSheet("background:transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(3, 0, 3, 0)
        row_layout.setSpacing(8)
        avatar = QLabel("ب")
        avatar.setFixedSize(22, 22)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(
            f"background:{p.accent}; color:{p.text_on_accent}; border-radius:11px; font-size:11px; font-weight:800;"
        )
        bubble = QLabel("")
        bubble.setTextFormat(Qt.RichText)
        bubble.setLayoutDirection(self.direction)
        bubble.setAlignment((Qt.AlignRight if self.rtl else Qt.AlignLeft) | Qt.AlignTop)
        bubble.setWordWrap(True)
        bubble.setContentsMargins(12, 9, 12, 9)
        bubble.setStyleSheet(f"QLabel {{ background:transparent; color:{p.text}; border:none; padding:0; }}")
        bubble.setFixedWidth(208)
        bubble.setFixedHeight(22)
        row_layout.addWidget(avatar, 0, Qt.AlignTop)
        row_layout.addWidget(bubble, 0, Qt.AlignLeft)
        row_layout.addStretch(1)
        self.ai_chat_messages_layout.addWidget(row)
        self.ai_stream_row = row
        self.ai_stream_bubble = bubble

    def _update_ai_stream_preview(self):
        safe_message = html.escape(self.ai_stream_text).replace("\n", "<br>")
        bubble_html = f'<span style="font-size:13px;">{safe_message}</span>'
        self.ai_stream_bubble.setText(bubble_html)
        content_width = 208 - 12 - 12
        bubble_height = self._measure_html_height(self.ai_stream_bubble.font(), bubble_html, content_width) + 9 + 9
        self.ai_stream_bubble.setFixedHeight(max(22, bubble_height))
        self.scroll_ai_chat_to_bottom()

    def _end_ai_stream_preview(self):
        if self.ai_stream_row is not None:
            self.ai_chat_messages_layout.removeWidget(self.ai_stream_row)
            self.ai_stream_row.deleteLater()
        self.ai_stream_row = None
        self.ai_stream_bubble = None
        self.ai_stream_text = ""

    def ensure_ai_server(self):
        if os.name == "nt":
            return self.ensure_background_ai_server()
        if self.ai_server is not None:
            return True
        model = self.ai_model_selector.currentText().strip() or DEFAULT_MODEL
        self.save_ai_model(model)
        server = AlBaaAIServer(self.ai_server_token, model=model)
        try:
            server.start()
        except OSError as error:
            QMessageBox.critical(
                self, self.t("Could Not Start AI Network"),
                self.t("Could not open port 8765 on this device:\n{error}", error=error),
            )
            return False
        self.ai_server = server
        self.ai_server_button.setText(self.t("Stop AI Network"))
        self.main_splitter.widget(1).show()
        self.output.setPlainText(
            self.t(
                "The AI server is running on this computer.\n\n"
                "Address: {address}\n"
                "Access token: {token}\n\n"
                "To use it from work: install Tailscale on both devices, sign in with the same account, "
                "then use this computer's name or Tailscale address with port 8765.\n"
                "Example: http://computer-name:8765\n\n"
                "If a Windows Firewall prompt appears, only allow access on private networks.",
                address=server.address, token=self.ai_server_token,
            )
        )
        return True

    def background_ai_is_running(self):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=0.6) as response:
                return response.status == 200
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    def ensure_background_ai_server(self):
        if self.background_ai_is_running():
            self.ai_server_button.setText(self.t("Stop AI Network"))
            return True
        app_data = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "AlBaa")
        roaming_data = os.path.join(os.environ.get("APPDATA", app_data), "AlBaa")
        os.makedirs(app_data, exist_ok=True)
        os.makedirs(roaming_data, exist_ok=True)
        token_file = os.path.join(roaming_data, "ai_server_token.txt")
        with open(token_file, "w", encoding="utf-8") as stream:
            stream.write(self.ai_server_token)

        if getattr(sys, "frozen", False):
            bundle_root = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
            packaged_host = os.path.join(bundle_root, "AlBaaAIHost.exe")
            installed_host = os.path.join(app_data, "AlBaaAIHost.exe")
            if not os.path.isfile(packaged_host):
                QMessageBox.critical(self, self.t("AI Server Not Found"), self.t("AlBaaAIHost.exe wasn't found inside the Al-Baa package."))
                return False
            shutil.copy2(packaged_host, installed_host)
            program, arguments = installed_host, []
            startup_command = f'"{installed_host}"'
        else:
            script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "launch_ai_server.py")
            pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            program = pythonw if os.path.isfile(pythonw) else sys.executable
            arguments = [script]
            startup_command = f'"{program}" "{script}"'

        startup = QSettings(
            r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run",
            QSettings.Format.NativeFormat,
        )
        startup.setValue("AlBaaAIHost", startup_command)
        if not QProcess.startDetached(program, arguments):
            QMessageBox.critical(self, self.t("Could Not Start AI Network"), self.t("Could not start the AI server in the background."))
            return False
        for _attempt in range(20):
            QApplication.processEvents()
            if self.background_ai_is_running():
                self.ai_server_button.setText(self.t("Stop AI Network"))
                self.main_splitter.widget(1).show()
                self.output.setPlainText(
                    self.t(
                        "The AI server is running in the background and will start automatically with Windows.\n\n"
                        "Local address: http://{address}:8765\n"
                        "Access token: {token}\n\n"
                        "You can now close or restart Al-Baa and AI will keep running. "
                        "Keep Ollama, Tailscale, and the computer powered on.",
                        address=local_ipv4(), token=self.ai_server_token,
                    )
                )
                return True
            time.sleep(0.1)
        QMessageBox.critical(self, self.t("Could Not Start AI Network"), self.t("The server started but didn't respond on port 8765."))
        return False

    def stop_background_ai_server(self):
        request = urllib.request.Request(
            "http://127.0.0.1:8765/shutdown",
            data=b"{}",
            headers={"Authorization": f"Bearer {self.ai_server_token}"},
            method="POST",
        )
        try:
            urllib.request.urlopen(request, timeout=2).close()
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        startup = QSettings(
            r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run",
            QSettings.Format.NativeFormat,
        )
        startup.remove("AlBaaAIHost")
        self.ai_server_button.setText(self.t("AI Network"))
        self.output.setPlainText(self.t("The background AI server was stopped and its auto-start was disabled."))

    def build_ai_providers_page(self):
        """A dedicated page listing every configured AI provider, with add/edit/remove."""
        page = QWidget(objectName="aiProvidersPage")
        layout = QVBoxLayout(page)
        header_row = QHBoxLayout()
        header_row.addWidget(QLabel(self.t("AI Providers"), objectName="panelTitle"))
        header_row.addStretch()
        close_button = self.make_button("×", self.close_ai_providers_page, "aiCloseButton")
        close_button.setFixedSize(22, 22)
        close_button.setToolTip(self.t("Close"))
        header_row.addWidget(close_button)
        layout.addLayout(header_row)
        toolbar_row = QHBoxLayout()
        self.ai_providers_add_button = self.make_button("+ " + self.t("Add Provider"), self.add_ai_provider)
        toolbar_row.addWidget(self.ai_providers_add_button)
        self.ai_providers_edit_button = self.make_button(self.t("Edit"), self.edit_selected_ai_provider)
        toolbar_row.addWidget(self.ai_providers_edit_button)
        self.ai_providers_default_button = self.make_button(self.t("Set as Default"), self.set_selected_ai_provider_default)
        toolbar_row.addWidget(self.ai_providers_default_button)
        self.ai_providers_remove_button = self.make_button(self.t("Remove"), self.remove_selected_ai_provider, "ragRemoveButton")
        toolbar_row.addWidget(self.ai_providers_remove_button)
        toolbar_row.addStretch()
        layout.addLayout(toolbar_row)
        self.ai_providers_list = QListWidget(objectName="aiProvidersList")
        layout.addWidget(self.ai_providers_list, 1)
        return page

    def refresh_ai_providers_list(self):
        self.ai_providers_list.clear()
        for config in self.ai_providers:
            spec = PROVIDER_TYPES.get(config.type)
            type_name = spec.display_name if spec else config.type
            entry = f"{config.label} — {type_name}"
            label = (
                self.t("{entry} (default)", entry=entry)
                if config.id == self.active_provider_id
                else entry
            )
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, config.id)
            self.ai_providers_list.addItem(item)

    def show_ai_providers_page(self):
        self.restore_sidebar_explorer_content()
        self.android_designer.hide()
        self.code_splitter.hide()
        self.rag_library_page.hide()
        self.ai_providers_page.show()
        self.refresh_ai_providers_list()

    def close_ai_providers_page(self):
        self.restore_editor_view()
        self.restore_sidebar_explorer_content()
        self.sidebar.show()
        self.set_active_activity(self.activity_buttons[0])

    def selected_ai_provider_config(self):
        item = self.ai_providers_list.currentItem()
        if item is None:
            return None
        provider_id = item.data(Qt.UserRole)
        return next((config for config in self.ai_providers if config.id == provider_id), None)

    def add_ai_provider(self):
        dialog = ProviderEditDialog(self, language=self.language, dark=self.ide_dark)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        config = dialog.result_config()
        self.ai_providers.append(config)
        if self.active_provider_id is None:
            self.active_provider_id = config.id
        self.provider_store.save(self.ai_providers, self.active_provider_id)
        self.invalidate_active_provider_cache()
        self.refresh_ai_providers_list()
        self.refresh_provider_selector()

    def edit_selected_ai_provider(self):
        config = self.selected_ai_provider_config()
        if config is None:
            return
        dialog = ProviderEditDialog(self, language=self.language, dark=self.ide_dark, existing=config)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.result_config()
        config.label = updated.label
        config.type = updated.type
        config.base_url = updated.base_url
        config.api_key = updated.api_key
        config.default_model = updated.default_model
        self.provider_store.save(self.ai_providers, self.active_provider_id)
        self.invalidate_active_provider_cache()
        self.refresh_ai_providers_list()
        self.refresh_provider_selector()

    def set_selected_ai_provider_default(self):
        config = self.selected_ai_provider_config()
        if config is None:
            return
        self.switch_active_provider(config.id)
        self.refresh_ai_providers_list()
        self.refresh_provider_selector()

    def remove_selected_ai_provider(self):
        config = self.selected_ai_provider_config()
        if config is None:
            return
        answer = QMessageBox.question(
            self, self.t("Remove Provider"),
            self.t('Remove "{name}"?', name=config.label),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.ai_providers = [entry for entry in self.ai_providers if entry.id != config.id]
        if self.active_provider_id == config.id:
            self.active_provider_id = self.ai_providers[0].id if self.ai_providers else None
            self.invalidate_active_provider_cache()
        self.provider_store.save(self.ai_providers, self.active_provider_id)
        self.refresh_ai_providers_list()
        self.refresh_provider_selector()

    def toggle_ai_server(self):
        if os.name == "nt":
            if self.background_ai_is_running():
                self.stop_background_ai_server()
            elif self.ensure_background_ai_server():
                QMessageBox.information(
                    self, self.t("AI Network Always On"),
                    self.t("The AI server is running in the background and will keep running when Al-Baa closes, starting automatically with Windows."),
                )
            return
        if self.ai_server is None:
            if self.ensure_ai_server():
                QMessageBox.information(
                    self, self.t("AI Network Ready"),
                    self.t("Address: {address}\n\nKeep Al-Baa and Ollama running while using the mobile app.",
                           address=self.ai_server.address),
                )
            return
        self.ai_server.stop()
        self.ai_server = None
        self.ai_server_button.setText(self.t("AI Network"))
        self.output.setPlainText(self.t("The local AI server was stopped."))

    def ai_export_credentials(self):
        if not self.ensure_ai_server():
            return None, None
        address = self.ai_server.address if self.ai_server is not None else f"http://{local_ipv4()}:8765"
        return address, self.ai_server_token

    def closeEvent(self, event):
        if self.ai_server is not None and os.name != "nt":
            self.ai_server.stop()
            self.ai_server = None
        if self.terminal_process is not None:
            self.terminal_process.kill()
            self.terminal_process.waitForFinished(2000)
            self.terminal_process = None
        super().closeEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() != QEvent.Type.WindowStateChange or not self.isMaximized():
            return
        # A frameless window on Windows can be re-maximized (e.g. after a
        # native dialog like a folder picker returns focus) to a geometry a
        # few pixels wider/taller than the real screen, since there's no
        # native frame for Windows to size against -- that's the "window
        # becomes wider" bug. Force it back to the true available area.
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None and self.geometry() != screen.availableGeometry():
            self.setGeometry(screen.availableGeometry())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Catch-all: whatever caused this resize (toolbar content growing,
        # a build-progress bar appearing, OS maximize quirks on a frameless
        # window...), the window must never end up bigger than the actual
        # screen. setMaximumSize should already prevent this, but that
        # constraint isn't always honored by every code path that can grow
        # a window, so also correct after the fact.
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        if self.width() > available.width() or self.height() > available.height():
            clamped_width = min(self.width(), available.width())
            clamped_height = min(self.height(), available.height())
            QTimer.singleShot(0, lambda: self.resize(clamped_width, clamped_height))

    def new_android_file(self):
        if self.rtl:
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
        else:
            source = (
                'اسم التطبيق هو Al-Baa\n\n'
                'في شريط السفلي ضع:\n'
                '    Home\n'
                '    Search\n'
                '    Alerts\n'
                '    Messages\n\n'
                'اطبع "What is your name"\n\n'
                'name = حقل "Type your name"\n\n'
                'اطبع name\n'
            )
        editor = self.add_editor_tab(source)
        editor.document().setModified(True)
        self.update_tab_title(True)
        editor.setFocus()
        QTimer.singleShot(0, self.show_android_designer)

    def new_pyside6_project(self):
        """Scaffold a standalone PySide6 app built on the Al-Baa Design System."""
        project_name, accepted = QInputDialog.getText(
            self, self.t("New PySide6 Project"), self.t("Project name:"), text="MyApp"
        )
        if not accepted or not project_name.strip():
            return
        parent_dir = QFileDialog.getExistingDirectory(self, self.t("Choose a Location for the New Project"))
        if not parent_dir:
            return
        target = os.path.join(parent_dir, safe_identifier(project_name))
        if os.path.exists(target):
            QMessageBox.warning(
                self, self.t("Folder Already Exists"),
                self.t('A folder named "{name}" already exists there.', name=os.path.basename(target)),
            )
            return
        try:
            generate_pyside_project(target, project_name.strip())
        except OSError as error:
            QMessageBox.critical(self, self.t("Project Creation Failed"), str(error))
            return
        QSettings("AlBaa", "AlBaaIDE").setValue("project_folder", target)
        self.open_folder_path(target)
        self.load_file(os.path.join(target, "main.py"))
        self.run_code()

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
            message = format_error(error, source) if error else self.t("Could not read the app code.")
            self.editor.show_error_line(getattr(error, "line", None))
            self.main_splitter.widget(1).show()
            self.main_splitter.setSizes([650, 190])
            self.output.setPlainText(message)
            QMessageBox.warning(
                self,
                self.t("Could Not Open Designer"),
                self.t("Fix the error first:\n\n{message}", message=getattr(error, 'message', str(error))),
            )
            return
        self.editor.clear_error_line()
        self.output_was_visible_before_designer = self.main_splitter.widget(1).isVisible()
        self.main_splitter.widget(1).hide()
        self.main_splitter.setSizes([1, 0])
        self.code_splitter.hide()
        self.android_designer.show()
        self.designer_button.setText(self.t("Code"))

    def hide_android_designer(self):
        if self.android_designer.preview_mode:
            self.android_designer.stop_preview()
            self.run_button.setText("▶")
            self.run_button.setToolTip(self.t("Run"))
        self.android_designer.hide()
        self.code_splitter.show()
        if self.output_was_visible_before_designer:
            self.main_splitter.widget(1).show()
            self.main_splitter.setSizes([650, 190])
        self.designer_button.setText(self.t("Designer"))

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
                self.t('This file isn\'t an Android app. Start with: تطبيق "App Name"')
            )
            return False

        directory = QFileDialog.getExistingDirectory(
            self, self.t("Choose an Android Project Folder")
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
                self.t("Replace Project Files"),
                self.t("main.py and buildozer.spec in the selected folder will be replaced. Continue?"),
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
            self.t("Android project exported to:\n{directory}\n\nClick «Build APK» to build it locally (needs WSL2 + Buildozer -- see Install APK Tools).",
                   directory=directory)
        )
        return True

    def export_cross_platform(self):
        source = self.editor.toPlainText()
        if not is_android_source(source):
            QMessageBox.warning(self, self.t("Not an App"), self.t("Open or create an Al-Baa app project first."))
            return False
        output_directory = QFileDialog.getExistingDirectory(self, self.t("Choose Where to Save the Cross-Platform Project"))
        if not output_directory:
            return False
        try:
            export_tauri_project(source, output_directory)
        except Exception as error:
            self.output.setPlainText(format_error(error, source))
            QMessageBox.critical(self, self.t("Export Failed"), str(error))
            return False
        self.main_splitter.widget(1).show()
        self.output.setPlainText(
            self.t("Cross-platform project exported to:\n{directory}\n\n"
                   "This includes project files for Browser, Windows, Linux, macOS, Android, and iOS. "
                   "Building a real app for each platform needs that platform's own toolchain.",
                   directory=output_directory)
        )
        QMessageBox.information(
            self, self.t("Export Complete"),
            self.t("Cross-platform project exported to:\n{directory}", directory=output_directory),
        )
        return True

    def build_android_apk(self):
        if self.android_build_process is not None:
            self.output.setPlainText(self.t("An APK build is already in progress. Wait for it to finish."))
            return
        if not self.apk_tools_are_ready():
            self.main_splitter.widget(1).show()
            self.output.setPlainText(
                self.t("APK tools aren't fully set up. First click: Install APK Tools.\n"
                       "If you just installed WSL on Windows, restart the device and click Install again.")
            )
            QMessageBox.warning(
                self, self.t("APK Tools Not Ready"),
                self.t("Can't build an APK right now.\n\n"
                       "Click «Install APK Tools» and complete every step first. "
                       "You may need to restart Windows.")
            )
            return
        if not self.android_project_path and not self.export_android():
            return

        self.main_splitter.widget(1).show()
        self.output.setPlainText(
            self.t("Starting Buildozer inside WSL2...\n"
                   "WSL2, Buildozer, and the Android requirements must already be installed.\n\n")
        )
        process = QProcess(self)
        self.android_build_process = process
        self.apk_button.setEnabled(False)
        self.apk_tools_button.setEnabled(False)
        self.apk_button.setText(self.t("… Building APK"))
        self.apk_progress.setToolTip(self.t("Building APK (local)"))
        self.apk_progress.show()
        process.setProgram("wsl.exe")
        process.setArguments([
            "-d", "Ubuntu", "--cd", self.android_project_path,
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
            "-d", "Ubuntu", "-u", "root", "--", "test", "-x",
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
            self.output.setPlainText(self.t("APK tools are already being installed. Wait for it to finish."))
            return
        self.main_splitter.widget(1).show()
        self.output.setPlainText(self.t("Checking WSL2 and Ubuntu...\n"))
        self.apk_tools_button.setEnabled(False)
        self.apk_button.setEnabled(False)
        self.apk_tools_button.setText(self.t("… Checking"))
        self.apk_progress.setToolTip(self.t("Checking and installing APK tools"))
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
                message = self.t(
                    "The WSL2 and Ubuntu installation step finished.\n\n"
                    "Restart Windows now, then open «Al-Baa» and click "
                    "«Install APK Tools» again to finish Buildozer."
                )
                self.output.appendPlainText("\n" + message)
                QMessageBox.information(self, self.t("First Stage Complete"), message)
            else:
                message = self.t(
                    "WSL2 installation failed with code {code}.\n\n"
                    "If error 14098 appears (corrupt component store), «Al-Baa» "
                    "can run the official Windows repair tools now. Start the repair?",
                    code=exit_code,
                )
                self.output.appendPlainText("\n" + message)
                answer = QMessageBox.question(
                    self, self.t("WSL2 Installation Failed"), message,
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
                )
                if answer == QMessageBox.Yes:
                    self.start_windows_component_repair()
                    return
            self.reset_apk_install_button()
            return

        if self.apk_install_stage == "repair":
            if exit_code == 0:
                message = self.t(
                    "Windows component repair finished. Restart the device, then click "
                    "«Install APK Tools» again."
                )
                QMessageBox.information(self, self.t("Windows Repair Complete"), message)
            else:
                message = self.t(
                    "Windows repair didn't complete (code {code}). Check the result in the PowerShell window. "
                    "You may need Windows Update or a Windows repair source matching your device's version.",
                    code=exit_code,
                )
                QMessageBox.critical(self, self.t("Could Not Repair Windows"), message)
            self.output.appendPlainText("\n" + message)
            self.reset_apk_install_button()
            return

        if exit_code == 0:
            message = self.t("APK tools installed successfully. You can now click Build APK.")
            self.output.appendPlainText("\n" + message)
            QMessageBox.information(self, self.t("Installation Complete"), message)
        else:
            message = self.t(
                "APK tools installation failed with code {code}. Check the output log.\n\n"
                "If Ubuntu is newly installed, open it once and finish its setup, then try again.",
                code=exit_code,
            )
            self.output.appendPlainText("\n" + message)
            QMessageBox.critical(self, self.t("APK Tools Installation Failed"), message)
        self.reset_apk_install_button()

    def start_wsl_install(self):
        """Run the elevated Windows installer while keeping its lifecycle visible."""
        self.apk_install_stage = "wsl"
        self.apk_tools_button.setText(self.t("… Installing WSL2"))
        self.output.setPlainText(
            self.t("Windows will ask for administrator permission to install WSL2 and Ubuntu.\n"
                   "Approve the prompt and wait until it finishes. Don't close «Al-Baa».\n\n")
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
            self.t("Starting to install Java, Buildozer, and Android requirements inside WSL2...\n"
                   "This may take several minutes depending on your internet speed.\n\n")
        )
        self.apk_tools_button.setText(self.t("… Installing"))
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
        self.apk_tools_button.setText(self.t("… Repairing Windows"))
        self.apk_progress.setToolTip(self.t("Repairing Windows components"))
        self.apk_progress.show()
        self.output.setPlainText(
            self.t("Starting to repair the Windows component store via DISM then SFC...\n"
                   "This can take a long time. Don't close the PowerShell window.\n\n")
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
        self.apk_tools_button.setText(self.t("↓ Install APK Tools"))
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
                "\n" + self.t("Could not start WSL2/Buildozer. Make sure they're installed and on PATH inside WSL.")
            )
            self.android_build_process.deleteLater()
            self.android_build_process = None
        self.apk_button.setEnabled(True)
        self.apk_tools_button.setEnabled(True)
        self.apk_button.setText(self.t("▣ Build APK"))
        self.apk_progress.hide()
        QMessageBox.critical(
            self, self.t("Could Not Build APK"),
            self.t("Could not run WSL2 or Buildozer. Click «Install APK Tools» and try again.")
        )

    def android_build_finished(self, exit_code, _status):
        if exit_code == 0:
            message = self.t("APK built successfully. You'll find it inside the project's bin folder.")
            self.output.appendPlainText("\n" + message)
            QMessageBox.information(self, self.t("APK Built"), message)
        else:
            message = self.t("APK build failed with exit code {code}. Check the Buildozer log in the output.", code=exit_code)
            self.output.appendPlainText("\n" + message)
            QMessageBox.critical(self, self.t("APK Build Failed"), message)
        if self.android_build_process is not None:
            self.android_build_process.deleteLater()
            self.android_build_process = None
        self.apk_button.setEnabled(True)
        self.apk_tools_button.setEnabled(True)
        self.apk_button.setText(self.t("▣ Build APK"))
        self.apk_progress.hide()

    # -- Al Baa Linux Builder ------------------------------------------------
    # Mirrors the Android/Buildozer WSL2 pipeline above. The WSL2-install
    # step is intentionally its own short copy rather than shared with
    # install_apk_tools()/start_wsl_install() -- see the "v1's WSL2-install
    # step is independent" design decision in the Al Baa Linux Builder plan.
    # No function here accepts a name/branding argument; the fixed identity
    # lives entirely in arabicpy/albaa_linux.py.

    def linux_builder_output_dir(self):
        return os.path.join(
            os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "AlBaa", "linux_builder", "output"
        )

    @staticmethod
    def windows_path_to_wsl(path):
        """C:\\Users\\... -> /mnt/c/Users/... , the path WSL2 uses for the same file."""
        drive, rest = path[0].lower(), path[2:].replace("\\", "/")
        return f"/mnt/{drive}{rest}"

    def check_linux_build_disk_space(self):
        """Return (ok, message). A live-build XFCE run needs headroom both on
        the Windows host drive (where the WSL2 vhdx grows and the final ISO
        is copied to) and inside WSL2's own filesystem (the live-build chroot)."""
        host_root = os.environ.get("LOCALAPPDATA", tempfile.gettempdir())
        try:
            host_free_gb = shutil.disk_usage(host_root).free / (1024 ** 3)
        except OSError:
            host_free_gb = None

        wsl_free_gb = None
        check = QProcess(self)
        check.setProgram("wsl.exe")
        check.setArguments(["-d", "Ubuntu", "-u", "root", "--", "df", "--output=avail", "-B1", "/"])
        check.start()
        if check.waitForStarted(2500) and check.waitForFinished(8000):
            output = bytes(check.readAllStandardOutput()).decode("utf-8", errors="replace")
            lines = [line.strip() for line in output.splitlines() if line.strip()]
            if len(lines) >= 2 and lines[1].isdigit():
                wsl_free_gb = int(lines[1]) / (1024 ** 3)

        if host_free_gb is not None and host_free_gb < 25:
            return False, self.t(
                "Only {free:.1f} GB free on the Windows drive. Al Baa Linux Builder needs at least 25 GB free.",
                free=host_free_gb,
            )
        if wsl_free_gb is not None and wsl_free_gb < 15:
            return False, self.t(
                "Only {free:.1f} GB free inside WSL2's Ubuntu filesystem. Al Baa Linux Builder needs at least 15 GB free there.",
                free=wsl_free_gb,
            )
        if host_free_gb is not None and host_free_gb < 35:
            return True, self.t(
                "Only {free:.1f} GB free on the Windows drive. The build should fit, but it's close.",
                free=host_free_gb,
            )
        return True, ""

    def linux_builder_tools_are_ready(self):
        """Return True only when the live-build toolchain is installed in WSL2."""
        check = QProcess(self)
        check.setProgram("wsl.exe")
        check.setArguments(["-d", "Ubuntu", "-u", "root", "--", "test", "-x", "/usr/bin/lb"])
        check.start()
        if not check.waitForStarted(2500):
            return False
        if not check.waitForFinished(8000):
            check.kill()
            return False
        return check.exitCode() == 0

    def install_linux_builder_tools(self):
        """Install WSL2 first if needed, then the live-build toolchain."""
        if self.linux_builder_install_process is not None:
            self.output.setPlainText(
                self.t("Al Baa Linux builder tools are already being installed. Wait for it to finish.")
            )
            return
        self.main_splitter.widget(1).show()
        self.output.setPlainText(self.t("Checking WSL2 and Ubuntu...\n"))
        self.linux_builder_tools_button.setEnabled(False)
        self.linux_build_iso_button.setEnabled(False)
        self.linux_builder_tools_button.setText(self.t("… Checking"))
        self.linux_iso_progress.setToolTip(self.t("Checking and installing Al Baa Linux builder tools"))
        self.linux_iso_progress.show()
        self.linux_builder_install_stage = "check"
        process = QProcess(self)
        self.linux_builder_install_process = process
        process.setProgram("wsl.exe")
        process.setArguments(["-d", "Ubuntu", "-u", "root", "--", "true"])
        process.readyReadStandardOutput.connect(self.read_linux_builder_install_output)
        process.readyReadStandardError.connect(self.read_linux_builder_install_output)
        process.finished.connect(self.linux_builder_install_finished)
        process.start()

    def read_linux_builder_install_output(self):
        process = self.linux_builder_install_process
        if process is None:
            return
        data = bytes(process.readAllStandardOutput()) + bytes(process.readAllStandardError())
        if data:
            encoding = "utf-16" if b"\x00" in data[:20] else "utf-8"
            self.output.appendPlainText(data.decode(encoding, errors="replace").rstrip())

    def linux_builder_install_finished(self, exit_code, _status):
        process = self.linux_builder_install_process
        if process is not None:
            self.read_linux_builder_install_output()
            process.deleteLater()
        self.linux_builder_install_process = None

        if self.linux_builder_install_stage == "check":
            if exit_code != 0:
                self.start_linux_builder_wsl_install()
                return
            self.start_linux_builder_tools_install()
            return

        if self.linux_builder_install_stage == "wsl":
            if exit_code == 0:
                message = self.t(
                    "The WSL2 and Ubuntu installation step finished.\n\n"
                    "Restart Windows now, then open «Al-Baa» and click "
                    "«Install Builder Tools» again to finish the live-build toolchain."
                )
                self.output.appendPlainText("\n" + message)
                QMessageBox.information(self, self.t("First Stage Complete"), message)
            else:
                message = self.t(
                    "WSL2 installation failed with code {code}.\n\n"
                    "The Android menu's «Install APK Tools» offers a Windows component repair "
                    "option for this same failure -- try that, then click «Install Builder Tools» again.",
                    code=exit_code,
                )
                self.output.appendPlainText("\n" + message)
                QMessageBox.critical(self, self.t("WSL2 Installation Failed"), message)
            self.reset_linux_builder_install_button()
            return

        if exit_code == 0:
            message = self.t(
                "Al Baa Linux builder tools installed successfully. You can now click Build Al Baa Linux ISO."
            )
            self.output.appendPlainText("\n" + message)
            QMessageBox.information(self, self.t("Installation Complete"), message)
        else:
            message = self.t(
                "Al Baa Linux builder tools installation failed with code {code}. Check the output log.\n\n"
                "If Ubuntu is newly installed, open it once and finish its setup, then try again.",
                code=exit_code,
            )
            self.output.appendPlainText("\n" + message)
            QMessageBox.critical(self, self.t("Installation Failed"), message)
        self.reset_linux_builder_install_button()

    def start_linux_builder_wsl_install(self):
        """Run the elevated Windows installer while keeping its lifecycle visible."""
        self.linux_builder_install_stage = "wsl"
        self.linux_builder_tools_button.setText(self.t("… Installing WSL2"))
        self.output.setPlainText(
            self.t("Windows will ask for administrator permission to install WSL2 and Ubuntu.\n"
                   "Approve the prompt and wait until it finishes. Don't close «Al-Baa».\n\n")
        )
        elevated_script = (
            "wsl.exe --install --web-download -d Ubuntu; "
            "$result = $LASTEXITCODE; "
            "Write-Host ''; "
            "if ($result -eq 0) { Write-Host 'WSL installation finished.' -ForegroundColor Green } "
            "else { Write-Host ('WSL installation failed. Exit code: ' + $result) -ForegroundColor Red }; "
            "Read-Host 'Press Enter to return to AlBaa'; exit $result"
        )
        encoded_script = base64.b64encode(elevated_script.encode("utf-16-le")).decode("ascii")
        command = (
            "$p = Start-Process -FilePath powershell.exe -WindowStyle Normal "
            f"-ArgumentList '-NoProfile','-EncodedCommand','{encoded_script}' "
            "-Verb RunAs -Wait -PassThru; exit $p.ExitCode"
        )
        process = QProcess(self)
        self.linux_builder_install_process = process
        process.setProgram("powershell.exe")
        process.setArguments(["-NoProfile", "-Command", command])
        process.readyReadStandardOutput.connect(self.read_linux_builder_install_output)
        process.readyReadStandardError.connect(self.read_linux_builder_install_output)
        process.finished.connect(self.linux_builder_install_finished)
        process.start()

    def start_linux_builder_tools_install(self):
        self.linux_builder_install_stage = "tools"
        self.output.setPlainText(
            self.t("Starting to install the live-build toolchain inside WSL2...\n"
                   "This may take a few minutes depending on your internet speed.\n\n")
        )
        self.linux_builder_tools_button.setText(self.t("… Installing"))
        process = QProcess(self)
        self.linux_builder_install_process = process
        process.setProgram("wsl.exe")
        process.setArguments(["-u", "root", "--", "bash", "-lc", albaa_linux.builder_tools_install_script()])
        process.readyReadStandardOutput.connect(self.read_linux_builder_install_output)
        process.readyReadStandardError.connect(self.read_linux_builder_install_output)
        process.finished.connect(self.linux_builder_install_finished)
        process.start()

    def reset_linux_builder_install_button(self):
        self.linux_builder_install_stage = None
        self.linux_builder_tools_button.setEnabled(True)
        self.linux_build_iso_button.setEnabled(True)
        self.linux_builder_tools_button.setText(self.t("↓ Install Builder Tools"))
        self.linux_iso_progress.hide()

    def build_albaa_linux_iso(self):
        if self.linux_iso_build_process is not None:
            self.output.setPlainText(self.t("An Al Baa Linux build is already in progress. Wait for it to finish."))
            return
        if not self.linux_builder_tools_are_ready():
            self.main_splitter.widget(1).show()
            self.output.setPlainText(
                self.t("Al Baa Linux builder tools aren't fully set up. First click: Install Builder Tools.\n"
                       "If you just installed WSL2 on Windows, restart the device and click Install again.")
            )
            QMessageBox.warning(
                self, self.t("Builder Tools Not Ready"),
                self.t("Can't build Al Baa Linux right now.\n\n"
                       "Click «Install Builder Tools» and complete every step first. "
                       "You may need to restart Windows.")
            )
            return
        ok, message = self.check_linux_build_disk_space()
        if not ok:
            self.main_splitter.widget(1).show()
            self.output.setPlainText(message)
            QMessageBox.warning(self, self.t("Not Enough Disk Space"), message)
            return

        output_dir = self.linux_builder_output_dir()
        os.makedirs(output_dir, exist_ok=True)
        output_iso_path = os.path.join(output_dir, albaa_linux.ISO_FILENAME)
        output_iso_wsl_path = self.windows_path_to_wsl(output_iso_path)

        wallpaper_base64 = ""
        wallpaper_path = os.path.join(os.path.dirname(__file__), "..", "assets", "albaa.png")
        if os.path.isfile(wallpaper_path):
            with open(wallpaper_path, "rb") as file:
                wallpaper_base64 = base64.b64encode(file.read()).decode("ascii")

        self.main_splitter.widget(1).show()
        self.output.setPlainText(
            self.t("Starting the Al Baa Linux build inside WSL2...\n"
                   "This produces a full Ubuntu-based ISO and can take a long time.\n\n")
            + (message + "\n\n" if message else "")
        )
        process = QProcess(self)
        self.linux_iso_build_process = process
        self.linux_build_iso_button.setEnabled(False)
        self.linux_builder_tools_button.setEnabled(False)
        self.linux_build_iso_button.setText(self.t("… Building ISO"))
        self.linux_iso_progress.setToolTip(self.t("Building Al Baa Linux ISO"))
        self.linux_iso_progress.show()
        process.setProgram("wsl.exe")
        process.setArguments([
            "-d", "Ubuntu", "-u", "root", "--", "bash", "-lc",
            albaa_linux.lb_build_script(output_iso_wsl_path, wallpaper_base64),
        ])
        process.readyReadStandardOutput.connect(self.read_linux_build_output)
        process.readyReadStandardError.connect(self.read_linux_build_output)
        process.errorOccurred.connect(self.linux_build_error)
        process.finished.connect(self.linux_build_finished)
        process.start()

    def read_linux_build_output(self):
        process = self.linux_iso_build_process
        if process is None:
            return
        data = bytes(process.readAllStandardOutput()) + bytes(process.readAllStandardError())
        if data:
            self.output.appendPlainText(data.decode("utf-8", errors="replace").rstrip())

    def linux_build_error(self, _error):
        if self.linux_iso_build_process is not None:
            self.output.appendPlainText(
                "\n" + self.t("Could not start WSL2/live-build. Make sure they're installed inside WSL.")
            )
            self.linux_iso_build_process.deleteLater()
            self.linux_iso_build_process = None
        self.linux_build_iso_button.setEnabled(True)
        self.linux_builder_tools_button.setEnabled(True)
        self.linux_build_iso_button.setText(self.t("▣ Build Al Baa Linux ISO"))
        self.linux_iso_progress.hide()
        QMessageBox.critical(
            self, self.t("Could Not Build Al Baa Linux"),
            self.t("Could not run WSL2 or live-build. Click «Install Builder Tools» and try again.")
        )

    def linux_build_finished(self, exit_code, _status):
        output_dir = self.linux_builder_output_dir()
        if exit_code == 0:
            iso_path = os.path.join(output_dir, albaa_linux.ISO_FILENAME)
            QSettings("AlBaa", "AlBaaIDE").setValue("linux_builder_last_build_path", iso_path)
            message = self.t("Al Baa Linux ISO built successfully:\n{path}", path=iso_path)
            self.output.appendPlainText("\n" + message)
            QMessageBox.information(self, self.t("Al Baa Linux Built"), message)
            try:
                os.startfile(output_dir)
            except OSError:
                pass
        else:
            message = self.t(
                "Al Baa Linux build failed with exit code {code}. Check the live-build log in the output.",
                code=exit_code,
            )
            self.output.appendPlainText("\n" + message)
            QMessageBox.critical(self, self.t("Al Baa Linux Build Failed"), message)
        if self.linux_iso_build_process is not None:
            self.linux_iso_build_process.deleteLater()
            self.linux_iso_build_process = None
        self.linux_build_iso_button.setEnabled(True)
        self.linux_builder_tools_button.setEnabled(True)
        self.linux_build_iso_button.setText(self.t("▣ Build Al Baa Linux ISO"))
        self.linux_iso_progress.hide()

    def new_file(self):
        self.add_editor_tab().setFocus()
        return
        self.current_file = None
        self.editor.clear()
        self.editor.document().setModified(False)
        self.update_tab_title()
        self.editor.setFocus()

    def new_flutter_file(self):
        """Start a Flutter/Dart tab -- syntax-highlighted, not runnable yet (build support is on the way)."""
        template = (
            "import 'package:flutter/material.dart';\n\n"
            "void main() {\n"
            "  runApp(const MyApp());\n"
            "}\n\n"
            "class MyApp extends StatelessWidget {\n"
            "  const MyApp({super.key});\n\n"
            "  @override\n"
            "  Widget build(BuildContext context) {\n"
            "    return MaterialApp(\n"
            "      home: Scaffold(\n"
            "        appBar: AppBar(title: const Text('Al-Baa Flutter App')),\n"
            "        body: const Center(child: Text('Hello, Flutter!')),\n"
            "      ),\n"
            "    );\n"
            "  }\n"
            "}\n"
        )
        editor = self.add_editor_tab(template, code_language="flutter")
        editor.document().setModified(True)
        self.update_tab_title(True)
        editor.setFocus()

    def new_python_file(self):
        """Start a plain Python tab -- syntax-highlighted and runnable via ▶ Run."""
        template = (
            "def main():\n"
            "    print('Hello from Python!')\n\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        editor = self.add_editor_tab(template, code_language="python")
        editor.document().setModified(True)
        self.update_tab_title(True)
        editor.setFocus()

    def open_project_file(self, item):
        self.load_file(item.data(Qt.UserRole))

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.t("Open File"), "",
            self.t("Al-Baa Files (*.apy);;Flutter Files (*.dart);;Python (*.py);;All Files (*)"),
        )
        if path:
            self.load_file(path)

    def load_file(self, path):
        for index in range(self.tab_widget.count()):
            editor = self.tab_widget.widget(index)
            if getattr(editor, "file_path", None) == path:
                self.tab_widget.setCurrentIndex(index)
                return
        try:
            lowered_path = path.lower()
            if lowered_path.endswith(".dart"):
                code_language = "flutter"
            elif lowered_path.endswith(".py"):
                code_language = "python"
            else:
                code_language = "albaa"
            with open(path, "r", encoding="utf-8") as file:
                self.add_editor_tab(file.read(), path, code_language=code_language)
            self.remember_project_file(path)
            return
            with open(path, "r", encoding="utf-8") as file:
                self.editor.setPlainText(file.read())
            self.current_file = path
            self.editor.document().setModified(False)
            self.update_tab_title()
        except OSError as error:
            self.output.setPlainText(self.t("Could not open the file:\n{error}", error=error))

    def save_file(self):
        editor = self.editor
        if not getattr(editor, "file_path", None):
            code_language = getattr(editor, "code_language", "albaa")
            default_name, save_filter = {
                "flutter": (self.t("main.dart"), self.t("Flutter Files (*.dart)")),
                "python": (self.t("main.py"), self.t("Python Files (*.py)")),
            }.get(code_language, (self.t("Untitled.apy"), self.t("Al-Baa Files (*.apy)")))
            suggested_name = getattr(editor, "display_name", default_name)
            path, _ = QFileDialog.getSaveFileName(self, self.t("Save File"), suggested_name, save_filter)
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
            self.autosave_status_label.setText(self.t("Saved"))
            return
        except OSError as error:
            self.output.setPlainText(self.t("Could not save the file:\n{error}", error=error))
            return
        if not self.current_file:
            path, _ = QFileDialog.getSaveFileName(self, self.t("Save File"), "", self.t("Al-Baa Files (*.apy)"))
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
            self.output.setPlainText(self.t("Could not save the file:\n{error}", error=error))

    def find_text(self):
        """Focus the title bar's search box -- the only find UI now, no second bar."""
        self.restore_sidebar_explorer_content()
        selected = self.editor.textCursor().selectedText()
        if selected:
            self.title_search_box.setText(selected)
        self.title_search_box.setFocus()
        self.title_search_box.selectAll()
        self.set_active_activity(self.activity_buttons[1])

    def find_next(self):
        text = self.title_search_box.text()
        if not text:
            return
        found = self.editor.document().find(text, self.editor.textCursor())
        if found.isNull():
            found = self.editor.document().find(text)
        if found.isNull():
            QToolTip.showText(
                self.title_search_box.mapToGlobal(self.title_search_box.rect().bottomLeft()),
                self.t("No results"),
                self.title_search_box,
            )
            return
        self.editor.setTextCursor(found)
        self.editor.ensureCursorVisible()

    def search_from_title_bar(self):
        """Enter in the title bar's search box jumps to the next match."""
        self.find_next()

    def run_code(self):
        code_language = getattr(self.editor, "code_language", "albaa")
        if code_language == "flutter":
            self.main_splitter.widget(1).show()
            self.output.setPlainText(
                self.t("Running Flutter/Dart files isn't supported yet -- it's on the way. "
                       "For now, this tab is for writing and syntax-highlighting Dart code.")
            )
            return
        if code_language == "python":
            self.run_python_file(self.editor.toPlainText())
            return
        source = self.editor.toPlainText()
        if is_android_source(source):
            try:
                generate_kivy(source)
                self.editor.clear_error_line()
                if self.android_designer.isVisible():
                    if self.android_designer.preview_mode:
                        self.android_designer.stop_preview()
                        self.run_button.setText("▶")
                        self.run_button.setToolTip(self.t("Run"))
                    else:
                        self.android_designer.load_source(source)
                        self.android_designer.start_preview()
                        self.run_button.setText("■")
                        self.run_button.setToolTip(self.t("Stop Preview"))
                    return
                self.output.setPlainText(
                    self.t("App verified successfully. Use the File and Run menus to export or build an APK.")
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
            self.output.setPlainText(result if result else self.t("Ran successfully — no output."))
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

    def run_python_file(self, source):
        """Run a plain Python tab with the same interpreter this IDE runs on."""
        if self.python_run_process is not None:
            QMessageBox.information(self, self.t("Run"), self.t("Wait for the current Python program to finish."))
            return
        self.main_splitter.widget(1).show()
        self.output.setPlainText(self.t("Running...") + "\n\n")
        path = getattr(self.editor, "file_path", None)
        if path and not self.editor.document().isModified():
            run_path = path
        else:
            run_path = os.path.join(tempfile.gettempdir(), "albaa_python_run.py")
            with open(run_path, "w", encoding="utf-8") as run_file:
                run_file.write(source)
        process = QProcess(self)
        self.python_run_process = process
        process.setWorkingDirectory(os.path.dirname(path) if path else tempfile.gettempdir())
        process.setProgram(sys.executable)
        process.setArguments([run_path])
        process.readyReadStandardOutput.connect(self.read_python_run_output)
        process.readyReadStandardError.connect(self.read_python_run_output)
        process.errorOccurred.connect(self.python_run_error)
        process.finished.connect(self.python_run_finished)
        process.start()

    def read_python_run_output(self):
        process = self.python_run_process
        if process is None:
            return
        data = bytes(process.readAllStandardOutput()) + bytes(process.readAllStandardError())
        if data:
            self.output.appendPlainText(data.decode("utf-8", errors="replace").rstrip("\n"))

    def python_run_error(self, _error):
        if self.python_run_process is None:
            return
        self.output.appendPlainText("\n" + self.t("Could not start Python."))

    def python_run_finished(self, exit_code, _status):
        process = self.python_run_process
        if process is not None:
            self.read_python_run_output()
            process.deleteLater()
        self.python_run_process = None
        self.output.appendPlainText("\n" + self.t("Finished (exit code {code}).", code=exit_code))


if __name__ == "__main__":
    app = QApplication([])
    window = ArabicPyIDE()
    window.show_fitted()
    app.exec()
