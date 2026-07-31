from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


class ArabicPyHighlighter(QSyntaxHighlighter):
    """Visual Studio-inspired syntax colours for ArabicPy and Python keywords."""

    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569cd6"))
        keyword_format.setFontWeight(QFont.Bold)
        keywords = [
            "اذا", "وإلا", "لكل", "بينما", "دالة", "ارجع", "صنف", "استورد", "من", "حاول", "إلا", "نهاية",
            "if", "else", "for", "while", "def", "class", "import", "from", "return", "try", "except",
        ]
        self._add_words(keywords, keyword_format)

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#ce9178"))
        self.rules.append((QRegularExpression(r'".*?"|\'.*?\''), string_format))

        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#b5cea8"))
        self.rules.append((QRegularExpression(r"\b[0-9]+(?:\.[0-9]+)?\b"), number_format))

        builtin_format = QTextCharFormat()
        builtin_format.setForeground(QColor("#dcdcaa"))
        self._add_words(["اطبع", "طباعة", "ادخل", "اسأل", "print", "input", "len", "range"], builtin_format)

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955"))
        comment_format.setFontItalic(True)
        self.rules.append((QRegularExpression(r"#.*"), comment_format))

    def _add_words(self, words, text_format):
        for word in words:
            self.rules.append((QRegularExpression(rf"\b{word}\b"), text_format))

    def highlightBlock(self, text):
        for pattern, text_format in self.rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), text_format)
