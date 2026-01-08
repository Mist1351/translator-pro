import os
import sys
import tempfile
from pathlib import Path

import requests
from PyQt6.QtCore import QThread, pyqtSignal

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
                        filename = Path(
                            os.path.join(
                                temp_dir, f"pkg_{self.src}_{self.target}.argosmodel"
                            )
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
