"""
Сравнение заказных спецификаций КМД.
А (исходник) — правильная заявка на материалы.
Б — заявка с возможными ошибками.
В = А - Б (разница: что нужно дозаказать или вернуть).
"""

import re
import sys
import os
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from copy import copy


def _parse_qty(qty_raw) -> float:
    """Извлечь числовое количество из разных форматов.

    Примеры: "3 x 6,5 м (18,3)" -> 18.3, "1 шт. (12)" -> 12,
    "256 x 7 м (1792)" -> 1792, "1 x 1044 м" -> 1044,
    "20\\nв упаковке по @ 200 шт. (3 860)" -> 3860
    """
    if pd.isna(qty_raw):
        return 0

    qty_str = str(qty_raw).replace('\n', ' ').strip()

    # Ищем число в скобках (основной формат Logical)
    match = re.search(r'\(([0-9\s]+[,.]?[0-9]*)\)', qty_str)
    if match:
        num_str = match.group(1).replace(' ', '').replace(',', '.')
        try:
            return float(num_str)
        except ValueError:
            pass

    # Формат "N x L м" без скобок (например "1 x 1044 м")
    match = re.search(r'(\d+)\s*[xхXХ]\s*([0-9]+[,.]?[0-9]*)\s*м', qty_str)
    if match:
        count = int(match.group(1))
        length = float(match.group(2).replace(',', '.'))
        return count * length

    # Просто число
    try:
        return float(qty_str.replace(',', '.').replace(' ', ''))
    except (ValueError, TypeError):
        return 0


def _detect_format(df_raw: pd.DataFrame) -> str:
    """Определить формат файла: 'logical_standard' (артикул в col5) или 'logical_alt' (артикул в col4)
    или 'summary' (файл потребности, артикул в col1)."""

    # Проверяем колонку 5 — стандартный формат
    col5_articles = 0
    col4_articles = 0
    col1_articles = 0

    for idx in range(min(20, df_raw.shape[0])):
        for col, counter_name in [(5, 'col5'), (4, 'col4'), (1, 'col1')]:
            if col >= df_raw.shape[1]:
                continue
            val = df_raw.iloc[idx].get(col)
            if pd.isna(val):
                continue
            val_s = str(val).strip()
            # Артикул — начинается с цифры/буквы, содержит точку или длиннее 6 символов
            if re.match(r'^[0-9A-Z]', val_s) and (('.' in val_s) or len(val_s) > 7):
                if val_s not in ('Номер', 'NaN') and 'Номер' not in val_s:
                    if counter_name == 'col5':
                        col5_articles += 1
                    elif counter_name == 'col4':
                        col4_articles += 1
                    elif counter_name == 'col1':
                        col1_articles += 1

    if col5_articles >= col4_articles and col5_articles >= col1_articles:
        return 'logical_standard'
    elif col4_articles >= col1_articles:
        return 'logical_alt'
    else:
        return 'summary'


def extract_articles(file_path: str) -> pd.DataFrame:
    """Извлечь артикулы, количество и цвет из файла заказа.

    Автоматически определяет формат файла и извлекает данные.
    """
    df_raw = pd.read_excel(file_path, header=None)
    fmt = _detect_format(df_raw)

    records = []

    if fmt == 'logical_standard':
        # Стандартный формат: col5=артикул, col3=кол-во, col12=цвет, col6=описание
        for idx in range(df_raw.shape[0]):
            row = df_raw.iloc[idx]
            article = row.get(5)
            qty_raw = row.get(3)
            color = row.get(12)
            description = row.get(6)

            if pd.isna(article) or str(article).strip() == '':
                continue
            article = str(article).strip()
            if article in ('Номер', 'NaN') or 'Номер' in article:
                continue

            records.append({
                'Артикул': article,
                'Артикул_норм': re.sub(r'\s+', '', article).rstrip('.'),
                'Количество': _parse_qty(qty_raw),
                'Цвет': str(color).strip() if not pd.isna(color) else '-',
                'Описание': str(description).strip() if not pd.isna(description) else '',
                'Строка_excel': idx + 1,
            })

    elif fmt == 'logical_alt':
        # Альтернативный формат: col4=артикул, col1=кол-во, col6=описание, col11=цвет
        for idx in range(df_raw.shape[0]):
            row = df_raw.iloc[idx]
            article = row.get(4)
            qty_raw = row.get(1)
            description = row.get(6)
            color = row.get(11) if 11 < df_raw.shape[1] else None

            if pd.isna(article) or str(article).strip() == '':
                continue
            article = str(article).strip()
            if article in ('Номер', 'NaN') or 'Номер' in article:
                continue

            records.append({
                'Артикул': article,
                'Артикул_норм': re.sub(r'\s+', '', article).rstrip('.'),
                'Количество': _parse_qty(qty_raw),
                'Цвет': str(color).strip() if not pd.isna(color) else '-',
                'Описание': str(description).strip() if not pd.isna(description) else '',
                'Строка_excel': idx + 1,
            })

    elif fmt == 'summary':
        # Формат потребности: col1 = "артикул (описание)", col2 = кол-во
        for idx in range(df_raw.shape[0]):
            row = df_raw.iloc[idx]
            name_raw = row.get(1)
            qty_raw = row.get(2)

            if pd.isna(name_raw) or pd.isna(qty_raw):
                continue

            name_str = str(name_raw).strip()
            # Извлекаем артикул из формата "0340581.04.7000 (Профиль - описание)"
            match = re.match(r'^([0-9A-Za-z][\w.\-]+(?:\.\d+)?)', name_str)
            if not match:
                continue
            article = match.group(1)

            # Извлекаем описание из скобок
            desc_match = re.search(r'\(.*?-\s*(.+?)\)', name_str)
            desc = desc_match.group(1) if desc_match else name_str

            try:
                qty = float(str(qty_raw).replace(',', '.').replace(' ', ''))
            except (ValueError, TypeError):
                continue

            records.append({
                'Артикул': article,
                'Артикул_норм': re.sub(r'\s+', '', article).rstrip('.'),
                'Количество': qty,
                'Цвет': '-',
                'Описание': desc,
                'Строка_excel': idx + 1,
            })

    df = pd.DataFrame(records)

    # Группируем дубли артикулов (суммируем количество)
    if not df.empty and df['Артикул_норм'].duplicated().any():
        grouped = df.groupby('Артикул_норм').agg({
            'Артикул': 'first',
            'Количество': 'sum',
            'Цвет': 'first',
            'Описание': 'first',
            'Строка_excel': 'first',
        }).reset_index()
        return grouped

    return df



def compare_orders(file_a: str, file_b: str, output_path: str = None, auto_format: bool = True):
    """Сравнить два файла заказа (А - Б) и создать файл В с разницей.

    А — исходник (правильная заявка)
    Б — заявка с возможными ошибками
    В = А - Б

    Положительное значение = нужно дозаказать
    Отрицательное значение = лишнее (можно вернуть)
    """
    print(f"\n{'='*60}")
    print(f"Сравнение заказов")
    print(f"  А (исходник): {os.path.basename(file_a)}")
    print(f"  Б (проверка): {os.path.basename(file_b)}")
    print(f"{'='*60}\n")

    # Извлекаем артикулы
    df_a = extract_articles(file_a)
    df_b = extract_articles(file_b)

    print(f"Файл А: {len(df_a)} позиций")
    print(f"Файл Б: {len(df_b)} позиций")

    if df_a.empty and df_b.empty:
        print("\n✓ Оба файла пусты.")
        return pd.DataFrame()

    if df_a.empty or df_b.empty:
        if df_a.empty:
            print("\n⚠ Файл А пуст — невозможно сравнить.")
        if df_b.empty:
            print("\n⚠ Файл Б пуст — невозможно сравнить.")
            # Все позиции А отсутствуют в Б
            df_b = pd.DataFrame(columns=df_a.columns)

    # Объединяем по нормализованному артикулу
    merged = pd.merge(
        df_a, df_b,
        on='Артикул_норм',
        how='outer',
        suffixes=('_А', '_Б')
    )

    results = []

    for _, row in merged.iterrows():
        art = row.get('Артикул_А') or row.get('Артикул_Б')
        art_norm = row['Артикул_норм']
        qty_a = row.get('Количество_А', 0)
        qty_b = row.get('Количество_Б', 0)

        if pd.isna(qty_a):
            qty_a = 0
        if pd.isna(qty_b):
            qty_b = 0

        diff = qty_a - qty_b
        color_a = row.get('Цвет_А', '-')
        color_b = row.get('Цвет_Б', '-')
        desc = row.get('Описание_А') or row.get('Описание_Б', '')

        if pd.isna(color_a):
            color_a = '-'
        if pd.isna(color_b):
            color_b = '-'
        if pd.isna(desc):
            desc = ''

        # Определяем тип различия
        if pd.isna(row.get('Количество_Б')) or (pd.isna(row.get('Артикул_Б'))):
            status = 'ОТСУТСТВУЕТ в Б (удалён)'
        elif pd.isna(row.get('Количество_А')) or (pd.isna(row.get('Артикул_А'))):
            status = 'ЛИШНИЙ в Б (нет в А)'
        elif diff != 0:
            status = f'Разница: {"+" if diff > 0 else ""}{diff}'
        elif color_a != color_b:
            status = f'Цвет изменён: {color_a} → {color_b}'
        else:
            status = 'Совпадает'
            continue  # Не выносим в таблицу В

        # Проверка изменения артикула (добавлены 00 и т.п.)
        art_a_str = str(row.get('Артикул_А', ''))
        art_b_str = str(row.get('Артикул_Б', ''))
        art_note = ''
        if art_a_str != art_b_str and art_a_str != 'nan' and art_b_str != 'nan':
            art_note = f' (артикул изменён: {art_a_str} → {art_b_str})'

        results.append({
            'Артикул': art,
            'Описание': desc,
            'Кол-во А': qty_a,
            'Кол-во Б': qty_b,
            'Разница (А-Б)': diff,
            'Цвет А': color_a,
            'Цвет Б': color_b,
            'Статус': status + art_note,
        })

    df_result = pd.DataFrame(results)

    if df_result.empty:
        print("\n✓ Файлы идентичны. Различий не найдено.")
        return df_result

    # Выводим результат
    print(f"\nНайдено различий: {len(df_result)}")
    print()

    for _, r in df_result.iterrows():
        marker = "🔴" if r['Разница (А-Б)'] > 0 else ("🟡" if r['Разница (А-Б)'] < 0 else "🔵")
        print(f"  {marker} {r['Артикул']}: {r['Статус']}")
        if r['Кол-во А'] != 0 or r['Кол-во Б'] != 0:
            print(f"     А={r['Кол-во А']}, Б={r['Кол-во Б']}, Δ={r['Разница (А-Б)']}")

    # Сводка
    added = df_result[df_result['Статус'].str.contains('ОТСУТСТВУЕТ')]
    extra = df_result[df_result['Статус'].str.contains('ЛИШНИЙ')]
    changed_qty = df_result[df_result['Статус'].str.contains('Разница')]

    print(f"\n--- СВОДКА ---")
    print(f"  Удалено из Б (нужно дозаказать): {len(added)}")
    print(f"  Лишнее в Б (нет в А):            {len(extra)}")
    print(f"  Изменено количество:              {len(changed_qty)}")

    # Сохраняем в Excel
    if output_path:
        save_comparison_xlsx(df_result, output_path, file_a, file_b)

    return df_result


def save_comparison_xlsx(df: pd.DataFrame, output_path: str, file_a: str, file_b: str):
    """Сохранить результат сравнения в форматированный XLSX."""

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Сравнение заказов"

    # Стили
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(name="Arial", bold=True, color="FFFFFF", size=11)
    red_fill = PatternFill(start_color="FCE4EC", end_color="FCE4EC", fill_type="solid")
    green_fill = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
    yellow_fill = PatternFill(start_color="FFF9C4", end_color="FFF9C4", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    # Заголовок
    ws.merge_cells('A1:H1')
    ws['A1'] = f"Сравнение заказов: А - Б"
    ws['A1'].font = Font(name="Arial", bold=True, size=14)
    ws['A2'] = f"А: {os.path.basename(file_a)}"
    ws['A3'] = f"Б: {os.path.basename(file_b)}"

    # Заголовки таблицы
    headers = list(df.columns)
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=5, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
        cell.border = thin_border

    # Данные
    for row_idx, (_, row) in enumerate(df.iterrows(), 6):
        for col_idx, col_name in enumerate(headers, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=row[col_name])
            cell.border = thin_border
            cell.alignment = Alignment(wrap_text=True)

        # Подсветка строк
        diff = row.get('Разница (А-Б)', 0)
        status = str(row.get('Статус', ''))

        fill = None
        if 'ОТСУТСТВУЕТ' in status:
            fill = red_fill
        elif 'ЛИШНИЙ' in status:
            fill = yellow_fill
        elif diff > 0:
            fill = red_fill
        elif diff < 0:
            fill = green_fill

        if fill:
            for col_idx in range(1, len(headers) + 1):
                ws.cell(row=row_idx, column=col_idx).fill = fill

    # Ширина колонок
    col_widths = [20, 40, 12, 12, 14, 12, 12, 35]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    wb.save(output_path)
    print(f"\n✓ Результат сохранён: {output_path}")


def run_all_tasks(tasks_dir: str, output_dir: str):
    """Выполнить все задания из папки."""
    os.makedirs(output_dir, exist_ok=True)

    # Задания 1-6 (стандартный формат)
    for i in range(1, 9):
        # Ищем файлы
        a_file = None
        b_file = None

        for f in os.listdir(tasks_dir):
            fl = f.lower()
            if f.startswith(f'{i} задн') or f.startswith(f'{i} задан'):
                if '1 а' in fl or '1а' in fl or '-1 а' in fl or '-1а' in fl:
                    a_file = os.path.join(tasks_dir, f)
                elif '1 б' in fl or '1б' in fl or '-1 б' in fl or '-1б' in fl:
                    b_file = os.path.join(tasks_dir, f)

        if a_file and b_file:
            output = os.path.join(output_dir, f"Задание_{i}_результат.xlsx")
            print(f"\n{'#'*60}")
            print(f"  ЗАДАНИЕ {i}")
            print(f"{'#'*60}")
            compare_orders(a_file, b_file, output)
        else:
            print(f"\nЗадание {i}: файлы не найдены (А={a_file}, Б={b_file})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python compare_orders.py all                 — выполнить все задания")
        print("  python compare_orders.py <файл_А> <файл_Б>  — сравнить два файла")
        sys.exit(0)

    if sys.argv[1] == "all":
        run_all_tasks(
            "Задания от АльдМЕгаЛаб",
            "Результаты"
        )
    else:
        file_a = sys.argv[1]
        file_b = sys.argv[2]
        output = sys.argv[3] if len(sys.argv) > 3 else None
        compare_orders(file_a, file_b, output)
