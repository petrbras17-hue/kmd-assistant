"""
KMD Assistant — веб-сервер для инженеров АЛЬДМЕГА ЛАБ.
FastAPI бэкенд с инструментами проверки КМД документации.
"""

import os
import sys
import uuid
import json
import shutil
import zipfile
import tempfile
import re as _re
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Добавляем tools в путь
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from compare_orders import extract_articles, compare_orders
from pdf_tools import extract_text_from_pdf, extract_tables_from_pdf
from docx_tools import read_docx, read_docx_with_tables
from dxf_tools import parse_dxf_for_web
from ocr_tools import (
    ocr_pil_image, preprocess_image,
    parse_positions, parse_articles, parse_dimensions,
)

app = FastAPI(title="KMD Assistant", version="1.0")

UPLOAD_DIR = Path(__file__).parent / "uploads"
RESULTS_DIR = Path(__file__).parent / "results"
UPLOAD_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

# ============== IN-MEMORY ACTIVITY LOG ==============

activity_log: list[dict] = []
MAX_ACTIVITY = 100

counters = {
    "compare": 0,
    "check_pdf": 0,
    "parse_kmd": 0,
    "checklist": 0,
    "cross_validate": 0,
    "compare_pdf": 0,
    "batch": 0,
    "generate_spec": 0,
    "recommend_profile": 0,
    "optimize_cutting": 0,
    "preview_3d": 0,
}


def log_activity(op_type: str, filename: str, summary: str):
    """Добавить запись в лог активности."""
    counters[op_type] = counters.get(op_type, 0) + 1
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "type": op_type,
        "filename": filename,
        "summary": summary,
    }
    activity_log.insert(0, entry)
    if len(activity_log) > MAX_ACTIVITY:
        activity_log.pop()


def save_upload(file: UploadFile) -> Path:
    """Сохранить загруженный файл с уникальным именем."""
    # Берём только имя файла без пути для защиты от path traversal
    original_name = Path(file.filename).name
    uid = uuid.uuid4().hex[:8]
    safe_name = f"{uid}_{original_name}"
    path = UPLOAD_DIR / safe_name
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return path


# ===================== СТРАНИЦА =====================

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "index.html"
    return html_path.read_text(encoding="utf-8")


# ============== 1. СРАВНЕНИЕ СПЕЦИФИКАЦИЙ ==============

@app.post("/api/compare")
async def api_compare(
    file_a: UploadFile = File(...),
    file_b: UploadFile = File(...),
):
    """Сравнить два файла заказных спецификаций (А - Б)."""
    path_a = save_upload(file_a)
    path_b = save_upload(file_b)

    try:
        # Извлекаем артикулы
        df_a = extract_articles(str(path_a))
        df_b = extract_articles(str(path_b))

        # Результат
        result_name = f"compare_{uuid.uuid4().hex[:8]}.xlsx"
        result_path = RESULTS_DIR / result_name

        import pandas as pd

        if df_a.empty and df_b.empty:
            return {"status": "ok", "message": "Оба файла пусты", "diffs": [], "summary": {}}

        if df_b.empty:
            df_b = pd.DataFrame(columns=df_a.columns)

        # Merge
        merged = pd.merge(
            df_a, df_b,
            on='Артикул_норм',
            how='outer',
            suffixes=('_А', '_Б')
        )

        import math

        def safe_float(val, default=0.0):
            try:
                v = float(val)
                return default if (math.isnan(v) or math.isinf(v)) else v
            except (ValueError, TypeError):
                return default

        diffs = []
        for _, row in merged.iterrows():
            art = row.get('Артикул_А') or row.get('Артикул_Б') or ''
            if pd.isna(art):
                art = ''
            qty_a = safe_float(row.get('Количество_А', 0))
            qty_b = safe_float(row.get('Количество_Б', 0))
            diff = round(qty_a - qty_b, 2)
            color_a = str(row.get('Цвет_А', '-') or '-')
            color_b = str(row.get('Цвет_Б', '-') or '-')
            if color_a == 'nan': color_a = '-'
            if color_b == 'nan': color_b = '-'
            desc = str(row.get('Описание_А') or row.get('Описание_Б', '') or '')
            if desc == 'nan': desc = ''

            if pd.isna(row.get('Артикул_Б')):
                status = 'removed'
                status_text = 'Удалён из Б'
            elif pd.isna(row.get('Артикул_А')):
                status = 'extra'
                status_text = 'Лишний в Б'
            elif diff != 0:
                status = 'changed'
                status_text = f'Разница: {diff:+.2f}'
            elif color_a != color_b:
                status = 'color'
                status_text = f'Цвет: {color_a} → {color_b}'
            else:
                continue

            diffs.append({
                "article": str(art),
                "description": desc[:60],
                "qty_a": qty_a,
                "qty_b": qty_b,
                "diff": diff,
                "color_a": color_a,
                "color_b": color_b,
                "status": status,
                "status_text": status_text,
            })

        # Сохраняем XLSX
        compare_orders(str(path_a), str(path_b), str(result_path))

        summary = {
            "total_a": len(df_a),
            "total_b": len(df_b),
            "removed": len([d for d in diffs if d['status'] == 'removed']),
            "extra": len([d for d in diffs if d['status'] == 'extra']),
            "changed": len([d for d in diffs if d['status'] == 'changed']),
            "identical": len(df_a) - len(diffs) + len([d for d in diffs if d['status'] == 'extra']),
        }

        log_activity("compare", f"{file_a.filename} / {file_b.filename}",
                     f"Различий: {len(diffs)}, удалено: {summary['removed']}, изменено: {summary['changed']}")

        return {
            "status": "ok",
            "diffs": diffs,
            "summary": summary,
            "download": f"/api/download/{result_name}",
            "file_a": file_a.filename,
            "file_b": file_b.filename,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path_a.unlink(missing_ok=True)
        path_b.unlink(missing_ok=True)


# ============== 2. ПРОВЕРКА КОМПЛЕКТНОСТИ PDF ==============

@app.post("/api/check-pdf")
async def api_check_pdf(file: UploadFile = File(...)):
    """Проверить комплектность PDF чертежей КМД."""
    path = save_upload(file)

    try:
        import fitz
        doc = fitz.open(str(path))
        total_pages = len(doc)

        pages_info = []
        for i in range(total_pages):
            page = doc[i]
            text = page.get_text().strip()
            images = page.get_images()

            # Определяем тип страницы
            page_type = "пустая"
            if text:
                text_lower = text.lower()
                if any(w in text_lower for w in ['титульный', 'договор', 'заказчик']):
                    page_type = "титульный лист"
                elif any(w in text_lower for w in ['пояснительная', 'записка', 'в соответствии']):
                    page_type = "пояснительная записка"
                elif any(w in text_lower for w in ['спецификация', 'ведомость']):
                    page_type = "спецификация"
                elif 'поз.' in text_lower or 'количество' in text_lower:
                    page_type = "чертёж изделия"
                elif any(w in text_lower for w in ['обработка', 'сборка', 'фрезеровка']):
                    page_type = "чертёж обработки"
                elif any(w in text_lower for w in ['фасад', 'план', 'разрез']):
                    page_type = "план/фасад"
                elif any(w in text_lower for w in ['узел', 'сечение']):
                    page_type = "узел/сечение"
                else:
                    page_type = "чертёж"
            elif images:
                page_type = "изображение"

            # Извлекаем позиции изделий
            positions = []
            import re
            for m in re.finditer(r'Поз\.\s*([А-Яа-яA-Za-z0-9\-\.]+).*?Количество\s*:?\s*(\d+)', text):
                positions.append({"pos": m.group(1), "qty": int(m.group(2))})

            pages_info.append({
                "page": i + 1,
                "type": page_type,
                "has_text": bool(text),
                "text_preview": text[:150] if text else "",
                "images_count": len(images),
                "positions": positions,
            })

        doc.close()

        # Сводка по типам
        type_counts = {}
        all_positions = []
        for p in pages_info:
            t = p['type']
            type_counts[t] = type_counts.get(t, 0) + 1
            all_positions.extend(p['positions'])

        # Проверка комплектности
        checks = []
        has_title = type_counts.get('титульный лист', 0) > 0
        has_note = type_counts.get('пояснительная записка', 0) > 0
        has_drawings = type_counts.get('чертёж изделия', 0) + type_counts.get('чертёж', 0) > 0

        checks.append({"check": "Титульный лист", "passed": has_title})
        checks.append({"check": "Пояснительная записка", "passed": has_note})
        checks.append({"check": "Чертежи изделий", "passed": has_drawings})
        checks.append({"check": "Пустые страницы отсутствуют",
                       "passed": type_counts.get('пустая', 0) == 0})

        log_activity("check_pdf", file.filename,
                     f"Страниц: {total_pages}, позиций: {len(all_positions)}")

        return {
            "status": "ok",
            "filename": file.filename,
            "total_pages": total_pages,
            "pages": pages_info,
            "type_counts": type_counts,
            "checks": checks,
            "positions": all_positions,
            "total_positions": sum(p['qty'] for p in all_positions),
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path.unlink(missing_ok=True)


# ============== 3. ПАРСИНГ КМД ЧЕРТЕЖЕЙ ==============

@app.post("/api/parse-kmd")
async def api_parse_kmd(file: UploadFile = File(...)):
    """Извлечь данные из PDF чертежей КМД: позиции, артикулы, размеры."""
    path = save_upload(file)

    try:
        import fitz
        import re
        doc = fitz.open(str(path))

        items = []
        all_articles = set()

        for i in range(len(doc)):
            text = doc[i].get_text().strip()
            if not text:
                continue

            # Ищем позиции: "Поз.О-1, Количество:38"
            pos_matches = re.finditer(
                r'Поз\.?\s*([А-Яа-яA-Za-z0-9\-\.]+)\s*,?\s*Количество\s*:?\s*(\d+)',
                text
            )
            for m in pos_matches:
                pos_name = m.group(1)
                qty = int(m.group(2))

                # Ищем артикулы на этой странице (7-8 цифр или формат XXXX.XXXX)
                page_articles = set()
                for am in re.finditer(r'\b(\d{7,8})\b', text):
                    art = am.group(1)
                    if int(art) > 100000:
                        page_articles.add(art)
                        all_articles.add(art)

                # Ищем размеры
                dims = []
                for dm in re.finditer(r'\b(\d{2,4}(?:[,\.]\d{1,2})?)\b', text):
                    val = float(dm.group(1).replace(',', '.'))
                    if 50 < val < 5000:
                        dims.append(val)
                dims = sorted(set(dims))[:6]

                # Высота ручки
                handle_match = re.search(r'[Вв]ысота\s+ручки\s*[\:\s]*(\d+)', text)
                handle_height = int(handle_match.group(1)) if handle_match else None

                items.append({
                    "page": i + 1,
                    "position": pos_name,
                    "quantity": qty,
                    "articles": sorted(page_articles),
                    "dimensions": dims,
                    "handle_height": handle_height,
                })

        doc.close()

        # Сводка
        total_items = sum(it['quantity'] for it in items)

        log_activity("parse_kmd", file.filename,
                     f"Позиций: {len(items)}, артикулов: {len(all_articles)}")

        return {
            "status": "ok",
            "filename": file.filename,
            "items": items,
            "total_positions": len(items),
            "total_items": total_items,
            "unique_articles": sorted(all_articles),
            "articles_count": len(all_articles),
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path.unlink(missing_ok=True)


# ============== 4. ПАРСИНГ DXF ЧЕРТЕЖЕЙ ==============

@app.post("/api/parse-dxf")
async def api_parse_dxf(file: UploadFile = File(...)):
    """Разобрать DXF чертёж AutoCAD: слои, тексты, размеры, блоки, КМД-данные."""
    if not file.filename.lower().endswith((".dxf",)):
        raise HTTPException(status_code=400, detail="Ожидается файл формата .dxf")

    path = save_upload(file)

    try:
        result = parse_dxf_for_web(str(path))

        log_activity("parse_kmd", file.filename,
                     f"DXF: слоёв {len(result['layers'])}, текстов {len(result['texts'])}, "
                     f"размеров {len(result['dimensions'])}, блоков {len(result['blocks'])}")

        return {
            "status": "ok",
            "filename": file.filename,
            **result,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path.unlink(missing_ok=True)


# ============== 5. OCR-ПАРСИНГ СКАНИРОВАННЫХ ЧЕРТЕЖЕЙ ==============

@app.post("/api/ocr-parse")
async def api_ocr_parse(file: UploadFile = File(...)):
    """OCR-парсинг сканированного PDF: распознать текст, позиции, артикулы.

    Для каждой страницы:
    - Если PyMuPDF извлекает текстовый слой — использует его.
    - Если страница image-only — рендерит в изображение, прогоняет Tesseract
      (русский + английский, предобработка: grayscale, threshold, denoise).
    - Парсит позиции (Поз.X-N), артикулы (7-8 цифр), размеры.
    """
    path = save_upload(file)

    try:
        import fitz
        import io
        from PIL import Image

        doc = fitz.open(str(path))
        total_pages = len(doc)
        DPI = 300

        pages_result = []
        all_positions = []
        all_articles = set()
        ocr_page_count = 0
        text_page_count = 0

        for i in range(total_pages):
            page = doc[i]
            native_text = page.get_text().strip()

            has_text = len(native_text) > 30  # meaningful text threshold

            if has_text:
                # Страница с текстовым слоем — используем как есть
                text_page_count += 1
                ocr_text = ""
                final_text = native_text
            else:
                # Image-only страница — OCR
                ocr_page_count += 1
                mat = fitz.Matrix(DPI / 72, DPI / 72)
                pix = page.get_pixmap(matrix=mat)
                img = Image.open(io.BytesIO(pix.tobytes("png")))

                # Два прохода: block (psm 6) + sparse (psm 11)
                text_block = ocr_pil_image(img, lang="rus+eng",
                                           preprocess=True, sparse=False)
                text_sparse = ocr_pil_image(img, lang="rus+eng",
                                            preprocess=True, sparse=True)

                # Объединяем: берём более полный, добавляем уникальные строки
                if len(text_sparse) > len(text_block):
                    text_block, text_sparse = text_sparse, text_block

                base_lines = set(text_block.strip().splitlines())
                extra = [ln for ln in text_sparse.strip().splitlines()
                         if ln.strip() and ln.strip() not in base_lines]

                ocr_text = text_block.strip()
                if extra:
                    ocr_text += "\n" + "\n".join(extra)

                final_text = ocr_text

            # Парсим результаты из текста (native или OCR)
            positions = parse_positions(final_text)
            articles = parse_articles(final_text)
            dimensions = parse_dimensions(final_text)

            all_positions.extend(positions)
            all_articles.update(articles)

            pages_result.append({
                "page": i + 1,
                "has_text": has_text,
                "ocr_text": ocr_text if not has_text else "",
                "text_preview": final_text[:200] if final_text else "",
                "positions": positions,
                "articles": articles,
                "dimensions": dimensions,
            })

        doc.close()

        # Сводка
        total_qty = sum(p.get("quantity", 0) for p in all_positions)
        summary = {
            "total_pages": total_pages,
            "text_pages": text_page_count,
            "ocr_pages": ocr_page_count,
            "total_positions": len(all_positions),
            "total_quantity": total_qty,
            "unique_articles": sorted(all_articles),
            "articles_count": len(all_articles),
        }

        log_activity("parse_kmd", file.filename,
                     f"OCR: {ocr_page_count} стр., позиций: {len(all_positions)}, "
                     f"артикулов: {len(all_articles)}")

        return {
            "status": "ok",
            "filename": file.filename,
            "pages": pages_result,
            "summary": summary,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path.unlink(missing_ok=True)


# ============== 6. ЧЕК-ЛИСТ КМД ==============

def _run_checklist(full_text: str, page_texts: list[str]) -> list[dict]:
    """
    Чек-лист КМД для алюминиевых светопрозрачных конструкций (окна, витражи, фасады).
    Основан на ГОСТ 21.502-2016, СП 426.1325800.2018, ГОСТ 21519-2022
    и реальной практике АЛЬДМЕГА ЛАБ.

    Проверки сгруппированы по 7 категориям с весами:
    - Критические (вес 3): без них производство невозможно
    - Важные (вес 2): влияют на качество/сроки
    - Рекомендуемые (вес 1): улучшают полноту документации

    Возвращает список проверок [{category, check_name, passed, details, weight}, ...].
    """
    import re

    full_lower = full_text.lower()
    checks: list[dict] = []

    def add(category: str, name: str, passed: bool, details: str = "", weight: int = 2):
        checks.append({
            "category": category,
            "check_name": name,
            "passed": passed,
            "details": details,
            "weight": weight,
        })

    # ======================================================================
    # 1. ТИТУЛЬНЫЙ ЛИСТ И РЕКВИЗИТЫ (вес: критический)
    # ======================================================================
    cat = "Титульный лист и реквизиты"

    # Проверяем первые 3 страницы на наличие ключевых реквизитов
    first_pages = "\n".join(p.lower() for p in page_texts[:3])

    # Наименование объекта (адрес, название ЖК/объекта)
    has_object = bool(re.search(
        r'(объект|жилая застройка|жилой комплекс|жк\b|корпус|по адресу|'
        r'строительств|реконструкци|здание)',
        first_pages
    ))
    add(cat, "Наименование объекта строительства", has_object,
        "Объект строительства указан" if has_object
        else "Не найдено наименование объекта в первых страницах", 3)

    # Заказчик
    has_customer = bool(re.search(r'заказчик|заказ\s*чик', first_pages))
    add(cat, "Указан заказчик", has_customer,
        "Заказчик указан" if has_customer else "Информация о заказчике не найдена", 2)

    # Договор или номер КМД
    has_contract = bool(re.search(r'договор|контракт|кмд\s*от|№\s*\d', first_pages))
    add(cat, "Номер договора / документа", has_contract,
        "Реквизиты договора найдены" if has_contract
        else "Номер договора или документа не обнаружен", 2)

    # Исполнитель (ООО, ИП, ИНН, ОГРН)
    has_executor = bool(re.search(r'(ооо|ип\s|инн\s*\d|огрн\s*\d|генеральный директор)', first_pages))
    add(cat, "Указан исполнитель (организация)", has_executor,
        "Данные исполнителя найдены" if has_executor
        else "Исполнитель (организация) не указан", 2)

    # Тип конструкций в заголовке
    has_type = bool(re.search(
        r'(алюминиев|светопрозрачн|окн[аы]|витраж|фасад|двер[ьи]|балконн|'
        r'входн[аыеой]|раздвижн)',
        first_pages
    ))
    add(cat, "Указан тип конструкций (окна/витражи/фасады)", has_type,
        "Тип конструкций определён" if has_type
        else "Тип конструкций не указан в заглавии", 3)

    # Дата документа
    has_date = bool(re.search(
        r'(\d{2}\.\d{2}\.\d{4}|\d{4}\s*г\.?|от\s*\d{2}\.\d{2})', first_pages
    ))
    add(cat, "Дата документа", has_date,
        "Дата обнаружена" if has_date else "Дата документа не найдена", 1)

    # ======================================================================
    # 2. ПОЯСНИТЕЛЬНАЯ ЗАПИСКА
    # ======================================================================
    cat = "Пояснительная записка"

    has_note = bool(re.search(r'пояснительн\w*\s+запис', full_lower))
    add(cat, "Наличие пояснительной записки", has_note,
        "Пояснительная записка найдена" if has_note
        else "Пояснительная записка не обнаружена", 2)

    # Состав документации
    has_composition = bool(re.search(
        r'(в состав|состав\s+документации|входят|разделы)',
        full_lower
    ))
    add(cat, "Описан состав документации", has_composition,
        "Состав документации описан" if has_composition
        else "Состав документации не описан", 1)

    # Указания по монтажу
    has_mounting = bool(re.search(
        r'(монтаж|при\s+монтаже|установк|сборк[аеи]|указани[яе])',
        full_lower
    ))
    add(cat, "Указания по монтажу/сборке", has_mounting,
        "Указания по монтажу найдены" if has_mounting
        else "Указания по монтажу не обнаружены", 2)

    # Профильная система
    profile_systems = [
        'reynaers', 'masterline', 'conceptwall', 'hi-finity', 'alumil',
        'schuco', 'schüco', 'alutech', 'алютех', 'vidnal', 'виднал',
        'tatprof', 'татпроф', 'agrisovglass', 'realit', 'provedal',
        'newtek', 'ньютек', 'sial', 'сиал',
    ]
    found_system = None
    for ps in profile_systems:
        if ps in full_lower:
            found_system = ps
            break
    add(cat, "Указана профильная система", found_system is not None,
        f"Профильная система: {found_system}" if found_system
        else "Профильная система не идентифицирована", 3)

    # ======================================================================
    # 3. ЧЕРТЕЖИ ИЗДЕЛИЙ (КРИТИЧЕСКИЙ РАЗДЕЛ)
    # ======================================================================
    cat = "Чертежи изделий"

    # Позиции (Поз.О-1, Поз.БФ1, Поз.В-3 и т.п.)
    positions = re.findall(
        r'[Пп]оз\.?\s*([А-Яа-яA-Za-z]{0,3}\-?\d+[\w\-]*)',
        full_text
    )
    unique_positions = list(set(positions))
    add(cat, "Маркировка позиций изделий", len(unique_positions) > 0,
        f"Найдено {len(unique_positions)} уникальных позиций" if unique_positions
        else "Позиции изделий не обнаружены", 3)

    # Количество при позиции
    qty_records = re.findall(
        r'[Кк]оличество\s*:?\s*(\d+)', full_text
    )
    add(cat, "Указано количество изделий по позициям", len(qty_records) > 0,
        f"Найдено {len(qty_records)} записей с количеством (сумма: {sum(int(q) for q in qty_records)})"
        if qty_records else "Количество изделий не указано", 3)

    # Высота ручки
    handle_records = re.findall(
        r'[Вв]ысота\s+ручки\s*:?\s*(\d+)', full_text
    )
    add(cat, "Указана высота ручки", len(handle_records) > 0,
        f"Высота ручки указана для {len(handle_records)} изделий"
        if handle_records else "Высота ручки не указана", 2)

    # Размеры (3-4 значные числа, мм — габариты деталей)
    dims_mm = re.findall(r'\b(\d{3,4}(?:[,\.]\d{1,2})?)\b', full_text)
    dims_valid = [float(d.replace(',', '.')) for d in dims_mm if 50 < float(d.replace(',', '.')) < 5000]
    add(cat, "Наличие размеров деталей (мм)", len(dims_valid) > 10,
        f"Найдено {len(dims_valid)} размерных значений"
        if dims_valid else "Размеры не обнаружены", 3)

    # Виды (изнутри / снаружи)
    has_views = bool(re.search(r'вид\s+(изнутри|снаружи|спереди|сзади|сбоку)', full_lower))
    add(cat, "Указан вид (изнутри/снаружи)", has_views,
        "Ориентация вида указана" if has_views
        else "Ориентация вида (изнутри/снаружи) не указана", 2)

    # Разрезы A-A, B-B и т.п. (линии сечений на чертежах)
    sections = re.findall(r'\b([A-ZА-Я])\s*[\-–]\s*\1\b', full_text)
    add(cat, "Наличие линий сечений (A-A, B-B)", len(sections) > 0,
        f"Найдено {len(set(sections))} типов сечений" if sections
        else "Линии сечений не обнаружены", 2)

    # ======================================================================
    # 4. АРТИКУЛЫ И КОМПЛЕКТУЮЩИЕ (КРИТИЧЕСКИЙ РАЗДЕЛ)
    # ======================================================================
    cat = "Артикулы и комплектующие"

    # Артикулы профилей (7-значные номера — Reynaers, Schuco и др.)
    articles_7 = set(re.findall(r'\b(\d{7})\b', full_text))
    articles_valid = {a for a in articles_7 if int(a) > 100000}
    add(cat, "Артикулы профилей", len(articles_valid) >= 3,
        f"Найдено {len(articles_valid)} уникальных артикулов"
        if articles_valid else "Артикулы профилей не обнаружены", 3)

    # Артикулы крепежа/фурнитуры (часто формат XXXX.XXX или 6-7 цифр)
    fastener_arts = set(re.findall(r'\b(\d{4,5}\.\d{3,5})\b', full_text))
    add(cat, "Артикулы крепежа/фурнитуры", len(fastener_arts) > 0,
        f"Найдено {len(fastener_arts)} артикулов крепежа"
        if fastener_arts else "Артикулы крепежа не обнаружены (допустимо, если входят в 7-значные)", 1)

    # Крепёж (саморезы, анкеры, болты, винты)
    fasteners = re.findall(
        r'(саморез|анкер|болт|винт|дюбел|шуруп)\w*\s*\d',
        full_lower
    )
    add(cat, "Указан крепёж (саморезы, анкеры)", len(fasteners) > 0,
        f"Найдено {len(fasteners)} записей о крепеже" if fasteners
        else "Крепёж не указан", 2)

    # Уплотнители / шнуры
    seals = re.findall(
        r'(шнур|уплотнител|epdm|силикон|резин)\w*',
        full_lower
    )
    add(cat, "Указаны уплотнители/шнуры", len(seals) > 0,
        f"Найдено {len(seals)} упоминаний уплотнителей" if seals
        else "Уплотнители не указаны", 2)

    # ======================================================================
    # 5. УЗЛЫ И ПРИМЫКАНИЯ
    # ======================================================================
    cat = "Узлы и примыкания"

    # Узлы (сборки, обработки, примыкания)
    has_nodes = bool(re.search(
        r'(узел|узл[ыа]|сборк[аи]|обработк[аи]|примыкани[еяй])',
        full_lower
    ))
    add(cat, "Наличие узлов сборки/обработки", has_nodes,
        "Узлы найдены" if has_nodes else "Узлы сборки не обнаружены", 2)

    # Герметизация (силикон, ПСУЛ, вилатерм, мембрана)
    sealant_kw = ['псул', 'вилатерм', 'силикон', 'герметик', 'мембран', 'пенополиуретан', 'монтажн']
    sealants_found = [kw for kw in sealant_kw if kw in full_lower]
    add(cat, "Указана герметизация (ПСУЛ, силикон, вилатерм)", len(sealants_found) > 0,
        f"Найдено: {', '.join(sealants_found)}" if sealants_found
        else "Материалы герметизации не указаны", 2)

    # Импосты (горизонтальные/вертикальные разделители)
    has_impost = bool(re.search(r'импост', full_lower))
    add(cat, "Указаны импосты", has_impost,
        "Импосты обнаружены в документации" if has_impost
        else "Импосты не упоминаются (допустимо для простых конструкций)", 1)

    # ======================================================================
    # 6. ПОЛНОТА И КОНСИСТЕНТНОСТЬ
    # ======================================================================
    cat = "Полнота и консистентность"

    # Достаточный объём документа
    total_pages = len(page_texts)
    add(cat, "Достаточный объём документации", total_pages >= 3,
        f"Всего страниц: {total_pages}"
        + (" (слишком мало для комплекта КМД)" if total_pages < 3 else ""), 2)

    # Пустые страницы (страницы без извлекаемого текста)
    empty_pages = sum(1 for pt in page_texts if len(pt.strip()) < 5)
    # В КМД чертежи часто почти без текста — это нормально
    many_empty = empty_pages > total_pages * 0.5
    add(cat, "Доля страниц с данными", not many_empty,
        f"{total_pages - empty_pages} из {total_pages} страниц содержат текст"
        + (f" ({empty_pages} пустых — возможно, графические чертежи)" if empty_pages else ""), 1)

    # Каждая позиция имеет количество
    if unique_positions and qty_records:
        coverage = min(len(qty_records) / len(unique_positions), 1.0)
        add(cat, "Количество указано для всех позиций",
            coverage >= 0.8,
            f"Позиций: {len(unique_positions)}, записей с количеством: {len(qty_records)} "
            f"(покрытие: {coverage:.0%})", 3)
    elif unique_positions:
        add(cat, "Количество указано для всех позиций", False,
            f"Найдено {len(unique_positions)} позиций, но количество не указано", 3)

    # Все артикулы — валидные (7 цифр, > 100000)
    all_7digit = set(re.findall(r'\b(\d{7})\b', full_text))
    invalid_arts = {a for a in all_7digit if int(a) <= 100000}
    add(cat, "Все артикулы корректны (7 цифр)", len(invalid_arts) == 0,
        f"Некорректных артикулов: {len(invalid_arts)}" if invalid_arts
        else f"Все {len(articles_valid)} артикулов валидны", 1)

    # Единообразие формата позиций
    pos_formats = set()
    for p in unique_positions:
        if re.match(r'[А-ЯA-Z]{1,3}\-?\d+', p):
            pos_formats.add("БУКВЫ-ЦИФРЫ")
        elif re.match(r'\d+', p):
            pos_formats.add("ЦИФРЫ")
        else:
            pos_formats.add("ДРУГОЕ")
    add(cat, "Единообразный формат позиций", len(pos_formats) <= 2,
        f"Форматы: {', '.join(pos_formats)}" if pos_formats
        else "Позиции не найдены", 1)

    # ======================================================================
    # 7. ОФОРМЛЕНИЕ ДОКУМЕНТАЦИИ
    # ======================================================================
    cat = "Оформление документации"

    # Наличие слова КМД
    has_kmd = 'кмд' in full_lower
    add(cat, "Документ идентифицирован как КМД", has_kmd,
        "Маркировка КМД найдена" if has_kmd else "Слово «КМД» не найдено в тексте", 2)

    # Конструкторская/рабочая документация
    has_doc_type = bool(re.search(
        r'(конструкторск\w+\s+документаци|рабоч\w+\s+документаци|чертеж\w+\s+кмд)',
        full_lower
    ))
    add(cat, "Указан тип документации", has_doc_type,
        "Тип документации определён" if has_doc_type
        else "Тип документации не указан в заголовке", 1)

    # Подписи (генеральный директор, проверил, разработал)
    has_signatures = bool(re.search(
        r'(генеральный директор|директор|проверил|разработал|утвердил|гл\.\s*инженер|'
        r'нач\w*\s+отдел|[А-Я]\.\s*[А-Я]\.)',
        full_lower
    ))
    add(cat, "Наличие подписей / ответственных лиц", has_signatures,
        "Подписи/ФИО обнаружены" if has_signatures else "Подписи не обнаружены", 1)

    return checks


@app.post("/api/checklist")
async def api_checklist(file: UploadFile = File(...)):
    """
    Автоматический чек-лист КМД по 8 разделам АЛЬДМЕГА ЛАБ.
    Принимает PDF-файл, извлекает текст со всех страниц (PyMuPDF),
    прогоняет проверки и возвращает результат с оценкой.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Принимаются только PDF файлы")

    path = save_upload(file)

    try:
        import fitz

        doc = fitz.open(str(path))
        page_texts = [doc[i].get_text() for i in range(len(doc))]
        full_text = "\n".join(page_texts)
        total_pages = len(doc)
        doc.close()

        if not full_text.strip():
            raise HTTPException(
                status_code=400,
                detail="PDF не содержит извлекаемого текста (возможно, это скан-копия без OCR)",
            )

        checks = _run_checklist(full_text, page_texts)
        passed_checks = sum(1 for c in checks if c["passed"])
        total_checks = len(checks)
        # Взвешенная оценка: критические проверки (вес 3) влияют сильнее
        total_weight = sum(c.get("weight", 2) for c in checks)
        passed_weight = sum(c.get("weight", 2) for c in checks if c["passed"])
        overall_score = round(passed_weight / total_weight * 100, 1) if total_weight else 0.0

        log_activity("checklist", file.filename,
                     f"Оценка: {overall_score}%, пройдено: {passed_checks}/{total_checks}")

        return {
            "status": "ok",
            "filename": file.filename,
            "total_pages": total_pages,
            "checks": checks,
            "overall_score": overall_score,
            "total_checks": total_checks,
            "passed_checks": passed_checks,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path.unlink(missing_ok=True)


# ============== 7. КРОСС-ВАЛИДАЦИЯ ЧЕРТЁЖ vs СПЕЦИФИКАЦИЯ ==============

@app.post("/api/cross-validate")
async def api_cross_validate(
    drawing: UploadFile = File(...),
    spec: UploadFile = File(...),
):
    """Кросс-валидация: сопоставить артикулы/количества из чертежа (PDF/DXF)
    с заказной спецификацией (XLSX)."""
    drawing_path = save_upload(drawing)
    spec_path = save_upload(spec)

    try:
        import re
        import math
        import pandas as pd

        def safe_float(val, default=0.0):
            try:
                v = float(val)
                return default if (math.isnan(v) or math.isinf(v)) else v
            except (ValueError, TypeError):
                return default

        # ---- 1. Извлечь данные из чертежа ----
        drawing_name = drawing.filename.lower()
        drawing_articles: dict[str, float] = {}  # article -> total qty
        drawing_positions: list[dict] = []
        unlinked_positions: list[str] = []

        if drawing_name.endswith(".dxf"):
            # DXF
            dxf_result = parse_dxf_for_web(str(drawing_path))
            # Собираем артикулы из текстов DXF
            all_texts = " ".join(t.get("text", "") for t in dxf_result.get("texts", []))
            for m in re.finditer(r'\b(\d{7,8})\b', all_texts):
                art = m.group(1)
                if int(art) > 100000:
                    drawing_articles[art] = drawing_articles.get(art, 0) + 1

            # Позиции из kmd_data
            for item in dxf_result.get("kmd_data", {}).get("items", []):
                pos = item.get("position", "")
                qty = item.get("quantity", 0)
                arts = item.get("articles", [])
                drawing_positions.append({"position": pos, "quantity": qty, "articles": arts})
                if not arts:
                    unlinked_positions.append(pos)
                for a in arts:
                    drawing_articles[a] = drawing_articles.get(a, 0) + qty

        elif drawing_name.endswith(".pdf"):
            # PDF — тот же алгоритм, что и /api/parse-kmd
            import fitz
            doc = fitz.open(str(drawing_path))

            for i in range(len(doc)):
                text = doc[i].get_text().strip()
                if not text:
                    continue

                pos_matches = re.finditer(
                    r'Поз\.?\s*([А-Яа-яA-Za-z0-9\-\.]+)\s*,?\s*Количество\s*:?\s*(\d+)',
                    text,
                )
                for m in pos_matches:
                    pos_name = m.group(1)
                    qty = int(m.group(2))

                    page_articles: list[str] = []
                    for am in re.finditer(r'\b(\d{7,8})\b', text):
                        art = am.group(1)
                        if int(art) > 100000:
                            page_articles.append(art)

                    drawing_positions.append({
                        "position": pos_name,
                        "quantity": qty,
                        "articles": sorted(set(page_articles)),
                    })

                    if not page_articles:
                        unlinked_positions.append(pos_name)

                    for a in set(page_articles):
                        drawing_articles[a] = drawing_articles.get(a, 0) + qty

                # Также собираем артикулы без привязки к позициям (свободные)
                for am in re.finditer(r'\b(\d{7,8})\b', text):
                    art = am.group(1)
                    if int(art) > 100000 and art not in drawing_articles:
                        drawing_articles[art] = drawing_articles.get(art, 0)

            doc.close()
        else:
            raise HTTPException(
                status_code=400,
                detail="Чертёж должен быть в формате PDF или DXF",
            )

        # ---- 2. Извлечь данные из спецификации XLSX ----
        df_spec = extract_articles(str(spec_path))

        spec_articles: dict[str, float] = {}
        if not df_spec.empty:
            for _, row in df_spec.iterrows():
                art = str(row.get("Артикул_норм", "")).strip().rstrip(".")
                qty = safe_float(row.get("Количество", 0))
                if art and art != "nan":
                    spec_articles[art] = spec_articles.get(art, 0) + qty

        # Нормализация ключей чертежа (rstrip('.'))
        drawing_articles_norm: dict[str, float] = {}
        for art, qty in drawing_articles.items():
            drawing_articles_norm[art.rstrip(".")] = (
                drawing_articles_norm.get(art.rstrip("."), 0) + qty
            )

        # ---- 3. Кросс-валидация ----
        all_drawing = set(drawing_articles_norm.keys())
        all_spec = set(spec_articles.keys())

        matches = []
        qty_mismatches = []
        missing_in_spec = []
        extra_in_spec = []

        # Совпадения и расхождения по количеству
        for art in sorted(all_drawing & all_spec):
            d_qty = safe_float(drawing_articles_norm[art])
            s_qty = safe_float(spec_articles[art])
            if abs(d_qty - s_qty) < 0.01:
                matches.append({
                    "article": art,
                    "drawing_qty": d_qty,
                    "spec_qty": s_qty,
                })
            else:
                qty_mismatches.append({
                    "article": art,
                    "drawing_qty": d_qty,
                    "spec_qty": s_qty,
                    "diff": round(d_qty - s_qty, 2),
                })

        # Есть в чертеже, нет в спецификации
        for art in sorted(all_drawing - all_spec):
            d_qty = safe_float(drawing_articles_norm[art])
            missing_in_spec.append({"article": art, "drawing_qty": d_qty})

        # Есть в спецификации, нет в чертеже
        for art in sorted(all_spec - all_drawing):
            s_qty = safe_float(spec_articles[art])
            extra_in_spec.append({"article": art, "spec_qty": s_qty})

        # ---- 4. Сводка ----
        total_d = len(all_drawing)
        total_s = len(all_spec)
        matched_count = len(matches)
        match_rate = round(matched_count / total_d * 100, 1) if total_d else 0.0

        summary = {
            "total_drawing_articles": total_d,
            "total_spec_articles": total_s,
            "matched": matched_count,
            "missing_in_spec": len(missing_in_spec),
            "extra_in_spec": len(extra_in_spec),
            "qty_mismatches": len(qty_mismatches),
            "match_rate": match_rate,
        }

        log_activity(
            "cross_validate",
            f"{drawing.filename} / {spec.filename}",
            f"Совпадений: {matched_count}, расхождений: {len(qty_mismatches)}, "
            f"нет в спец.: {len(missing_in_spec)}, лишних: {len(extra_in_spec)}",
        )

        return {
            "status": "ok",
            "drawing_file": drawing.filename,
            "spec_file": spec.filename,
            "drawing_articles": sorted(all_drawing),
            "spec_articles": sorted(all_spec),
            "matches": matches,
            "missing_in_spec": missing_in_spec,
            "extra_in_spec": extra_in_spec,
            "qty_mismatches": qty_mismatches,
            "unlinked_positions": sorted(set(unlinked_positions)),
            "summary": summary,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        drawing_path.unlink(missing_ok=True)
        spec_path.unlink(missing_ok=True)


# ============== 8. СРАВНЕНИЕ ВЕРСИЙ PDF ==============

def _classify_page(text: str) -> str:
    """Определить тип страницы КМД по содержимому текста."""
    if not text or not text.strip():
        return "пустая"
    text_lower = text.lower()
    if any(w in text_lower for w in ['титульный', 'договор', 'заказчик']):
        return "титульный лист"
    if any(w in text_lower for w in ['пояснительная', 'записка', 'в соответствии']):
        return "пояснительная записка"
    if any(w in text_lower for w in ['спецификация', 'ведомость']):
        return "спецификация"
    if 'поз.' in text_lower or 'количество' in text_lower:
        return "чертёж изделия"
    if any(w in text_lower for w in ['обработка', 'сборка', 'фрезеровка']):
        return "чертёж обработки"
    if any(w in text_lower for w in ['фасад', 'план', 'разрез']):
        return "план/фасад"
    if any(w in text_lower for w in ['узел', 'сечение']):
        return "узел/сечение"
    return "чертёж"


def _extract_kmd_data(text: str):
    """Извлечь КМД-данные: позиции, артикулы, количество."""
    import re
    positions = {}
    for m in re.finditer(
        r'[Пп]оз\.?\s*([А-Яа-яA-Za-z0-9\-\.]+)\s*,?\s*[Кк]оличество\s*:?\s*(\d+)',
        text,
    ):
        positions[m.group(1)] = int(m.group(2))

    articles = set()
    for m in re.finditer(r'\b(\d{7,8})\b', text):
        art = m.group(1)
        if int(art) > 100000:
            articles.add(art)

    return positions, articles


@app.post("/api/compare-pdf")
async def api_compare_pdf(
    file_a: UploadFile = File(...),
    file_b: UploadFile = File(...),
):
    """Сравнить две версии PDF КМД-документа и показать все различия."""
    if not file_a.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Файл А должен быть PDF")
    if not file_b.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Файл Б должен быть PDF")

    path_a = save_upload(file_a)
    path_b = save_upload(file_b)

    try:
        import fitz
        import re
        import difflib

        # --- Извлечение текста из обоих PDF ---
        doc_a = fitz.open(str(path_a))
        doc_b = fitz.open(str(path_b))
        pages_a = len(doc_a)
        pages_b = len(doc_b)

        texts_a = []
        types_a = []
        for i in range(pages_a):
            t = doc_a[i].get_text().strip()
            texts_a.append(t)
            types_a.append(_classify_page(t))

        texts_b = []
        types_b = []
        for i in range(pages_b):
            t = doc_b[i].get_text().strip()
            texts_b.append(t)
            types_b.append(_classify_page(t))

        doc_a.close()
        doc_b.close()

        # --- Сопоставление страниц по содержимому (similarity matching) ---
        SIMILARITY_THRESHOLD = 0.3

        # Вычисляем similarity matrix
        sim_pairs = []
        for ai in range(pages_a):
            if not texts_a[ai]:
                continue
            for bi in range(pages_b):
                if not texts_b[bi]:
                    continue
                ratio = difflib.SequenceMatcher(
                    None, texts_a[ai], texts_b[bi]
                ).ratio()
                if ratio >= SIMILARITY_THRESHOLD:
                    sim_pairs.append((ratio, ai, bi))

        # Greedy matching: лучшие пары первыми
        matched_a_to_b = {}  # a_idx -> (b_idx, ratio)
        matched_b = set()
        sim_pairs.sort(reverse=True)
        for ratio, ai, bi in sim_pairs:
            if ai in matched_a_to_b or bi in matched_b:
                continue
            matched_a_to_b[ai] = (bi, ratio)
            matched_b.add(bi)

        # --- Deleted pages (в A, но нет match в B) ---
        deleted_pages = []
        for ai in range(pages_a):
            if ai not in matched_a_to_b:
                deleted_pages.append({
                    "page": ai + 1,
                    "type": types_a[ai],
                    "preview": texts_a[ai][:100] if texts_a[ai] else "",
                })

        # --- Added pages (в B, но нет match из A) ---
        added_pages = []
        for bi in range(pages_b):
            if bi not in matched_b:
                added_pages.append({
                    "page": bi + 1,
                    "type": types_b[bi],
                    "preview": texts_b[bi][:100] if texts_b[bi] else "",
                })

        # --- Modified pages (matched, но similarity < 1.0) ---
        modified_pages = []
        unchanged_count = 0
        for ai, (bi, ratio) in matched_a_to_b.items():
            if ratio >= 0.9999:
                unchanged_count += 1
                continue

            # Вычисляем unified diff
            lines_a = texts_a[ai].splitlines()
            lines_b = texts_b[bi].splitlines()
            diff_lines = list(difflib.unified_diff(
                lines_a, lines_b, lineterm='',
                fromfile=f'стр.{ai+1}', tofile=f'стр.{bi+1}',
            ))

            added_text = [ln[1:] for ln in diff_lines if ln.startswith('+') and not ln.startswith('+++')]
            removed_text = [ln[1:] for ln in diff_lines if ln.startswith('-') and not ln.startswith('---')]

            changes = []
            for ln in diff_lines:
                if ln.startswith('@@') or ln.startswith('+++') or ln.startswith('---'):
                    continue
                if ln.startswith('+') or ln.startswith('-'):
                    changes.append(ln)

            modified_pages.append({
                "page_a": ai + 1,
                "page_b": bi + 1,
                "similarity": round(ratio, 4),
                "changes": changes[:20],
                "added_text": added_text[:10],
                "removed_text": removed_text[:10],
            })

        # --- KMD-specific changes ---
        full_text_a = "\n".join(texts_a)
        full_text_b = "\n".join(texts_b)

        positions_a, articles_a = _extract_kmd_data(full_text_a)
        positions_b, articles_b = _extract_kmd_data(full_text_b)

        removed_positions = sorted(set(positions_a.keys()) - set(positions_b.keys()))
        added_positions = sorted(set(positions_b.keys()) - set(positions_a.keys()))

        removed_articles = sorted(articles_a - articles_b)
        added_articles = sorted(articles_b - articles_a)

        quantity_changes = []
        for pos in sorted(set(positions_a.keys()) & set(positions_b.keys())):
            if positions_a[pos] != positions_b[pos]:
                quantity_changes.append({
                    "position": pos,
                    "old": positions_a[pos],
                    "new": positions_b[pos],
                })

        kmd_changes = {
            "removed_positions": removed_positions,
            "added_positions": added_positions,
            "removed_articles": removed_articles,
            "added_articles": added_articles,
            "quantity_changes": quantity_changes,
        }

        # --- Overall similarity ---
        if pages_a > 0 and pages_b > 0:
            all_ratios = [ratio for _, (_, ratio) in matched_a_to_b.items()]
            overall_sim = round(sum(all_ratios) / max(pages_a, pages_b), 4) if all_ratios else 0.0
        else:
            overall_sim = 0.0

        summary = {
            "deleted_pages": len(deleted_pages),
            "added_pages": len(added_pages),
            "modified_pages": len(modified_pages),
            "unchanged_pages": unchanged_count,
            "overall_similarity": overall_sim,
        }

        log_activity(
            "compare_pdf",
            f"{file_a.filename} / {file_b.filename}",
            f"Удалено: {len(deleted_pages)}, добавлено: {len(added_pages)}, "
            f"изменено: {len(modified_pages)}, схожесть: {overall_sim:.0%}",
        )

        return {
            "status": "ok",
            "file_a": file_a.filename,
            "file_b": file_b.filename,
            "pages_a": pages_a,
            "pages_b": pages_b,
            "deleted_pages": deleted_pages,
            "added_pages": added_pages,
            "modified_pages": modified_pages,
            "kmd_changes": kmd_changes,
            "summary": summary,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path_a.unlink(missing_ok=True)
        path_b.unlink(missing_ok=True)


# ============== 9. ПАКЕТНАЯ ОБРАБОТКА ==============

MAX_ZIP_SIZE = 100 * 1024 * 1024  # 100 MB


@app.post("/api/batch-process")
async def api_batch_process(file: UploadFile = File(...)):
    """
    Пакетная обработка ZIP-архива с проектом КМД.
    Принимает ZIP с PDF, DXF, XLSX файлами, прогоняет все доступные проверки
    и возвращает единый отчёт.
    """
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Принимаются только ZIP-архивы")

    zip_path = save_upload(file)
    zip_size = zip_path.stat().st_size

    if zip_size > MAX_ZIP_SIZE:
        zip_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"Размер архива ({zip_size // 1024 // 1024} МБ) превышает лимит 100 МБ",
        )

    tmp_dir = tempfile.mkdtemp(prefix="kmd_batch_")

    try:
        import fitz

        # Распаковываем
        with zipfile.ZipFile(str(zip_path), "r") as zf:
            total_uncompressed = sum(i.file_size for i in zf.infolist())
            if total_uncompressed > MAX_ZIP_SIZE * 3:
                raise HTTPException(
                    status_code=400,
                    detail="Распакованный размер слишком велик",
                )
            zf.extractall(tmp_dir)

        # Классификация файлов
        files_found = {"pdf": [], "dxf": [], "xlsx": [], "other": []}
        tmp_path = Path(tmp_dir)

        for fp in sorted(tmp_path.rglob("*")):
            if fp.is_dir():
                continue
            if fp.name.startswith(".") or fp.name.startswith("__"):
                continue
            ext = fp.suffix.lower()
            name = fp.name
            if ext == ".pdf":
                files_found["pdf"].append(name)
            elif ext == ".dxf":
                files_found["dxf"].append(name)
            elif ext in (".xlsx", ".xls"):
                files_found["xlsx"].append(name)
            else:
                files_found["other"].append(name)

        # --- PDF обработка ---
        pdf_results = []
        all_issues = []
        total_pdf_pages = 0
        all_unique_articles = set()
        all_positions_count = 0

        for pdf_name in files_found["pdf"]:
            pdf_files = list(tmp_path.rglob(pdf_name))
            if not pdf_files:
                continue
            pdf_path = pdf_files[0]

            try:
                doc = fitz.open(str(pdf_path))
                page_texts = [doc[i].get_text() for i in range(len(doc))]
                full_text = "\n".join(page_texts)
                pages = len(doc)
                doc.close()
                total_pdf_pages += pages

                if full_text.strip():
                    checks = _run_checklist(full_text, page_texts)
                    passed = sum(1 for c in checks if c["passed"])
                    total = len(checks)
                    tw = sum(c.get("weight", 2) for c in checks)
                    pw = sum(c.get("weight", 2) for c in checks if c["passed"])
                    score = round(pw / tw * 100, 1) if tw else 0.0
                else:
                    checks = []
                    passed = 0
                    total = 0
                    score = 0.0

                positions_found = set()
                articles_found = set()

                for pt in page_texts:
                    for m in _re.finditer(
                        r'Поз\.?\s*([А-Яа-яA-Za-z0-9\-\.]+)', pt,
                    ):
                        positions_found.add(m.group(1))
                    for m in _re.finditer(r'\b(\d{7,8})\b', pt):
                        art = m.group(1)
                        if int(art) > 100000:
                            articles_found.add(art)

                all_unique_articles.update(articles_found)
                all_positions_count += len(positions_found)

                issues = [c["check_name"] for c in checks if not c["passed"]]
                critical_keywords = [
                    "титульн", "спецификаци", "пояснительн", "позиций",
                ]
                for issue in issues:
                    issue_lower = issue.lower()
                    if any(kw in issue_lower for kw in critical_keywords):
                        all_issues.append({"file": pdf_name, "issue": issue, "severity": "critical"})
                    else:
                        all_issues.append({"file": pdf_name, "issue": issue, "severity": "warning"})

                pdf_results.append({
                    "filename": pdf_name,
                    "total_pages": pages,
                    "checklist_score": score,
                    "passed_checks": passed,
                    "total_checks": total,
                    "positions_found": len(positions_found),
                    "articles_found": len(articles_found),
                    "issues": issues,
                })

            except Exception as e:
                pdf_results.append({
                    "filename": pdf_name,
                    "total_pages": 0,
                    "checklist_score": 0,
                    "passed_checks": 0,
                    "total_checks": 0,
                    "positions_found": 0,
                    "articles_found": 0,
                    "issues": [f"Ошибка обработки: {str(e)}"],
                })
                all_issues.append({"file": pdf_name, "issue": f"Ошибка обработки: {str(e)}", "severity": "critical"})

        # --- DXF обработка ---
        dxf_results = []
        for dxf_name in files_found["dxf"]:
            dxf_files = list(tmp_path.rglob(dxf_name))
            if not dxf_files:
                continue
            dxf_path = dxf_files[0]

            try:
                result = parse_dxf_for_web(str(dxf_path))

                dxf_positions = set()
                dxf_articles = set()
                for txt_entry in result.get("texts", []):
                    txt = txt_entry.get("text", "") if isinstance(txt_entry, dict) else str(txt_entry)
                    for m in _re.finditer(r'[А-ЯA-Z]\s*[\-\.]\s*\d+', txt):
                        dxf_positions.add(m.group(0).strip())
                    for m in _re.finditer(r'\b(\d{7,8})\b', txt):
                        art = m.group(1)
                        if int(art) > 100000:
                            dxf_articles.add(art)
                            all_unique_articles.add(art)

                all_positions_count += len(dxf_positions)

                dxf_results.append({
                    "filename": dxf_name,
                    "layers": len(result.get("layers", [])),
                    "texts": len(result.get("texts", [])),
                    "dimensions": len(result.get("dimensions", [])),
                    "positions": sorted(dxf_positions),
                    "articles": sorted(dxf_articles),
                })

            except Exception as e:
                dxf_results.append({
                    "filename": dxf_name,
                    "layers": 0,
                    "texts": 0,
                    "dimensions": 0,
                    "positions": [],
                    "articles": [],
                    "error": str(e),
                })
                all_issues.append({"file": dxf_name, "issue": f"Ошибка DXF: {str(e)}", "severity": "warning"})

        # --- XLSX обработка ---
        xlsx_results = []
        for xlsx_name in files_found["xlsx"]:
            xlsx_files = list(tmp_path.rglob(xlsx_name))
            if not xlsx_files:
                continue
            xlsx_path = xlsx_files[0]

            try:
                df = extract_articles(str(xlsx_path))
                xlsx_articles = set()
                if not df.empty and "Артикул_норм" in df.columns:
                    xlsx_articles = set(df["Артикул_норм"].dropna().astype(str).tolist())
                    all_unique_articles.update(xlsx_articles)

                xlsx_results.append({
                    "filename": xlsx_name,
                    "total_positions": len(df),
                    "articles_count": len(xlsx_articles),
                })

            except Exception as e:
                xlsx_results.append({
                    "filename": xlsx_name,
                    "total_positions": 0,
                    "articles_count": 0,
                    "error": str(e),
                })
                all_issues.append({"file": xlsx_name, "issue": f"Ошибка XLSX: {str(e)}", "severity": "warning"})

        # --- Итоговая сводка ---
        total_files = sum(len(v) for v in files_found.values())
        scores = [r["checklist_score"] for r in pdf_results if r["checklist_score"] > 0]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
        critical_count = sum(1 for i in all_issues if i["severity"] == "critical")
        warning_count = sum(1 for i in all_issues if i["severity"] == "warning")

        log_activity(
            "batch",
            file.filename,
            f"Файлов: {total_files}, PDF: {len(files_found['pdf'])}, "
            f"DXF: {len(files_found['dxf'])}, оценка: {avg_score}%",
        )

        return {
            "status": "ok",
            "archive_name": file.filename,
            "files_found": files_found,
            "pdf_results": pdf_results,
            "dxf_results": dxf_results,
            "xlsx_results": xlsx_results,
            "issues": all_issues,
            "overall_summary": {
                "total_files": total_files,
                "total_pdf_pages": total_pdf_pages,
                "avg_checklist_score": avg_score,
                "total_positions": all_positions_count,
                "total_unique_articles": len(all_unique_articles),
                "critical_issues": critical_count,
                "warnings": warning_count,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        zip_path.unlink(missing_ok=True)
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ============== 11. ГЕНЕРАЦИЯ СПЕЦИФИКАЦИИ ==============

def _extract_kmd_data_from_pdf(pdf_path: str) -> list[dict]:
    """Извлечь КМД-данные из PDF: позиции, артикулы, размеры, цвета."""
    import fitz
    import re

    doc = fitz.open(pdf_path)
    raw_items: list[dict] = []

    for i in range(len(doc)):
        text = doc[i].get_text().strip()
        if not text:
            continue

        page_num = i + 1

        # Ищем позиции: "Поз.О-1", "Поз. Д-3", "Поз.ОК-12"
        pos_matches = list(re.finditer(
            r'Поз\.?\s*([А-Яа-яA-Za-z]{1,3}\s*[\-\.]\s*\d{1,3})',
            text
        ))

        # Ищем артикулы (7-8 цифр > 100000)
        page_articles = []
        for am in re.finditer(r'\b(\d{7,8})\b', text):
            art = am.group(1)
            if int(art) > 100000:
                page_articles.append(art)

        # Ищем количество
        qty_match = re.search(r'Количество\s*:?\s*(\d+)', text)
        quantity = int(qty_match.group(1)) if qty_match else 0

        # Ищем размеры WxH
        dim_wxh = re.findall(r'(\d{3,4})\s*[xхXХ×]\s*(\d{3,4})', text)
        # Отдельные размеры 50-5000 мм
        individual_dims = []
        for dm in re.finditer(r'\b(\d{2,4}(?:[,\.]\d{1,2})?)\b', text):
            val = float(dm.group(1).replace(',', '.'))
            if 50 <= val <= 5000:
                individual_dims.append(int(val))
        individual_dims = sorted(set(individual_dims))[:8]

        # Ищем цвет/RAL
        color = ""
        ral_match = re.search(r'RAL\s*(\d{4})', text, re.IGNORECASE)
        if ral_match:
            color = f"RAL{ral_match.group(1)}"
        else:
            color_match = re.search(
                r'(?:цвет|окраска|покрытие)\s*[:;\-]?\s*([^\n,]{2,30})',
                text, re.IGNORECASE,
            )
            if color_match:
                color = color_match.group(1).strip()

        # Ищем описания профилей (текст рядом с артикулами)
        descriptions: dict[str, str] = {}
        for art in page_articles:
            desc_match = re.search(
                rf'([А-Яа-яA-Za-z][^\n]{{5,60}})\s*{art}|{art}\s+([А-Яа-яA-Za-z][^\n]{{5,60}})',
                text,
            )
            if desc_match:
                descriptions[art] = (desc_match.group(1) or desc_match.group(2) or "").strip()

        if pos_matches:
            for pm in pos_matches:
                pos_name = pm.group(1).replace(' ', '')
                raw_items.append({
                    "position": pos_name,
                    "articles": list(set(page_articles)),
                    "descriptions": descriptions,
                    "quantity": quantity,
                    "dimensions": individual_dims,
                    "dim_wxh": [f"{w}x{h}" for w, h in dim_wxh],
                    "color": color,
                    "page": page_num,
                })
        elif page_articles:
            raw_items.append({
                "position": f"Стр.{page_num}",
                "articles": list(set(page_articles)),
                "descriptions": descriptions,
                "quantity": quantity,
                "dimensions": individual_dims,
                "dim_wxh": [f"{w}x{h}" for w, h in dim_wxh],
                "color": color,
                "page": page_num,
            })

    doc.close()

    # Группируем по позиции
    grouped: dict[str, dict] = {}
    for item in raw_items:
        pos = item["position"]
        if pos not in grouped:
            grouped[pos] = {
                "position": pos,
                "articles": [],
                "descriptions": {},
                "quantity": item["quantity"],
                "dimensions": [],
                "dim_wxh": [],
                "color": item["color"],
                "page": item["page"],
            }
        g = grouped[pos]
        g["articles"].extend(item["articles"])
        g["descriptions"].update(item["descriptions"])
        if item["quantity"] and not g["quantity"]:
            g["quantity"] = item["quantity"]
        g["dimensions"].extend(item["dimensions"])
        g["dim_wxh"].extend(item["dim_wxh"])
        if item["color"] and not g["color"]:
            g["color"] = item["color"]

    # Дедупликация
    positions = []
    for pos_name, g in grouped.items():
        g["articles"] = sorted(set(g["articles"]))
        g["dimensions"] = sorted(set(g["dimensions"]))
        g["dim_wxh"] = sorted(set(g["dim_wxh"]))
        positions.append(g)

    return positions


def _generate_spec_xlsx(positions: list[dict], source_file: str) -> Path:
    """Сгенерировать XLSX спецификацию из извлечённых позиций."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = Workbook()

    # --- Лист 1: Спецификация ---
    ws = wb.active
    ws.title = "Спецификация"

    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="212529", end_color="212529", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin", color="DEE2E6"),
        right=Side(style="thin", color="DEE2E6"),
        top=Side(style="thin", color="DEE2E6"),
        bottom=Side(style="thin", color="DEE2E6"),
    )
    alt_fill = PatternFill(start_color="F8F9FA", end_color="F8F9FA", fill_type="solid")

    headers = ["No", "Позиция", "Артикул", "Описание", "Количество",
               "Ед.изм.", "Цвет", "Размеры", "Примечание"]
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    row_num = 2
    global_idx = 0
    for pos in positions:
        articles = pos.get("articles", [])
        descriptions = pos.get("descriptions", {})
        dims_str = ", ".join(pos.get("dim_wxh", []))
        if not dims_str and pos.get("dimensions"):
            dims_str = " x ".join(str(d) for d in pos["dimensions"][:4])

        if not articles:
            global_idx += 1
            row_data = [
                global_idx, pos["position"], "", "",
                pos.get("quantity", 0) or "", "шт.",
                pos.get("color", ""), dims_str,
                f"стр. {pos.get('page', '')}",
            ]
            for col_idx, val in enumerate(row_data, 1):
                cell = ws.cell(row=row_num, column=col_idx, value=val)
                cell.border = thin_border
                cell.alignment = Alignment(vertical="center")
                if row_num % 2 == 0:
                    cell.fill = alt_fill
            row_num += 1
        else:
            for art in articles:
                global_idx += 1
                desc = descriptions.get(art, "")
                row_data = [
                    global_idx, pos["position"], art,
                    desc[:60] if desc else "",
                    pos.get("quantity", 0) or "", "шт.",
                    pos.get("color", ""), dims_str,
                    f"стр. {pos.get('page', '')}",
                ]
                for col_idx, val in enumerate(row_data, 1):
                    cell = ws.cell(row=row_num, column=col_idx, value=val)
                    cell.border = thin_border
                    cell.alignment = Alignment(vertical="center")
                    if row_num % 2 == 0:
                        cell.fill = alt_fill
                row_num += 1

    # Авто-ширина колонок
    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            try:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 8), 40)

    # --- Лист 2: Сводка ---
    ws2 = wb.create_sheet("Сводка")

    all_articles = set()
    total_qty = 0
    all_colors = set()
    all_dims = []
    for pos in positions:
        all_articles.update(pos.get("articles", []))
        total_qty += pos.get("quantity", 0) or 0
        if pos.get("color"):
            all_colors.add(pos["color"])
        all_dims.extend(pos.get("dimensions", []))

    summary_data = [
        ["Сводка по спецификации", ""],
        ["Исходный файл", source_file],
        ["Дата генерации", datetime.now().strftime("%d.%m.%Y %H:%M")],
        ["", ""],
        ["Всего позиций", len(positions)],
        ["Уникальных артикулов", len(all_articles)],
        ["Общее количество изделий", total_qty],
        ["Цвета", ", ".join(sorted(all_colors)) if all_colors else "Не указаны"],
        ["Диапазон размеров",
         f"{min(all_dims)} - {max(all_dims)} мм" if all_dims else "Не указан"],
    ]

    summary_header_font = Font(name="Arial", size=11, bold=True)
    for r_idx, (label, value) in enumerate(summary_data, 1):
        cell_a = ws2.cell(row=r_idx, column=1, value=label)
        cell_b = ws2.cell(row=r_idx, column=2, value=value)
        cell_a.border = thin_border
        cell_b.border = thin_border
        if r_idx == 1:
            cell_a.font = Font(name="Arial", size=12, bold=True, color="FFFFFF")
            cell_a.fill = header_fill
            cell_b.fill = header_fill
        else:
            cell_a.font = summary_header_font

    ws2.column_dimensions["A"].width = 30
    ws2.column_dimensions["B"].width = 40

    result_name = f"spec_{uuid.uuid4().hex[:8]}.xlsx"
    result_path = RESULTS_DIR / result_name
    wb.save(str(result_path))
    return result_path


@app.post("/api/generate-spec")
async def api_generate_spec(file: UploadFile = File(...)):
    """Сгенерировать XLSX спецификацию из КМД чертежа (PDF или DXF)."""
    fname_lower = file.filename.lower()
    if not fname_lower.endswith((".pdf", ".dxf")):
        raise HTTPException(status_code=400, detail="Принимаются файлы PDF или DXF")

    path = save_upload(file)

    try:
        import re

        source_type = "dxf" if fname_lower.endswith(".dxf") else "pdf"

        if source_type == "pdf":
            positions = _extract_kmd_data_from_pdf(str(path))
        else:
            # DXF
            dxf_data = parse_dxf_for_web(str(path))
            positions = []
            dxf_articles = set()
            dxf_dims = []

            for t in dxf_data.get("texts", []):
                txt = t.get("text", "")
                for am in re.finditer(r'\b(\d{7,8})\b', txt):
                    art = am.group(1)
                    if int(art) > 100000:
                        dxf_articles.add(art)

            for d in dxf_data.get("dimensions", []):
                val = d.get("measurement", 0)
                if 50 <= val <= 5000:
                    dxf_dims.append(int(val))

            pos_found: dict[str, dict] = {}
            for t in dxf_data.get("texts", []):
                txt = t.get("text", "")
                pm = re.search(
                    r'Поз\.?\s*([А-Яа-яA-Za-z]{1,3}\s*[\-\.]\s*\d{1,3})', txt,
                )
                if pm:
                    pos_name = pm.group(1).replace(' ', '')
                    if pos_name not in pos_found:
                        pos_found[pos_name] = {
                            "position": pos_name,
                            "articles": [], "descriptions": {},
                            "quantity": 0, "dimensions": [],
                            "dim_wxh": [], "color": "", "page": 1,
                        }

            if pos_found:
                for pos_name, pdata in pos_found.items():
                    pdata["articles"] = sorted(dxf_articles)
                    pdata["dimensions"] = sorted(set(dxf_dims))[:8]
                positions = list(pos_found.values())
            elif dxf_articles or dxf_dims:
                positions = [{
                    "position": "DXF",
                    "articles": sorted(dxf_articles),
                    "descriptions": {}, "quantity": 0,
                    "dimensions": sorted(set(dxf_dims))[:8],
                    "dim_wxh": [], "color": "", "page": 1,
                }]

        # Генерируем XLSX
        result_path = _generate_spec_xlsx(positions, file.filename)
        result_name = result_path.name

        # Собираем сводку
        all_articles_set = set()
        total_qty = 0
        all_colors = set()
        all_dims_list = []
        for pos in positions:
            all_articles_set.update(pos.get("articles", []))
            total_qty += pos.get("quantity", 0) or 0
            if pos.get("color"):
                all_colors.add(pos["color"])
            all_dims_list.extend(pos.get("dimensions", []))

        response_positions = []
        for pos in positions:
            art_list = []
            for art in pos.get("articles", []):
                art_list.append({
                    "article": art,
                    "description": pos.get("descriptions", {}).get(art, ""),
                    "quantity": pos.get("quantity", 0),
                })
            dims_str = ", ".join(pos.get("dim_wxh", []))
            if not dims_str and pos.get("dimensions"):
                dims_str = " x ".join(str(d) for d in pos["dimensions"][:4])
            response_positions.append({
                "position": pos["position"],
                "articles": art_list,
                "dimensions": pos.get("dimensions", []),
                "dimensions_str": dims_str,
                "color": pos.get("color", ""),
                "quantity": pos.get("quantity", 0),
                "page": pos.get("page", 0),
            })

        summary = {
            "total_positions": len(positions),
            "total_articles": len(all_articles_set),
            "total_items": total_qty,
            "unique_colors": sorted(all_colors),
            "dimension_range": (
                f"{min(all_dims_list)} - {max(all_dims_list)} мм"
                if all_dims_list else ""
            ),
        }

        log_activity(
            "generate_spec", file.filename,
            f"Позиций: {len(positions)}, артикулов: {len(all_articles_set)}, "
            f"изделий: {total_qty}",
        )

        return {
            "status": "ok",
            "source_file": file.filename,
            "source_type": source_type,
            "positions": response_positions,
            "summary": summary,
            "download": f"/api/download/{result_name}",
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path.unlink(missing_ok=True)


# ============== 3D PREVIEW ==============


def _build_scene(params: dict) -> dict:
    """Build a 3D scene description from construction parameters."""
    w = params.get("width_mm", 1500)
    h = params.get("height_mm", 2100)
    depth = params.get("frame_depth_mm", 72)
    profile_w = 65
    sections = params.get("sections", [])
    has_impost = params.get("has_impost", False)
    glass_formula = params.get("glass_formula", "4-16-4-16-4")
    color_outside = params.get("color_outside", "#7B7B7B")
    color_inside = params.get("color_inside", "#FFFFFF")

    # Parse glass thickness
    glass_parts = [int(p) for p in glass_formula.split("-") if p.strip().isdigit()]
    glass_thickness = sum(glass_parts) if glass_parts else 24

    # Build sections data
    scene_sections = []
    glass_panels = []
    handles = []
    impost_data = None

    if not sections:
        # Single section default
        sections = [{"type": "fixed", "x": 0, "y": 0, "w": w, "h": h}]

    # Auto-compute x offsets if not specified
    cur_x = 0
    for i, sec in enumerate(sections):
        sx = sec.get("x", cur_x)
        sy = sec.get("y", 0)
        sw = sec.get("w", w // len(sections))
        sh = sec.get("h", h)
        stype = sec.get("type", "fixed")

        scene_sections.append({
            "index": i,
            "type": stype,
            "x": sx,
            "y": sy,
            "width": sw,
            "height": sh,
            "label": {
                "fixed": "Глухое",
                "tilt_turn": "ПО",
                "tilt": "П",
                "turn": "О",
                "sliding": "Раздв.",
            }.get(stype, stype),
        })

        # Glass panel for this section (inset by profile width)
        glass_panels.append({
            "index": i,
            "x": sx + profile_w,
            "y": sy + profile_w,
            "width": sw - 2 * profile_w,
            "height": sh - 2 * profile_w,
            "thickness": glass_thickness,
        })

        # Handle for opening sections
        if stype in ("tilt_turn", "tilt", "turn"):
            handle_h = sec.get("handle_height_mm") or sec.get("handle_height") or sh // 2
            handles.append({
                "section_index": i,
                "x": sx + sw - profile_w - 10,
                "y": handle_h,
                "side": "right",
                "opening_type": stype,
            })

        cur_x = sx + sw

    # Impost between sections
    if has_impost and len(sections) >= 2:
        impost_x = sections[0].get("x", 0) + sections[0].get("w", w // 2)
        impost_data = {
            "x": impost_x,
            "orientation": "vertical",
            "width": 45,
            "height": h,
            "depth": depth,
        }

    return {
        "frame": {
            "width": w,
            "height": h,
            "depth": depth,
            "profile_width": profile_w,
        },
        "sections": scene_sections,
        "impost": impost_data,
        "glass_panels": glass_panels,
        "handles": handles,
        "glass_formula": glass_formula,
        "glass_thickness": glass_thickness,
        "color_outside": color_outside,
        "color_inside": color_inside,
    }


@app.post("/api/preview-3d")
async def api_preview_3d(params: dict):
    """Build 3D scene data from manual construction parameters."""
    try:
        counters["preview_3d"] += 1
        scene = _build_scene(params)
        ctype = params.get("construction_type", "окно")
        log_activity(
            "preview_3d", f"{ctype}",
            f"{scene['frame']['width']}x{scene['frame']['height']} мм, "
            f"секций: {len(scene['sections'])}",
        )
        return {"status": "ok", "scene": scene}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/preview-3d-from-pdf")
async def api_preview_3d_from_pdf(file: UploadFile = File(...)):
    """Extract construction data from a KMD PDF and return 3D scene."""
    path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{file.filename}"
    try:
        data = await file.read()
        path.write_bytes(data)

        text = extract_text_from_pdf(str(path))

        # Parse dimensions (WxH patterns)
        dim_pattern = _re.compile(
            r"(\d{3,5})\s*[xXхХ*×]\s*(\d{3,5})"
        )
        dims_found = dim_pattern.findall(text)

        width_mm = 1500
        height_mm = 2100
        if dims_found:
            # Take first reasonable match
            for dw, dh in dims_found:
                dw_i, dh_i = int(dw), int(dh)
                if 200 <= dw_i <= 10000 and 200 <= dh_i <= 10000:
                    width_mm = dw_i
                    height_mm = dh_i
                    break

        # Detect construction type
        construction_type = "окно"
        text_lower = text.lower()
        if "витраж" in text_lower:
            construction_type = "витраж"
        elif "дверь" in text_lower or "дверной" in text_lower:
            construction_type = "дверь"
        elif "фасад" in text_lower:
            construction_type = "фасад"

        # Detect sections
        sections = []
        has_impost = False

        # Check for impost
        if "импост" in text_lower:
            has_impost = True

        # Check for створка (opening sash)
        stvorka_count = len(_re.findall(r"створк", text_lower))
        gluhoe_count = len(_re.findall(r"глух", text_lower))

        # Detect handle height
        handle_pattern = _re.compile(r"руч\w*\s*[:=]?\s*(\d{3,4})")
        handle_match = handle_pattern.search(text_lower)
        handle_height = int(handle_match.group(1)) if handle_match else 1050

        if has_impost or stvorka_count > 0:
            # Two-section window
            half_w = width_mm // 2
            sections = [
                {"type": "fixed", "x": 0, "y": 0, "w": half_w, "h": height_mm},
                {
                    "type": "tilt_turn", "x": half_w, "y": 0,
                    "w": width_mm - half_w, "h": height_mm,
                    "handle_height_mm": handle_height,
                },
            ]
            has_impost = True
        elif gluhoe_count > 0 and stvorka_count == 0:
            sections = [
                {"type": "fixed", "x": 0, "y": 0, "w": width_mm, "h": height_mm},
            ]
        else:
            # Default: single tilt-turn
            sections = [
                {
                    "type": "tilt_turn", "x": 0, "y": 0,
                    "w": width_mm, "h": height_mm,
                    "handle_height_mm": handle_height,
                },
            ]

        # Parse glass formula
        glass_formula = "4-16-4-16-4"
        glass_pattern = _re.compile(r"(\d{1,2}[-/]\d{1,2}[-/]\d{1,2}(?:[-/]\d{1,2})*)")
        glass_match = glass_pattern.search(text)
        if glass_match:
            candidate = glass_match.group(1).replace("/", "-")
            parts = candidate.split("-")
            if len(parts) >= 3 and all(1 <= int(p) <= 50 for p in parts if p.isdigit()):
                glass_formula = candidate

        params = {
            "construction_type": construction_type,
            "width_mm": width_mm,
            "height_mm": height_mm,
            "frame_depth_mm": 72,
            "sections": sections,
            "glass_formula": glass_formula,
            "has_impost": has_impost,
            "color_outside": "#7B7B7B",
            "color_inside": "#FFFFFF",
        }

        scene = _build_scene(params)

        counters["preview_3d"] += 1
        log_activity(
            "preview_3d", file.filename,
            f"PDF -> {construction_type} {width_mm}x{height_mm} мм, "
            f"секций: {len(sections)}",
        )

        return {
            "status": "ok",
            "source_file": file.filename,
            "extracted_params": params,
            "scene": scene,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path.unlink(missing_ok=True)


# ============== ОПТИМИЗАЦИЯ РАСКРОЯ ПРОФИЛЕЙ ==============

import math
from pydantic import BaseModel
from typing import List


class CutItem(BaseModel):
    article: str
    length_mm: int
    quantity: int


class CuttingRequest(BaseModel):
    stock_length_mm: int = 6500
    cuts: List[CutItem]
    blade_width_mm: int = 5
    min_remnant_mm: int = 50


def _optimize_cutting(req: CuttingRequest) -> dict:
    """
    1D bin-packing: First Fit Decreasing (FFD) + improvement pass.
    """
    stock = req.stock_length_mm
    blade = req.blade_width_mm

    # Expand all cuts into individual items
    items = []
    for c in req.cuts:
        for _ in range(c.quantity):
            items.append({"article": c.article, "length_mm": c.length_mm})

    if not items:
        return {
            "status": "ok",
            "stock_length_mm": stock,
            "blade_width_mm": blade,
            "total_bars_needed": 0,
            "total_stock_length_mm": 0,
            "total_used_mm": 0,
            "total_waste_mm": 0,
            "waste_percent": 0.0,
            "savings_vs_naive": 0.0,
            "cutting_plan": [],
            "summary_by_article": [],
        }

    # Sort descending by length (FFD)
    items.sort(key=lambda x: x["length_mm"], reverse=True)

    # Bars: each bar tracks cuts and remaining space
    bars: list[dict] = []

    def _space_needed(bar_cuts_count: int, cut_len: int) -> int:
        """Space needed to add a cut to a bar with bar_cuts_count existing cuts."""
        if bar_cuts_count == 0:
            return cut_len
        return blade + cut_len

    # FFD pass
    for item in items:
        placed = False
        for bar in bars:
            needed = _space_needed(len(bar["cuts"]), item["length_mm"])
            if needed <= bar["remaining_mm"]:
                bar["cuts"].append(item)
                bar["remaining_mm"] -= needed
                placed = True
                break
        if not placed:
            new_bar = {"cuts": [item], "remaining_mm": stock - item["length_mm"]}
            bars.append(new_bar)

    # Improvement pass: try to move cuts from high-waste bars to others
    improved = True
    max_iters = 50
    iteration = 0
    while improved and iteration < max_iters:
        improved = False
        iteration += 1
        bars.sort(key=lambda b: b["remaining_mm"], reverse=True)
        for i in range(len(bars)):
            if not bars[i]["cuts"]:
                continue
            for ci in range(len(bars[i]["cuts"]) - 1, -1, -1):
                cut = bars[i]["cuts"][ci]
                for j in range(len(bars)):
                    if i == j:
                        continue
                    needed = _space_needed(len(bars[j]["cuts"]), cut["length_mm"])
                    if needed <= bars[j]["remaining_mm"]:
                        bars[i]["cuts"].pop(ci)
                        used_i = sum(c["length_mm"] for c in bars[i]["cuts"])
                        if bars[i]["cuts"]:
                            used_i += blade * (len(bars[i]["cuts"]) - 1)
                        bars[i]["remaining_mm"] = stock - used_i
                        bars[j]["cuts"].append(cut)
                        bars[j]["remaining_mm"] -= needed
                        improved = True
                        break
                if improved:
                    break
            if improved:
                break

    # Remove empty bars
    bars = [b for b in bars if b["cuts"]]

    # Calculate naive baseline: sequential placement without optimization
    naive_bars_seq = 0
    naive_remaining = 0
    for item in items:
        if naive_remaining >= item["length_mm"] + (blade if naive_bars_seq > 0 and naive_remaining < stock else 0):
            if naive_remaining == stock:
                naive_remaining -= item["length_mm"]
            else:
                naive_remaining -= (item["length_mm"] + blade)
        else:
            naive_bars_seq += 1
            naive_remaining = stock - item["length_mm"]
    total_cut_length = sum(item["length_mm"] for item in items)
    naive_bars_theoretical = math.ceil(total_cut_length / stock) if stock > 0 else len(bars)
    naive_bars = max(naive_bars_theoretical, naive_bars_seq)

    total_bars = len(bars)
    total_stock = total_bars * stock
    total_used = 0
    cutting_plan = []

    for idx, bar in enumerate(bars, 1):
        bar_used = sum(c["length_mm"] for c in bar["cuts"])
        if len(bar["cuts"]) > 1:
            bar_used += blade * (len(bar["cuts"]) - 1)
        bar_waste = stock - bar_used
        utilization = round(bar_used / stock * 100, 1) if stock > 0 else 0
        total_used += bar_used

        cutting_plan.append({
            "bar_number": idx,
            "cuts": [{"article": c["article"], "length_mm": c["length_mm"]} for c in bar["cuts"]],
            "used_mm": bar_used,
            "waste_mm": bar_waste,
            "utilization_percent": utilization,
        })

    total_waste = total_stock - total_used
    waste_pct = round(total_waste / total_stock * 100, 1) if total_stock > 0 else 0

    if naive_bars > 0 and naive_bars > total_bars:
        savings = round((1 - total_bars / naive_bars) * 100, 1)
    else:
        savings = 0.0

    # Summary by article
    article_summary: dict[str, dict] = {}
    for item in items:
        art = item["article"]
        if art not in article_summary:
            article_summary[art] = {"article": art, "total_cuts": 0, "total_length_mm": 0}
        article_summary[art]["total_cuts"] += 1
        article_summary[art]["total_length_mm"] += item["length_mm"]

    return {
        "status": "ok",
        "stock_length_mm": stock,
        "blade_width_mm": blade,
        "total_bars_needed": total_bars,
        "total_stock_length_mm": total_stock,
        "total_used_mm": total_used,
        "total_waste_mm": total_waste,
        "waste_percent": waste_pct,
        "savings_vs_naive": savings,
        "cutting_plan": cutting_plan,
        "summary_by_article": sorted(article_summary.values(), key=lambda x: x["article"]),
    }


@app.post("/api/optimize-cutting")
async def api_optimize_cutting(req: CuttingRequest):
    """Оптимизировать раскрой профилей (ручной ввод)."""
    try:
        result = _optimize_cutting(req)
        log_activity(
            "optimize_cutting", "manual",
            f"Хлыстов: {result['total_bars_needed']}, отходы: {result['waste_percent']}%",
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/optimize-cutting-from-pdf")
async def api_optimize_cutting_from_pdf(
    file: UploadFile = File(...),
    stock_length_mm: int = Form(6500),
    blade_width_mm: int = Form(5),
    min_remnant_mm: int = Form(50),
):
    """Извлечь профили из PDF КМД и оптимизировать раскрой."""
    path = save_upload(file)
    try:
        text = extract_text_from_pdf(str(path))

        # Find all 7-digit articles
        articles_found = _re.findall(r'\b(\d{7})\b', text)
        unique_articles = sorted(set(articles_found))

        # Find dimensions: numbers 100-6500 followed by mm
        dimensions = _re.findall(r'\b(\d{3,4})\s*(?:мм|mm)\b', text, _re.IGNORECASE)
        dim_values = [int(d) for d in dimensions if 50 <= int(d) <= 6500]

        # Build cuts list by pairing articles with dimensions
        cuts_list: list[dict] = []

        if unique_articles and dim_values:
            for art in unique_articles:
                art_positions = [m.start() for m in _re.finditer(r'\b' + art + r'\b', text)]
                nearby_dims = set()
                for apos in art_positions:
                    snippet = text[apos:apos + 300]
                    dims_in_snippet = _re.findall(r'\b(\d{3,4})\s*(?:мм|mm)?\b', snippet)
                    for d in dims_in_snippet:
                        dv = int(d)
                        if 100 <= dv <= 6500 and dv != int(art):
                            nearby_dims.add(dv)

                if nearby_dims:
                    for dim in sorted(nearby_dims):
                        qty = 1
                        for apos in art_positions:
                            snippet = text[max(0, apos - 100):apos + 300]
                            q_match = _re.findall(
                                r'(?:Количество|Кол[\-\.]?\s*во|qty|кол)\s*[:\s]\s*(\d+)',
                                snippet, _re.IGNORECASE,
                            )
                            if q_match:
                                qty = int(q_match[0])
                                break
                        cuts_list.append({
                            "article": art,
                            "length_mm": dim,
                            "quantity": qty,
                        })
                else:
                    if dim_values:
                        cuts_list.append({
                            "article": art,
                            "length_mm": dim_values[0],
                            "quantity": 1,
                        })

        if not cuts_list:
            raise HTTPException(
                status_code=400,
                detail="Не удалось извлечь артикулы и размеры из PDF. "
                       "Убедитесь, что документ содержит 7-значные артикулы и размеры в мм.",
            )

        cut_items = [CutItem(**c) for c in cuts_list]
        req = CuttingRequest(
            stock_length_mm=stock_length_mm,
            cuts=cut_items,
            blade_width_mm=blade_width_mm,
            min_remnant_mm=min_remnant_mm,
        )
        result = _optimize_cutting(req)

        result["extracted_articles"] = unique_articles
        result["extracted_cuts"] = cuts_list

        log_activity(
            "optimize_cutting", file.filename,
            f"Артикулов: {len(unique_articles)}, хлыстов: {result['total_bars_needed']}, "
            f"отходы: {result['waste_percent']}%",
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path.unlink(missing_ok=True)


# ============== 12. AI ПОДБОР ПРОФИЛЬНОЙ СИСТЕМЫ ==============

PROFILE_SYSTEMS = [
    # --- Reynaers ---
    {
        "system": "Reynaers MasterLine 8",
        "manufacturer": "Reynaers Aluminium",
        "series": "MasterLine 8",
        "types": ["окна"],
        "thermal_uf_min": 1.3, "thermal_uf_max": 1.5,
        "max_sash_weight_kg": 160,
        "max_height_mm": 2800, "max_width_mm": 1400,
        "glass_max_mm": 52,
        "wind_resistance_pa": 2400,
        "fire_resistant": False,
        "budget": "премиум",
        "sound_db": 45,
        "pros": ["Высокая теплоизоляция", "Скрытая фурнитура", "Большие створки"],
        "cons": ["Высокая стоимость профиля"],
        "norms": ["ГОСТ 21519-2022", "СП 426.1325800.2018"],
        "articles_example": ["4580102", "4580183"],
    },
    {
        "system": "Reynaers MasterLine 8 HI",
        "manufacturer": "Reynaers Aluminium",
        "series": "MasterLine 8 HI",
        "types": ["окна"],
        "thermal_uf_min": 0.9, "thermal_uf_max": 1.1,
        "max_sash_weight_kg": 150,
        "max_height_mm": 2600, "max_width_mm": 1300,
        "glass_max_mm": 56,
        "wind_resistance_pa": 2200,
        "fire_resistant": False,
        "budget": "премиум",
        "sound_db": 48,
        "pros": ["Лучшая теплоизоляция в классе", "Тройное уплотнение", "Пассивный дом"],
        "cons": ["Высокая цена", "Увеличенная монтажная глубина"],
        "norms": ["ГОСТ 21519-2022", "СП 50.13330.2012"],
        "articles_example": ["4580202", "4580283"],
    },
    {
        "system": "Reynaers ConceptWall 50",
        "manufacturer": "Reynaers Aluminium",
        "series": "CW 50",
        "types": ["витражи", "фасады"],
        "thermal_uf_min": 1.5, "thermal_uf_max": 2.0,
        "max_sash_weight_kg": 0,
        "max_height_mm": 6000, "max_width_mm": 3000,
        "glass_max_mm": 44,
        "wind_resistance_pa": 3000,
        "fire_resistant": False,
        "budget": "стандарт",
        "sound_db": 42,
        "pros": ["Узкие профили 50мм", "Высокие пролёты", "Стоечно-ригельная система"],
        "cons": ["Средняя теплоизоляция", "Требует расчёта несущей способности"],
        "norms": ["ГОСТ 33079-2014", "СП 426.1325800.2018"],
        "articles_example": ["CW50-01", "CW50-02"],
    },
    {
        "system": "Reynaers ConceptWall 60",
        "manufacturer": "Reynaers Aluminium",
        "series": "CW 60",
        "types": ["витражи", "фасады"],
        "thermal_uf_min": 0.8, "thermal_uf_max": 1.2,
        "max_sash_weight_kg": 0,
        "max_height_mm": 6000, "max_width_mm": 3000,
        "glass_max_mm": 54,
        "wind_resistance_pa": 3500,
        "fire_resistant": True,
        "budget": "премиум",
        "sound_db": 48,
        "pros": ["Отличная теплоизоляция", "Большие пролёты", "Противопожарное исполнение"],
        "cons": ["Высокая стоимость", "Увеличенная видимая ширина"],
        "norms": ["ГОСТ 33079-2014", "СП 426.1325800.2018", "ГОСТ 53308-2009"],
        "articles_example": ["CW60-01", "CW60-02"],
    },
    {
        "system": "Reynaers Hi-Finity",
        "manufacturer": "Reynaers Aluminium",
        "series": "Hi-Finity",
        "types": ["раздвижные"],
        "thermal_uf_min": 1.4, "thermal_uf_max": 1.8,
        "max_sash_weight_kg": 400,
        "max_height_mm": 3500, "max_width_mm": 3000,
        "glass_max_mm": 52,
        "wind_resistance_pa": 2000,
        "fire_resistant": False,
        "budget": "премиум",
        "sound_db": 40,
        "pros": ["Минимальные рамки", "Панорамное остекление", "Створки до 400кг"],
        "cons": ["Высокая стоимость", "Сложный монтаж"],
        "norms": ["ГОСТ 21519-2022", "СП 426.1325800.2018"],
        "articles_example": ["HF-01", "HF-02"],
    },
    {
        "system": "Reynaers CS 86-HI",
        "manufacturer": "Reynaers Aluminium",
        "series": "CS 86-HI",
        "types": ["двери"],
        "thermal_uf_min": 1.0, "thermal_uf_max": 1.3,
        "max_sash_weight_kg": 200,
        "max_height_mm": 3000, "max_width_mm": 1400,
        "glass_max_mm": 52,
        "wind_resistance_pa": 2500,
        "fire_resistant": False,
        "budget": "премиум",
        "sound_db": 44,
        "pros": ["Высокая теплоизоляция", "Тяжёлые створки до 200кг", "Скрытые петли"],
        "cons": ["Высокая стоимость профиля"],
        "norms": ["ГОСТ 23747-2015", "СП 426.1325800.2018"],
        "articles_example": ["CS86-01", "CS86-02"],
    },
    # --- Schuco ---
    {
        "system": "Schüco AWS 75.SI+",
        "manufacturer": "Schüco",
        "series": "AWS 75.SI+",
        "types": ["окна"],
        "thermal_uf_min": 1.2, "thermal_uf_max": 1.6,
        "max_sash_weight_kg": 150,
        "max_height_mm": 2600, "max_width_mm": 1400,
        "glass_max_mm": 50,
        "wind_resistance_pa": 2400,
        "fire_resistant": False,
        "budget": "стандарт",
        "sound_db": 45,
        "pros": ["Оптимальное соотношение цена/качество", "Широкая линейка фурнитуры", "Проверенная система"],
        "cons": ["Стандартный дизайн"],
        "norms": ["ГОСТ 21519-2022", "СП 426.1325800.2018"],
        "articles_example": ["242480", "242485"],
    },
    {
        "system": "Schüco AWS 90.SI+",
        "manufacturer": "Schüco",
        "series": "AWS 90.SI+",
        "types": ["окна"],
        "thermal_uf_min": 0.8, "thermal_uf_max": 1.0,
        "max_sash_weight_kg": 160,
        "max_height_mm": 2700, "max_width_mm": 1400,
        "glass_max_mm": 56,
        "wind_resistance_pa": 2600,
        "fire_resistant": False,
        "budget": "премиум",
        "sound_db": 50,
        "pros": ["Лучшая теплоизоляция Schüco", "Пассивный дом", "Тройное уплотнение"],
        "cons": ["Высокая стоимость", "Монтажная глубина 90мм"],
        "norms": ["ГОСТ 21519-2022", "СП 50.13330.2012"],
        "articles_example": ["288900", "288905"],
    },
    {
        "system": "Schüco FWS 50+.SI",
        "manufacturer": "Schüco",
        "series": "FWS 50+.SI",
        "types": ["витражи", "фасады"],
        "thermal_uf_min": 1.0, "thermal_uf_max": 1.5,
        "max_sash_weight_kg": 0,
        "max_height_mm": 6000, "max_width_mm": 3000,
        "glass_max_mm": 50,
        "wind_resistance_pa": 3200,
        "fire_resistant": False,
        "budget": "стандарт",
        "sound_db": 44,
        "pros": ["Узкие видимые профили", "Высокая ветровая стойкость", "Совместимость с AWS"],
        "cons": ["Требует расчёта несущей способности"],
        "norms": ["ГОСТ 33079-2014", "СП 426.1325800.2018"],
        "articles_example": ["FWS50-01", "FWS50-02"],
    },
    {
        "system": "Schüco FWS 60+.SI",
        "manufacturer": "Schüco",
        "series": "FWS 60+.SI",
        "types": ["витражи", "фасады"],
        "thermal_uf_min": 0.7, "thermal_uf_max": 1.0,
        "max_sash_weight_kg": 0,
        "max_height_mm": 6000, "max_width_mm": 3500,
        "glass_max_mm": 58,
        "wind_resistance_pa": 3800,
        "fire_resistant": True,
        "budget": "премиум",
        "sound_db": 50,
        "pros": ["Лучшая теплоизоляция фасадов", "Противопожарное исполнение EI30/EI60", "Максимальные пролёты"],
        "cons": ["Высокая стоимость", "Увеличенная монтажная глубина"],
        "norms": ["ГОСТ 33079-2014", "СП 426.1325800.2018", "ГОСТ 53308-2009"],
        "articles_example": ["FWS60-01", "FWS60-02"],
    },
    {
        "system": "Schüco ASS 77 PD.HI",
        "manufacturer": "Schüco",
        "series": "ASS 77 PD.HI",
        "types": ["раздвижные"],
        "thermal_uf_min": 1.2, "thermal_uf_max": 1.5,
        "max_sash_weight_kg": 300,
        "max_height_mm": 3200, "max_width_mm": 3000,
        "glass_max_mm": 50,
        "wind_resistance_pa": 2200,
        "fire_resistant": False,
        "budget": "премиум",
        "sound_db": 42,
        "pros": ["Параллельно-сдвижная система", "Тяжёлые створки", "Хорошая теплоизоляция"],
        "cons": ["Высокая стоимость", "Требует ровного проёма"],
        "norms": ["ГОСТ 21519-2022", "СП 426.1325800.2018"],
        "articles_example": ["ASS77-01", "ASS77-02"],
    },
    {
        "system": "Schüco ADS 90.SI",
        "manufacturer": "Schüco",
        "series": "ADS 90.SI",
        "types": ["двери"],
        "thermal_uf_min": 0.9, "thermal_uf_max": 1.2,
        "max_sash_weight_kg": 200,
        "max_height_mm": 3000, "max_width_mm": 1400,
        "glass_max_mm": 54,
        "wind_resistance_pa": 2600,
        "fire_resistant": False,
        "budget": "премиум",
        "sound_db": 46,
        "pros": ["Высокая теплоизоляция", "Створки до 200кг", "Три контура уплотнения"],
        "cons": ["Высокая стоимость", "Монтажная глубина 90мм"],
        "norms": ["ГОСТ 23747-2015", "СП 426.1325800.2018"],
        "articles_example": ["ADS90-01", "ADS90-02"],
    },
    # --- Alutech ---
    {
        "system": "Alutech ALT W72",
        "manufacturer": "Alutech",
        "series": "ALT W72",
        "types": ["окна"],
        "thermal_uf_min": 1.4, "thermal_uf_max": 1.8,
        "max_sash_weight_kg": 120,
        "max_height_mm": 2400, "max_width_mm": 1200,
        "glass_max_mm": 44,
        "wind_resistance_pa": 2000,
        "fire_resistant": False,
        "budget": "эконом",
        "sound_db": 38,
        "pros": ["Доступная цена", "Наличие на складе", "Производство в РБ/РФ"],
        "cons": ["Ограничения по размерам створок", "Меньший выбор фурнитуры"],
        "norms": ["ГОСТ 21519-2022", "СП 426.1325800.2018"],
        "articles_example": ["ALT-W72-01", "ALT-W72-02"],
    },
    {
        "system": "Alutech ALT F50",
        "manufacturer": "Alutech",
        "series": "ALT F50",
        "types": ["витражи", "фасады"],
        "thermal_uf_min": 1.7, "thermal_uf_max": 2.2,
        "max_sash_weight_kg": 0,
        "max_height_mm": 5000, "max_width_mm": 2500,
        "glass_max_mm": 40,
        "wind_resistance_pa": 2400,
        "fire_resistant": False,
        "budget": "эконом",
        "sound_db": 38,
        "pros": ["Доступная цена", "Быстрая поставка", "Простой монтаж"],
        "cons": ["Средняя теплоизоляция", "Ограничения по высоте"],
        "norms": ["ГОСТ 33079-2014"],
        "articles_example": ["ALT-F50-01", "ALT-F50-02"],
    },
    {
        "system": "Alutech ALT F50 NL",
        "manufacturer": "Alutech",
        "series": "ALT F50 NL",
        "types": ["витражи", "фасады"],
        "thermal_uf_min": 1.5, "thermal_uf_max": 2.0,
        "max_sash_weight_kg": 0,
        "max_height_mm": 5000, "max_width_mm": 2500,
        "glass_max_mm": 44,
        "wind_resistance_pa": 2600,
        "fire_resistant": False,
        "budget": "стандарт",
        "sound_db": 40,
        "pros": ["Полуструктурное остекление", "Современный вид", "Средняя цена"],
        "cons": ["Средняя теплоизоляция", "Ограничения по пролётам"],
        "norms": ["ГОСТ 33079-2014"],
        "articles_example": ["ALT-F50NL-01", "ALT-F50NL-02"],
    },
    {
        "system": "Alutech ALT SL160",
        "manufacturer": "Alutech",
        "series": "ALT SL160",
        "types": ["раздвижные"],
        "thermal_uf_min": 1.5, "thermal_uf_max": 2.0,
        "max_sash_weight_kg": 200,
        "max_height_mm": 2800, "max_width_mm": 2500,
        "glass_max_mm": 40,
        "wind_resistance_pa": 1800,
        "fire_resistant": False,
        "budget": "стандарт",
        "sound_db": 36,
        "pros": ["Доступная раздвижная система", "Простой монтаж", "Наличие"],
        "cons": ["Средние характеристики", "Ограничения по весу створки"],
        "norms": ["ГОСТ 21519-2022"],
        "articles_example": ["ALT-SL160-01", "ALT-SL160-02"],
    },
    {
        "system": "Alutech ALT C48",
        "manufacturer": "Alutech",
        "series": "ALT C48",
        "types": ["окна", "витражи"],
        "thermal_uf_min": 5.0, "thermal_uf_max": 6.0,
        "max_sash_weight_kg": 80,
        "max_height_mm": 2200, "max_width_mm": 1200,
        "glass_max_mm": 32,
        "wind_resistance_pa": 1800,
        "fire_resistant": False,
        "budget": "эконом",
        "sound_db": 28,
        "pros": ["Минимальная цена", "Быстрая поставка", "Простой монтаж"],
        "cons": ["Холодная система без терморазрыва", "Только неотапливаемые помещения"],
        "norms": ["ГОСТ 21519-2022"],
        "articles_example": ["ALT-C48-01", "ALT-C48-02"],
    },
    # --- TATPROF ---
    {
        "system": "TATPROF ТПТ 65А",
        "manufacturer": "TATPROF",
        "series": "ТПТ 65А",
        "types": ["окна"],
        "thermal_uf_min": 1.5, "thermal_uf_max": 1.9,
        "max_sash_weight_kg": 100,
        "max_height_mm": 2200, "max_width_mm": 1200,
        "glass_max_mm": 40,
        "wind_resistance_pa": 1800,
        "fire_resistant": False,
        "budget": "эконом",
        "sound_db": 36,
        "pros": ["Российское производство", "Доступная цена", "Быстрая поставка"],
        "cons": ["Ограничения по размерам", "Базовый дизайн", "Меньший выбор фурнитуры"],
        "norms": ["ГОСТ 21519-2022"],
        "articles_example": ["TPT-65A-01", "TPT-65A-02"],
    },
    {
        "system": "TATPROF ТПТ 47А",
        "manufacturer": "TATPROF",
        "series": "ТПТ 47А",
        "types": ["окна"],
        "thermal_uf_min": 5.5, "thermal_uf_max": 7.0,
        "max_sash_weight_kg": 60,
        "max_height_mm": 2000, "max_width_mm": 1000,
        "glass_max_mm": 24,
        "wind_resistance_pa": 1500,
        "fire_resistant": False,
        "budget": "эконом",
        "sound_db": 25,
        "pros": ["Минимальная цена", "Российское производство", "Быстрая поставка"],
        "cons": ["Холодная система", "Только неотапливаемые помещения", "Малые размеры"],
        "norms": ["ГОСТ 21519-2022"],
        "articles_example": ["TPT-47A-01", "TPT-47A-02"],
    },
]

WIND_PRESSURE_BASE = {
    "I": 0.17, "II": 0.30, "III": 0.38, "IV": 0.48,
    "V": 0.60, "VI": 0.73, "VII": 0.85,
}


def _calc_wind_pressure(wind_region: str, floors: int) -> float:
    """Расчёт ветрового давления по СП 20.13330 (упрощённый)."""
    w0 = WIND_PRESSURE_BASE.get(wind_region, 0.38)
    height_m = max(floors * 3.0, 3.0)
    k_z = (height_m / 10.0) ** 0.2
    return w0 * k_z * 1.4


def _score_profile(profile: dict, params: dict, wind_pa: float) -> int:
    """Подсчёт рейтинга профильной системы 0-100."""
    score = 0.0

    # 1. Теплоизоляция (25%)
    if params.get("thermal_required"):
        uf_avg = (profile["thermal_uf_min"] + profile["thermal_uf_max"]) / 2
        if uf_avg <= 1.0:
            thermal_score = 100
        elif uf_avg <= 1.5:
            thermal_score = 85 - (uf_avg - 1.0) * 40
        elif uf_avg <= 2.0:
            thermal_score = 65 - (uf_avg - 1.5) * 50
        else:
            thermal_score = max(0, 40 - (uf_avg - 2.0) * 30)
        score += thermal_score * 0.25
    else:
        score += 80 * 0.25

    # 2. Размеры (20%)
    w = params.get("width_mm", 1500)
    h = params.get("height_mm", 2100)
    if h <= profile["max_height_mm"] and w <= profile["max_width_mm"]:
        dim_score = 100
    elif h <= profile["max_height_mm"] * 1.1 and w <= profile["max_width_mm"] * 1.1:
        dim_score = 60
    else:
        dim_score = 10
    score += dim_score * 0.20

    # 3. Ветровая нагрузка (20%)
    if profile["wind_resistance_pa"] >= wind_pa:
        wind_score = 100
    elif profile["wind_resistance_pa"] >= wind_pa * 0.8:
        wind_score = 60
    else:
        wind_score = 20
    score += wind_score * 0.20

    # 4. Бюджет (15%)
    budget = params.get("budget", "стандарт")
    p_budget = profile["budget"]
    if budget == p_budget:
        budget_score = 100
    elif (budget == "стандарт" and p_budget == "эконом") or (
        budget == "премиум" and p_budget == "стандарт"
    ):
        budget_score = 70
    elif budget == "стандарт" and p_budget == "премиум":
        budget_score = 50
    elif budget == "эконом" and p_budget == "стандарт":
        budget_score = 50
    else:
        budget_score = 30
    score += budget_score * 0.15

    # 5. Стеклопакет (10%)
    sound_db = params.get("sound_insulation_db", 35)
    glass_cap = profile["glass_max_mm"]
    if glass_cap >= 50:
        glass_score = 100
    elif glass_cap >= 44:
        glass_score = 80
    elif glass_cap >= 36:
        glass_score = 60
    else:
        glass_score = 30
    if profile["sound_db"] >= sound_db:
        glass_score = min(100, glass_score + 10)
    score += glass_score * 0.10

    # 6. Огнестойкость (10%)
    if params.get("fire_resistance"):
        fire_score = 100 if profile["fire_resistant"] else 0
    else:
        fire_score = 80
    score += fire_score * 0.10

    return max(0, min(100, round(score)))


@app.post("/api/recommend-profile")
async def api_recommend_profile(data: dict):
    """AI-подбор профильной системы по параметрам проекта."""
    try:
        construction_type = data.get("construction_type", "окна")
        width_mm = int(data.get("width_mm", 1500))
        height_mm = int(data.get("height_mm", 2100))
        floors = int(data.get("floors", 5))
        wind_region = data.get("wind_region", "III")
        thermal_required = bool(data.get("thermal_required", True))
        sound_insulation_db = int(data.get("sound_insulation_db", 35))
        fire_resistance = bool(data.get("fire_resistance", False))
        budget = data.get("budget", "стандарт")

        params = {
            "construction_type": construction_type,
            "width_mm": width_mm,
            "height_mm": height_mm,
            "floors": floors,
            "wind_region": wind_region,
            "thermal_required": thermal_required,
            "sound_insulation_db": sound_insulation_db,
            "fire_resistance": fire_resistance,
            "budget": budget,
        }

        wind_pa = _calc_wind_pressure(wind_region, floors) * 1000

        candidates = [
            p for p in PROFILE_SYSTEMS if construction_type in p["types"]
        ]
        if not candidates:
            candidates = PROFILE_SYSTEMS

        scored = []
        for p in candidates:
            s = _score_profile(p, params, wind_pa)
            uf_avg = (p["thermal_uf_min"] + p["thermal_uf_max"]) / 2

            reasons = []
            if thermal_required and uf_avg <= 1.2:
                reasons.append("высокие требования к теплоизоляции")
            if floors >= 9:
                reasons.append(f"здание {floors} этажей")
            if fire_resistance and p["fire_resistant"]:
                reasons.append("огнестойкое исполнение")
            if budget == "эконом":
                reasons.append("экономичное решение")
            elif budget == "премиум":
                reasons.append("премиальное качество")

            reason = (
                f"Оптимальный выбор для {construction_type}: "
                + ", ".join(reasons)
                if reasons
                else f"Подходящая система для {construction_type}"
            )

            scored.append({
                "system": p["system"],
                "manufacturer": p["manufacturer"],
                "series": p["series"],
                "score": s,
                "thermal_uf": round(uf_avg, 2),
                "max_sash_weight_kg": p["max_sash_weight_kg"],
                "max_height_mm": p["max_height_mm"],
                "glass_max_mm": p["glass_max_mm"],
                "pros": p["pros"],
                "cons": p["cons"],
                "reason": reason,
                "norms": p["norms"],
                "articles_example": p["articles_example"],
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        for i, item in enumerate(scored):
            item["rank"] = i + 1

        warnings = []
        if height_mm > 3000:
            warnings.append(
                "При высоте конструкции более 3м требуется индивидуальный расчёт несущей способности"
            )
        if floors >= 15:
            warnings.append(
                "При высоте более 15 этажей требуется расчёт ветровой нагрузки по СП 20.13330"
            )
        if wind_region in ("V", "VI", "VII"):
            warnings.append(
                f"Ветровой район {wind_region} — рекомендуется усиленное армирование профилей"
            )
        if fire_resistance and not any(p["fire_resistant"] for p in candidates):
            warnings.append(
                "Огнестойкие исполнения доступны не во всех системах — уточняйте у производителя"
            )

        log_activity(
            "recommend_profile",
            f"{construction_type} {width_mm}x{height_mm}",
            f"Найдено {len(scored)} систем, лучшая: {scored[0]['system']} ({scored[0]['score']})",
        )

        return {
            "status": "ok",
            "recommendations": scored[:8],
            "parameters_used": params,
            "wind_pressure_pa": round(wind_pa),
            "warnings": warnings,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== 13. СТАТИСТИКА / ДАШБОРД ==============

@app.get("/api/stats")
async def api_stats():
    """Вернуть счётчики и последние операции."""
    return {
        "counters": counters,
        "total_operations": sum(counters.values()),
        "recent": activity_log[:20],
    }


# ============== СКАЧИВАНИЕ РЕЗУЛЬТАТОВ ==============

@app.get("/api/download/{filename}")
async def download_result(filename: str):
    # Защита от path traversal: берём только имя файла
    safe_name = Path(filename).name
    path = (RESULTS_DIR / safe_name).resolve()
    if not path.is_relative_to(RESULTS_DIR.resolve()) or not path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path, filename=safe_name,
                       media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
