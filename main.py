import sys

from PyQt6.QtWidgets import QApplication

from app import TranslatorApp

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        window = TranslatorApp()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(e)
        sys.exit(1)
