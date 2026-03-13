"""
КМД Rules Engine — детерминистическая система валидации КМД документации.

Кодифицирует экспертные знания инженера-конструктора алюминиевых
оконных/дверных/фасадных систем с 30-летним опытом.

НЕТ ИИ, НЕТ ML. Чистая логика, правила и математика.

Входные данные: результат parse_kmd_pdf() из kmd_parser.py.
Выходные данные: структурированный отчёт с ошибками, предупреждениями,
                 оценкой качества документации.

Коды ошибок:
  ART-xxx — артикулы (профильная система)
  DIM-xxx — размеры (габариты, допуски)
  GLS-xxx — стеклопакеты (формулы, вес)
  HDW-xxx — фурнитура (ручки, петли, ограничения)
  DOC-xxx — комплектность документации
  CRS-xxx — перекрёстная валидация (согласованность данных)
"""

from __future__ import annotations

import re
import math
from dataclasses import dataclass, field
from typing import Optional


# ===========================================================================
# Общие структуры
# ===========================================================================

@dataclass
class ValidationError:
    """Единичная ошибка/предупреждение валидации."""
    code: str
    severity: str          # "critical" | "warning" | "info"
    category: str          # "articles" | "dimensions" | "glass" | ...
    message: str
    details: str = ""
    position: str = ""     # Позиция (О-1, В-2, ...) если применимо
    page: int = 0          # Номер страницы если применимо

    def to_dict(self) -> dict:
        d = {
            "code": self.code,
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "details": self.details,
        }
        if self.position:
            d["position"] = self.position
        if self.page:
            d["page"] = self.page
        return d


# ===========================================================================
# 1. ArticleCompatibilityValidator
# ===========================================================================
# ЗАЧЕМ: Смешение артикулов разных профильных систем в одной позиции —
# гарантия того, что конструкция не соберётся на производстве.
# Профили разных систем имеют разную геометрию пазов, разные притворы,
# разные уплотнительные контуры. Даже визуально похожие — несовместимы.
# ===========================================================================

# Префиксы артикулов по профильным системам.
# Каждый производитель использует свою систему кодировки.
# Reynaers: 7-значные цифровые коды с характерными первыми 4 цифрами.
# Alutech: строковые артикулы вида AYPC.Wxx.xxxx или цифровые 109xxxxxx.
# Schüco: смешанная нумерация.

ARTICLE_PREFIXES: dict[str, list[str]] = {
    # Reynaers MasterLine 8 — оконно-дверная система тёплого класса.
    # 4080xxx — основные рамные и створочные профили ML8,
    # 0303xxx — штапики и уплотнители ML8,
    # 0535xxx — подставочные и соединительные профили,
    # 0566xxx — расширители и доборные профили.
    "Reynaers MasterLine 8": ["4080", "0303", "0535", "0566"],

    # Reynaers CS 77 — среднебюджетная тёплая система.
    "Reynaers CS 77": ["4037", "0300", "0533"],

    # Reynaers CW 50 — стоечно-ригельный фасад 50мм.
    # 3900xxx — стойки и ригели, 0325xxx — прижимные планки,
    # 0555xxx — термовставки и декоративные крышки.
    "Reynaers CW 50": ["3900", "0325", "0555"],

    # Reynaers SlimLine 38 — минималистичная система с узкими видимыми частями.
    "Reynaers SlimLine 38": ["4100", "0310"],

    # Reynaers Hi-Finity — сверхбольшие раздвижные конструкции.
    "Reynaers Hi-Finity": ["4200", "0315"],

    # Reynaers CP 130 — раздвижная система подъёмно-сдвижная.
    "Reynaers CP 130": ["4300", "0320"],

    # Reynaers CP 155 — раздвижная система параллельно-сдвижная.
    "Reynaers CP 155": ["4310", "0321"],

    # Schüco AWS 75 — основная оконная система Schüco.
    # Артикулы Schüco начинаются с характерных для серии префиксов.
    "Schüco AWS 75": ["2490", "2560", "2741"],

    # Schüco FWS 50+ — фасадная стоечно-ригельная система.
    "Schüco FWS 50+": ["2630", "2640", "2670"],

    # Schüco ASS 77 PD — раздвижная система.
    "Schüco ASS 77 PD": ["2780", "2790"],

    # Schüco ADS 75 — дверная система Schüco.
    "Schüco ADS 75": ["2500", "2510"],

    # Alutech ALT W72 — тёплая оконно-дверная система Алютех.
    # AYPC.W72 — стандартный формат артикулов Алютех, 109052806 — крепёж.
    "Alutech ALT W72": ["AYPC.W72", "109052"],

    # Alutech ALT C48 — стоечно-ригельная фасадная система Алютех.
    "Alutech ALT C48": ["AYPC.C48", "109053"],

    # Alutech ALT F50 — фасадная система.
    "Alutech ALT F50": ["AYPC.F50", "109054"],

    # Alutech ALT SL160 — раздвижная подъёмно-сдвижная система.
    "Alutech ALT SL160": ["AYPC.SL160", "109055"],

    # TATPROF ТП-5003 — тёплая оконно-дверная система.
    "TATPROF ТП-5003": ["5003"],

    # TATPROF ТП-7004 — фасадная стоечно-ригельная система.
    "TATPROF ТП-7004": ["7004"],

    # Vidnal В-64 — тёплая оконная система.
    "Vidnal В-64": ["B64", "В64"],

    # Vidnal В-72 — тёплая оконная система повышенной теплоизоляции.
    "Vidnal В-72": ["B72", "В72"],

    # Vidnal С-50 — фасадная система.
    "Vidnal С-50": ["C50", "С50"],
}


def _match_article_to_system(article: str) -> list[str]:
    """Определить, к каким профильным системам может относиться артикул.

    Артикул может совпадать с несколькими системами одного производителя
    (например, общие комплектующие), но НИКОГДА — с системами разных
    производителей.
    """
    matched = []
    for system, prefixes in ARTICLE_PREFIXES.items():
        for prefix in prefixes:
            if article.startswith(prefix):
                matched.append(system)
                break
    return matched


class ArticleCompatibilityValidator:
    """Проверяет совместимость артикулов в пределах одной позиции и документа.

    Основной принцип: ВСЕ артикулы одной позиции должны принадлежать
    ОДНОЙ профильной системе. Смешение систем — критическая ошибка.
    """

    def validate(self, parsed_data: dict) -> list[ValidationError]:
        errors: list[ValidationError] = []
        declared_system = parsed_data.get("profile_system", "")

        # --- Проверка артикулов в каждой позиции ---
        for pos in parsed_data.get("positions", []):
            pos_name = pos.get("position", "?")
            page = pos.get("page", 0)
            articles = pos.get("articles", [])
            if not articles:
                continue

            systems_found: set[str] = set()
            unrecognized: list[str] = []

            for art in articles:
                matched = _match_article_to_system(art)
                if matched:
                    systems_found.update(matched)
                else:
                    unrecognized.append(art)

            # Смешение профильных систем в одной позиции — КРИТИЧЕСКАЯ ошибка.
            # На производстве такое изделие невозможно собрать:
            # пазы не совпадут, уплотнители не встанут, притвор не закроется.
            if len(systems_found) > 1:
                errors.append(ValidationError(
                    code="ART-001",
                    severity="critical",
                    category="articles",
                    message=f"Смешение профильных систем в позиции {pos_name}",
                    details=(
                        f"Обнаружены артикулы из разных систем: "
                        f"{', '.join(sorted(systems_found))}. "
                        f"Все профили одной позиции ОБЯЗАНЫ принадлежать одной системе."
                    ),
                    position=pos_name,
                    page=page,
                ))

            # Несоответствие заявленной системе на титульном листе.
            # Если на титуле написано "MasterLine 8", а в чертежах стоят
            # артикулы CW 50 — значит либо титул скопирован с прошлого проекта,
            # либо проектировщик ошибся в выборе системы.
            if declared_system and systems_found:
                for sys_name in systems_found:
                    if sys_name != declared_system:
                        errors.append(ValidationError(
                            code="ART-002",
                            severity="critical",
                            category="articles",
                            message=(
                                f"Артикулы позиции {pos_name} не соответствуют "
                                f"заявленной системе «{declared_system}»"
                            ),
                            details=(
                                f"Артикулы соответствуют системе «{sys_name}», "
                                f"но в документе указана «{declared_system}»."
                            ),
                            position=pos_name,
                            page=page,
                        ))

            # Нераспознанные артикулы — предупреждение.
            # Могут быть комплектующими (крепёж, герметик, метизы),
            # но могут и указывать на опечатку в номере артикула.
            if unrecognized and len(unrecognized) > len(articles) * 0.5:
                errors.append(ValidationError(
                    code="ART-003",
                    severity="warning",
                    category="articles",
                    message=f"Более 50% артикулов позиции {pos_name} не распознаны",
                    details=(
                        f"Нераспознанные артикулы: {', '.join(unrecognized[:10])}. "
                        f"Возможно, неизвестная профильная система или опечатки."
                    ),
                    position=pos_name,
                    page=page,
                ))

        # --- Проверка уникальных артикулов на уровне документа ---
        all_articles = parsed_data.get("unique_articles", [])
        if all_articles:
            doc_systems: set[str] = set()
            for art in all_articles:
                matched = _match_article_to_system(art)
                doc_systems.update(matched)

            # Больше одной базовой системы во всём документе — подозрительно.
            # В реальности бывают исключения (например, витраж + окна из разных
            # систем), но это должно быть явно обосновано.
            manufacturers = set()
            for sys_name in doc_systems:
                mfr = sys_name.split()[0]  # "Reynaers", "Schüco", "Alutech"...
                manufacturers.add(mfr)

            if len(manufacturers) > 1:
                errors.append(ValidationError(
                    code="ART-004",
                    severity="warning",
                    category="articles",
                    message="В документе обнаружены артикулы разных производителей",
                    details=(
                        f"Производители: {', '.join(sorted(manufacturers))}. "
                        f"Обычно КМД содержит изделия одного производителя. "
                        f"Проверьте, что это не ошибка копирования из другого проекта."
                    ),
                ))

        return errors


# ===========================================================================
# 2. DimensionValidator
# ===========================================================================
# ЗАЧЕМ: Ошибки в размерах — самая дорогая категория дефектов.
# Неправильный размер → нарезали профиль → выбросили материал + задержка.
# Тепловое расширение не учтено → конструкция заклинивает летом или
# продувается зимой.
# ===========================================================================

# Максимальные габариты створки (ширина x высота, мм) по профильным системам.
# Ограничения определяются жёсткостью профиля и возможностями фурнитуры.
# Превышение → прогиб створки → негерметичность → рекламация.
MAX_SASH_DIMENSIONS: dict[str, tuple[int, int]] = {
    "Reynaers MasterLine 8": (1400, 2400),
    "Reynaers CS 77": (1300, 2300),
    "Reynaers CW 50": (2500, 3500),       # фасадное заполнение — поле остекления
    "Reynaers SlimLine 38": (1000, 2200),  # узкий профиль — жёсткость ниже
    "Reynaers Hi-Finity": (3000, 3000),    # спецсистема для больших полотен
    "Reynaers CP 130": (2000, 2700),
    "Reynaers CP 155": (3000, 2700),
    "Schüco AWS 75": (1400, 2400),
    "Schüco FWS 50+": (2500, 3500),
    "Schüco ASS 77 PD": (3200, 2700),
    "Schüco ADS 75": (1400, 2800),
    "Alutech ALT W72": (1300, 2300),
    "Alutech ALT C48": (2400, 3500),
    "Alutech ALT F50": (2500, 3500),
    "Alutech ALT SL160": (2500, 2700),
    "TATPROF ТП-5003": (1300, 2300),
    "TATPROF ТП-7004": (2400, 3200),
    "Vidnal В-64": (1200, 2200),
    "Vidnal В-72": (1300, 2400),
    "Vidnal С-50": (2400, 3200),
}

# Коэффициент линейного теплового расширения алюминия: 23.1 мкм/(м·°C).
# При длине профиля 3м и перепаде температуры 60°C (от -30 до +30):
# ΔL = 3.0 * 23.1e-6 * 60 = 4.16 мм.
# Если зазоры не предусмотрены — профиль упрётся в стену, деформируется,
# выдавит уплотнение или сломает крепёж.
ALPHA_ALUMINUM = 23.1e-6  # мкм/(м·°C) → м/(м·°C) = безразмерный коэф.

# Стандартные допуски по ГОСТ 21519-2003 и каталогам производителей.
TOLERANCE_PROFILE_MM = 1.0     # допуск на длину профиля ±1мм
TOLERANCE_GLASS_MM = 0.5       # допуск на размеры стеклопакета ±0.5мм
TOLERANCE_OVERALL_MM = 2.0     # допуск на габаритный размер изделия ±2мм


class DimensionValidator:
    """Валидатор размеров: габариты, допуски, тепловое расширение."""

    def __init__(self, delta_t: float = 50.0):
        """
        delta_t: расчётный перепад температур, °C.
        Типично 40-60°C (от минимума зимой до максимума на солнце летом).
        Для южных регионов может быть выше (фасады на солнечной стороне
        нагреваются до +80°C при наружном воздухе +40°C).
        """
        self.delta_t = delta_t

    def validate(self, parsed_data: dict) -> list[ValidationError]:
        errors: list[ValidationError] = []
        profile_system = parsed_data.get("profile_system", "")

        for pos in parsed_data.get("positions", []):
            pos_name = pos.get("position", "?")
            page = pos.get("page", 0)
            dims = pos.get("dimensions", [])

            for dim in dims:
                w = dim.get("width", 0)
                h = dim.get("height", 0)
                if not w or not h:
                    continue

                # --- Проверка максимальных габаритов створки ---
                # Превышение допустимых размеров створки приведёт к:
                # 1) Провисанию створки на петлях (из-за веса)
                # 2) Невозможности обеспечить герметичность притвора
                # 3) Повышенному износу фурнитуры
                max_dims = MAX_SASH_DIMENSIONS.get(profile_system)
                if max_dims:
                    max_w, max_h = max_dims
                    if w > max_w:
                        errors.append(ValidationError(
                            code="DIM-001",
                            severity="critical",
                            category="dimensions",
                            message=(
                                f"Ширина {w}мм превышает максимум "
                                f"{max_w}мм для {profile_system}"
                            ),
                            details=(
                                f"Позиция {pos_name}: ширина {w}мм > "
                                f"допустимая {max_w}мм. Створка будет провисать, "
                                f"фурнитура не выдержит нагрузку."
                            ),
                            position=pos_name,
                            page=page,
                        ))
                    if h > max_h:
                        errors.append(ValidationError(
                            code="DIM-002",
                            severity="critical",
                            category="dimensions",
                            message=(
                                f"Высота {h}мм превышает максимум "
                                f"{max_h}мм для {profile_system}"
                            ),
                            details=(
                                f"Позиция {pos_name}: высота {h}мм > "
                                f"допустимая {max_h}мм. Необходимо разделить "
                                f"на несколько створок или использовать другую систему."
                            ),
                            position=pos_name,
                            page=page,
                        ))

                # --- Проверка теплового расширения ---
                # Для длинных профилей (> 2000мм) тепловое расширение
                # становится значимым. Если в чертеже не предусмотрены
                # компенсационные зазоры — конструкция «встанет колом» летом.
                for length_mm, axis in [(w, "ширине"), (h, "высоте")]:
                    length_m = length_mm / 1000.0
                    expansion_mm = length_m * ALPHA_ALUMINUM * self.delta_t * 1000
                    # Порог предупреждения: расширение > 1.5мм
                    # (при стандартном допуске ±2мм общий это уже 75%)
                    if expansion_mm > 1.5:
                        errors.append(ValidationError(
                            code="DIM-003",
                            severity="warning",
                            category="dimensions",
                            message=(
                                f"Значительное тепловое расширение по {axis}: "
                                f"{expansion_mm:.1f}мм"
                            ),
                            details=(
                                f"Позиция {pos_name}: при длине {length_mm}мм "
                                f"и ΔT={self.delta_t}°C расширение составит "
                                f"{expansion_mm:.2f}мм. Убедитесь, что предусмотрены "
                                f"компенсационные зазоры в узлах примыкания."
                            ),
                            position=pos_name,
                            page=page,
                        ))

                # --- Подозрительно малые размеры ---
                # Окно менее 300x300мм — скорее всего ошибка парсинга
                # или опечатка в чертеже. Такие размеры встречаются только
                # в технологических люках, и это требует отдельного проектирования.
                if w < 300 or h < 300:
                    errors.append(ValidationError(
                        code="DIM-004",
                        severity="warning",
                        category="dimensions",
                        message=f"Подозрительно малый размер: {w}x{h}мм",
                        details=(
                            f"Позиция {pos_name}: размер {w}x{h}мм необычно мал "
                            f"для алюминиевой конструкции. Проверьте корректность."
                        ),
                        position=pos_name,
                        page=page,
                    ))

                # --- Нестандартные пропорции ---
                # Соотношение сторон > 1:5 — конструкция будет нестабильной.
                # Узкие и высокие створки подвержены ветровым нагрузкам
                # и могут деформироваться.
                if w > 0 and h > 0:
                    ratio = max(w, h) / min(w, h)
                    if ratio > 5.0:
                        errors.append(ValidationError(
                            code="DIM-005",
                            severity="warning",
                            category="dimensions",
                            message=(
                                f"Нестандартная пропорция {ratio:.1f}:1 "
                                f"для позиции {pos_name}"
                            ),
                            details=(
                                f"Размер {w}x{h}мм — соотношение сторон "
                                f"{ratio:.1f}:1. Конструкция может быть нестабильной "
                                f"при ветровых нагрузках."
                            ),
                            position=pos_name,
                            page=page,
                        ))

        # --- Проверка согласованности размеров между страницами ---
        # Один и тот же размер позиции должен быть одинаков на всех страницах
        # документа. Расхождение > допуска → ошибка.
        pos_dims_map: dict[str, list[tuple[int, int, int]]] = {}
        for pos in parsed_data.get("positions", []):
            pos_name = pos.get("position", "?")
            page = pos.get("page", 0)
            for dim in pos.get("dimensions", []):
                w, h = dim.get("width", 0), dim.get("height", 0)
                if w and h:
                    pos_dims_map.setdefault(pos_name, []).append((w, h, page))

        for pos_name, dim_list in pos_dims_map.items():
            if len(dim_list) < 2:
                continue
            # Сравниваем все пары размеров
            base_w, base_h, base_page = dim_list[0]
            for w, h, page in dim_list[1:]:
                dw = abs(w - base_w)
                dh = abs(h - base_h)
                if dw > TOLERANCE_OVERALL_MM or dh > TOLERANCE_OVERALL_MM:
                    errors.append(ValidationError(
                        code="DIM-006",
                        severity="critical",
                        category="dimensions",
                        message=(
                            f"Расхождение размеров позиции {pos_name} "
                            f"на разных страницах"
                        ),
                        details=(
                            f"Стр. {base_page}: {base_w}x{base_h}мм, "
                            f"стр. {page}: {w}x{h}мм. "
                            f"Разница: Δw={dw}мм, Δh={dh}мм. "
                            f"Допуск: ±{TOLERANCE_OVERALL_MM}мм."
                        ),
                        position=pos_name,
                        page=page,
                    ))

        return errors


# ===========================================================================
# 3. GlassValidator
# ===========================================================================
# ЗАЧЕМ: Стеклопакет — самый тяжёлый и хрупкий элемент конструкции.
# Ошибка в формуле стеклопакета может привести к:
# - Превышению допустимого веса створки → провисание, поломка фурнитуры
# - Неправильной теплоизоляции → конденсат, промерзание
# - Разрушению стекла от ветровой/снеговой нагрузки
# ===========================================================================

# Стандартные толщины стёкол, мм.
# Нестандартные толщины — ошибка или спецзаказ, требующий подтверждения.
STANDARD_GLASS_THICKNESSES = {3, 4, 5, 6, 8, 10, 12}

# Стандартные ширины дистанционных рамок (спейсеров), мм.
# Определяют расстояние между стёклами в стеклопакете.
# Слишком узкая рамка — конвекция газа, плохая теплоизоляция.
# Слишком широкая — тоже конвекция + риск разрушения от давления.
STANDARD_SPACER_WIDTHS = {6, 8, 10, 12, 14, 16, 18, 20, 22, 24}

# Плотность стекла: 2.5 кг на м² на 1мм толщины.
# Это физическая константа для натрий-кальций-силикатного стекла (ГОСТ 111-2014).
GLASS_DENSITY_KG_PER_M2_PER_MM = 2.5

# Допустимые газовые заполнения для герметичных стеклопакетов.
# Ar (аргон) — стандарт, снижает теплопроводность на ~15%.
# Kr (криптон) — премиум, снижает на ~25%, но в 10 раз дороже.
# Воздух — бюджетный вариант (без маркировки).
# Любой другой газ — ошибка.
VALID_GAS_FILLS = {"Ar", "Kr", "Air", ""}


def _parse_glass_formula(formula: str) -> Optional[dict]:
    """Разобрать формулу стеклопакета на составляющие.

    Примеры:
        "4-16-4"         → однокамерный, 2 стекла по 4мм, рамка 16мм
        "4-12Ar-4i-12Ar-4i" → двухкамерный с аргоном и i-покрытием
        "6-16Ar-4-16Ar-6" → двухкамерный с разными стёклами

    Returns:
        {
            "glass_layers": [4, 4, 4],       # толщины стёкол
            "spacers": [12, 12],             # ширины рамок
            "gas_fills": ["Ar", "Ar"],       # газовое заполнение
            "coatings": ["", "i", "i"],      # покрытия стёкол
            "total_glass_mm": 12,            # суммарная толщина стёкол
            "total_thickness_mm": 36,        # полная толщина стеклопакета
            "chambers": 2,                   # количество камер
        }
    """
    # Нормализуем разделители: – → -, убираем пробелы вокруг дефисов
    f = formula.replace("–", "-").replace("—", "-")
    f = re.sub(r'\s*-\s*', '-', f)

    parts = f.split("-")
    if len(parts) < 3:
        return None

    glass_layers: list[int] = []
    spacers: list[int] = []
    gas_fills: list[str] = []
    coatings: list[str] = []

    # Формула чередуется: стекло - рамка - стекло - рамка - стекло
    for i, part in enumerate(parts):
        if i % 2 == 0:
            # Стекло: число + опциональное покрытие (i, k, K)
            m = re.match(r'^(\d{1,2})([ikIK]*)$', part)
            if not m:
                return None
            glass_layers.append(int(m.group(1)))
            coatings.append(m.group(2).lower())
        else:
            # Рамка: число + опциональный газ (Ar, Kr)
            m = re.match(r'^(\d{1,2})([A-Za-z]*)$', part)
            if not m:
                return None
            spacers.append(int(m.group(1)))
            gas = m.group(2)
            # Нормализуем: "Ar" и "ar" → "Ar"
            if gas.lower() == "ar":
                gas = "Ar"
            elif gas.lower() == "kr":
                gas = "Kr"
            gas_fills.append(gas)

    if not glass_layers or not spacers:
        return None
    if len(glass_layers) != len(spacers) + 1:
        return None

    total_glass = sum(glass_layers)
    total_thickness = total_glass + sum(spacers)

    return {
        "glass_layers": glass_layers,
        "spacers": spacers,
        "gas_fills": gas_fills,
        "coatings": coatings,
        "total_glass_mm": total_glass,
        "total_thickness_mm": total_thickness,
        "chambers": len(spacers),
    }


class GlassValidator:
    """Валидатор стеклопакетов: формулы, вес, допуски."""

    def validate(self, parsed_data: dict) -> list[ValidationError]:
        errors: list[ValidationError] = []

        for pos in parsed_data.get("positions", []):
            pos_name = pos.get("position", "?")
            page = pos.get("page", 0)
            glass_formulas = pos.get("glass", [])
            dims = pos.get("dimensions", [])

            for formula in glass_formulas:
                parsed = _parse_glass_formula(formula)

                if parsed is None:
                    errors.append(ValidationError(
                        code="GLS-001",
                        severity="warning",
                        category="glass",
                        message=f"Не удалось разобрать формулу стеклопакета: {formula}",
                        details=(
                            f"Позиция {pos_name}: формула «{formula}» "
                            f"не соответствует стандартному формату."
                        ),
                        position=pos_name,
                        page=page,
                    ))
                    continue

                # --- Проверка толщин стёкол ---
                # Нестандартная толщина может быть: триплекс (3.3.1 = 6.38мм
                # округляют до 6), калёное 12мм — но тогда нужна маркировка.
                for gl_mm in parsed["glass_layers"]:
                    if gl_mm not in STANDARD_GLASS_THICKNESSES:
                        errors.append(ValidationError(
                            code="GLS-002",
                            severity="warning",
                            category="glass",
                            message=(
                                f"Нестандартная толщина стекла {gl_mm}мм "
                                f"в формуле {formula}"
                            ),
                            details=(
                                f"Позиция {pos_name}: стандартные толщины — "
                                f"{sorted(STANDARD_GLASS_THICKNESSES)}мм. "
                                f"Если это триплекс или закалённое стекло, "
                                f"убедитесь в корректности обозначения."
                            ),
                            position=pos_name,
                            page=page,
                        ))

                # --- Проверка ширин дистанционных рамок ---
                # Слишком узкая рамка (<6мм) — технологически не производится.
                # Слишком широкая (>24мм) — конвекция газа, потеря теплоизоляции.
                for sp_mm in parsed["spacers"]:
                    if sp_mm not in STANDARD_SPACER_WIDTHS:
                        errors.append(ValidationError(
                            code="GLS-003",
                            severity="warning",
                            category="glass",
                            message=(
                                f"Нестандартная ширина дистанционной рамки {sp_mm}мм "
                                f"в формуле {formula}"
                            ),
                            details=(
                                f"Позиция {pos_name}: стандартные ширины рамок — "
                                f"{sorted(STANDARD_SPACER_WIDTHS)}мм."
                            ),
                            position=pos_name,
                            page=page,
                        ))

                # --- Проверка газового заполнения ---
                for gas in parsed["gas_fills"]:
                    if gas and gas not in VALID_GAS_FILLS:
                        errors.append(ValidationError(
                            code="GLS-004",
                            severity="warning",
                            category="glass",
                            message=(
                                f"Неизвестное газовое заполнение «{gas}» "
                                f"в формуле {formula}"
                            ),
                            details=(
                                f"Позиция {pos_name}: допустимые газы — Ar (аргон), "
                                f"Kr (криптон). «{gas}» не распознан."
                            ),
                            position=pos_name,
                            page=page,
                        ))

                # --- Проверка структуры: однокамерный или двухкамерный ---
                chambers = parsed["chambers"]
                if chambers < 1 or chambers > 3:
                    # 3 камеры (4 стекла) — крайне редко, почти наверняка ошибка.
                    errors.append(ValidationError(
                        code="GLS-005",
                        severity="warning" if chambers == 3 else "critical",
                        category="glass",
                        message=(
                            f"Необычное количество камер стеклопакета: "
                            f"{chambers} в формуле {formula}"
                        ),
                        details=(
                            f"Позиция {pos_name}: стандарт — 1 камера "
                            f"(2 стекла + 1 рамка) или 2 камеры (3 стекла + "
                            f"2 рамки). {chambers} камер — требует подтверждения."
                        ),
                        position=pos_name,
                        page=page,
                    ))

                # --- Расчёт и проверка веса стеклопакета ---
                # Вес стеклопакета = площадь (м²) × сумма толщин стёкол (мм) × 2.5
                # Тяжёлый стеклопакет → нагрузка на фурнитуру → провисание створки.
                if dims:
                    for dim in dims:
                        w_m = dim.get("width", 0) / 1000.0
                        h_m = dim.get("height", 0) / 1000.0
                        if w_m <= 0 or h_m <= 0:
                            continue
                        area = w_m * h_m
                        weight = area * parsed["total_glass_mm"] * GLASS_DENSITY_KG_PER_M2_PER_MM

                        # > 80 кг — предупреждение: нужна усиленная фурнитура.
                        # > 150 кг — критическая ошибка: стандартная фурнитура
                        #   не выдержит, нужна спецфурнитура или пересмотр конструкции.
                        if weight > 150:
                            errors.append(ValidationError(
                                code="GLS-006",
                                severity="critical",
                                category="glass",
                                message=(
                                    f"Вес стеклопакета {weight:.0f}кг "
                                    f"превышает 150кг (позиция {pos_name})"
                                ),
                                details=(
                                    f"Формула {formula}, размер "
                                    f"{dim.get('width')}x{dim.get('height')}мм, "
                                    f"площадь {area:.2f}м², вес {weight:.1f}кг. "
                                    f"Стандартная фурнитура не рассчитана на такой вес. "
                                    f"Необходима спецфурнитура или пересмотр конструкции."
                                ),
                                position=pos_name,
                                page=page,
                            ))
                        elif weight > 80:
                            errors.append(ValidationError(
                                code="GLS-007",
                                severity="warning",
                                category="glass",
                                message=(
                                    f"Значительный вес стеклопакета: "
                                    f"{weight:.0f}кг (позиция {pos_name})"
                                ),
                                details=(
                                    f"Формула {formula}, размер "
                                    f"{dim.get('width')}x{dim.get('height')}мм, "
                                    f"вес {weight:.1f}кг. Убедитесь, что "
                                    f"выбрана фурнитура, рассчитанная на вес ≥{weight:.0f}кг."
                                ),
                                position=pos_name,
                                page=page,
                            ))

                # --- Проверка общей толщины стеклопакета ---
                # Стеклопакет должен помещаться в фальц профиля.
                # Типичный фальц: 24-52мм для разных систем.
                total = parsed["total_thickness_mm"]
                if total > 52:
                    errors.append(ValidationError(
                        code="GLS-008",
                        severity="critical",
                        category="glass",
                        message=(
                            f"Общая толщина стеклопакета {total}мм может не "
                            f"поместиться в фальц профиля"
                        ),
                        details=(
                            f"Позиция {pos_name}, формула {formula}: "
                            f"толщина {total}мм. Максимальный фальц большинства "
                            f"систем — 52мм. Проверьте совместимость с профилем."
                        ),
                        position=pos_name,
                        page=page,
                    ))
                elif total < 16:
                    errors.append(ValidationError(
                        code="GLS-009",
                        severity="warning",
                        category="glass",
                        message=(
                            f"Тонкий стеклопакет {total}мм — возможен конденсат "
                            f"и низкая теплоизоляция"
                        ),
                        details=(
                            f"Позиция {pos_name}, формула {formula}: "
                            f"толщина {total}мм. Для климата с отрицательными "
                            f"температурами рекомендуется ≥24мм."
                        ),
                        position=pos_name,
                        page=page,
                    ))

        return errors


# ===========================================================================
# 4. HardwareValidator
# ===========================================================================
# ЗАЧЕМ: Фурнитура определяет работоспособность и долговечность конструкции.
# Неправильная высота ручки — неудобство для пользователя + нарушение
# норм доступной среды. Перегруз петель — провисание створки через 1-2 года.
# Несоответствие типа открывания — створка не откроется как ожидается.
# ===========================================================================

# Допустимые диапазоны высоты ручки (от низа створки), мм.
# Для окон: 800-1200мм — эргономичная высота для среднего роста.
# Для дверей: 900-1100мм — стандарт по ГОСТ и нормам доступности.
HANDLE_HEIGHT_RANGE = {
    "window": (800, 1200),
    "door": (900, 1100),
}

# Максимальный вес створки по типу фурнитуры, кг.
# Превышение → ускоренный износ → провисание → негерметичность.
# Данные из каталогов производителей фурнитуры.
MAX_SASH_WEIGHT_BY_HARDWARE: dict[str, int] = {
    "Roto NT": 130,
    "Roto NX": 150,
    "Roto AL": 160,
    "Siegenia Titan AF": 150,
    "Siegenia Titan AF Aero": 130,
    "Siegenia Portal HS": 400,     # подъёмно-сдвижная — особый случай
    "GU": 130,
    "GU Uni-Jet": 150,
    "MACO": 130,
    "MACO Rail": 200,              # раздвижная фурнитура
    "Winkhaus activPilot": 130,
    "Winkhaus autoPilot": 150,
}

# Количество петель по весу створки.
# Определяется несущей способностью каждой петли (~40-50кг на петлю).
# Недостаточно петель → неравномерная нагрузка → перекос → продувание.
HINGE_COUNT_RULES: list[tuple[float, float, int]] = [
    (0, 80, 2),       # до 80кг — 2 петли
    (80, 130, 3),     # 80-130кг — 3 петли
    (130, float('inf'), 4),  # более 130кг — 4 петли
]

# Допустимые типы открывания.
# Каждый тип имеет свои ограничения по размерам и весу.
VALID_OPENING_TYPES = {
    "поворотное",           # обычное распашное (налево/направо)
    "откидное",             # откидывается сверху вниз (проветривание)
    "поворотно-откидное",   # комбинированное (самый частый тип)
    "раздвижное",           # сдвигается вбок
    "подъёмно-сдвижное",    # приподнимается и сдвигается (HS)
    "параллельно-сдвижное", # PSK
    "складное",             # гармошка
    "глухое",               # не открывается
    "фрамужное",            # откидывается наружу (верхняя фрамуга)
}


def _guess_position_type(pos_name: str) -> str:
    """Определить тип позиции (окно/дверь) по имени.

    Д-1, БД-1, ВД-1 → дверь. О-1, ОК-1, В-1 → окно.
    """
    name_upper = pos_name.upper().replace(" ", "")
    if re.match(r'^(Д|БД|ВД|ДВЕРЬ)', name_upper):
        return "door"
    return "window"


class HardwareValidator:
    """Валидатор фурнитуры: ручки, петли, типы открывания, весовые ограничения."""

    def validate(self, parsed_data: dict) -> list[ValidationError]:
        errors: list[ValidationError] = []

        for pos in parsed_data.get("positions", []):
            pos_name = pos.get("position", "?")
            page = pos.get("page", 0)
            handle_h = pos.get("handle_height")
            pos_type = _guess_position_type(pos_name)

            # --- Проверка высоты ручки ---
            if handle_h is not None:
                h_range = HANDLE_HEIGHT_RANGE.get(pos_type, (800, 1200))
                if handle_h < h_range[0]:
                    errors.append(ValidationError(
                        code="HDW-001",
                        severity="warning",
                        category="hardware",
                        message=(
                            f"Высота ручки {handle_h}мм ниже нормы "
                            f"{h_range[0]}мм ({pos_name})"
                        ),
                        details=(
                            f"Позиция {pos_name} ({pos_type}): "
                            f"высота ручки {handle_h}мм. "
                            f"Нормативный диапазон: {h_range[0]}-{h_range[1]}мм. "
                            f"Низкая ручка неудобна в эксплуатации и может "
                            f"не соответствовать нормам доступной среды."
                        ),
                        position=pos_name,
                        page=page,
                    ))
                elif handle_h > h_range[1]:
                    errors.append(ValidationError(
                        code="HDW-002",
                        severity="warning",
                        category="hardware",
                        message=(
                            f"Высота ручки {handle_h}мм выше нормы "
                            f"{h_range[1]}мм ({pos_name})"
                        ),
                        details=(
                            f"Позиция {pos_name} ({pos_type}): "
                            f"высота ручки {handle_h}мм. "
                            f"Нормативный диапазон: {h_range[0]}-{h_range[1]}мм. "
                            f"Высокая ручка затрудняет управление, особенно "
                            f"для людей невысокого роста и маломобильных групп."
                        ),
                        position=pos_name,
                        page=page,
                    ))

            # --- Расчёт веса створки и проверка петель ---
            # Вес створки ≈ вес стеклопакета + вес профильной рамки.
            # Рамку оцениваем приблизительно: периметр × ~1.5 кг/м
            # (средний вес алюминиевого профиля с термовставкой).
            dims = pos.get("dimensions", [])
            glass_formulas = pos.get("glass", [])

            for dim in dims:
                w = dim.get("width", 0)
                h = dim.get("height", 0)
                if not w or not h:
                    continue

                w_m = w / 1000.0
                h_m = h / 1000.0
                area = w_m * h_m

                # Вес рамки створки
                perimeter = 2 * (w_m + h_m)
                frame_weight = perimeter * 1.5  # ~1.5 кг/погонный метр

                # Вес стеклопакета (берём первую формулу если есть)
                glass_weight = 0.0
                if glass_formulas:
                    parsed_glass = _parse_glass_formula(glass_formulas[0])
                    if parsed_glass:
                        glass_weight = (
                            area
                            * parsed_glass["total_glass_mm"]
                            * GLASS_DENSITY_KG_PER_M2_PER_MM
                        )

                total_weight = frame_weight + glass_weight

                if total_weight > 0:
                    # Определяем необходимое количество петель
                    required_hinges = 2
                    for w_min, w_max, hinges in HINGE_COUNT_RULES:
                        if w_min <= total_weight < w_max:
                            required_hinges = hinges
                            break

                    if required_hinges > 2:
                        errors.append(ValidationError(
                            code="HDW-003",
                            severity="info",
                            category="hardware",
                            message=(
                                f"Позиция {pos_name}: расчётный вес створки "
                                f"{total_weight:.0f}кг → требуется {required_hinges} петли"
                            ),
                            details=(
                                f"Размер {w}x{h}мм, вес рамки ~{frame_weight:.1f}кг, "
                                f"вес стеклопакета ~{glass_weight:.1f}кг, "
                                f"итого ~{total_weight:.0f}кг. "
                                f"При весе >80кг — 3 петли, >130кг — 4 петли."
                            ),
                            position=pos_name,
                            page=page,
                        ))

                    # Проверка по типу фурнитуры (если в документе указан)
                    # Проверяем все известные типы фурнитуры по максимальному весу
                    for hw_name, max_weight in MAX_SASH_WEIGHT_BY_HARDWARE.items():
                        # Ищем упоминание фурнитуры в артикулах или тексте
                        # (в текущем формате данных фурнитура не выделена отдельно,
                        # поэтому проверяем по абсолютному максимуму).
                        pass  # Будет использоваться при расширении формата

                    # Общий максимум для стандартной фурнитуры — 150кг.
                    if total_weight > 150:
                        errors.append(ValidationError(
                            code="HDW-004",
                            severity="critical",
                            category="hardware",
                            message=(
                                f"Вес створки {total_weight:.0f}кг превышает "
                                f"предел стандартной фурнитуры (150кг)"
                            ),
                            details=(
                                f"Позиция {pos_name}: расчётный вес {total_weight:.0f}кг. "
                                f"Максимум для Siegenia Titan AF — 150кг, "
                                f"Roto NX — 150кг. Необходима спецфурнитура "
                                f"(например, Siegenia Portal HS для раздвижных "
                                f"конструкций до 400кг)."
                            ),
                            position=pos_name,
                            page=page,
                        ))

        return errors


# ===========================================================================
# 5. DocumentCompletenessValidator
# ===========================================================================
# ЗАЧЕМ: Неполный комплект КМД = производство не может начать работу,
# монтажники не знают, как ставить. В итоге — простои, звонки проектировщику,
# ошибки «на глаз».
# Чек-лист основан на требованиях АЛЬДМЕГАЛАБ к комплектности КМД.
# ===========================================================================

# Обязательные разделы КМД по стандарту АЛЬДМЕГАЛАБ.
# Каждый раздел — это тип страницы, который ОБЯЗАН присутствовать.
# Ключевые слова для поиска в тексте страниц.
REQUIRED_SECTIONS: list[dict] = [
    {
        "name": "Титульный лист",
        "name_en": "title_page",
        "keywords": ["титульный", "договор", "заказчик", "подрядчик", "шифр проекта"],
        "description": "Содержит информацию о проекте, заказчике, исполнителе, шифр.",
        # ЗАЧЕМ: без титульного листа непонятно, к какому объекту относится КМД.
        # На производстве десятки проектов одновременно — путаница гарантирована.
    },
    {
        "name": "Общие данные",
        "name_en": "general_data",
        "keywords": ["общие данные", "пояснительная записка", "нормативные документы"],
        "description": "Нормативные ссылки, общие указания, условия эксплуатации.",
        # ЗАЧЕМ: определяет климатический район, ветровые нагрузки, требования
        # к огнестойкости. Без этого невозможно проверить расчёты.
    },
    {
        "name": "Ведомость комплекта чертежей",
        "name_en": "drawing_register",
        "keywords": ["ведомость чертежей", "содержание", "состав проекта", "ведомость рабочих чертежей"],
        "description": "Перечень всех чертежей комплекта с номерами листов.",
        # ЗАЧЕМ: позволяет убедиться, что все листы на месте и ничего не потеряно.
    },
    {
        "name": "Спецификация изделий",
        "name_en": "product_spec",
        "keywords": ["спецификация изделий", "ведомость изделий", "перечень позиций"],
        "description": "Таблица всех позиций с количествами, размерами, весами.",
        # ЗАЧЕМ: основной документ для планирования производства.
        # Сколько чего делать, какие материалы заказывать.
    },
    {
        "name": "Планы этажей",
        "name_en": "floor_plans",
        "keywords": ["план ", "план\n", "поэтажный план", "план этажа", "план типового"],
        "description": "Привязка позиций к зданию — где что стоит.",
        # ЗАЧЕМ: монтажники должны знать, какое изделие куда ставить.
        # Без планов — хаос на площадке.
    },
    {
        "name": "Фасады",
        "name_en": "facades",
        "keywords": ["фасад", "фрагмент фасада", "вид фасада", "развёртка фасада"],
        "description": "Внешний вид здания с отметками позиций.",
        # ЗАЧЕМ: визуальная проверка, что позиции на планах совпадают
        # с позициями на фасаде. Плюс монтажники видят общую картину.
    },
    {
        "name": "Разрезы",
        "name_en": "sections",
        "keywords": ["разрез", "сечение", "узел примыкания", "монтажный узел"],
        "description": "Вертикальные и горизонтальные сечения конструкций.",
        # ЗАЧЕМ: показывают, как конструкция крепится к стене, как
        # организован водоотвод, утепление откосов, примыкание к подоконнику.
    },
    {
        "name": "Спецификация материалов",
        "name_en": "material_spec",
        "keywords": ["спецификация материалов", "ведомость материалов", "сводная ведомость"],
        "description": "Полный перечень профилей, комплектующих, уплотнителей с количествами.",
        # ЗАЧЕМ: отдел закупок заказывает материалы по этой спецификации.
        # Ошибка → заказали не то → простой производства.
    },
    {
        "name": "Чертежи обработки",
        "name_en": "machining_drawings",
        "keywords": ["обработка", "фрезеровка", "засверловка", "чертёж обработки"],
        "description": "Точные чертежи обработки каждого профиля (фрезеровка, сверление).",
        # ЗАЧЕМ: оператор ЧПУ программирует станок по этим чертежам.
        # Без них — ручная разметка, ошибки, брак.
    },
    {
        "name": "Сборочные чертежи",
        "name_en": "assembly_drawings",
        "keywords": ["сборочный", "сборка", "поз.", "витраж"],
        "description": "Чертежи каждого изделия с размерами, артикулами, стеклопакетами.",
        # ЗАЧЕМ: основной рабочий документ сборщика на производстве.
    },
    {
        "name": "Карта раскроя",
        "name_en": "cutting_map",
        "keywords": ["раскрой", "карта раскроя", "оптимизация раскроя", "нарезка"],
        "description": "Оптимальная схема нарезки профилей из хлыстов (6-7м).",
        # ЗАЧЕМ: минимизация отходов. Без оптимизации раскроя —
        # до 30% материала уходит в отходы вместо 5-10%.
    },
    {
        "name": "Монтажная схема",
        "name_en": "installation_diagram",
        "keywords": ["монтаж", "монтажная схема", "установка", "крепление к стене"],
        "description": "Схема установки конструкций на объекте.",
        # ЗАЧЕМ: монтажники должны знать тип крепежа, шаг анкеров,
        # монтажные зазоры. Без схемы — «как обычно», а «обычно» бывает по-разному.
    },
]


class DocumentCompletenessValidator:
    """Проверяет наличие всех обязательных разделов КМД."""

    def validate(self, parsed_data: dict) -> list[ValidationError]:
        errors: list[ValidationError] = []
        pages = parsed_data.get("pages", [])

        if not pages:
            # Если страницы не переданы, проверяем по косвенным признакам
            errors.append(ValidationError(
                code="DOC-000",
                severity="info",
                category="completeness",
                message="Нет данных о страницах для проверки комплектности",
                details=(
                    "Для полноценной проверки комплектности необходимо передать "
                    "список страниц с типами в поле 'pages'."
                ),
            ))
            return errors

        # Собираем весь текст всех страниц для поиска ключевых слов.
        all_text_lower = ""
        page_types: set[str] = set()
        for p in pages:
            text = p.get("text", "")
            all_text_lower += " " + text.lower()
            ptype = p.get("type", "")
            if ptype:
                page_types.add(ptype.lower())

        # Проверяем каждый обязательный раздел
        for section in REQUIRED_SECTIONS:
            found = False
            for kw in section["keywords"]:
                if kw.lower() in all_text_lower:
                    found = True
                    break

            if not found:
                errors.append(ValidationError(
                    code="DOC-001",
                    severity="critical",
                    category="completeness",
                    message=f"Отсутствует обязательный раздел: {section['name']}",
                    details=(
                        f"{section['description']} "
                        f"Раздел не обнаружен в документе. "
                        f"Искали по ключевым словам: {', '.join(section['keywords'][:3])}."
                    ),
                ))

        # --- Проверка минимального количества страниц ---
        # Реальный КМД содержит минимум 15-20 страниц.
        # Менее 10 — скорее всего неполный файл.
        total_pages = len(pages)
        if total_pages < 10:
            errors.append(ValidationError(
                code="DOC-002",
                severity="warning",
                category="completeness",
                message=f"Подозрительно мало страниц: {total_pages}",
                details=(
                    f"В документе {total_pages} страниц. Типичный КМД "
                    f"содержит 15-100+ страниц. Возможно, загружена "
                    f"только часть документа."
                ),
            ))

        return errors


# ===========================================================================
# 6. CrossValidator
# ===========================================================================
# ЗАЧЕМ: Даже если каждый раздел корректен по отдельности, данные МЕЖДУ
# разделами могут противоречить друг другу. Типичные ошибки:
# - Спецификация на 15 позиций, а чертежей только 12
# - Общее количество 300шт, а если сложить по позициям — 280шт
# - На титуле RAL 7016, а в чертеже RAL 9016 (серый vs белый!)
# ===========================================================================

class CrossValidator:
    """Перекрёстная валидация: согласованность данных между разделами."""

    def validate(self, parsed_data: dict) -> list[ValidationError]:
        errors: list[ValidationError] = []
        positions = parsed_data.get("positions", [])
        declared_total_positions = parsed_data.get("total_positions", 0)
        declared_total_items = parsed_data.get("total_items", 0)
        declared_profile = parsed_data.get("profile_system", "")
        declared_colors = parsed_data.get("colors", [])

        # --- Количество позиций в спецификации vs количество чертежей ---
        # Каждая позиция ДОЛЖНА иметь чертёж. Если спецификация говорит 15
        # позиций, а чертежей 12 — три позиции не будут изготовлены правильно.
        actual_positions = len(positions)
        if declared_total_positions and actual_positions:
            diff = abs(declared_total_positions - actual_positions)
            if diff > 0:
                severity = "critical" if diff > 2 else "warning"
                errors.append(ValidationError(
                    code="CRS-001",
                    severity=severity,
                    category="cross-validation",
                    message=(
                        f"Количество позиций не совпадает: "
                        f"заявлено {declared_total_positions}, "
                        f"обнаружено {actual_positions}"
                    ),
                    details=(
                        f"В данных указано {declared_total_positions} позиций, "
                        f"но фактически обнаружено {actual_positions}. "
                        f"Разница: {diff}. Проверьте, все ли чертежи на месте."
                    ),
                ))

        # --- Общее количество изделий ---
        # Сумма количеств по отдельным позициям должна совпадать
        # с заявленным общим количеством.
        if positions and declared_total_items:
            calculated_total = sum(
                p.get("quantity", 0) for p in positions
                if p.get("quantity", 0) > 0
            )
            if calculated_total > 0 and calculated_total != declared_total_items:
                diff = abs(declared_total_items - calculated_total)
                severity = "critical" if diff > 5 else "warning"
                errors.append(ValidationError(
                    code="CRS-002",
                    severity=severity,
                    category="cross-validation",
                    message=(
                        f"Сумма количеств по позициям ({calculated_total}) "
                        f"не совпадает с общим количеством ({declared_total_items})"
                    ),
                    details=(
                        f"Сумма 'количество' по всем позициям = {calculated_total}, "
                        f"но в документе заявлено total_items = {declared_total_items}. "
                        f"Разница: {diff} изделий. Это может означать пропуск "
                        f"позиции или ошибку в количестве."
                    ),
                ))

        # --- Согласованность цвета ---
        # Все позиции одного КМД обычно одного цвета (если не указано иное).
        # Если на титуле RAL 7016, а в чертеже RAL 9016 — критическая ошибка
        # (серый вместо белого, или наоборот).
        position_colors: dict[str, set[str]] = {}
        for pos in positions:
            pos_name = pos.get("position", "?")
            color = pos.get("color", "")
            if color:
                position_colors.setdefault(pos_name, set()).add(color)

        for pos_name, colors in position_colors.items():
            if len(colors) > 1:
                errors.append(ValidationError(
                    code="CRS-003",
                    severity="critical",
                    category="cross-validation",
                    message=(
                        f"Несколько цветов для позиции {pos_name}: "
                        f"{', '.join(sorted(colors))}"
                    ),
                    details=(
                        f"Позиция {pos_name} имеет разные цвета на разных "
                        f"страницах: {', '.join(sorted(colors))}. "
                        f"Одна позиция = один цвет. Разный цвет = разные позиции."
                    ),
                    position=pos_name,
                ))

        # Проверка цвета позиций vs цвет на титуле
        if declared_colors and position_colors:
            declared_set = set(declared_colors)
            for pos_name, colors in position_colors.items():
                for c in colors:
                    if c not in declared_set:
                        errors.append(ValidationError(
                            code="CRS-004",
                            severity="warning",
                            category="cross-validation",
                            message=(
                                f"Цвет «{c}» позиции {pos_name} "
                                f"не заявлен в общих данных документа"
                            ),
                            details=(
                                f"На титульном листе указаны цвета: "
                                f"{', '.join(declared_colors)}. "
                                f"Позиция {pos_name} содержит цвет «{c}», "
                                f"который не заявлен. Возможная ошибка копирования."
                            ),
                            position=pos_name,
                        ))

        # --- Профильная система на титуле vs фактические артикулы ---
        # Уже проверяется в ArticleCompatibilityValidator (ART-002),
        # но здесь — дополнительная проверка по данным из позиций.
        if declared_profile and positions:
            pos_systems: set[str] = set()
            for pos in positions:
                ps = pos.get("profile_system")
                if ps:
                    pos_systems.add(ps)

            for ps in pos_systems:
                if ps != declared_profile:
                    errors.append(ValidationError(
                        code="CRS-005",
                        severity="critical",
                        category="cross-validation",
                        message=(
                            f"Профильная система «{ps}» в чертежах "
                            f"не соответствует титулу «{declared_profile}»"
                        ),
                        details=(
                            f"На титульном листе указана система «{declared_profile}», "
                            f"но в чертежах обнаружена «{ps}». "
                            f"Возможно, титульный лист скопирован из другого проекта."
                        ),
                    ))

        # --- Позиции с нулевым количеством ---
        # Если у позиции не указано количество — непонятно, сколько
        # изделий изготавливать. Производство не сможет спланировать работу.
        for pos in positions:
            pos_name = pos.get("position", "?")
            qty = pos.get("quantity", 0)
            if qty <= 0:
                errors.append(ValidationError(
                    code="CRS-006",
                    severity="warning",
                    category="cross-validation",
                    message=f"Не указано количество для позиции {pos_name}",
                    details=(
                        f"Позиция {pos_name}: количество = 0 или не найдено. "
                        f"Производство не сможет определить объём без количества."
                    ),
                    position=pos_name,
                ))

        # --- Позиции без артикулов ---
        # Без артикулов невозможно определить, какие профили нарезать.
        for pos in positions:
            pos_name = pos.get("position", "?")
            articles = pos.get("articles", [])
            if not articles:
                errors.append(ValidationError(
                    code="CRS-007",
                    severity="warning",
                    category="cross-validation",
                    message=f"Нет артикулов для позиции {pos_name}",
                    details=(
                        f"Позиция {pos_name}: артикулы не обнаружены. "
                        f"Без артикулов невозможно определить состав профилей."
                    ),
                    position=pos_name,
                ))

        # --- Позиции без размеров ---
        for pos in positions:
            pos_name = pos.get("position", "?")
            dims = pos.get("dimensions", [])
            if not dims:
                errors.append(ValidationError(
                    code="CRS-008",
                    severity="warning",
                    category="cross-validation",
                    message=f"Нет размеров для позиции {pos_name}",
                    details=(
                        f"Позиция {pos_name}: размеры WxH не обнаружены. "
                        f"Без габаритных размеров невозможно изготовить изделие."
                    ),
                    position=pos_name,
                ))

        # --- Дублирование позиций ---
        # Два чертежа с одинаковым именем позиции — ошибка нумерации.
        pos_names = [p.get("position", "") for p in positions]
        seen: dict[str, int] = {}
        for pn in pos_names:
            if not pn:
                continue
            seen[pn] = seen.get(pn, 0) + 1
        for pn, count in seen.items():
            if count > 1:
                errors.append(ValidationError(
                    code="CRS-009",
                    severity="warning",
                    category="cross-validation",
                    message=f"Позиция {pn} встречается {count} раз(а)",
                    details=(
                        f"Позиция «{pn}» обнаружена на {count} страницах. "
                        f"Это нормально, если данные дополняют друг друга "
                        f"(спецификация + чертёж), но может быть ошибкой нумерации."
                    ),
                    position=pn,
                ))

        return errors


# ===========================================================================
# 7. Главная функция валидации
# ===========================================================================

def validate_kmd_full(parsed_data: dict) -> dict:
    """Полная валидация КМД документа.

    Запускает ВСЕ валидаторы и возвращает структурированный результат.

    Args:
        parsed_data: результат parse_kmd_pdf() из kmd_parser.py.

    Returns:
        {
            "status": "ok" | "warning" | "critical",
            "score": 0-100,
            "errors": [ValidationError.to_dict(), ...],
            "checks_passed": int,
            "checks_total": int,
            "validators_run": [str, ...],
        }
    """
    all_errors: list[ValidationError] = []
    validators_run: list[str] = []

    # --- Запуск всех валидаторов ---
    validator_map: list[tuple[str, object]] = [
        ("articles", ArticleCompatibilityValidator()),
        ("dimensions", DimensionValidator()),
        ("glass", GlassValidator()),
        ("hardware", HardwareValidator()),
        ("completeness", DocumentCompletenessValidator()),
        ("cross", CrossValidator()),
    ]

    for name, validator in validator_map:
        try:
            errs = validator.validate(parsed_data)
            all_errors.extend(errs)
            validators_run.append(name)
        except Exception as exc:
            # Валидатор упал — не останавливаем весь процесс, но фиксируем.
            all_errors.append(ValidationError(
                code=f"SYS-001",
                severity="warning",
                category=name,
                message=f"Ошибка выполнения валидатора «{name}»: {exc}",
                details=str(exc),
            ))
            validators_run.append(name)

    # --- Подсчёт проверок ---
    # checks_total — общее количество потенциальных проверок.
    # Оценивается как: количество позиций × количество типов проверок
    # + документные проверки.
    num_positions = len(parsed_data.get("positions", []))
    # ~6 проверок на позицию (артикулы, размеры, стекло, фурнитура,
    # количество, цвет) + 12 разделов документа + 5 перекрёстных
    checks_per_position = 6
    doc_checks = len(REQUIRED_SECTIONS)
    cross_checks = 5
    checks_total = max(
        num_positions * checks_per_position + doc_checks + cross_checks,
        len(all_errors) + 1,  # Минимум — больше количества ошибок
    )

    # Считаем количество пройденных проверок (total - ошибки с severity != info)
    real_errors = sum(
        1 for e in all_errors if e.severity in ("critical", "warning")
    )
    checks_passed = max(checks_total - real_errors, 0)

    # --- Расчёт оценки (score) ---
    # 100 = идеально, 0 = полный провал.
    # Критические ошибки штрафуют по 10 баллов, предупреждения по 3.
    critical_count = sum(1 for e in all_errors if e.severity == "critical")
    warning_count = sum(1 for e in all_errors if e.severity == "warning")
    info_count = sum(1 for e in all_errors if e.severity == "info")

    penalty = critical_count * 10 + warning_count * 3
    score = max(0, min(100, 100 - penalty))

    # --- Определение общего статуса ---
    if critical_count > 0:
        status = "critical"
    elif warning_count > 0:
        status = "warning"
    else:
        status = "ok"

    return {
        "status": status,
        "score": score,
        "errors": [e.to_dict() for e in all_errors],
        "checks_passed": checks_passed,
        "checks_total": checks_total,
        "validators_run": validators_run,
        "summary": {
            "critical": critical_count,
            "warning": warning_count,
            "info": info_count,
            "total_errors": len(all_errors),
        },
    }


# ===========================================================================
# Утилиты для быстрого использования
# ===========================================================================

def validate_kmd_pdf(pdf_path: str) -> dict:
    """Удобная обёртка: парсит PDF и сразу валидирует.

    Args:
        pdf_path: путь к PDF файлу КМД.

    Returns:
        Результат validate_kmd_full().
    """
    from kmd_parser import parse_kmd_pdf
    parsed = parse_kmd_pdf(pdf_path)
    return validate_kmd_full(parsed)


def print_validation_report(result: dict) -> None:
    """Печатает читаемый отчёт валидации в консоль."""
    status_icons = {"ok": "OK", "warning": "ВНИМАНИЕ", "critical": "КРИТИЧНО"}
    status_label = status_icons.get(result["status"], result["status"])

    print("=" * 60)
    print(f"  ОТЧЁТ ВАЛИДАЦИИ КМД")
    print(f"  Статус: {status_label}  |  Оценка: {result['score']}/100")
    print(f"  Проверок пройдено: {result['checks_passed']}/{result['checks_total']}")
    print("=" * 60)

    summary = result.get("summary", {})
    if summary.get("critical"):
        print(f"  Критических ошибок: {summary['critical']}")
    if summary.get("warning"):
        print(f"  Предупреждений: {summary['warning']}")
    if summary.get("info"):
        print(f"  Информационных: {summary['info']}")
    print()

    # Группировка по категории
    errors_by_cat: dict[str, list[dict]] = {}
    for err in result.get("errors", []):
        cat = err.get("category", "other")
        errors_by_cat.setdefault(cat, []).append(err)

    cat_names = {
        "articles": "АРТИКУЛЫ / ПРОФИЛЬНАЯ СИСТЕМА",
        "dimensions": "РАЗМЕРЫ / ГАБАРИТЫ",
        "glass": "СТЕКЛОПАКЕТЫ",
        "hardware": "ФУРНИТУРА",
        "completeness": "КОМПЛЕКТНОСТЬ ДОКУМЕНТАЦИИ",
        "cross-validation": "ПЕРЕКРЁСТНАЯ ПРОВЕРКА",
    }

    for cat, errs in errors_by_cat.items():
        print(f"--- {cat_names.get(cat, cat.upper())} ---")
        for err in errs:
            sev = err["severity"].upper()
            code = err["code"]
            pos_str = f" [{err['position']}]" if err.get("position") else ""
            page_str = f" (стр. {err['page']})" if err.get("page") else ""
            print(f"  [{sev}] {code}{pos_str}{page_str}: {err['message']}")
            if err.get("details"):
                # Ограничиваем длину деталей для читаемости
                details = err["details"]
                if len(details) > 120:
                    details = details[:117] + "..."
                print(f"         {details}")
        print()

    print("=" * 60)
    print(f"  Валидаторы: {', '.join(result.get('validators_run', []))}")
    print("=" * 60)


# ===========================================================================
# CLI-интерфейс
# ===========================================================================

if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("КМД Rules Engine — детерминистическая система проверки КМД")
        print()
        print("Использование:")
        print("  python kmd_rules_engine.py <файл.pdf>       — проверить КМД")
        print("  python kmd_rules_engine.py --json <файл.pdf> — вывод в JSON")
        sys.exit(0)

    json_mode = "--json" in sys.argv
    pdf_path = [a for a in sys.argv[1:] if not a.startswith("--")][0]

    result = validate_kmd_pdf(pdf_path)

    if json_mode:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_validation_report(result)
