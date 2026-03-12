"""
OCR инструменты — распознавание текста на сканах чертежей КМД.

Поддерживает:
- Предобработку изображений (grayscale, threshold, denoise)
- Два режима Tesseract: block text (psm 6) и sparse text (psm 11)
- Кириллицу (русские надписи на чертежах)
- Парсинг позиций, артикулов, количеств, размеров из OCR-текста
"""

import re
import sys
from pathlib import Path
from typing import Optional


# --------------- image preprocessing ---------------

def preprocess_image(img, denoise: bool = True):
    """Подготовить изображение для OCR: grayscale → threshold → denoise.

    Args:
        img: PIL.Image
        denoise: применить медианный фильтр для удаления шума

    Returns:
        PIL.Image — обработанное изображение
    """
    from PIL import Image, ImageFilter

    # Grayscale
    gray = img.convert("L")

    # Adaptive-like threshold: Otsu via simple 2-level quantize
    # For scanned drawings a fixed threshold of 180 works well
    bw = gray.point(lambda px: 255 if px > 180 else 0, mode="1")

    # Back to "L" so Tesseract can handle it
    bw = bw.convert("L")

    # Median filter to remove salt-and-pepper noise
    if denoise:
        bw = bw.filter(ImageFilter.MedianFilter(size=3))

    return bw


# --------------- tesseract wrappers ---------------

def ocr_image(image_path: str, lang: str = "rus+eng",
              preprocess: bool = True) -> str:
    """Распознать текст на изображении (скан чертежа).

    Использует --oem 3 (LSTM+Legacy) и --psm 6 (block of text).
    """
    import pytesseract
    from PIL import Image

    img = Image.open(image_path)
    if preprocess:
        img = preprocess_image(img)

    config = "--oem 3 --psm 6"
    return pytesseract.image_to_string(img, lang=lang, config=config)


def ocr_image_sparse(image_path: str, lang: str = "rus+eng",
                     preprocess: bool = True) -> str:
    """Распознать разреженный текст (надписи, размеры на чертеже).

    Использует --psm 11 (sparse text, find as much text as possible).
    """
    import pytesseract
    from PIL import Image

    img = Image.open(image_path)
    if preprocess:
        img = preprocess_image(img)

    config = "--oem 3 --psm 11"
    return pytesseract.image_to_string(img, lang=lang, config=config)


def ocr_pil_image(img, lang: str = "rus+eng",
                  preprocess: bool = True, sparse: bool = False) -> str:
    """Распознать текст из PIL.Image напрямую (без файла).

    Args:
        img: PIL.Image
        lang: языки Tesseract
        preprocess: предобработка
        sparse: True → psm 11 (разреженный), False → psm 6 (блок)

    Returns:
        распознанный текст
    """
    import pytesseract

    if preprocess:
        img = preprocess_image(img)

    psm = "11" if sparse else "6"
    config = f"--oem 3 --psm {psm}"
    return pytesseract.image_to_string(img, lang=lang, config=config)


# --------------- PDF processing ---------------

def ocr_pdf(pdf_path: str, lang: str = "rus+eng", dpi: int = 300) -> str:
    """Распознать текст в отсканированном PDF.

    Каждая страница рендерится через PyMuPDF (fitz) в изображение,
    предобрабатывается и прогоняется через Tesseract.
    """
    import fitz
    from PIL import Image
    import io

    doc = fitz.open(pdf_path)
    full_text = ""

    for i in range(len(doc)):
        page = doc[i]
        # Рендерим страницу в pixmap
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.open(io.BytesIO(pix.tobytes("png")))

        # Два прохода: block + sparse, объединяем
        text_block = ocr_pil_image(img, lang=lang, sparse=False)
        text_sparse = ocr_pil_image(img, lang=lang, sparse=True)

        # Берём более длинный результат как основной,
        # добавляем уникальные строки из второго
        if len(text_sparse) > len(text_block):
            text_block, text_sparse = text_sparse, text_block

        base_lines = set(text_block.strip().splitlines())
        extra = [ln for ln in text_sparse.strip().splitlines()
                 if ln.strip() and ln.strip() not in base_lines]

        combined = text_block.strip()
        if extra:
            combined += "\n" + "\n".join(extra)

        full_text += f"\n=== Страница {i + 1} ===\n{combined}"

    doc.close()
    return full_text


def ocr_stamp(image_path: str, stamp_region: tuple = None) -> str:
    """Распознать текст в штампе чертежа.

    stamp_region: (x1, y1, x2, y2) — координаты области штампа.
    Если не указано, берётся правый нижний угол (типичное расположение).
    """
    from PIL import Image

    img = Image.open(image_path)
    w, h = img.size

    if stamp_region:
        crop = img.crop(stamp_region)
    else:
        # Штамп обычно в правом нижнем углу, ~30% ширины и ~20% высоты
        crop = img.crop((int(w * 0.65), int(h * 0.75), w, h))

    return ocr_pil_image(crop, lang="rus+eng", preprocess=True, sparse=False)


# --------------- parsing helpers ---------------

def parse_positions(text: str) -> list[dict]:
    """Найти позиции вида Поз.X-N, Поз. О-1 и т.п. с количеством.

    Returns:
        [{"position": "О-1", "quantity": 38}, ...]
    """
    results = []
    # Паттерн: Поз. <код>, возможно через пробелы, потом Количество: <число>
    for m in re.finditer(
        r'Поз\.?\s*([А-Яа-яA-Za-z0-9\-\.]+)\s*[,\s]*'
        r'(?:Количество|Кол[\-\.]?во)\s*:?\s*(\d+)',
        text, re.IGNORECASE
    ):
        results.append({
            "position": m.group(1).strip(),
            "quantity": int(m.group(2)),
        })

    # Если не нашли с количеством — ищем просто позиции
    if not results:
        for m in re.finditer(r'Поз\.?\s*([А-Яа-яA-Za-z0-9\-\.]+)', text):
            results.append({
                "position": m.group(1).strip(),
                "quantity": 0,
            })

    return results


def parse_articles(text: str) -> list[str]:
    """Найти артикулы — 7-8-значные числовые коды.

    Отфильтровываем маловероятные значения (< 100000).
    """
    articles = set()
    for m in re.finditer(r'\b(\d{7,8})\b', text):
        code = m.group(1)
        if int(code) > 100000:
            articles.add(code)
    return sorted(articles)


def parse_dimensions(text: str) -> list[float]:
    """Найти размеры (50–5000 мм) в тексте.

    Returns:
        отсортированный список уникальных размеров
    """
    dims = set()
    for m in re.finditer(r'\b(\d{2,4}(?:[,\.]\d{1,2})?)\b', text):
        val = float(m.group(1).replace(',', '.'))
        if 50 < val < 5000:
            dims.add(val)
    return sorted(dims)[:10]


# --------------- CLI ---------------

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Использование: python ocr_tools.py <команда> <файл>")
        print("Команды: image, sparse, pdf, stamp")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "image":
        print(ocr_image(sys.argv[2]))
    elif cmd == "sparse":
        print(ocr_image_sparse(sys.argv[2]))
    elif cmd == "pdf":
        print(ocr_pdf(sys.argv[2]))
    elif cmd == "stamp":
        print(ocr_stamp(sys.argv[2]))
