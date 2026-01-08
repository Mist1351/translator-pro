import sys

from PyQt6.QtWidgets import QApplication

from translator_app import TranslatorApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TranslatorApp()
    window.show()
    sys.exit(app.exec())
