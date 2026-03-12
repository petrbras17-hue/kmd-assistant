"""
Инструменты для работы с архивами (RAR, ZIP, 7z).
"""

import os
import sys
import zipfile


def extract_rar(rar_path: str, output_dir: str = None) -> list:
    """Распаковать RAR архив."""
    import rarfile
    out = output_dir or os.path.splitext(rar_path)[0]
    os.makedirs(out, exist_ok=True)
    with rarfile.RarFile(rar_path) as rf:
        rf.extractall(out)
        return rf.namelist()


def extract_zip(zip_path: str, output_dir: str = None) -> list:
    """Распаковать ZIP архив."""
    out = output_dir or os.path.splitext(zip_path)[0]
    os.makedirs(out, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(out)
        return zf.namelist()


def extract_7z(path_7z: str, output_dir: str = None) -> list:
    """Распаковать 7z архив."""
    import py7zr
    out = output_dir or os.path.splitext(path_7z)[0]
    os.makedirs(out, exist_ok=True)
    with py7zr.SevenZipFile(path_7z) as sz:
        sz.extractall(out)
        return sz.getnames()


def create_zip(files: list, output_path: str):
    """Создать ZIP архив из списка файлов."""
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, os.path.basename(f))
    print(f"Архив создан: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Использование: python archive_tools.py <extract|create> <файл>")
        sys.exit(1)

    cmd = sys.argv[1]
    path = sys.argv[2]

    if cmd == "extract":
        ext = os.path.splitext(path)[1].lower()
        if ext == ".rar":
            files = extract_rar(path)
        elif ext == ".zip":
            files = extract_zip(path)
        elif ext == ".7z":
            files = extract_7z(path)
        else:
            print(f"Неподдерживаемый формат: {ext}")
            sys.exit(1)
        print(f"Извлечено {len(files)} файлов")
