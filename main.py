import os
import sys
import tempfile  # Нужен для создания временного файла

import requests  # Нужен для скачивания с прогрессом
from PyQt6 import uic
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QProgressBar

# Импорт библиотек перевода
try:
    import argostranslate.package
    import argostranslate.translate
    from deep_translator import GoogleTranslator
except ImportError:
    print("Ошибка: Установите библиотеки!")
    sys.exit(1)


# --- Поток с поддержкой прогресса скачивания ---
class TranslationWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    status = pyqtSignal(str)
    progress_val = pyqtSignal(int)  # Сигнал для прогресс-бара (0-100)
    progress_visible = pyqtSignal(bool)  # Показать/Скрыть бар

    def __init__(self, text, src_lang, target_lang, mode):
        super().__init__()
        self.text = text
        self.src = src_lang
        self.target = target_lang
        self.mode = mode

    def run(self):
        self.progress_visible.emit(False)  # Скрываем бар в начале
        if not self.text.strip():
            self.finished.emit("")
            return

        try:
            result = ""
            if self.mode == "Online":
                self.status.emit("Выполняется онлайн перевод...")
                src = "auto" if self.src == "auto" else self.src
                translator = GoogleTranslator(source=src, target=self.target)
                result = translator.translate(self.text)

            else:  # Offline Mode
                if self.src == "auto":
                    self.error.emit("Офлайн режим: выберите язык источника.")
                    return

                # Проверка наличия пакета
                self.status.emit("Проверка пакетов...")
                installed_packages = argostranslate.package.get_installed_packages()
                is_installed = any(
                    pkg.from_code == self.src and pkg.to_code == self.target
                    for pkg in installed_packages
                )

                if not is_installed:
                    self.status.emit(f"Поиск пакета {self.src}->{self.target}...")
                    argostranslate.package.update_package_index()
                    available_packages = argostranslate.package.get_available_packages()

                    pkg_to_install = next(
                        filter(
                            lambda x: x.from_code == self.src
                            and x.to_code == self.target,
                            available_packages,
                        ),
                        None,
                    )

                    if pkg_to_install:
                        # --- РУЧНОЕ СКАЧИВАНИЕ С ПРОГРЕССОМ ---
                        download_url = pkg_to_install.links[0]
                        self.status.emit("Скачивание модели...")
                        self.progress_visible.emit(True)  # Показываем бар

                        # Создаем временный файл
                        temp_dir = tempfile.gettempdir()
                        filename = os.path.join(
                            temp_dir, f"argos_{self.src}_{self.target}.argosmodel"
                        )

                        response = requests.get(download_url, stream=True)
                        total_length = response.headers.get("content-length")

                        if total_length is None:  # Если сервер не отдал размер
                            with open(filename, "wb") as f:
                                f.write(response.content)
                        else:
                            dl = 0
                            total_length = int(total_length)
                            with open(filename, "wb") as f:
                                for data in response.iter_content(chunk_size=4096):
                                    dl += len(data)
                                    f.write(data)
                                    # Вычисляем процент
                                    percent = int((dl / total_length) * 100)
                                    self.progress_val.emit(percent)

                        self.status.emit("Установка модели...")
                        self.progress_visible.emit(
                            False
                        )  # Скрываем бар, идет установка
                        argostranslate.package.install_from_path(filename)

                        # Удаляем временный файл
                        try:
                            os.remove(filename)
                        except:
                            pass
                    else:
                        self.error.emit("Пакет языка не найден.")
                        return

                self.status.emit("Перевод...")
                result = argostranslate.translate.translate(
                    self.text, self.src, self.target
                )

            self.finished.emit(result)
            self.status.emit("Готово")

        except Exception as e:
            self.error.emit(str(e))
            self.status.emit("Ошибка")
        finally:
            self.progress_visible.emit(False)


class TranslatorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        if os.path.exists("interface.ui"):
            uic.loadUi("interface.ui", self)
        else:
            sys.exit("Файл interface.ui не найден!")

        self.languages = {
            "Автоопределение": "auto",
            "Английский": "en",
            "Русский": "ru",
            "Китайский": "zh",
            "Немецкий": "de",
            "Французский": "fr",
            "Испанский": "es",
        }
        self.init_ui()
        self.setup_connections()

    def init_ui(self):
        # ... (Код заполнения comboSource/Target тот же, что был) ...
        for name, code in self.languages.items():
            self.comboSource.addItem(name, code)
            if code != "auto":
                self.comboTarget.addItem(name, code)
        self.comboSource.setCurrentIndex(0)
        self.comboTarget.setCurrentIndex(1)

        # === ДОБАВЛЯЕМ PROGRESS BAR В STATUS BAR ===
        self.progressBar = QProgressBar()
        self.progressBar.setMaximumWidth(200)  # Ширина бара
        self.progressBar.setValue(0)
        self.progressBar.setVisible(False)  # Скрыт по умолчанию
        # Стиль бара (зеленый)
        self.progressBar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555;
                border-radius: 5px;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #2ecc71; 
                width: 10px;
            }
        """)
        # Добавляем виджет справа в статус бар
        self.statusbar.addPermanentWidget(self.progressBar)

        # Ваши стили (добавьте сюда исправленные стили из прошлого ответа)
        self.setStyleSheet("""
            QMainWindow { background-color: #2b2b2b; }
            QLabel { color: #ffffff; font-size: 14px; font-weight: bold; }
            QTextEdit { 
                background-color: #353535; color: #ffffff; border: 1px solid #555; 
                border-radius: 8px; padding: 10px; font-size: 14px;
            }
            QTextEdit:focus { border: 1px solid #3a86ff; }
            QComboBox { 
                background-color: #404040; color: white; border: 1px solid #555;
                border-radius: 5px; padding: 5px; min-width: 150px;
            }
            QComboBox QAbstractItemView {
                background-color: #404040; color: white; selection-background-color: #3a86ff;
            }
            QPushButton {
                background-color: #3a86ff; color: white; border-radius: 8px; font-size: 16px; font-weight: bold;
            }
            QStatusBar { color: #aaaaaa; }
            QMessageBox { background-color: #2b2b2b; }
            QMessageBox QLabel { color: white; }
            QMessageBox QPushButton { background-color: #404040; color: white; padding: 5px 15px; }
        """)

    def setup_connections(self):
        self.btnTranslate.clicked.connect(self.start_translation)
        self.comboSource.currentIndexChanged.connect(self.check_language_conflict)
        self.comboTarget.currentIndexChanged.connect(self.check_language_conflict)

    def check_language_conflict(self):
        # ... (Старый код) ...
        pass

    def start_translation(self):
        text = self.TextInput.toPlainText()
        src_code = self.comboSource.currentData()
        tgt_code = self.comboTarget.currentData()
        mode = "Online" if "Online" in self.comboMode.currentText() else "Offline"

        if not text:
            self.statusbar.showMessage("Нет текста")
            return

        self.btnTranslate.setEnabled(False)
        self.btnTranslate.setText("...")

        self.worker = TranslationWorker(text, src_code, tgt_code, mode)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.status.connect(self.statusbar.showMessage)

        # Подключаем сигналы прогресса
        self.worker.progress_val.connect(self.progressBar.setValue)
        self.worker.progress_visible.connect(self.progressBar.setVisible)

        self.worker.start()

    def on_finished(self, result):
        self.TextOutput.setPlainText(result)
        self.reset_ui()

    def on_error(self, err):
        QMessageBox.warning(self, "Ошибка", str(err))
        self.reset_ui()

    def reset_ui(self):
        self.btnTranslate.setEnabled(True)
        self.btnTranslate.setText("ПЕРЕВЕСТИ")
        self.progressBar.setVisible(False)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TranslatorApp()
    window.show()
    sys.exit(app.exec())
