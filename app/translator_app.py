import os
import sys

# Импортируем модуль загрузки интерфейса напрямую, чтобы не было проблем с линтером
from PyQt6 import uic
from PyQt6.QtWidgets import (
    QComboBox,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QTextEdit,
)

from translator import (
    Translator,
    TranslatorOffline,
    TranslatorOnline,
)

# Импортируем наш класс рабочего потока
from translator.worker import TranslatorWorker


def get_resource_path(relative_path: str) -> str:
    """
    Возвращает путь к внутренним ресурсам
    """
    if getattr(sys, "frozen", False):
        # В EXE ресурсы лежат во временной папке sys._MEIPASS
        base_path = sys._MEIPASS  # type: ignore
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


class TranslatorApp(QMainWindow):
    """
    Главный класс приложения-переводчика.
    Наследуется от QMainWindow.
    Отвечает за отображение интерфейса, обработку нажатий и запуск потоков перевода.
    """

    # Аннотация типов для виджетов из interface.ui (нужно для подсказок в IDE)
    TextInput: QTextEdit
    TextOutput: QTextEdit
    comboSource: QComboBox
    comboTarget: QComboBox
    comboMode: QComboBox
    btnTranslate: QPushButton
    statusbar: QStatusBar
    progressBar: QProgressBar

    def __init__(self):
        """
        Конструктор класса.
        Выполняет загрузку UI из файла, инициализацию данных и настройку связей.
        """
        super().__init__()

        self.translators: list[Translator] = [
            TranslatorOnline(),
            TranslatorOffline(),
        ]

        # Вызываем методы настройки
        self.init_ui()
        self.setup_connections()

    def get_current_translator(self) -> Translator:
        index: int = self.comboMode.currentData()
        return self.translators[index]

    def _load_interface(self) -> None:
        """
        Загрузка интерфейса из файла.
        """
        # Ищем interface.ui через get_resource_path
        ui_path: str = get_resource_path("interface.ui")

        # Проверяем наличие файла разметки и загружаем в случае успеха
        if os.path.exists(ui_path):
            uic.load_ui.loadUi(ui_path, self)
        else:
            raise FileExistsError(f"Interface file not found at: {ui_path}")

    def _fillup_combo_boxes(self) -> None:
        """
        Настройка выпадающих списков языков.
        """
        translator: Translator = self.get_current_translator()

        self.comboSource.blockSignals(True)
        self.comboTarget.blockSignals(True)

        # Заполнение списков языками из словаря
        self.comboSource.clear()
        self.comboTarget.clear()
        for name, code in translator.languages.items():
            self.comboSource.addItem(name, code)
            # В целевой язык (Target) нельзя добавить "Автоопределение"
            if code != "auto":
                self.comboTarget.addItem(name, code)

        # Выбор начальных языков
        self.comboSource.setCurrentIndex(translator.source_index)
        self.comboTarget.setCurrentIndex(translator.target_index)

        self.comboTarget.blockSignals(False)
        self.comboSource.blockSignals(False)

    def init_ui(self) -> None:
        """
        Настройка внешнего вида приложения.
        Заполняет выпадающие списки, настраивает прогресс-бар и применяет CSS-стили.
        """
        self._load_interface()

        # Заполнение списка режимов
        for index, translator in enumerate(self.translators):
            self.comboMode.addItem(translator.name, index)
        self.comboMode.setCurrentIndex(0)

        self._fillup_combo_boxes()
        self.statusbar.addPermanentWidget(self.progressBar)

    def setup_connections(self) -> None:
        """
        Подключение сигналов к слотам (обработчикам событий).
        """
        self.btnTranslate.clicked.connect(self.start_translation)
        # Подключаем сигналы изменения индекса в комбобоксах
        self.comboSource.currentIndexChanged.connect(self.on_source_changed)
        self.comboTarget.currentIndexChanged.connect(self.on_target_changed)
        self.comboMode.currentIndexChanged.connect(self.on_mode_changed)

    def _resolve_lang_conflict(
        self,
        from_combo_box: QComboBox,
        to_combo_box: QComboBox,
    ) -> None:
        from_code: str = from_combo_box.currentData()
        to_code: str = to_combo_box.currentData()
        translator: Translator = self.get_current_translator()

        # Языки разные, нечего делать
        if from_code != to_code:
            return

        # Блокируем сигналы правого списка, чтобы избежать рекурсии
        to_combo_box.blockSignals(True)

        last_from_idx: int = (
            translator.source_index
            if from_combo_box == self.comboSource
            else translator.target_index
        )

        # Логика обмена: пытаемся поставить справа тот язык, который был слева
        prev_from_code: str = from_combo_box.itemData(last_from_idx)
        new_to_index: int = -1
        if prev_from_code != from_code:
            new_to_index: int = to_combo_box.findData(prev_from_code)

        # Если предыдущий язык отсутствует в списке
        if new_to_index == -1:
            # Поиск первого отличающегося языка
            new_to_index = next(
                (
                    i
                    for i in range(to_combo_box.count())
                    if to_combo_box.itemData(i) != from_code
                ),
                0,
            )
        to_combo_box.setCurrentIndex(new_to_index)

        # Обновляем сохраненный индекс правого списка
        if to_combo_box == self.comboSource:
            translator.source_index = new_to_index
        else:
            translator.target_index = new_to_index

        # Разблокируем сигналы
        to_combo_box.blockSignals(False)

    def on_source_changed(self, index: int) -> None:
        """
        Слот, вызываемый при изменении языка источника (левый список).
        """
        self._resolve_lang_conflict(self.comboSource, self.comboTarget)
        # Запоминаем текущий выбор
        self.get_current_translator().source_index = index

    def on_target_changed(self, index: int) -> None:
        """
        Слот, вызываемый при изменении целевого языка (правый список).
        """
        self._resolve_lang_conflict(self.comboTarget, self.comboSource)
        # Запоминаем текущий выбор
        self.get_current_translator().target_index = index

    def on_mode_changed(self, index: int) -> None:
        """
        Слот, вызываемый при изменении режима перевода.
        """
        self._fillup_combo_boxes()
        self._resolve_lang_conflict(self.comboSource, self.comboTarget)

    def start_translation(self) -> None:
        """
        Метод запуска процесса перевода.
        Считывает данные, блокирует интерфейс и запускает рабочий поток.
        """
        text = self.TextInput.toPlainText()
        src_code: str = self.comboSource.currentData()
        tgt_code: str = self.comboTarget.currentData()
        translator: Translator = self.get_current_translator()

        # text пустой, нечего переводить
        if not text:
            self.statusbar.showMessage("Введите текст")
            return

        # Визуальная индикация работы
        self.btnTranslate.setEnabled(False)
        self.btnTranslate.setText("...")

        # Создаем экземпляр потока (Worker)
        self.worker: TranslatorWorker = translator.run_translator_worker(
            text,
            src_code,
            tgt_code,
        )

        # Подписываемся на сигналы от потока
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.status.connect(self.statusbar.showMessage)
        self.worker.progress_val.connect(self.progressBar.setValue)
        self.worker.progress_visible.connect(self.progressBar.setVisible)

        # Запускаем поток
        self.worker.start()

    def on_finished(self, result):
        """
        Вызывается, когда перевод успешно завершен.
        """
        self.TextOutput.setPlainText(result)
        self.reset_ui()

    def on_error(self, err):
        """
        Вызывается, если в потоке произошла ошибка.
        Показывает всплывающее окно.
        """
        QMessageBox.warning(self, "Ошибка", str(err))
        self.reset_ui()

    def reset_ui(self):
        """
        Возвращает элементы интерфейса в исходное состояние.
        """
        self.btnTranslate.setEnabled(True)
        self.btnTranslate.setText("ПЕРЕВЕСТИ")
        self.progressBar.setVisible(False)
