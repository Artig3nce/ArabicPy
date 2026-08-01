"""Windows executable entry point for الباء."""

from PySide6.QtWidgets import QApplication

from arabicpy.ide import ArabicPyIDE


def main():
    app = QApplication([])
    window = ArabicPyIDE()
    window.show_fitted()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
