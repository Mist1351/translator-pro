from PySide6.QtCore import QThread, Signal

try:
    from deep_translator import GoogleTranslator
except ImportError:
    raise ImportError(
        "Ошибка: Не установлены библиотеки! Выполните:\npip install pyside6 deep-translator"
    )


class TranslatorWorker(QThread):
    """
    Класс-рабочий (Worker), который выполняется в отдельном потоке.

    Зачем это нужно:
    Если выполнять перевод в основном потоке,
    интерфейс программы "зависнет" и перестанет отвечать на клики.
    QThread позволяет выполнять тяжелые задачи фоном.
    """

    # Сигналы (Signals) — это способ связи фонового потока с главным окном.
    finished = Signal(str)  # Отправляет готовый текст перевода
    error = Signal(str)  # Отправляет текст ошибки, если она случилась
    status = Signal(str)  # Отправляет статус (например, "Скачивание...")
    progress_val = Signal(int)  # Отправляет процент загрузки (0-100)
    progress_visible = Signal(bool)  # Говорит, нужно ли показывать полосу загрузки

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
        """
        Перевод online, с использованием GoogleTranslator.
        """
        self.status.emit("Онлайн перевод...")

        # Используем deep_translator для запроса к Google API
        translator = GoogleTranslator(source=self.src, target=self.target)
        return translator.translate(self.text)

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
