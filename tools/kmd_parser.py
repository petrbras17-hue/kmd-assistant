"""
Universal KMD Parser — Multi-format position/article/quantity extraction.

Handles ALL real-world KMD document formats:
- Поз.О-1, Поз. Д-3, Поз.ОК-12, Поз.БФ1
- Витраж В-1, Угловой витраж В-1.1
- Балконная дверь БД-1, Входная дверь ВД-1
- Окно Ок-1, Ок-13, Ок-14
- Кол-во : 19 шт., Количество: 38, Кол.во: 5
- 7-digit articles, RAL colors, dimensions WxH
"""

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Position detection — comprehensive patterns
# ---------------------------------------------------------------------------

# All known position prefixes in real KMD documents
_POS_PATTERNS = [
    # Standard: Поз.О-1, Поз. Д-3, Поз.ОК-12, Поз.БФ1, Поз.В3
    r'[Пп]оз\.?\s*([А-ЯA-Z]{1,4}\s*[\-\.]?\s*\d{1,3}(?:\.\d{1,2})?)',

    # Named constructions: Витраж В-1, Угловой витраж В-1.1
    r'(?:[Уу]гловой\s+)?[Вв]итраж\s+([А-ЯA-Z]{1,3}\s*[\-\.]\s*\d{1,3}(?:\.\d{1,2})?)',

    # Doors: Балконная дверь БД-1, Входная дверь ВД-1, Дверь Д-1
    r'(?:[Бб]алконная\s+|[Вв]ходная\s+)?[Дд]верь\s+([А-ЯA-Z]{1,4}\s*[\-\.]\s*\d{1,3})',

    # Windows: Окно Ок-1, Ок-13
    r'[Оо]кно\s+([А-ЯA-Z]{1,4}\s*[\-\.]\s*\d{1,3})',

    # Short codes without "Поз.": Ок-1, Ок-13, В-1, БД-1 (only when in table context)
    r'(?:^|\n|\|)\s*([А-ЯA-Z]{1,4}\s*[\-]\s*\d{1,3}(?:\.\d{1,2})?)\s*(?:\||,|\s+\d)',

    # Facade: Фасад Ф-1, Ф-2
    r'[Фф]асад\s+([А-ЯA-Z]{1,3}\s*[\-\.]\s*\d{1,3})',

    # Railing: Ограждение ОГ-1
    r'[Оо]граждени[ея]\s+([А-ЯA-Z]{1,4}\s*[\-\.]\s*\d{1,3})',
]

# Quantity patterns — all known formats
_QTY_PATTERNS = [
    # Количество: 38, Количество :38
    r'[Кк]оличество\s*:?\s*(\d+)',
    # Кол-во : 19 шт., Кол-во:19, Кол.во: 5
    r'[Кк]ол[\-\.\s]*во\s*:?\s*(\d+)',
    # N шт., N шт (standalone number + шт)
    r'(?:^|\s)(\d+)\s*шт\.?(?:\s|$|,)',
    # Кол.: 5
    r'[Кк]ол\.?\s*:?\s*(\d+)',
]


def normalize_position(raw: str) -> str:
    """Normalize a position code: remove extra spaces, standardize separators."""
    s = raw.strip()
    # Collapse multiple spaces
    s = re.sub(r'\s+', '', s)
    # Ensure dash between letters and numbers if missing: БФ1 → БФ-1 (optional)
    # Actually, keep original format — some KMDs use БФ1 without dash
    return s


def extract_positions(text: str) -> list[dict]:
    """
    Extract all position codes from KMD text.
    Returns [{"position": "О-1", "raw_match": "Поз.О-1", "start": 42}, ...]
    """
    found = []
    seen_positions = set()

    for pattern in _POS_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
            pos = normalize_position(m.group(1))
            if pos and pos not in seen_positions and len(pos) >= 2:
                seen_positions.add(pos)
                found.append({
                    "position": pos,
                    "raw_match": m.group(0).strip(),
                    "start": m.start(),
                })

    return found


def extract_quantity(text: str, near_pos: int = -1, window: int = 500) -> int:
    """
    Extract quantity from text. If near_pos is given, search within window chars.
    Returns the quantity or 0 if not found.
    """
    if near_pos >= 0:
        start = max(0, near_pos - 100)
        end = min(len(text), near_pos + window)
        search_text = text[start:end]
    else:
        search_text = text

    for pattern in _QTY_PATTERNS:
        m = re.search(pattern, search_text)
        if m:
            qty = int(m.group(1))
            if 0 < qty < 100000:  # Sanity check
                return qty

    return 0


def extract_articles(text: str) -> list[str]:
    """Extract 7-8 digit article codes from text."""
    articles = set()
    for m in re.finditer(r'\b(\d{7,8})\b', text):
        code = m.group(1)
        val = int(code)
        # Filter out unlikely values (dates, phone numbers, etc.)
        if 100000 < val < 99999999:
            articles.add(code)
    return sorted(articles)


def extract_dimensions(text: str) -> list[dict]:
    """
    Extract dimensions from text.
    Returns [{"width": 1200, "height": 1500, "raw": "1200x1500"}, ...]
    """
    dims = []
    seen = set()

    # WxH format: 1200x1500, 1200×1500, 1200х1500
    for m in re.finditer(r'(\d{3,4})\s*[xхXХ×]\s*(\d{3,4})', text):
        w, h = int(m.group(1)), int(m.group(2))
        key = (w, h)
        if key not in seen and 50 <= w <= 6000 and 50 <= h <= 6000:
            seen.add(key)
            dims.append({"width": w, "height": h, "raw": f"{w}x{h}"})

    return dims


def extract_dimensions_individual(text: str) -> list[float]:
    """Extract individual dimension values (mm) from text."""
    values = set()
    for m in re.finditer(r'\b(\d{2,4}(?:[,\.]\d{1,2})?)\b', text):
        val = float(m.group(1).replace(',', '.'))
        if 50 <= val <= 6000:
            values.add(val)
    return sorted(values)[:10]


def extract_color(text: str) -> str:
    """Extract color/RAL code from text."""
    # RAL code
    m = re.search(r'RAL\s*(\d{4})', text, re.IGNORECASE)
    if m:
        return f"RAL {m.group(1)}"

    # Named colors
    m = re.search(
        r'(?:цвет|окраска|покрытие|отделка)\s*[:;\-–]?\s*([^\n,]{2,40})',
        text, re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()

    return ""


def extract_handle_height(text: str) -> Optional[int]:
    """Extract handle height in mm."""
    patterns = [
        r'[Вв]ысота\s+ручки\s*[:=\s]*(\d{3,4})',
        r'[Рр]учка\s+(?:на\s+)?(?:высот[еу]|h)\s*[:=\s]*(\d{3,4})',
        r'h\s*[=:]\s*(\d{3,4})\s*(?:мм|mm)',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if 200 <= val <= 2000:
                return val
    return None


def extract_profile_system(text: str) -> Optional[str]:
    """Detect the aluminum profile system mentioned in text."""
    systems = {
        # Reynaers
        r'(?:Reynaers\s+)?MasterLine\s*8': 'Reynaers MasterLine 8',
        r'(?:Reynaers\s+)?CS\s*77': 'Reynaers CS 77',
        r'(?:Reynaers\s+)?CW\s*50': 'Reynaers CW 50',
        r'(?:Reynaers\s+)?SlimLine\s*38': 'Reynaers SlimLine 38',
        r'(?:Reynaers\s+)?Hi[\-\s]?Finity': 'Reynaers Hi-Finity',
        r'(?:Reynaers\s+)?CP\s*130': 'Reynaers CP 130',
        r'(?:Reynaers\s+)?CP\s*155': 'Reynaers CP 155',
        # Schüco
        r'(?:Sch[uü]co\s+)?AWS\s*75': 'Schüco AWS 75',
        r'(?:Sch[uü]co\s+)?FWS\s*50': 'Schüco FWS 50+',
        r'(?:Sch[uü]co\s+)?ASS\s*77': 'Schüco ASS 77 PD',
        r'(?:Sch[uü]co\s+)?ADS\s*75': 'Schüco ADS 75',
        # Alutech
        r'(?:Alutech|Алютех)\s+ALT\s*F\s*50': 'Alutech ALT F50',
        r'(?:Alutech|Алютех)\s+ALT\s*W\s*72': 'Alutech ALT W72',
        r'(?:Alutech|Алютех)\s+ALT\s*C\s*48': 'Alutech ALT C48',
        r'(?:Alutech|Алютех)\s+ALT\s*SL\s*160': 'Alutech ALT SL160',
        # TATPROF
        r'(?:TATPROF|Татпроф)\s+ТП[\-\s]*5003': 'TATPROF ТП-5003',
        r'(?:TATPROF|Татпроф)\s+ТП[\-\s]*7004': 'TATPROF ТП-7004',
        # Vidnal
        r'(?:Vidnal|Виднал)\s+[ВB][\-\s]*64': 'Vidnal В-64',
        r'(?:Vidnal|Виднал)\s+[ВB][\-\s]*72': 'Vidnal В-72',
        r'(?:Vidnal|Виднал)\s+[СC][\-\s]*50': 'Vidnal С-50',
        # AGS
        r'AGS\s*450': 'AGS 450',
        r'AGS\s*550': 'AGS 550',
        r'AGS\s*680': 'AGS 680',
    }

    for pattern, name in systems.items():
        if re.search(pattern, text, re.IGNORECASE):
            return name

    # Generic manufacturer detection
    for mfr in ['Reynaers', 'Schüco', 'Schuco', 'Alutech', 'Алютех',
                 'TATPROF', 'Татпроф', 'Vidnal', 'Виднал', 'AGS']:
        if re.search(mfr, text, re.IGNORECASE):
            return mfr

    return None


def extract_glass_formula(text: str) -> list[str]:
    """Extract glass unit formulas like 4-16-4, 4-12Ar-4i-12Ar-4i."""
    formulas = set()
    # Standard IGU: digits-digits-digits (with optional Ar, Kr, i, k suffixes)
    for m in re.finditer(
        r'\b(\d{1,2}(?:[ikIK])?\s*[\-–]\s*\d{1,2}(?:[AaKkRr]{1,2})?\s*'
        r'[\-–]\s*\d{1,2}(?:[ikIK])?'
        r'(?:\s*[\-–]\s*\d{1,2}(?:[AaKkRr]{1,2})?\s*[\-–]\s*\d{1,2}(?:[ikIK])?)?)\b',
        text
    ):
        formulas.add(m.group(1).strip())
    return sorted(formulas)


# ---------------------------------------------------------------------------
# Full page parser
# ---------------------------------------------------------------------------

def parse_kmd_page(text: str, page_num: int = 0) -> dict:
    """
    Parse a single page of KMD document.
    Returns structured data with all detected elements.
    """
    positions = extract_positions(text)
    articles = extract_articles(text)
    color = extract_color(text)
    handle_height = extract_handle_height(text)
    profile_system = extract_profile_system(text)
    glass_formulas = extract_glass_formula(text)
    dims_wxh = extract_dimensions(text)
    dims_individual = extract_dimensions_individual(text)

    # For each position, find nearby quantity
    items = []
    for pos_info in positions:
        qty = extract_quantity(text, near_pos=pos_info["start"])
        items.append({
            "position": pos_info["position"],
            "quantity": qty,
            "articles": articles,  # Page-level articles
            "dimensions": dims_wxh,
            "dimensions_mm": dims_individual,
            "color": color,
            "handle_height": handle_height,
            "glass": glass_formulas,
            "profile_system": profile_system,
            "page": page_num,
        })

    # If no positions found but we have articles, create a page-level entry
    if not items and articles:
        items.append({
            "position": f"Стр.{page_num}" if page_num else "unknown",
            "quantity": extract_quantity(text),
            "articles": articles,
            "dimensions": dims_wxh,
            "dimensions_mm": dims_individual,
            "color": color,
            "handle_height": handle_height,
            "glass": glass_formulas,
            "profile_system": profile_system,
            "page": page_num,
        })

    return {
        "items": items,
        "positions_count": len(positions),
        "articles": articles,
        "articles_count": len(articles),
        "color": color,
        "handle_height": handle_height,
        "profile_system": profile_system,
        "glass_formulas": glass_formulas,
        "page": page_num,
    }


def parse_kmd_pdf(pdf_path: str) -> dict:
    """
    Parse entire KMD PDF document.
    Returns comprehensive extraction with all positions, articles, etc.
    """
    import fitz

    doc = fitz.open(pdf_path)
    all_items = []
    all_articles = set()
    all_positions = set()
    profile_system = None
    colors = set()

    for i in range(len(doc)):
        text = doc[i].get_text().strip()
        if not text:
            continue

        page_data = parse_kmd_page(text, page_num=i + 1)

        for item in page_data["items"]:
            all_items.append(item)
            all_positions.add(item["position"])
            all_articles.update(item["articles"])
            if item["color"]:
                colors.add(item["color"])

        if page_data["profile_system"] and not profile_system:
            profile_system = page_data["profile_system"]

    doc.close()

    # Group by position
    grouped = {}
    for item in all_items:
        pos = item["position"]
        if pos not in grouped:
            grouped[pos] = {
                "position": pos,
                "articles": [],
                "quantity": 0,
                "dimensions": [],
                "dimensions_mm": [],
                "color": "",
                "handle_height": None,
                "glass": [],
                "page": item["page"],
            }
        g = grouped[pos]
        g["articles"].extend(item["articles"])
        if item["quantity"] and not g["quantity"]:
            g["quantity"] = item["quantity"]
        g["dimensions"].extend(item["dimensions"])
        g["dimensions_mm"].extend(item["dimensions_mm"])
        if item["color"] and not g["color"]:
            g["color"] = item["color"]
        if item["handle_height"] and not g["handle_height"]:
            g["handle_height"] = item["handle_height"]
        g["glass"].extend(item["glass"])

    # Deduplicate
    positions = []
    for pos_name, g in grouped.items():
        g["articles"] = sorted(set(g["articles"]))
        g["dimensions"] = list({d["raw"]: d for d in g["dimensions"]}.values())
        g["dimensions_mm"] = sorted(set(g["dimensions_mm"]))
        g["glass"] = sorted(set(g["glass"]))
        positions.append(g)

    total_items = sum(p["quantity"] for p in positions if p["quantity"])

    return {
        "positions": positions,
        "total_positions": len(positions),
        "total_items": total_items,
        "unique_articles": sorted(all_articles),
        "articles_count": len(all_articles),
        "profile_system": profile_system,
        "colors": sorted(colors),
    }


# ---------------------------------------------------------------------------
# Classify page type
# ---------------------------------------------------------------------------

def classify_page(text: str) -> str:
    """Classify KMD page type by content analysis."""
    t = text.lower()

    if any(w in t for w in ["титульный", "договор оказания", "заказчик", "подрядчик"]):
        return "титульный лист"
    if any(w in t for w in ["содержание", "ведомость рабочих чертежей"]):
        return "содержание"
    if any(w in t for w in ["общие данные", "пояснительная", "записка"]):
        return "пояснительная записка"
    if any(w in t for w in ["спецификация", "ведомость материалов", "сводная ведомость"]):
        return "спецификация"
    if any(w in t for w in ["план ", "план\n", "фасад ", "фрагмент фасада", "разрез "]):
        return "план/фасад"
    if re.search(r'поз[\.\s]', t) or re.search(r'витраж\s+[а-я]', t):
        return "чертёж изделия"
    if any(w in t for w in ["обработка", "фрезеровка", "засверловка"]):
        return "чертёж обработки"
    if any(w in t for w in ["узел", "сечение", "примыкание", "деталь"]):
        return "узел/сечение"
    if any(w in t for w in ["монтаж", "установка", "крепление"]):
        return "монтажная схема"

    return "другое"
