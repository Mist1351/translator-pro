# Настройка переменных для Windows
ifeq ($(OS),Windows_NT)
	VENV_DIR = venv
	BIN = $(VENV_DIR)\Scripts
	PYTHON_SYS = python
	# Слеш для путей
	FixPath = $(subst /,\,$1)
	# Команды для удаления
	RM_DIR = rmdir /s /q
	# Команда проверки папки
	CHECK_VENV = if not exist $(VENV_DIR)
	ACTIVATE = .\$(BIN)\activate
else # Настройка переменных для Linux
	VENV_DIR = venv
	BIN = $(VENV_DIR)/bin
	PYTHON_SYS = python3
	FixPath = $1
	RM_DIR = rm -rf
	CHECK_VENV = test -d $(VENV_DIR) ||
	ACTIVATE = source $(BIN)/activate
endif

VENV_PYTHON = $(call FixPath,$(BIN)/python)
VENV_PIP = $(call FixPath,$(BIN)/pip)

default: run

setup: venv install
	@echo [SUCCESS] Setup complete! You can now run: make run

venv:
	@echo [INFO] Checking virtual environment...
	$(CHECK_VENV) $(PYTHON_SYS) -m venv $(VENV_DIR)

activate:
	@echo Run this command in terminal: $(ACTIVATE)

freeze:
	@echo [INFO] Freeze requirements...
	echo --extra-index-url https://download.pytorch.org/whl/cpu > requirements.txt
	$(VENV_PIP) freeze >> requirements.txt

install:
	@echo [INFO] Installing requirements...
	$(VENV_PIP) install -r requirements.txt

run:
	$(VENV_PYTHON) main.py

clean:
	@echo [INFO] Cleaning up...
	$(RM_DIR) $(VENV_DIR)
	@echo [INFO] Done.

build: setup
	@echo [INFO] Building EXE...
	$(VENV_PIP) install pyinstaller
	pyinstaller --noconsole --onefile --name="TranslatorPro" --add-data=app/interface.ui:. main.py
	@echo [SUCCESS] Executable is in dist/ folder.

editor:
	pyside6-designer app/interface.ui
