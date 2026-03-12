#!/bin/bash
# Установка всех зависимостей KMD Tools
# Запуск: bash tools/install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== KMD Tools — Установка зависимостей ==="
echo ""

# Создаём виртуальное окружение если нет
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "Создаю виртуальное окружение..."
    python3 -m venv "$PROJECT_DIR/venv"
fi

# Активируем
source "$PROJECT_DIR/venv/bin/activate"
echo "Python: $(python --version)"
echo "Pip: $(pip --version)"

# Обновляем pip
pip install --upgrade pip

# Устанавливаем зависимости
echo ""
echo "Устанавливаю библиотеки..."
pip install -r "$SCRIPT_DIR/requirements.txt"

# Проверяем Tesseract OCR
echo ""
if command -v tesseract &> /dev/null; then
    echo "Tesseract OCR: $(tesseract --version 2>&1 | head -1)"
else
    echo "ВНИМАНИЕ: Tesseract OCR не установлен."
    echo "Для OCR функций установите:"
    echo "  brew install tesseract tesseract-lang"
fi

# Проверяем Graphviz
if command -v dot &> /dev/null; then
    echo "Graphviz: $(dot -V 2>&1)"
else
    echo "ВНИМАНИЕ: Graphviz не установлен."
    echo "Для диаграмм установите:"
    echo "  brew install graphviz"
fi

# Проверяем unrar
if command -v unrar &> /dev/null; then
    echo "UnRAR: доступен"
else
    echo "ВНИМАНИЕ: unrar не установлен."
    echo "Для RAR архивов установите:"
    echo "  brew install unrar"
fi

echo ""
echo "=== Установка завершена ==="
echo ""
echo "Активация окружения:"
echo "  source venv/bin/activate"
echo ""
echo "Примеры использования:"
echo "  python tools/kmd_checker.py scan ."
echo "  python tools/pdf_tools.py text 'файл.pdf'"
echo "  python tools/excel_tools.py summary 'файл.xlsx'"
echo "  python tools/docx_tools.py read 'файл.docx'"
