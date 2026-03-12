"""
OCR инструменты — распознавание текста на сканах чертежей КМД.
"""

import sys


def ocr_image(image_path: str, lang: str = "rus+eng") -> str:
    """Распознать текст на изображении (скан чертежа)."""
    import pytesseract
    from PIL import Image
    img = Image.open(image_path)
    return pytesseract.image_to_string(img, lang=lang)


def ocr_pdf(pdf_path: str, lang: str = "rus+eng", dpi: int = 300) -> str:
    """Распознать текст в отсканированном PDF."""
    from pdf2image import convert_from_path
    import pytesseract

    images = convert_from_path(pdf_path, dpi=dpi)
    full_text = ""
    for i, img in enumerate(images):
        text = pytesseract.image_to_string(img, lang=lang)
        full_text += f"\n=== Страница {i+1} ===\n{text}"
    return full_text


def ocr_stamp(image_path: str, stamp_region: tuple = None) -> str:
    """Распознать текст в штампе чертежа.

    stamp_region: (x1, y1, x2, y2) — координаты области штампа.
    Если не указано, берётся правый нижний угол (типичное расположение).
    """
    import pytesseract
    from PIL import Image

    img = Image.open(image_path)
    w, h = img.size

    if stamp_region:
        crop = img.crop(stamp_region)
    else:
        # Штамп обычно в правом нижнем углу, ~30% ширины и ~20% высоты
        crop = img.crop((int(w * 0.65), int(h * 0.75), w, h))

    return pytesseract.image_to_string(crop, lang="rus+eng")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Использование: python ocr_tools.py <команда> <файл>")
        print("Команды: image, pdf, stamp")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "image":
        print(ocr_image(sys.argv[2]))
    elif cmd == "pdf":
        print(ocr_pdf(sys.argv[2]))
    elif cmd == "stamp":
        print(ocr_stamp(sys.argv[2]))
