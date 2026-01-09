from . import Translator
from .worker import (
    TranslatorWorker,
    TranslatorWorkerOnline,
)


class TranslatorOnline(Translator):
    def __init__(self):
        super().__init__(
            name="Online",
            languages={
                "Автоопределение": "auto",
                "Английский": "en",
                "Русский": "ru",
                "Китайский": "zh",
                "Немецкий": "de",
                "Французский": "fr",
                "Испанский": "es",
            },
        )

    def run_translator_worker(
        self,
        text: str,
        src_lang: str,
        target_lang: str,
    ) -> TranslatorWorker:
        return TranslatorWorkerOnline(text, src_lang, target_lang)
