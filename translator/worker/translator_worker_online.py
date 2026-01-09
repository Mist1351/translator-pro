from .translator_worker import TranslatorWorker

try:
    from deep_translator import GoogleTranslator
except ImportError:
    raise ImportError(
        "Ошибка: Не установлены библиотеки! Выполните:\npip install pyside6 deep-translator"
    )


class TranslatorWorkerOnline(TranslatorWorker):
    def _translate(self) -> str:
        """
        Перевод online, с использованием GoogleTranslator.
        """
        self.status.emit("Онлайн перевод...")

        # Используем deep_translator для запроса к Google API
        translator = GoogleTranslator(source=self.src, target=self.target)
        return translator.translate(self.text)
