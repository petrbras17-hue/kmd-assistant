"""
КМД Checker — главный инструмент проверки КМД документации.
Объединяет все инструменты для комплексной проверки.
"""

import os
import sys
import json
from pathlib import Path


def scan_project_files(project_dir: str) -> dict:
    """Просканировать директорию проекта и классифицировать файлы."""
    result = {"pdf": [], "xlsx": [], "docx": [], "dxf": [], "images": [], "archives": [], "other": []}
    ext_map = {
        ".pdf": "pdf", ".xlsx": "xlsx", ".xls": "xlsx",
        ".docx": "docx", ".doc": "docx",
        ".dxf": "dxf", ".dwg": "dxf",
        ".png": "images", ".jpg": "images", ".jpeg": "images", ".tiff": "images",
        ".rar": "archives", ".zip": "archives", ".7z": "archives",
    }
    for root, _, files in os.walk(project_dir):
        for f in files:
            if f.startswith("."):
                continue
            ext = Path(f).suffix.lower()
            category = ext_map.get(ext, "other")
            result[category].append(os.path.join(root, f))
    return result


def quick_report(project_dir: str):
    """Быстрый отчёт о составе проекта КМД."""
    files = scan_project_files(project_dir)
    print("=" * 50)
    print("ОТЧЁТ О СОСТАВЕ ПРОЕКТА КМД")
    print("=" * 50)
    for category, file_list in files.items():
        if file_list:
            print(f"\n{category.upper()} ({len(file_list)} файлов):")
            for f in file_list:
                size = os.path.getsize(f) / 1024
                unit = "KB"
                if size > 1024:
                    size /= 1024
                    unit = "MB"
                print(f"  {os.path.basename(f)} ({size:.1f} {unit})")
    print("\n" + "=" * 50)


def compare_variants(error_pdf: str, correct_pdf: str, error_desc_docx: str = None) -> dict:
    """Комплексное сравнение ошибочного и правильного вариантов КМД.

    Returns: словарь с результатами сравнения текста, таблиц и описанием ошибок.
    """
    from pdf_tools import extract_text_from_pdf, extract_tables_from_pdf, compare_pdfs_text

    result = {
        "text_diff": compare_pdfs_text(error_pdf, correct_pdf),
        "error_tables": extract_tables_from_pdf(error_pdf),
        "correct_tables": extract_tables_from_pdf(correct_pdf),
    }

    if error_desc_docx:
        from docx_tools import read_docx_with_tables
        result["error_description"] = read_docx_with_tables(error_desc_docx)

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("КМД Checker — инструмент проверки КМД документации")
        print()
        print("Использование:")
        print("  python kmd_checker.py scan <директория>     — сканировать файлы проекта")
        print("  python kmd_checker.py compare <ошиб.pdf> <прав.pdf> [описание.docx]")
        print("                                              — сравнить варианты КМД")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "scan":
        quick_report(sys.argv[2] if len(sys.argv) > 2 else ".")
    elif cmd == "compare":
        if len(sys.argv) < 4:
            print("Нужно указать два PDF файла для сравнения")
            sys.exit(1)
        desc = sys.argv[4] if len(sys.argv) > 4 else None
        result = compare_variants(sys.argv[2], sys.argv[3], desc)
        print(json.dumps({
            "text_changes": len(result["text_diff"]["added"]) + len(result["text_diff"]["removed"]),
            "error_tables_count": len(result["error_tables"]),
            "correct_tables_count": len(result["correct_tables"]),
        }, ensure_ascii=False, indent=2))
