"""
Инструменты для работы с PDF чертежами КМД.
- Извлечение текста, таблиц, изображений
- Сравнение версий чертежей
- Генерация отчётов
"""

import os
import sys
from pathlib import Path


def extract_text_from_pdf(pdf_path: str) -> str:
    """Извлечь весь текст из PDF."""
    import fitz  # PyMuPDF
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text() + "\n--- Страница ---\n"
    doc.close()
    return text


def extract_tables_from_pdf(pdf_path: str) -> list:
    """Извлечь таблицы из PDF (спецификации, ведомости)."""
    import pdfplumber
    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_tables = page.extract_tables()
            for t in page_tables:
                tables.append({"page": i + 1, "data": t})
    return tables


def pdf_to_images(pdf_path: str, output_dir: str, dpi: int = 200) -> list:
    """Конвертировать страницы PDF в изображения."""
    from pdf2image import convert_from_path
    os.makedirs(output_dir, exist_ok=True)
    images = convert_from_path(pdf_path, dpi=dpi)
    paths = []
    for i, img in enumerate(images):
        p = os.path.join(output_dir, f"page_{i+1}.png")
        img.save(p, "PNG")
        paths.append(p)
    return paths


def merge_pdfs(pdf_paths: list, output_path: str):
    """Объединить несколько PDF в один."""
    import pikepdf
    merged = pikepdf.Pdf.new()
    for path in pdf_paths:
        src = pikepdf.open(path)
        merged.pages.extend(src.pages)
    merged.save(output_path)


def split_pdf(pdf_path: str, output_dir: str) -> list:
    """Разделить PDF на отдельные страницы."""
    import pikepdf
    os.makedirs(output_dir, exist_ok=True)
    src = pikepdf.open(pdf_path)
    paths = []
    for i, page in enumerate(src.pages):
        dst = pikepdf.Pdf.new()
        dst.pages.append(page)
        p = os.path.join(output_dir, f"page_{i+1}.pdf")
        dst.save(p)
        paths.append(p)
    return paths


def compare_pdfs_text(pdf1: str, pdf2: str) -> dict:
    """Сравнить текст двух PDF (ошибочный vs правильный вариант)."""
    import difflib
    text1 = extract_text_from_pdf(pdf1)
    text2 = extract_text_from_pdf(pdf2)
    diff = list(difflib.unified_diff(
        text1.splitlines(), text2.splitlines(),
        fromfile="Ошибочный", tofile="Правильный", lineterm=""
    ))
    return {
        "added": [l for l in diff if l.startswith("+") and not l.startswith("+++")],
        "removed": [l for l in diff if l.startswith("-") and not l.startswith("---")],
        "diff_lines": diff,
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Использование: python pdf_tools.py <команда> <файл>")
        print("Команды: text, tables, images, compare")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "text":
        print(extract_text_from_pdf(sys.argv[2]))
    elif cmd == "tables":
        import json
        tables = extract_tables_from_pdf(sys.argv[2])
        print(json.dumps(tables, ensure_ascii=False, indent=2))
    elif cmd == "images":
        out = sys.argv[3] if len(sys.argv) > 3 else "output_images"
        paths = pdf_to_images(sys.argv[2], out)
        print(f"Сохранено {len(paths)} изображений в {out}/")
    elif cmd == "compare":
        if len(sys.argv) < 4:
            print("Использование: python pdf_tools.py compare <файл1> <файл2>")
            sys.exit(1)
        result = compare_pdfs_text(sys.argv[2], sys.argv[3])
        print(f"Добавлено строк: {len(result['added'])}")
        print(f"Удалено строк: {len(result['removed'])}")
        for line in result["diff_lines"][:50]:
            print(line)
