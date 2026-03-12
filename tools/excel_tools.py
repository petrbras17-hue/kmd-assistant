"""
Инструменты для работы с Excel (XLSX) — чек-листы, задания, спецификации КМД.
"""

import os
import sys
from pathlib import Path


def read_xlsx(file_path: str, sheet_name: str = None) -> "pd.DataFrame":
    """Прочитать XLSX в DataFrame."""
    import pandas as pd
    return pd.read_excel(file_path, sheet_name=sheet_name)


def read_all_sheets(file_path: str) -> dict:
    """Прочитать все листы XLSX."""
    import pandas as pd
    return pd.read_excel(file_path, sheet_name=None)


def xlsx_to_csv(file_path: str, output_dir: str = None):
    """Конвертировать все листы XLSX в CSV."""
    import pandas as pd
    sheets = pd.read_excel(file_path, sheet_name=None)
    out = output_dir or os.path.dirname(file_path)
    os.makedirs(out, exist_ok=True)
    base = Path(file_path).stem
    for name, df in sheets.items():
        csv_path = os.path.join(out, f"{base}_{name}.csv")
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"Сохранено: {csv_path}")


def compare_xlsx(file1: str, file2: str, sheet: str = None) -> dict:
    """Сравнить два XLSX файла (вариант А vs Б)."""
    import pandas as pd
    df1 = pd.read_excel(file1, sheet_name=sheet or 0)
    df2 = pd.read_excel(file2, sheet_name=sheet or 0)

    # Приведём к одинаковым колонкам
    common_cols = list(set(df1.columns) & set(df2.columns))
    df1 = df1[common_cols].fillna("")
    df2 = df2[common_cols].fillna("")

    diff_mask = df1.ne(df2)
    diffs = []
    for row in diff_mask.index:
        for col in diff_mask.columns:
            if diff_mask.at[row, col]:
                diffs.append({
                    "row": int(row) + 2,  # +2 для Excel-нумерации
                    "col": col,
                    "file1": str(df1.at[row, col]),
                    "file2": str(df2.at[row, col]),
                })
    return {"total_diffs": len(diffs), "diffs": diffs}


def create_checklist_report(file_path: str, output_path: str = None):
    """Создать отформатированный отчёт из чек-листа."""
    import pandas as pd
    from tabulate import tabulate

    df = pd.read_excel(file_path)
    report = tabulate(df, headers="keys", tablefmt="grid", showindex=False)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Отчёт сохранён: {output_path}")
    else:
        print(report)


def xlsx_summary(file_path: str):
    """Показать сводку по XLSX файлу."""
    import pandas as pd
    sheets = pd.read_excel(file_path, sheet_name=None)
    print(f"Файл: {file_path}")
    print(f"Листов: {len(sheets)}")
    for name, df in sheets.items():
        print(f"\n  Лист: {name}")
        print(f"  Строк: {len(df)}, Колонок: {len(df.columns)}")
        print(f"  Колонки: {list(df.columns)}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Использование: python excel_tools.py <команда> <файл>")
        print("Команды: read, summary, compare, csv, checklist")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "summary":
        xlsx_summary(sys.argv[2])
    elif cmd == "csv":
        xlsx_to_csv(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "compare":
        result = compare_xlsx(sys.argv[2], sys.argv[3])
        print(f"Найдено различий: {result['total_diffs']}")
        for d in result["diffs"][:20]:
            print(f"  Строка {d['row']}, колонка '{d['col']}': '{d['file1']}' → '{d['file2']}'")
    elif cmd == "checklist":
        create_checklist_report(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "read":
        df = read_xlsx(sys.argv[2])
        print(df.to_string())
