ifeq ($(OS),Windows_NT)
	VENV_DIR = venv
	BIN = $(VENV_DIR)\Scripts
	PYTHON_SYS = python
	FixPath = $(subst /,\,$1)
else
	VENV_DIR = venv
	BIN = $(VENV_DIR)/bin
	PYTHON_SYS = python3
	FixPath = $1
endif

VENV_PYTHON = $(call FixPath,$(BIN)/python)
VENV_PIP = $(call FixPath,$(BIN)/pip)

venv:
	$(PYTHON_SYS) -m venv $(VENV_DIR)

activate:
ifeq ($(OS),Windows_NT)
	.\$(BIN)\activate
else
	source $(BIN)/activate
endif

freeze:
	$(VENV_PIP) freeze > requirements.txt

install:
	$(VENV_PIP) install -r requirements.txt

run:
	$(VENV_PYTHON) main.py

clean:
ifeq ($(OS),Windows_NT)
	rmdir /s /q $(VENV_DIR)
else
	rm -rf $(VENV_DIR)
endif
