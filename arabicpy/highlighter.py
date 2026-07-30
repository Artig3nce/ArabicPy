from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtCore import QRegularExpression


class ArabicPyHighlighter(QSyntaxHighlighter):

    def __init__(self, document):
        super().__init__(document)

        self.rules = []

        # Keywords
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))
        keyword_format.setFontWeight(QFont.Bold)

        keywords = [
            "اذا",
            "وإلا",
            "لكل",
            "بينما",
            "دالة",
            "ارجع",
            "صنف",
            "استورد",
            "من",
            "حاول",
            "إلا",
            "نهاية",
            
            # english
            "if",
            "else",
            "for",
            "while",
            "def",
            "class",
            "import",
            "from",
            "return",
            "try",
            "except"
        ]

        for word in keywords:
            self.rules.append(
                (
                    QRegularExpression(
                        rf"\b{word}\b"
                    ),
                    keyword_format
                )
            )


        # Strings
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))

        self.rules.append(
            (
                QRegularExpression(
                    r'".*?"|\' .*?\''
                ),
                string_format
            )
        )


        # Numbers
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#B5CEA8"))

        self.rules.append(
            (
                QRegularExpression(
                    r"\b[0-9]+\b"
                ),
                number_format
            )
        )


        # Comments
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6A9955"))
        comment_format.setFontItalic(True)

        self.rules.append(
            (
                QRegularExpression(
                    r"#.*"
                ),
                comment_format
            )
        )


        # Built-in functions
        builtin_format = QTextCharFormat()
        builtin_format.setForeground(QColor("#DCDCAA"))

        builtins = [
            "اطبع",
            "طباعة",
            "print",
            "input",
            "len",
            "range"
        ]

        for func in builtins:
            self.rules.append(
                (
                    QRegularExpression(
                        rf"\b{func}\b"
                    ),
                    builtin_format
                )
            )


    def highlightBlock(self, text):

        for pattern, fmt in self.rules:

            iterator = pattern.globalMatch(text)

            while iterator.hasNext():

                match = iterator.next()

                self.setFormat(
                    match.capturedStart(),
                    match.capturedLength(),
                    fmt
                )