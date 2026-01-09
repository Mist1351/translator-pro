import os
import sys
import tempfile
from pathlib import Path

import requests

from .translator_worker import TranslatorWorker

# Импортируем базовые классы для многопоточности в Qt

# ==========================================================================
# НАСТРОЙКА ПОРТАТИВНОСТИ (Portable Mode)
# ==========================================================================
# Мы должны настроить пути ДО импорта библиотеки argostranslate,
# потому что она считывает переменные окружения в момент инициализации.

# 1. Получаем абсолютный путь к папке, где лежит этот скрипт или EXE
if getattr(sys, "frozen", False):
    BASE_DIR: str = os.path.dirname(sys.executable)
else:
    BASE_DIR: str = Path(
        os.path.dirname(os.path.abspath(__file__))
    ).parent.parent.as_posix()

# 2. Формируем путь к папке "translation_data" рядом со скриптом.
# Именно здесь будут храниться гигабайты нейросетевых моделей.
DATA_DIR: str = os.path.join(BASE_DIR, "translation_data")

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
    from argostranslate.package import AvailablePackage, Package
except ImportError:
    raise ImportError(
        "Ошибка: Не установлены библиотеки! Выполните:\npip install torch --index-url https://download.pytorch.org/whl/cpu\npip install pyside6 requests argostranslate"
    )


class TranslatorWorkerOffline(TranslatorWorker):
    def _install_package(self) -> None:
        """
        Установка языковых пакетов.
        """
        self.status.emit("Проверка наличия языков...")

        # 1. Проверяем, есть ли нужный пакет уже на диске.
        # Функция get_installed_packages сама посмотрит в нашу папку DATA_DIR
        installed_packages: list[Package] = (
            argostranslate.package.get_installed_packages()
        )
        is_installed: bool = any(
            pkg.from_code == self.src and pkg.to_code == self.target
            for pkg in installed_packages
        )
        if not is_installed:
            self._download_package()

    def _download_package(self) -> None:
        """
        Скачивание языковых пакетов.
        """
        self.status.emit("Пакет не найден локально. Поиск в сети...")

        # Обновляем индекс (список всех существующих пакетов с сервера)
        argostranslate.package.update_package_index()
        available_packages: list[AvailablePackage] = (
            argostranslate.package.get_available_packages()
        )

        # Ищем нужную пару языков в списке доступных
        pkg_to_install: AvailablePackage | None = next(
            filter(
                lambda x: x.from_code == self.src and x.to_code == self.target,
                available_packages,
            ),
            None,
        )

        if pkg_to_install:
            # Получаем ссылку на zip-файл модели
            download_url: str = pkg_to_install.links[0]
            self._download_process(download_url)
        else:
            # Если такой языковой пары вообще не существует в Argos
            msg: str = "Не удалось найти пакет для этой пары языков."
            self.error.emit(msg)
            self.status.emit(msg)
            raise FileNotFoundError(msg)

    def _download_process(self, download_url: str) -> None:
        """
        Скачивание данных по указанной ссылке.
        """
        self.status.emit(f"Скачивание {self.src}->{self.target} в локальную папку...")
        self.progress_visible.emit(True)

        # Создаем путь к временному файлу в системной папке Temp
        temp_dir: str = tempfile.gettempdir()
        filename: Path = Path(
            os.path.join(temp_dir, f"pkg_{self.src}_{self.target}.argosmodel")
        )

        # --- РУЧНОЕ СКАЧИВАНИЕ (ЧТОБЫ БЫЛ ПРОГРЕСС-БАР) ---
        try:
            # stream=True позволяет качать файл кусками
            # timeout=(5, 10) означает:
            # 5 секунд ждем установки соединения
            # 10 секунд ждем каждый новый кусок данных (chunk) внутри цикла
            response: requests.Response = requests.get(
                download_url,
                stream=True,
                timeout=(5, 10),
            )
            total_content_length: str | None = response.headers.get("content-length")

            if total_content_length is None:
                # Если сервер не сказал размер файла, просто качаем
                with open(filename, "wb") as f:
                    f.write(response.content)
            else:
                # Если размер известен, считаем проценты
                downloaded_length: int = 0
                total_length: int = int(total_content_length)
                with open(filename, "wb") as f:
                    for data in response.iter_content(chunk_size=4096):
                        downloaded_length += len(data)
                        f.write(data)
                        # Математика процента
                        percent = int((downloaded_length / total_length) * 100)
                        self.progress_val.emit(percent)

            self.status.emit("Распаковка и установка...")
            self.progress_visible.emit(False)
            self.progress_val.emit(0)

            # Устанавливаем скачанный файл (он распакуется в DATA_DIR)
            argostranslate.package.install_from_path(filename)

        except requests.exceptions.ReadTimeout:
            raise Exception(
                "Ошибка: Время ожидания скачивания истекло (медленный интернет или сбой сервера)."
            )
        except requests.exceptions.ConnectionError:
            raise Exception("Ошибка: Нет соединения с интернетом.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ошибка скачивания: {e}")

        finally:
            # Обязательно удаляем мусор (временный файл) за собой
            if os.path.exists(filename):
                os.remove(filename)

    def _translate(self) -> str:
        """
        Перевод offline, с использованием нейросети.
        Если нет нужных пакетов, тогда они скачаются автоматически.
        """
        self._install_package()
        self.status.emit("Перевод нейросетью...")
        return argostranslate.translate.translate(self.text, self.src, self.target)
