from PySide6.QtGui import (
    QSyntaxHighlighter,
    QTextCharFormat,
    QColor,
    QFont,
)

from PySide6.QtCore import QRegularExpression


class ArabicPyHighlighter(QSyntaxHighlighter):

    def __init__(self, document):
        super().__init__(document)

        self.rules = []


        # ==========================
        # Keywords
        # ==========================

        keyword_format = QTextCharFormat()

        keyword_format.setForeground(
            QColor("#007acc")
        )

        keyword_format.setFontWeight(
            QFont.Bold
        )


        keywords = [
            "دالة",
            "ارجع",
            "اطبع",
            "اذا",
            "والا",
            "بينما",
            "كرر",
            "مرات",
            "صح",
            "خطأ",
        ]


        for word in keywords:

            self.rules.append(
                (
                    QRegularExpression(word),
                    keyword_format
                )
            )



        # ==========================
        # Strings
        # ==========================

        string_format = QTextCharFormat()

        string_format.setForeground(
            QColor("#008000")
        )


        self.rules.append(
            (
                QRegularExpression(
                    r'"[^"]*"'
                ),
                string_format
            )
        )



        # ==========================
        # Numbers
        # ==========================

        number_format = QTextCharFormat()

        number_format.setForeground(
            QColor("#b8860b")
        )


        self.rules.append(
            (
                QRegularExpression(
                    r"\b[0-9]+\b"
                ),
                number_format
            )
        )



        # ==========================
        # Comments
        # ==========================

        comment_format = QTextCharFormat()

        comment_format.setForeground(
            QColor("#808080")
        )


        self.rules.append(
            (
                QRegularExpression(
                    r"#.*"
                ),
                comment_format
            )
        )



    # ==========================
    # Apply highlighting
    # ==========================

    def highlightBlock(self, text):

        for pattern, format in self.rules:

            matches = pattern.globalMatch(text)


            while matches.hasNext():

                match = matches.next()


                self.setFormat(
                    match.capturedStart(),
                    match.capturedLength(),
                    format
                )