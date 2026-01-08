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

# Импортируем наш класс рабочего потока
from translator_worker import TranslationWorker


class TranslatorApp(QMainWindow):
    """
    Главный класс приложения-переводчика.
    Наследуется от QMainWindow.
    Отвечает за отображение интерфейса, обработку нажатий и запуск потоков перевода.
    """

    # Аннотация типов для виджетов (нужно для подсказок в IDE и проверки типов)
    TextInput: QTextEdit
    TextOutput: QTextEdit
    comboSource: QComboBox
    comboTarget: QComboBox
    comboMode: QComboBox
    btnTranslate: QPushButton
    statusbar: QStatusBar

    def __init__(self):
        """
        Конструктор класса.
        Выполняет загрузку UI из файла, инициализацию данных и настройку связей.
        """
        super().__init__()

        # Проверяем наличие файла разметки перед загрузкой
        if os.path.exists("interface.ui"):
            # Динамически загружаем интерфейс из .ui файла
            uic.load_ui.loadUi("interface.ui", self)
        else:
            sys.exit("Interface file not found!")

        # Словарь поддерживаемых языков: Название -> Код ISO
        self.languages: dict[str, str] = {
            "Автоопределение": "auto",
            "Английский": "en",
            "Русский": "ru",
            "Китайский": "zh",
            "Немецкий": "de",
            "Французский": "fr",
            "Испанский": "es",
        }

        # Индексы для хранения предыдущего выбора в комбобоксах.
        # Нужны для реализации логики "swap" (обмена языками).
        self.last_src_idx: int = 0
        self.last_tgt_idx: int = 1

        # Вызываем методы настройки
        self.init_ui()
        self.setup_connections()

    def init_ui(self):
        """
        Настройка внешнего вида приложения.
        Заполняет выпадающие списки, настраивает прогресс-бар и применяет CSS-стили.
        """
        # Заполнение списков языками из словаря
        for name, code in self.languages.items():
            self.comboSource.addItem(name, code)
            # В целевой язык (Target) нельзя добавить "Автоопределение"
            if code != "auto":
                self.comboTarget.addItem(name, code)

        # Установка значений по умолчанию (Авто -> Русский)
        self.comboSource.setCurrentIndex(0)
        self.comboTarget.setCurrentIndex(1)

        # Запоминаем начальные индексы
        self.last_src_idx = self.comboSource.currentIndex()
        self.last_tgt_idx = self.comboTarget.currentIndex()

        # Создаем и настраиваем ProgressBar в статус-баре (скрыт по умолчанию)
        self.progressBar = QProgressBar()
        self.progressBar.setMaximumWidth(200)
        self.progressBar.setValue(0)
        self.progressBar.setVisible(False)
        # Стилизация прогресс-бара (зеленый цвет загрузки)
        self.progressBar.setStyleSheet("""
            QProgressBar { border: 1px solid #555; border-radius: 5px; text-align: center; color: white; }
            QProgressBar::chunk { background-color: #2ecc71; }
        """)
        self.statusbar.addPermanentWidget(self.progressBar)

        # Применяем темную тему оформления (Dark Mode) через QSS
        self.setStyleSheet("""
            QMainWindow { background-color: #2b2b2b; }
            QLabel { color: #ffffff; font-size: 14px; font-weight: bold; }
            QTextEdit { 
                background-color: #353535; color: #ffffff; 
                border: 1px solid #555; border-radius: 8px; padding: 10px; font-size: 14px;
            }
            QTextEdit:focus { border: 1px solid #3a86ff; }
            QComboBox { 
                background-color: #404040; color: white; 
                border: 1px solid #555; border-radius: 5px; padding: 5px; min-width: 150px;
            }
            QComboBox QAbstractItemView {
                background-color: #404040; color: white; selection-background-color: #3a86ff;
            }
            QPushButton {
                background-color: #3a86ff; color: white; border-radius: 8px; font-size: 16px; font-weight: bold;
            }
            QStatusBar { color: #aaaaaa; }
            QMessageBox { background-color: #2b2b2b; }
            QMessageBox QLabel { color: white; }
            QMessageBox QPushButton { background-color: #404040; color: white; padding: 5px 15px; }
        """)

    def setup_connections(self):
        """
        Подключение сигналов к слотам (обработчикам событий).
        """
        self.btnTranslate.clicked.connect(self.start_translation)
        # Подключаем сигналы изменения индекса в комбобоксах
        self.comboSource.currentIndexChanged.connect(self.on_source_changed)
        self.comboTarget.currentIndexChanged.connect(self.on_target_changed)

    def on_source_changed(self, index):
        """
        Слот, вызываемый при изменении языка источника (левый список).
        Реализует логику предотвращения выбора одинаковых языков.
        """
        src_code = self.comboSource.currentData()
        tgt_code = self.comboTarget.currentData()

        # Проверка конфликта: если выбран не Auto, и языки совпадают
        if src_code != "auto" and src_code == tgt_code:
            # Блокируем сигналы правого списка, чтобы избежать рекурсии
            self.comboTarget.blockSignals(True)

            # Логика обмена: пытаемся поставить справа тот язык, который был слева
            prev_src_code = self.comboSource.itemData(self.last_src_idx)
            new_tgt_index = self.comboTarget.findData(prev_src_code)

            if new_tgt_index != -1:
                # Если предыдущий язык есть в списке, выбираем его (Swap)
                self.comboTarget.setCurrentIndex(new_tgt_index)
            else:
                # Если предыдущим был "Auto", его нет справа. Ищем замену.
                # Логика: если выбрали En, ставим Ru. Иначе ставим En.
                if src_code == "en":
                    fallback_index = self.comboTarget.findData("ru")
                else:
                    fallback_index = self.comboTarget.findData("en")

                # Страховка на случай, если "en" нет в списке
                if fallback_index == -1:
                    for i in range(self.comboTarget.count()):
                        if self.comboTarget.itemData(i) != src_code:
                            fallback_index = i
                            break

                self.comboTarget.setCurrentIndex(fallback_index)

            # Обновляем сохраненный индекс правого списка
            self.last_tgt_idx = self.comboTarget.currentIndex()
            # Разблокируем сигналы
            self.comboTarget.blockSignals(False)

        # Запоминаем текущий выбор
        self.last_src_idx = index

    def on_target_changed(self, index):
        """
        Слот, вызываемый при изменении целевого языка (правый список).
        Аналогичная логика обмена, но проще, так как справа нет "Auto".
        """
        src_code = self.comboSource.currentData()
        tgt_code = self.comboTarget.currentData()

        if src_code != "auto" and src_code == tgt_code:
            self.comboSource.blockSignals(True)

            # Берем язык, который был справа, и ищем его слева
            prev_tgt_code = self.comboTarget.itemData(self.last_tgt_idx)
            new_src_index = self.comboSource.findData(prev_tgt_code)

            if new_src_index != -1:
                self.comboSource.setCurrentIndex(new_src_index)
                self.last_src_idx = new_src_index

            self.comboSource.blockSignals(False)

        self.last_tgt_idx = index

    def start_translation(self):
        """
        Метод запуска процесса перевода.
        Считывает данные, блокирует интерфейс и запускает рабочий поток.
        """
        text = self.TextInput.toPlainText()
        src_code = self.comboSource.currentData()
        tgt_code = self.comboTarget.currentData()
        # Определяем режим по тексту в выпадающем списке
        mode = "Online" if "Online" in self.comboMode.currentText() else "Offline"

        if not text:
            self.statusbar.showMessage("Введите текст")
            return

        # Визуальная индикация работы
        self.btnTranslate.setEnabled(False)
        self.btnTranslate.setText("...")

        # Создаем экземпляр потока (Worker)
        self.worker = TranslationWorker(text, src_code, tgt_code, mode)

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
