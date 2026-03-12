"""
KMD Assistant — веб-сервер для инженеров АЛЬДМЕГА ЛАБ.
FastAPI бэкенд с инструментами проверки КМД документации.
"""

import os
import sys
import uuid
import json
import shutil
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Добавляем tools в путь
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from compare_orders import extract_articles, compare_orders
from pdf_tools import extract_text_from_pdf, extract_tables_from_pdf
from docx_tools import read_docx, read_docx_with_tables

app = FastAPI(title="KMD Assistant", version="1.0")

UPLOAD_DIR = Path(__file__).parent / "uploads"
RESULTS_DIR = Path(__file__).parent / "results"
UPLOAD_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)


def save_upload(file: UploadFile) -> Path:
    """Сохранить загруженный файл с уникальным именем."""
    ext = Path(file.filename).suffix
    uid = uuid.uuid4().hex[:8]
    safe_name = f"{uid}_{file.filename}"
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


# ============== СКАЧИВАНИЕ РЕЗУЛЬТАТОВ ==============

@app.get("/api/download/{filename}")
async def download_result(filename: str):
    path = RESULTS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path, filename=filename,
                       media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
