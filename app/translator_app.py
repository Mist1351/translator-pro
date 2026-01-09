import os
import sys
from typing import cast

from PySide6.QtCore import QFile
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QComboBox,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QWidget,
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


# Аннотация типов для виджетов из interface.ui (нужно для подсказок в IDE)
class InterfaceUI(QWidget):
    textInput: QTextEdit
    textOutput: QTextEdit
    comboSource: QComboBox
    comboTarget: QComboBox
    comboMode: QComboBox
    btnTranslate: QPushButton
    progressBar: QProgressBar


class TranslatorApp(QMainWindow):
    """
    Главный класс приложения-переводчика.
    Наследуется от QMainWindow.
    Отвечает за отображение интерфейса, обработку нажатий и запуск потоков перевода.
    """

    ui: InterfaceUI

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
        index: int = self.ui.comboMode.currentData()
        return self.translators[index]

    def _load_interface(self) -> None:
        """
        Загрузка интерфейса из файла.
        """
        # Ищем interface.ui через get_resource_path
        ui_path: str = get_resource_path("interface.ui")

        # Проверяем наличие файла разметки и загружаем в случае успеха
        if os.path.exists(ui_path):
            # 1. Загружаем файл
            loader: QUiLoader = QUiLoader()
            ui_file: QFile = QFile(ui_path)
            ui_file.open(QFile.OpenModeFlag.ReadOnly)

            # 2. Получаем виджет из файла
            self.ui = cast(InterfaceUI, loader.load(ui_file, self))
            ui_file.close()

            # 3. Применяем его к главному окну (self)
            styles = self.ui.styleSheet()
            self.setStyleSheet(styles)
            self.ui.setStyleSheet("")

            # 5. Делаем загруженный виджет центральным (если это Main Window)
            self.setCentralWidget(self.ui)
        else:
            raise FileExistsError(f"Interface file not found at: {ui_path}")

    def _fillup_combo_boxes(self) -> None:
        """
        Настройка выпадающих списков языков.
        """
        translator: Translator = self.get_current_translator()

        self.ui.comboSource.blockSignals(True)
        self.ui.comboTarget.blockSignals(True)

        # Заполнение списков языками из словаря
        self.ui.comboSource.clear()
        self.ui.comboTarget.clear()
        for name, code in translator.languages.items():
            self.ui.comboSource.addItem(name, code)
            # В целевой язык (Target) нельзя добавить "Автоопределение"
            if code != "auto":
                self.ui.comboTarget.addItem(name, code)

        # Выбор начальных языков
        self.ui.comboSource.setCurrentIndex(translator.source_index)
        self.ui.comboTarget.setCurrentIndex(translator.target_index)

        self.ui.comboTarget.blockSignals(False)
        self.ui.comboSource.blockSignals(False)

    def init_ui(self) -> None:
        """
        Настройка внешнего вида приложения.
        Заполняет выпадающие списки, настраивает прогресс-бар и применяет CSS-стили.
        """
        self._load_interface()

        # Заполнение списка режимов
        for index, translator in enumerate(self.translators):
            self.ui.comboMode.addItem(translator.name, index)
        self.ui.comboMode.setCurrentIndex(0)

        self._fillup_combo_boxes()
        self.ui.progressBar.hide()
        self.statusBar().addPermanentWidget(self.ui.progressBar)

    def setup_connections(self) -> None:
        """
        Подключение сигналов к слотам (обработчикам событий).
        """
        self.ui.btnTranslate.clicked.connect(self.start_translation)
        # Подключаем сигналы изменения индекса в комбобоксах
        self.ui.comboSource.currentIndexChanged.connect(self.on_source_changed)
        self.ui.comboTarget.currentIndexChanged.connect(self.on_target_changed)
        self.ui.comboMode.currentIndexChanged.connect(self.on_mode_changed)

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
            if from_combo_box == self.ui.comboSource
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
        if to_combo_box == self.ui.comboSource:
            translator.source_index = new_to_index
        else:
            translator.target_index = new_to_index

        # Разблокируем сигналы
        to_combo_box.blockSignals(False)

    def on_source_changed(self, index: int) -> None:
        """
        Слот, вызываемый при изменении языка источника (левый список).
        """
        self._resolve_lang_conflict(self.ui.comboSource, self.ui.comboTarget)
        # Запоминаем текущий выбор
        self.get_current_translator().source_index = index

    def on_target_changed(self, index: int) -> None:
        """
        Слот, вызываемый при изменении целевого языка (правый список).
        """
        self._resolve_lang_conflict(self.ui.comboTarget, self.ui.comboSource)
        # Запоминаем текущий выбор
        self.get_current_translator().target_index = index

    def on_mode_changed(self, index: int) -> None:
        """
        Слот, вызываемый при изменении режима перевода.
        """
        self._fillup_combo_boxes()
        self._resolve_lang_conflict(self.ui.comboSource, self.ui.comboTarget)

    def start_translation(self) -> None:
        """
        Метод запуска процесса перевода.
        Считывает данные, блокирует интерфейс и запускает рабочий поток.
        """
        text = self.ui.textInput.toPlainText()
        src_code: str = self.ui.comboSource.currentData()
        tgt_code: str = self.ui.comboTarget.currentData()
        translator: Translator = self.get_current_translator()

        # text пустой, нечего переводить
        if not text:
            self.statusBar().showMessage("Введите текст")
            return

        # Визуальная индикация работы
        self.ui.btnTranslate.setEnabled(False)
        self.ui.btnTranslate.setText("...")

        # Создаем экземпляр потока (Worker)
        self.worker: TranslatorWorker = translator.run_translator_worker(
            text,
            src_code,
            tgt_code,
        )

        # Подписываемся на сигналы от потока
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.status.connect(self.statusBar().showMessage)
        self.worker.progress_val.connect(self.ui.progressBar.setValue)
        self.worker.progress_visible.connect(self.ui.progressBar.setVisible)

        # Запускаем поток
        self.worker.start()

    def on_finished(self, result):
        """
        Вызывается, когда перевод успешно завершен.
        """
        self.ui.textOutput.setPlainText(result)
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
        self.ui.btnTranslate.setEnabled(True)
        self.ui.btnTranslate.setText("ПЕРЕВЕСТИ")
        self.ui.progressBar.setVisible(False)
