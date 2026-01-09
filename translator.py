from translator_worker import TranslatorWorker


class Translator:
    def __init__(self):
        self.source_index: int = 0
        self.target_index: int = 0
        self.languages: dict[str, str] = {
            "Автоопределение": "auto",
            "Английский": "en",
            "Русский": "ru",
            "Китайский": "zh",
            "Немецкий": "de",
            "Французский": "fr",
            "Испанский": "es",
        }
        self.name: str = "Online"

    def run_translator_worker(
        self,
        text: str,
        src_lang: str,
        target_lang: str,
    ) -> TranslatorWorker:
        return TranslatorWorker(text, src_lang, target_lang)
