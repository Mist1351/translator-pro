import os
import sys
import tempfile
from pathlib import Path

# Библиотека для выполнения HTTP-запросов (нужна для скачивания моделей)
import requests

# Импортируем базовые классы для многопоточности в Qt
from PyQt6.QtCore import QThread, pyqtSignal

# ==========================================================================
# НАСТРОЙКА ПОРТАТИВНОСТИ (Portable Mode)
# ==========================================================================
# Мы должны настроить пути ДО импорта библиотеки argostranslate,
# потому что она считывает переменные окружения в момент инициализации.

# 1. Получаем абсолютный путь к папке, где лежит этот скрипт или EXE
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Формируем путь к папке "translation_data" рядом со скриптом.
# Именно здесь будут храниться гигабайты нейросетевых моделей.
DATA_DIR = os.path.join(BASE_DIR, "translation_data")

# 3. Если папки нет — создаем её.
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# 4. Устанавливаем переменную окружения.
# Теперь argostranslate будет думать, что это системная папка для данных.
os.environ["ARGOS_PACKAGES_DIR"] = DATA_DIR
print(f"Путь к базе данных перевода: {DATA_DIR}")

# ==========================================================================

# Импорт библиотек перевода (оборачиваем в try-except для красивой ошибки)
try:
    import argostranslate.package
    import argostranslate.translate
    from deep_translator import GoogleTranslator
except ImportError:
    print(
        "Ошибка: Не установлены библиотеки! Выполните: pip install deep-translator argostranslate requests PyQt6"
    )
    sys.exit(1)


class TranslationWorker(QThread):
    """
    Класс-рабочий (Worker), который выполняется в отдельном потоке.

    Зачем это нужно:
    Если выполнять перевод (особенно скачивание файла на 100 Мб) в основном потоке,
    интерфейс программы "зависнет" и перестанет отвечать на клики.
    QThread позволяет выполнять тяжелые задачи фоном.
    """

    # Сигналы (Signals) — это способ связи фонового потока с главным окном.
    finished = pyqtSignal(str)  # Отправляет готовый текст перевода
    error = pyqtSignal(str)  # Отправляет текст ошибки, если она случилась
    status = pyqtSignal(str)  # Отправляет статус (например, "Скачивание...")
    progress_val = pyqtSignal(int)  # Отправляет процент загрузки (0-100)
    progress_visible = pyqtSignal(bool)  # Говорит, нужно ли показывать полосу загрузки

    def __init__(self, text, src_lang, target_lang, mode):
        """
        Инициализация потока. Принимает параметры для перевода.
        """
        super().__init__()
        self.text = text
        self.src = src_lang
        self.target = target_lang
        self.mode = mode

    def run(self):
        """
        Основной метод потока. Запускается автоматически при вызове .start().
        Здесь происходит вся "тяжелая" логика.
        """
        # Скрываем прогресс-бар в начале работы
        self.progress_visible.emit(False)

        # Проверка на пустой текст
        if not self.text.strip():
            self.finished.emit("")
            return

        try:
            result = ""

            # === РЕЖИМ 1: ОНЛАЙН ПЕРЕВОД ===
            if self.mode == "Online":
                self.status.emit("Онлайн перевод...")

                # Google понимает 'auto', передаем как есть
                src = "auto" if self.src == "auto" else self.src

                # Используем deep_translator для запроса к Google API
                translator = GoogleTranslator(source=src, target=self.target)
                result = translator.translate(self.text)

            # === РЕЖИМ 2: ОФФЛАЙН ПЕРЕВОД (Argos Translate) ===
            else:
                # Оффлайн движок пока не умеет определять язык сам
                if self.src == "auto":
                    self.error.emit("Офлайн режим: выберите язык источника.")
                    return

                self.status.emit("Проверка наличия языков...")

                # 1. Проверяем, есть ли нужный пакет уже на диске.
                # Функция get_installed_packages сама посмотрит в нашу папку DATA_DIR
                installed_packages = argostranslate.package.get_installed_packages()
                is_installed = any(
                    pkg.from_code == self.src and pkg.to_code == self.target
                    for pkg in installed_packages
                )

                # 2. Если пакета нет — начинаем процедуру скачивания
                if not is_installed:
                    self.status.emit("Пакет не найден локально. Поиск в сети...")

                    # Обновляем индекс (список всех существующих пакетов с сервера)
                    argostranslate.package.update_package_index()
                    available_packages = argostranslate.package.get_available_packages()

                    # Ищем нужную пару языков в списке доступных
                    pkg_to_install = next(
                        filter(
                            lambda x: x.from_code == self.src
                            and x.to_code == self.target,
                            available_packages,
                        ),
                        None,
                    )

                    if pkg_to_install:
                        # Получаем ссылку на zip-файл модели
                        download_url = pkg_to_install.links[0]
                        self.status.emit(
                            f"Скачивание {self.src}->{self.target} в локальную папку..."
                        )
                        self.progress_visible.emit(True)

                        # Создаем путь к временному файлу в системной папке Temp
                        temp_dir = tempfile.gettempdir()
                        filename = Path(
                            os.path.join(
                                temp_dir, f"pkg_{self.src}_{self.target}.argosmodel"
                            )
                        )

                        # --- РУЧНОЕ СКАЧИВАНИЕ (ЧТОБЫ БЫЛ ПРОГРЕСС-БАР) ---
                        try:
                            # stream=True позволяет качать файл кусками
                            response = requests.get(download_url, stream=True)
                            total_length = response.headers.get("content-length")

                            if total_length is None:
                                # Если сервер не сказал размер файла, просто качаем
                                with open(filename, "wb") as f:
                                    f.write(response.content)
                            else:
                                # Если размер известен, считаем проценты
                                dl = 0
                                total_length = int(total_length)
                                with open(filename, "wb") as f:
                                    for data in response.iter_content(chunk_size=4096):
                                        dl += len(data)
                                        f.write(data)
                                        # Математика процента
                                        percent = int((dl / total_length) * 100)
                                        self.progress_val.emit(percent)

                            self.status.emit("Распаковка и установка...")
                            self.progress_visible.emit(False)

                            # Устанавливаем скачанный файл (он распакуется в DATA_DIR)
                            argostranslate.package.install_from_path(filename)

                        finally:
                            # Обязательно удаляем мусор (временный файл) за собой
                            if os.path.exists(filename):
                                os.remove(filename)
                    else:
                        # Если такой языковой пары вообще не существует в Argos
                        msg = "Не удалось найти пакет для этой пары языков."
                        self.error.emit(msg)
                        self.status.emit(msg)
                        return

                # 3. Сам процесс перевода (нейросеть)
                self.status.emit("Перевод нейросетью...")
                result = argostranslate.translate.translate(
                    self.text, self.src, self.target
                )

            # Отправляем результат в GUI
            self.finished.emit(result)
            self.status.emit("Готово")

        except Exception as e:
            # Ловим любые ошибки (нет интернета, сбой диска и т.д.)
            self.error.emit(str(e))
            self.status.emit("Ошибка")
        finally:
            # В любом случае скрываем прогресс-бар в конце
            self.progress_visible.emit(False)
