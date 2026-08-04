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
            "اذا", "والا", "وإلا", "لكل", "في", "بينما", "كرر", "مرات",
            "دالة", "ارجع", "صح", "خطأ", "و", "او", "أو", "ليس",
            "توقف", "استمر", "تجاوز", "صنف", "استورد", "من", "حاول", "إلا", "نهاية",
            "تطبيق", "عند_النقر", "غيّر_النص", "لون_النص", "لون_الخلفية", "لون_الشاشة",
            "اسم", "التطبيق", "هو", "ضع", "شريط", "السفلي", "عند", "النقر", "على", "لون", "الشاشة", "النص",
            "if", "else", "for", "in", "while", "def", "class", "import", "from",
            "return", "and", "or", "not", "break", "continue", "pass",
            "try", "except", "True", "False",
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
        self._add_words([
            "اطبع", "طباعة", "ادخل", "اسأل", "نص", "زر", "حقل",
            "print", "input", "len", "range",
        ], builtin_format)

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955"))
        comment_format.setFontItalic(True)
        self.rules.append((QRegularExpression(r"#.*"), comment_format))

    def set_theme(self, dark):
        """Use high-contrast syntax colours for the active editor theme."""
        dark_to_light = {
            "#569cd6": "#005cc5",  # keywords
            "#ce9178": "#a31515",  # strings
            "#b5cea8": "#098658",  # numbers
            "#dcdcaa": "#795e26",  # builtins/functions
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
            # PCRE's default \b handling does not reliably treat Arabic
            # letters as word characters. Explicit Unicode-aware boundaries
            # give ArabicPy and Python equivalents the same semantic colour.
            escaped_word = QRegularExpression.escape(word)
            pattern = rf"(?<![\w\x{{0600}}-\x{{06FF}}]){escaped_word}(?![\w\x{{0600}}-\x{{06FF}}])"
            self.rules.append((QRegularExpression(pattern), text_format))

    def highlightBlock(self, text):
        for pattern, text_format in self.rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), text_format)
