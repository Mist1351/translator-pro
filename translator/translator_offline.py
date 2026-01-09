from . import Translator
from .worker import (
    TranslatorWorker,
    TranslatorWorkerOffline,
)


class TranslatorOffline(Translator):
    def __init__(self):
        super().__init__(
            name="Offline",
            languages={
                "Английский": "en",
                "Русский": "ru",
            },
        )

    def run_translator_worker(
        self,
        text: str,
        src_lang: str,
        target_lang: str,
    ) -> TranslatorWorker:
        return TranslatorWorkerOffline(text, src_lang, target_lang)
