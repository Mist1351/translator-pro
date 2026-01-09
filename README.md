# Переводчик online и offline

Проверялся на `Python 3.13.11`

## Развёртывание проекта

### Makefile

#### 1. Настройка проекта

```bash
make setup
```

#### 2. Отстройка проекта

```bash
make build
```

`TranslatorPro.exe` окажется в папке `dist/`.

#### 3. Запуск для локального тестирования

```bash
make run
```

### Вручную

#### 1. Настройка проекта

```bash
python3 -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

#### 2. Отстройка проекта

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name="TranslatorPro" --add-data=app/interface.ui:. main.py
```

`TranslatorPro.exe` окажется в папке `dist/`.

#### 3. Запуск для локального тестирования

```bash
python3 main.py
```

## Запуск

Скачайте [translation_data.zip](https://github.com/Mist1351/translator-pro/releases/download/data/translation_data.zip) и распакуйте содержимое рядом с `TranslatorPro.exe` или в корне проекта, если запускать `main.py`.
