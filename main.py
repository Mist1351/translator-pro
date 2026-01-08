import os
import sys

from PyQt6 import uic
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox

# Импорт библиотек перевода
try:
    import argostranslate.package
    import argostranslate.translate
    from deep_translator import GoogleTranslator
except ImportError:
    print("Ошибка: Установите библиотеки: pip install deep-translator argostranslate")
    sys.exit(1)


# --- Поток для перевода (чтобы интерфейс не вис) ---
class TranslationWorker(QThread):
    finished = pyqtSignal(str)  # Сигнал успешного перевода
    error = pyqtSignal(str)  # Сигнал ошибки
    status = pyqtSignal(str)  # Сигнал для статус-бара

    def __init__(self, text, src_lang, target_lang, mode):
        super().__init__()
        self.text = text
        self.src = src_lang
        self.target = target_lang
        self.mode = mode

    def run(self):
        if not self.text.strip():
            self.finished.emit("")
            return

        try:
            result = ""
            if self.mode == "Online":
                self.status.emit("Выполняется онлайн перевод...")
                # 'auto' для автоопределения
                src = "auto" if self.src == "auto" else self.src
                translator = GoogleTranslator(source=src, target=self.target)
                result = translator.translate(self.text)

            else:  # Offline Mode
                self.status.emit("Подготовка офлайн движка...")

                if self.src == "auto":
                    self.error.emit(
                        "Офлайн режим пока не поддерживает автоопределение (выберите язык)."
                    )
                    return

                # Проверка и установка пакетов (упрощенная логика)
                # В реальном приложении лучше проверять наличие пакетов при старте
                self.status.emit(f"Проверка пакетов {self.src} -> {self.target}...")

                # Логика Argos Translate
                argostranslate.package.update_package_index()
                available_packages = argostranslate.package.get_available_packages()
                package_to_install = next(
                    filter(
                        lambda x: x.from_code == self.src and x.to_code == self.target,
                        available_packages,
                    ),
                    None,
                )

                if package_to_install:
                    if not package_to_install.is_installed:
                        self.status.emit(
                            "Скачивание нейросетевой модели (это может занять время)..."
                        )
                        argostranslate.package.install_from_path(
                            package_to_install.download()
                        )

                self.status.emit("Перевод нейросетью...")
                result = argostranslate.translate.translate(
                    self.text, self.src, self.target
                )

            self.finished.emit(result)
            self.status.emit("Готово")

        except Exception as e:
            self.error.emit(str(e))
            self.status.emit("Ошибка перевода")


# --- Основное окно ---
class TranslatorApp(QMainWindow):
    def __init__(self):
        super().__init__()

        # Загрузка интерфейса из файла
        if os.path.exists("interface.ui"):
            uic.loadUi("interface.ui", self)
        else:
            QMessageBox.critical(self, "Ошибка", "Файл interface.ui не найден!")
            sys.exit()

        # Словари языков
        self.languages = {
            "Автоопределение": "auto",
            "Английский": "en",
            "Русский": "ru",
            "Китайский": "zh",  # Для Google (zh-CN), для Argos (zh)
            "Немецкий": "de",
            "Французский": "fr",
            "Испанский": "es",
        }

        self.init_ui()
        self.setup_connections()

    def init_ui(self):
        # Заполнение Combo Boxes
        for name, code in self.languages.items():
            self.comboSource.addItem(name, code)
            if code != "auto":
                self.comboTarget.addItem(name, code)

        # Установка значений по умолчанию
        self.comboSource.setCurrentIndex(0)  # Авто
        self.comboTarget.setCurrentIndex(1)  # Русский (или 2-й в списке)

        # Стилизация (Dark Theme)
        self.setStyleSheet("""
            QMainWindow { background-color: #2b2b2b; }
            QLabel { color: #ffffff; font-size: 14px; font-weight: bold; }
            QTextEdit { 
                background-color: #353535; 
                color: #ffffff; 
                border: 1px solid #555; 
                border-radius: 8px; 
                padding: 10px; 
                font-size: 14px;
            }
            QTextEdit:focus { border: 1px solid #3a86ff; }
            QComboBox { 
                background-color: #404040; 
                color: white; 
                border-radius: 5px; 
                padding: 5px; 
                min-width: 150px;
            }
            QPushButton {
                background-color: #3a86ff;
                color: white;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #266dd3; }
            QPushButton:pressed { background-color: #1b4b91; }
            QStatusBar { color: #aaaaaa; }
        """)

    def setup_connections(self):
        self.btnTranslate.clicked.connect(self.start_translation)

        # Логика: Нельзя выбрать один язык в обоих полях
        self.comboSource.currentIndexChanged.connect(self.check_language_conflict)
        self.comboTarget.currentIndexChanged.connect(self.check_language_conflict)

    def check_language_conflict(self):
        src_code = self.comboSource.currentData()
        tgt_code = self.comboTarget.currentData()

        if src_code == "auto":
            return

        if src_code == tgt_code:
            # Если выбрали одинаковый, меняем целевой на следующий доступный
            current_index = self.comboTarget.currentIndex()
            next_index = (current_index + 1) % self.comboTarget.count()
            self.comboTarget.setCurrentIndex(next_index)

    def start_translation(self):
        text = self.TextInput.toPlainText()
        src_code = self.comboSource.currentData()
        tgt_code = self.comboTarget.currentData()
        mode_text = self.comboMode.currentText()

        mode = "Online" if "Online" in mode_text else "Offline"

        if not text:
            self.statusbar.showMessage("Введите текст для перевода")
            return

        # Блокируем интерфейс на время работы
        self.btnTranslate.setEnabled(False)
        self.btnTranslate.setText("ПЕРЕВОД...")

        # Запускаем поток
        self.worker = TranslationWorker(text, src_code, tgt_code, mode)
        self.worker.finished.connect(self.on_translation_finished)
        self.worker.error.connect(self.on_translation_error)
        self.worker.status.connect(self.update_status)
        self.worker.start()

    def on_translation_finished(self, result):
        self.TextOutput.setPlainText(result)
        self.reset_ui()

    def on_translation_error(self, err_msg):
        QMessageBox.warning(self, "Ошибка", f"Не удалось перевести:\n{err_msg}")
        self.reset_ui()

    def update_status(self, msg):
        self.statusbar.showMessage(msg)

    def reset_ui(self):
        self.btnTranslate.setEnabled(True)
        self.btnTranslate.setText("ПЕРЕВЕСТИ")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TranslatorApp()
    window.show()
    sys.exit(app.exec())
