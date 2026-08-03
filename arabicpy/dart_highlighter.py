from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


class DartHighlighter(QSyntaxHighlighter):
    """Basic Dart/Flutter syntax colours, matching the same VS Code-inspired palette
    used for Al-Baa so a Flutter tab doesn't look like a different app."""

    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569cd6"))
        keyword_format.setFontWeight(QFont.Bold)
        keywords = [
            "abstract", "as", "assert", "async", "await", "break", "case", "catch",
            "class", "const", "continue", "covariant", "default", "deferred", "do",
            "dynamic", "else", "enum", "export", "extends", "extension", "external",
            "factory", "false", "final", "finally", "for", "get", "hide", "if",
            "implements", "import", "in", "interface", "is", "late", "library",
            "mixin", "new", "null", "on", "operator", "part", "required", "rethrow",
            "return", "set", "show", "static", "super", "switch", "sync", "this",
            "throw", "true", "try", "typedef", "var", "void", "while", "with", "yield",
        ]
        self._add_words(keywords, keyword_format)

        type_format = QTextCharFormat()
        type_format.setForeground(QColor("#4ec9b0"))
        self._add_words([
            "int", "double", "String", "bool", "num", "List", "Map", "Set", "Object",
            "Function", "Future", "Stream", "Widget", "StatelessWidget", "StatefulWidget",
            "State", "BuildContext", "Key",
        ], type_format)

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#ce9178"))
        self.rules.append((QRegularExpression(r'".*?"|\'.*?\''), string_format))

        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#b5cea8"))
        self.rules.append((QRegularExpression(r"\b[0-9]+(?:\.[0-9]+)?\b"), number_format))

        builtin_format = QTextCharFormat()
        builtin_format.setForeground(QColor("#dcdcaa"))
        self._add_words([
            "print", "runApp", "MaterialApp", "Scaffold", "AppBar", "Text", "Container",
            "Column", "Row", "Center", "Padding", "Icon", "Image", "ListView",
        ], builtin_format)

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955"))
        comment_format.setFontItalic(True)
        self.rules.append((QRegularExpression(r"//.*"), comment_format))

        annotation_format = QTextCharFormat()
        annotation_format.setForeground(QColor("#dcdcaa"))
        self.rules.append((QRegularExpression(r"@\w+"), annotation_format))

    def set_theme(self, dark):
        """Use high-contrast syntax colours for the active editor theme."""
        dark_to_light = {
            "#569cd6": "#005cc5",  # keywords
            "#4ec9b0": "#0e7566",  # types
            "#ce9178": "#a31515",  # strings
            "#b5cea8": "#098658",  # numbers
            "#dcdcaa": "#795e26",  # builtins/annotations
            "#6a9955": "#237a30",  # comments
        }
        light_to_dark = {light: dark_color for dark_color, light in dark_to_light.items()}
        palette = light_to_dark if dark else dark_to_light
        for _pattern, text_format in self.rules:
            current = text_format.foreground().color().name().lower()
            target = palette.get(current)
            if target:
                text_format.setForeground(QColor(target))
        self.rehighlight()

    def _add_words(self, words, text_format):
        for word in words:
            pattern = rf"\b{QRegularExpression.escape(word)}\b"
            self.rules.append((QRegularExpression(pattern), text_format))

    def highlightBlock(self, text):
        for pattern, text_format in self.rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), text_format)
