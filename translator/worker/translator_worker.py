# Библиотека для выполнения HTTP-запросов (нужна для скачивания моделей)
# Импортируем базовые классы для многопоточности в Qt
from PyQt6.QtCore import QThread, pyqtSignal


class TranslatorWorker(QThread):
    """
    Класс-рабочий (Worker), который выполняется в отдельном потоке.

    Зачем это нужно:
    Если выполнять перевод в основном потоке,
    интерфейс программы "зависнет" и перестанет отвечать на клики.
    QThread позволяет выполнять тяжелые задачи фоном.
    """

    # Сигналы (Signals) — это способ связи фонового потока с главным окном.
    finished = pyqtSignal(str)  # Отправляет готовый текст перевода
    error = pyqtSignal(str)  # Отправляет текст ошибки, если она случилась
    status = pyqtSignal(str)  # Отправляет статус (например, "Скачивание...")
    progress_val = pyqtSignal(int)  # Отправляет процент загрузки (0-100)
    progress_visible = pyqtSignal(bool)  # Говорит, нужно ли показывать полосу загрузки

    def __init__(
        self,
        text: str,
        src_lang: str,
        target_lang: str,
    ):
        """
        Инициализация потока. Принимает параметры для перевода.
        """
        super().__init__()
        self.text = text
        self.src = src_lang
        self.target = target_lang

    def _translate(self) -> str:
        return ""

    def run(self) -> None:
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
            result: str = self._translate()
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
