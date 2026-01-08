import os
import sys
import tempfile

import requests
from PyQt6 import uic
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QProgressBar

# === НАСТРОЙКА ПОРТАТИВНОСТИ (Важно: делать ДО импорта argostranslate) ===
# Получаем путь к папке, где лежит скрипт
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Папка для языков рядом со скриптом
DATA_DIR = os.path.join(BASE_DIR, "translation_data")

# Создаем папку, если нет
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Говорим библиотеке искать/сохранять языки здесь
os.environ["ARGOS_PACKAGES_DIR"] = DATA_DIR
print(f"Путь к базе данных перевода: {DATA_DIR}")
# ==========================================================================

# Импорт библиотек
try:
    import argostranslate.package
    import argostranslate.translate
    from deep_translator import GoogleTranslator
except ImportError:
    print("Ошибка: pip install deep-translator argostranslate requests PyQt6")
    sys.exit(1)


class TranslationWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    status = pyqtSignal(str)
    progress_val = pyqtSignal(int)
    progress_visible = pyqtSignal(bool)

    def __init__(self, text, src_lang, target_lang, mode):
        super().__init__()
        self.text = text
        self.src = src_lang
        self.target = target_lang
        self.mode = mode

    def run(self):
        self.progress_visible.emit(False)
        if not self.text.strip():
            self.finished.emit("")
            return

        try:
            result = ""
            if self.mode == "Online":
                self.status.emit("Онлайн перевод...")
                src = "auto" if self.src == "auto" else self.src
                translator = GoogleTranslator(source=src, target=self.target)
                result = translator.translate(self.text)

            else:  # Offline
                if self.src == "auto":
                    self.error.emit("Офлайн режим: выберите язык источника.")
                    return

                # Проверяем, установлен ли пакет в НАШУ папку (argostranslate сам проверит DATA_DIR)
                self.status.emit("Проверка наличия языков...")

                # Обновляем индекс пакетов только если он пустой или старый (опционально)
                # Но для надежности проверяем установленные
                installed_packages = argostranslate.package.get_installed_packages()
                is_installed = any(
                    pkg.from_code == self.src and pkg.to_code == self.target
                    for pkg in installed_packages
                )

                if not is_installed:
                    self.status.emit("Пакет не найден локально. Поиск в сети...")
                    # Обновляем список доступных пакетов (скачивает index.json в DATA_DIR)
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
                        # Скачивание
                        download_url = pkg_to_install.links[0]
                        self.status.emit(
                            f"Скачивание {self.src}->{self.target} в локальную папку..."
                        )
                        self.progress_visible.emit(True)

                        temp_dir = tempfile.gettempdir()
                        filename = os.path.join(
                            temp_dir, f"pkg_{self.src}_{self.target}.argosmodel"
                        )

                        try:
                            response = requests.get(download_url, stream=True)
                            total_length = response.headers.get("content-length")

                            if total_length is None:
                                with open(filename, "wb") as f:
                                    f.write(response.content)
                            else:
                                dl = 0
                                total_length = int(total_length)
                                with open(filename, "wb") as f:
                                    for data in response.iter_content(chunk_size=4096):
                                        dl += len(data)
                                        f.write(data)
                                        percent = int((dl / total_length) * 100)
                                        self.progress_val.emit(percent)

                            self.status.emit("Распаковка и установка...")
                            self.progress_visible.emit(False)
                            # Установит пакет именно в DATA_DIR
                            argostranslate.package.install_from_path(filename)
                        finally:
                            if os.path.exists(filename):
                                os.remove(filename)
                    else:
                        self.error.emit("Не удалось найти пакет для этой пары языков.")
                        self.status.emit("Не удалось найти пакет для этой пары языков.")
                        return

                self.status.emit("Перевод нейросетью...")
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
            sys.exit("Interface file not found!")

        self.languages = {
            "Автоопределение": "auto",
            "Английский": "en",
            "Русский": "ru",
            "Китайский": "zh",
            "Немецкий": "de",
            "Французский": "fr",
            "Испанский": "es",
        }

        # Переменные для хранения предыдущего состояния (для свапа)
        self.last_src_idx = 0
        self.last_tgt_idx = 1  # Предполагаем, что по умолчанию выбран 2-й элемент

        self.init_ui()
        self.setup_connections()

    def init_ui(self):
        # Заполнение списков
        for name, code in self.languages.items():
            self.comboSource.addItem(name, code)
            if code != "auto":
                self.comboTarget.addItem(name, code)

        # Дефолтные значения
        self.comboSource.setCurrentIndex(0)  # Auto
        self.comboTarget.setCurrentIndex(1)  # Ru (индекс 1, т.к. в Target нет "Auto")

        # Запоминаем начальные индексы
        self.last_src_idx = self.comboSource.currentIndex()
        self.last_tgt_idx = self.comboTarget.currentIndex()

        # ProgressBar
        self.progressBar = QProgressBar()
        self.progressBar.setMaximumWidth(200)
        self.progressBar.setValue(0)
        self.progressBar.setVisible(False)
        self.progressBar.setStyleSheet("""
            QProgressBar { border: 1px solid #555; border-radius: 5px; text-align: center; color: white; }
            QProgressBar::chunk { background-color: #2ecc71; }
        """)
        self.statusbar.addPermanentWidget(self.progressBar)

        # Стили (включая исправление цвета)
        self.setStyleSheet("""
            QMainWindow { background-color: #2b2b2b; }
            QLabel { color: #ffffff; font-size: 14px; font-weight: bold; }
            QTextEdit { 
                background-color: #353535; color: #ffffff; 
                border: 1px solid #555; border-radius: 8px; padding: 10px; font-size: 14px;
            }
            QTextEdit:focus { border: 1px solid #3a86ff; }
            QComboBox { 
                background-color: #404040; color: white; 
                border: 1px solid #555; border-radius: 5px; padding: 5px; min-width: 150px;
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
        # Подключаем отдельные обработчики для каждого комбобокса
        self.comboSource.currentIndexChanged.connect(self.on_source_changed)
        self.comboTarget.currentIndexChanged.connect(self.on_target_changed)

    # === ЛОГИКА ОБМЕНА ЯЗЫКАМИ (SWAP) ===
    def on_source_changed(self, index):
        src_code = self.comboSource.currentData()
        tgt_code = self.comboTarget.currentData()

        # Если выбран не Auto и языки совпали
        if src_code != "auto" and src_code == tgt_code:
            # Блокируем сигналы, чтобы не вызвать зацикливание
            self.comboTarget.blockSignals(True)
            # Ставим в правое окно то, что БЫЛО в левом
            # Но нужно учесть, что в comboTarget нет пункта "auto"
            # Поэтому мы берем код предыдущего Source и ищем его индекс в Target

            # Получаем код языка, который был выбран ДО этого
            prev_src_code = self.comboSource.itemData(self.last_src_idx)

            # Ищем этот предыдущий язык в правом списке
            new_tgt_index = self.comboTarget.findData(prev_src_code)

            if new_tgt_index != -1:
                # Сценарий 1: Обычный обмен (было En->Ru, выбрали Ru, стало Ru->En)
                self.comboTarget.setCurrentIndex(new_tgt_index)
            else:
                # Сценарий 2: Раньше было "Auto". Его нет в правом списке.
                # Чтобы не осталось Ru -> Ru, нужно выбрать что-то другое.

                # Если выбрали Английский, ставим Русский
                if src_code == "en":
                    fallback_index = self.comboTarget.findData("ru")
                else:
                    # В любом другом случае ставим Английский
                    fallback_index = self.comboTarget.findData("en")

                # Если вдруг "en" нет (маловероятно, но для надежности)
                if fallback_index == -1:
                    # Просто берем первый доступный язык, который не равен текущему
                    for i in range(self.comboTarget.count()):
                        if self.comboTarget.itemData(i) != src_code:
                            fallback_index = i
                            break

                self.comboTarget.setCurrentIndex(fallback_index)

            # Обновляем "память" для правого списка, так как мы его насильно изменили
            self.last_tgt_idx = self.comboTarget.currentIndex()

            self.comboTarget.blockSignals(False)

        # Запоминаем текущий выбор как "прошлый" для следующего раза
        self.last_src_idx = index

    def on_target_changed(self, index):
        src_code = self.comboSource.currentData()
        tgt_code = self.comboTarget.currentData()

        if src_code != "auto" and src_code == tgt_code:
            self.comboSource.blockSignals(True)

            prev_tgt_code = self.comboTarget.itemData(self.last_tgt_idx)
            new_src_index = self.comboSource.findData(prev_tgt_code)

            if new_src_index != -1:
                self.comboSource.setCurrentIndex(new_src_index)
                self.last_src_idx = new_src_index

            self.comboSource.blockSignals(False)

        self.last_tgt_idx = index

    # ====================================

    def start_translation(self):
        text = self.TextInput.toPlainText()
        src_code = self.comboSource.currentData()
        tgt_code = self.comboTarget.currentData()
        mode = "Online" if "Online" in self.comboMode.currentText() else "Offline"

        if not text:
            self.statusbar.showMessage("Введите текст")
            return

        self.btnTranslate.setEnabled(False)
        self.btnTranslate.setText("...")

        self.worker = TranslationWorker(text, src_code, tgt_code, mode)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.status.connect(self.statusbar.showMessage)
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
