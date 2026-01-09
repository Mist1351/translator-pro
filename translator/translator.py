from abc import ABC, abstractmethod

from .worker import TranslatorWorker


class Translator(ABC):
    def __init__(self, name: str, languages: dict[str, str]):
        self.source_index: int = 0
        self.target_index: int = 0
        self.languages: dict[str, str] = languages
        self.name: str = name

    @abstractmethod
    def run_translator_worker(
        self,
        text: str,
        src_lang: str,
        target_lang: str,
    ) -> TranslatorWorker:
        pass
