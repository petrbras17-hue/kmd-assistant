"""
multi_validator.py — Multi-agent validation pipeline for KMD documents.

Five independent AI agents (via OpenRouter LLM calls) each specialise in a
different aspect of KMD validation.  Results are aggregated through a
consensus mechanism: an error must be flagged by multiple agents before it
is considered confirmed.

Usage:
    from tools.multi_validator import validate_with_agents

    result = await validate_with_agents(parsed_data, raw_text)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
from collections import defaultdict
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent.parent / ".env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemini-2.0-flash-001"

# ── Agent system prompts ───────────────────────────────────────────────────

GEOMETRY_SYSTEM_PROMPT = """Ты — экспертный инженер-конструктор алюминиевых светопрозрачных конструкций с 30-летним стажем.
Твоя задача — проверить ВСЕ геометрические параметры в документации КМД.

### Что проверять:
1. **Габаритные размеры изделия**
   - Ширина конструкции обычно 400–4000 мм. Если > 3500 мм — требуется разделительная стойка (импост) или термовставка.
   - Высота конструкции обычно 400–3500 мм. Если > 2800 мм для створки — пометить как ошибку.
   - Соотношение сторон створки не должно превышать 1:4 (узкие высокие створки ненадёжны).

2. **Диагонали**
   - Разница диагоналей рамы не должна превышать 2 мм на 1 м длины.
   - Для створок — не более 1.5 мм на 1 м.

3. **Монтажные зазоры**
   - Зазор между рамой и проёмом: 10–25 мм с каждой стороны (ГОСТ 30971-2012).
   - Зазор между створкой и рамой: 12–18 мм (зависит от системы профиля).

4. **Сумма размеров**
   - Ширина рамы = сумма ширин заполнений + ширины импостов + зазоры.
   - Высота аналогично. Несовпадение > 1 мм — ошибка.

5. **Допуски и посадки**
   - Длина профиля: ±0.5 мм для рамных, ±0.3 мм для штапиков.
   - Углы: 90° ±0.2° для прямоугольных, точно по чертежу для трапеций.

6. **Размеры стеклопакетов / заполнений**
   - Стеклопакет = размер светового проёма − 2×(высота фальца − запас на прокладку).
   - Обычно: размер заполнения = проём − 8..12 мм.
   - Если стеклопакет слишком мал — будет болтаться; слишком велик — не войдёт.

7. **Толщина стенки профиля**
   - Минимальная толщина стенки по ГОСТ 22233-2018: ≥ 1.2 мм (класс A), ≥ 1.0 мм (класс B).
   - Для несущих элементов ≥ 1.5 мм.

### Формат ответа — строго JSON:
{
  "agent": "geometry",
  "status": "ok" | "warning" | "critical",
  "errors": [
    {
      "code": "GEO-001",
      "severity": "critical" | "warning" | "info",
      "message": "Описание ошибки на русском",
      "details": "Подробности: найдено X мм, допустимо Y мм",
      "location": "Позиция / страница / элемент"
    }
  ],
  "summary": "Краткий вывод на русском"
}

Если данных недостаточно для проверки конкретного пункта — не выдумывай ошибки, но укажи info-замечание.
Отвечай ТОЛЬКО валидным JSON без markdown-обёрток."""

MATERIALS_SYSTEM_PROMPT = """Ты — инженер-технолог по алюминиевым профильным системам с 30-летним стажем.
Ты знаешь наизусть каталоги Reynaers, Schüco, Alutech, TATPROF, Alumil, Profilco, NewTec.

### Что проверять:
1. **Артикулы профилей**
   - Reynaers: 6-значные числа (например, 123456, CW 50-HI имеет артикулы 4xxxxx).
   - Schüco: формат "xxxxxx" или "xxx.xxx" (например, 242870, 276.050).
   - Alutech: формат "ALT.Fxx.xxxx" или "ALT.Wxx.xxxx" (фасадные / оконные).
   - TATPROF: формат "ТПxxx-xxxxx" или 6-7-значные номера.
   - Если артикул не соответствует ни одному паттерну — пометить как подозрительный.

2. **Совместимость системы**
   - ВСЕ профили в одном изделии должны быть из ОДНОЙ профильной системы.
   - Нельзя смешивать Reynaers CW 50 с Schüco FWS 50+.
   - Штапики должны соответствовать раме (размер паза).
   - Уплотнители — по каталогу системы.

3. **Фурнитура**
   - Roto, Siegenia, Maco, Winkhaus — проверить совместимость с профильной системой.
   - Максимальный вес створки для фурнитуры (обычно 80–130 кг).
   - Количество точек запирания: ≥3 для створок > 1200 мм.

4. **Стеклопакеты**
   - Формула стеклопакета: например "4-16Ar-4-16Ar-4i" (толщина стекла - камера - ...).
   - Общая толщина должна соответствовать фальцу профиля (обычно 24, 32, 40, 44, 52 мм).
   - Закалённое стекло обязательно для створок > 2.0 м², для стёкол до пола, для дверей.

5. **Крепёж и соединители**
   - Угловые соединители должны соответствовать размеру камеры профиля.
   - Саморезы: нержавеющие для фасадных, оцинкованные для внутренних.

6. **Цвет и покрытие**
   - RAL-код должен быть одинаковым для всех видимых профилей.
   - Анодирование: указать класс (10, 15, 20, 25 мкм).

### Формат ответа — строго JSON:
{
  "agent": "materials",
  "status": "ok" | "warning" | "critical",
  "errors": [
    {
      "code": "MAT-001",
      "severity": "critical" | "warning" | "info",
      "message": "Описание на русском",
      "details": "Подробности",
      "location": "Где обнаружено"
    }
  ],
  "summary": "Краткий вывод"
}

Отвечай ТОЛЬКО валидным JSON без markdown-обёрток."""

NORMATIVE_SYSTEM_PROMPT = """Ты — эксперт по нормативной документации в строительстве РФ с 30-летним стажем.
Ты знаешь наизусть все ГОСТы, СП, СНиП, связанные с алюминиевыми конструкциями.

### Нормативная база для проверки:

1. **ГОСТ 21.502-2016** — Правила выполнения проектной и рабочей документации
   - Форматы листов: A1, A2, A3, A4 (допускаются кратные).
   - Основная надпись (штамп) по ГОСТ 21.101-2020: форма 3 для чертежей, форма 4 для текстовых.
   - Обязательные поля штампа: наименование организации, обозначение документа, наименование изделия, масштаб, масса, лист/листов, подписи (разработал, проверил, ГИП).

2. **ГОСТ 21519-2022** — Конструкции оконные и балконные
   - Классификация по типам открывания.
   - Предельные отклонения размеров: ±1.0 мм для конструкций до 1500 мм, ±1.5 мм свыше.
   - Маркировка обязательна.

3. **ГОСТ 34378-2018** — Профили алюминиевые для светопрозрачных конструкций
   - Минимальная толщина стенки.
   - Момент инерции и момент сопротивления — проверка несущей способности.

4. **СП 50.13330.2012** — Тепловая защита зданий
   - Приведённое сопротивление теплопередаче окон: ≥ 0.51 м²·°C/Вт (Москва).
   - Зависит от климатического района.

5. **ГОСТ 30674-99** / **ГОСТ 23166-2021** — Блоки оконные
   - Требования к комплектности документации.
   - Маркировка, упаковка, транспортирование.

6. **ГОСТ 30971-2012** — Швы монтажные
   - Трёхслойная система: паропроницаемый, теплоизолирующий, пароизолирующий.

7. **СП 20.13330.2016** — Нагрузки и воздействия
   - Ветровые нагрузки по районам.
   - Особые нагрузки для высотных зданий.

### Что проверять в документе:
- Наличие и правильность заполнения штампа.
- Обозначение чертежа по СПДС (шифр проекта-марка-номер).
- Наличие ссылок на ГОСТы в пояснительной записке.
- Указание климатического района и ветрового давления.
- Соответствие масштаба указанному в штампе.
- Наличие спецификации элементов.

### Формат ответа — строго JSON:
{
  "agent": "normative",
  "status": "ok" | "warning" | "critical",
  "errors": [
    {
      "code": "NORM-001",
      "severity": "critical" | "warning" | "info",
      "message": "Описание нарушения",
      "details": "Ссылка на пункт ГОСТ/СП и требование",
      "location": "Где обнаружено"
    }
  ],
  "summary": "Краткий вывод"
}

Отвечай ТОЛЬКО валидным JSON без markdown-обёрток."""

STRUCTURAL_SYSTEM_PROMPT = """Ты — инженер-расчётчик по алюминиевым конструкциям с 30-летним стажем.
Твоя специализация — прочностные и теплотехнические расчёты.

### Что проверять:

1. **Ветровые нагрузки (СП 20.13330.2016)**
   - Нормативное ветровое давление w₀ по району (I–VII): 0.17–1.00 кПа.
   - Коэффициент высоты k(z): от 0.5 (5 м) до 1.85 (> 300 м).
   - Аэродинамический коэффициент: обычно −1.4 для отсоса, +0.8 для напора.
   - Расчётная нагрузка = w₀ × k(z) × c × γf (γf = 1.4).
   - Прогиб ригеля/стойки ≤ 1/200 пролёта, но не более 15 мм (для витражей).

2. **Вес стеклопакета**
   - Плотность стекла: 2500 кг/м³. Вес = толщина(м) × площадь(м²) × 2500 × 9.81.
   - Однокамерный 4-16-4: ≈20 кг/м². Двухкамерный 4-12-4-12-4: ≈30 кг/м².
   - Триплекс 6.6.2: ≈34 кг/м².
   - Максимальный вес на одну опору штапика — проверить.

3. **Несущая способность фурнитуры**
   - Поворотная створка: max вес 80–130 кг (зависит от серии).
   - Поворотно-откидная: обычно до 130 кг (Roto NX), до 150 кг (Siegenia Titan AF).
   - Раздвижная: до 200–400 кг на полотно.
   - Максимальная ширина створки: обычно 1300 мм (поворотная), 1600 мм (раздвижная).
   - Максимальная высота створки: обычно 2400 мм.

4. **Термическое расширение алюминия**
   - Коэффициент: 23.5 × 10⁻⁶ 1/°C.
   - ΔL = L × α × ΔT. Для L=6000 мм и ΔT=80°C → ΔL = 11.3 мм.
   - Компенсационные зазоры обязательны для фасадов: ≥5 мм на каждые 3 метра.

5. **Прочность соединений**
   - Угловые соединения рамы: прочность на разрыв ≥ 2.5 кН.
   - Момент затяжки крепёжных элементов.
   - Крепление к стене: анкеры ≥ 6 мм, шаг ≤ 700 мм, от угла ≤ 150 мм.

6. **Стекло — расчёт на нагрузку**
   - Прочность стекла на изгиб: σ = 45 МПа (отожжённое), 120 МПа (закалённое).
   - Максимальный прогиб стекла ≤ 1/100 короткой стороны.
   - Для стёкол площадью > 2.5 м² или с низкой стороной > 1500 мм — закалка обязательна.

### Формат ответа — строго JSON:
{
  "agent": "structural",
  "status": "ok" | "warning" | "critical",
  "errors": [
    {
      "code": "STR-001",
      "severity": "critical" | "warning" | "info",
      "message": "Описание проблемы",
      "details": "Расчётные значения и нормативные требования",
      "location": "Элемент / позиция"
    }
  ],
  "summary": "Краткий вывод"
}

Отвечай ТОЛЬКО валидным JSON без markdown-обёрток."""

FORMATTING_SYSTEM_PROMPT = """Ты — ведущий инженер отдела технической документации компании АЛЬДМЕГАЛАБ с 30-летним стажем.
Ты отвечаешь за комплектность и оформление комплектов КМД.

### Стандарты оформления АЛЬДМЕГАЛАБ:

1. **Состав комплекта КМД**
   Обязательные разделы (в порядке следования):
   - Титульный лист (1 стр.) — наименование объекта, заказчик, подрядчик, дата.
   - Содержание / Оглавление.
   - Пояснительная записка (1–3 стр.) — описание конструкций, материалы, ГОСТы.
   - Ведомость изделий / Спецификация (общая таблица позиций).
   - Чертежи изделий (по одному листу на каждую позицию).
   - Узлы и сечения (при необходимости).
   - Спецификация комплектующих (профили, фурнитура, заполнения).

2. **Нумерация страниц**
   - Сквозная нумерация всего комплекта.
   - Номер страницы в правом нижнем углу штампа.
   - Лист/Листов в штампе — заполнены корректно.

3. **Штамп (основная надпись)**
   - Организация: «АЛЬДМЕГАЛАБ» или «АЛДМЕГАЛАБ» (допускаются варианты).
   - Шифр проекта: формат «XXXX-КМД» или «XX.XXXX-КМД».
   - Подписи: Разработал, Проверил, Н. контр. (при наличии), Утв.
   - Дата: формат ДД.ММ.ГГ или ДД.ММ.ГГГГ.
   - Масштаб: указан для чертежей, прочерк для текстовых документов.

4. **Позиции изделий**
   - Каждая позиция имеет уникальный номер (Поз.1, Поз.2, ...).
   - Количество изделий указано для каждой позиции.
   - Сумма количеств в ведомости = сумма на чертежах.
   - Позиции идут по порядку, без пропусков.

5. **Чертежи изделий**
   - Вид спереди (фасад) — обязателен.
   - Горизонтальный разрез — обязателен.
   - Вертикальный разрез — обязателен.
   - Спецификация заполнений (стеклопакеты, панели).
   - Размеры: габаритные, монтажные, размеры заполнений.
   - Маркировка открывания створок (стандартные обозначения).

6. **Перекрёстная проверка**
   - Количество позиций в ведомости = количество чертежей изделий.
   - Артикулы в спецификации упоминаются на чертежах.
   - Размеры на чертеже = размерам в ведомости.
   - Общая площадь по ведомости ≈ сумма площадей по позициям.

### Формат ответа — строго JSON:
{
  "agent": "formatting",
  "status": "ok" | "warning" | "critical",
  "errors": [
    {
      "code": "FMT-001",
      "severity": "critical" | "warning" | "info",
      "message": "Описание проблемы оформления",
      "details": "Что должно быть по стандарту",
      "location": "Раздел / страница"
    }
  ],
  "summary": "Краткий вывод"
}

Отвечай ТОЛЬКО валидным JSON без markdown-обёрток."""

# ── Agent registry ─────────────────────────────────────────────────────────

AGENTS: list[dict[str, str]] = [
    {"name": "geometry",   "prompt": GEOMETRY_SYSTEM_PROMPT},
    {"name": "materials",  "prompt": MATERIALS_SYSTEM_PROMPT},
    {"name": "normative",  "prompt": NORMATIVE_SYSTEM_PROMPT},
    {"name": "structural", "prompt": STRUCTURAL_SYSTEM_PROMPT},
    {"name": "formatting", "prompt": FORMATTING_SYSTEM_PROMPT},
]


# ── OpenRouter call ───────────────────────────────────────────────────────

async def _call_agent(
    agent_name: str,
    system_prompt: str,
    kmd_data: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4000,
    timeout: float = 120.0,
) -> dict:
    """Call one specialist agent via OpenRouter. Returns structured validation result."""

    if not OPENROUTER_API_KEY:
        return {
            "agent": agent_name,
            "status": "error",
            "errors": [
                {
                    "code": f"{agent_name.upper()}-ERR",
                    "severity": "critical",
                    "message": "OpenRouter API key не настроен",
                    "details": "Добавьте OPENROUTER_API_KEY в .env",
                    "location": "конфигурация",
                }
            ],
            "summary": "Агент не смог выполнить проверку: отсутствует API-ключ.",
        }

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                "Проверь следующую документацию КМД и верни результат "
                "в формате JSON, как указано в системном промпте.\n\n"
                "--- ДАННЫЕ КМД ---\n"
                f"{kmd_data}\n"
                "--- КОНЕЦ ДАННЫХ ---"
            ),
        },
    ]

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            raw_content = data["choices"][0]["message"]["content"]

        # Parse the JSON response — strip markdown fences if present.
        cleaned = raw_content.strip()
        if cleaned.startswith("```"):
            # Remove ```json ... ``` wrapper
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        result = json.loads(cleaned)

        # Ensure mandatory fields are present.
        result.setdefault("agent", agent_name)
        result.setdefault("status", "ok")
        result.setdefault("errors", [])
        result.setdefault("summary", "")
        return result

    except json.JSONDecodeError:
        return {
            "agent": agent_name,
            "status": "error",
            "errors": [
                {
                    "code": f"{agent_name.upper()}-PARSE",
                    "severity": "warning",
                    "message": "Не удалось разобрать ответ агента как JSON",
                    "details": raw_content[:500] if "raw_content" in dir() else "no response",
                    "location": "ответ LLM",
                }
            ],
            "summary": "Ответ агента не является валидным JSON.",
        }
    except httpx.HTTPStatusError as exc:
        return {
            "agent": agent_name,
            "status": "error",
            "errors": [
                {
                    "code": f"{agent_name.upper()}-HTTP",
                    "severity": "critical",
                    "message": f"OpenRouter вернул HTTP {exc.response.status_code}",
                    "details": exc.response.text[:300],
                    "location": "OpenRouter API",
                }
            ],
            "summary": f"HTTP-ошибка при обращении к OpenRouter: {exc.response.status_code}.",
        }
    except Exception as exc:
        return {
            "agent": agent_name,
            "status": "error",
            "errors": [
                {
                    "code": f"{agent_name.upper()}-FAIL",
                    "severity": "critical",
                    "message": f"Ошибка агента: {exc}",
                    "details": str(exc),
                    "location": "runtime",
                }
            ],
            "summary": f"Непредвиденная ошибка агента {agent_name}.",
        }


# ── Consensus ──────────────────────────────────────────────────────────────

def _error_fingerprint(error: dict) -> str:
    """Create a normalised key for grouping similar errors across agents.

    We hash the lowercased message to cluster semantically identical issues
    reported with slightly different wording.  The ``code`` prefix (e.g.
    GEO-001) is deliberately excluded so that overlapping findings from
    different agents (which use different code prefixes) can still be matched.
    """
    msg = error.get("message", "").lower().strip()
    # Remove non-alphanumeric chars for fuzzy grouping
    normalised = re.sub(r"[^а-яa-z0-9 ]", "", msg)
    # Collapse whitespace
    normalised = re.sub(r"\s+", " ", normalised).strip()
    return hashlib.md5(normalised.encode()).hexdigest()[:12]


def build_consensus(agent_results: list[dict]) -> dict:
    """Aggregate individual agent results with consensus rules.

    Consensus rules
    ---------------
    - If >= 3 agents flag the same issue -> CONFIRMED error
    - If exactly 2 agents flag         -> PROBABLE error
    - If exactly 1 agent flags          -> POSSIBLE (needs human review)
    - Confidence = agreement_count / total_agents * 100
    """

    total_agents = len(agent_results)
    succeeded = [r for r in agent_results if r.get("status") != "error"]
    agents_succeeded = len(succeeded)

    # Collect all errors and group by fingerprint.
    fingerprint_map: dict[str, list[dict]] = defaultdict(list)
    # Track which agents contributed each fingerprint.
    fingerprint_agents: dict[str, set[str]] = defaultdict(set)

    for result in succeeded:
        agent_name = result.get("agent", "unknown")
        for err in result.get("errors", []):
            fp = _error_fingerprint(err)
            fingerprint_map[fp].append(err)
            fingerprint_agents[fp].add(agent_name)

    confirmed_errors: list[dict] = []
    probable_errors: list[dict] = []
    possible_errors: list[dict] = []

    for fp, errors in fingerprint_map.items():
        agreement = len(fingerprint_agents[fp])
        # Pick the most detailed version of the error (longest details text).
        representative = max(errors, key=lambda e: len(e.get("details", "")))
        entry = {
            **representative,
            "agreement_count": agreement,
            "agents_agreed": sorted(fingerprint_agents[fp]),
            "confidence": round(agreement / total_agents * 100, 1),
        }

        if agreement >= 3:
            confirmed_errors.append(entry)
        elif agreement == 2:
            probable_errors.append(entry)
        else:
            possible_errors.append(entry)

    # Sort by severity (critical first).
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    for lst in (confirmed_errors, probable_errors, possible_errors):
        lst.sort(key=lambda e: severity_order.get(e.get("severity", "info"), 3))

    # Overall status.
    if any(e.get("severity") == "critical" for e in confirmed_errors):
        overall_status = "critical"
    elif confirmed_errors or any(e.get("severity") == "critical" for e in probable_errors):
        overall_status = "warning"
    elif probable_errors or possible_errors:
        overall_status = "warning"
    else:
        overall_status = "ok"

    # Overall confidence: average of individual error confidences,
    # or 100 % if no errors were found.
    all_entries = confirmed_errors + probable_errors + possible_errors
    if all_entries:
        overall_confidence = round(
            sum(e["confidence"] for e in all_entries) / len(all_entries), 1
        )
    else:
        overall_confidence = 100.0

    # Agent detail map.
    agent_details: dict[str, dict] = {}
    for result in agent_results:
        name = result.get("agent", "unknown")
        agent_details[name] = {
            "status": result.get("status", "error"),
            "errors": result.get("errors", []),
            "summary": result.get("summary", ""),
        }

    # Russian summary text.
    parts: list[str] = [
        f"Документ проверен {total_agents} агентами "
        f"({agents_succeeded} успешно)."
    ]
    if confirmed_errors:
        parts.append(
            f"Найдено {len(confirmed_errors)} подтверждённых ошибок "
            f"(≥3 агента согласны)."
        )
    if probable_errors:
        parts.append(
            f"Найдено {len(probable_errors)} вероятных ошибок "
            f"(2 агента согласны)."
        )
    if possible_errors:
        parts.append(
            f"Найдено {len(possible_errors)} возможных замечаний "
            f"(1 агент)."
        )
    if not all_entries:
        parts.append("Ошибок не обнаружено.")

    summary_ru = " ".join(parts)

    return {
        "status": overall_status,
        "confidence": overall_confidence,
        "agents_run": total_agents,
        "agents_succeeded": agents_succeeded,
        "confirmed_errors": confirmed_errors,
        "probable_errors": probable_errors,
        "possible_errors": possible_errors,
        "agent_details": agent_details,
        "summary_ru": summary_ru,
    }


# ── Main entry point ──────────────────────────────────────────────────────

def _prepare_kmd_text(parsed_data: dict, raw_text: str = "") -> str:
    """Combine parsed KMD data and optional raw text into a single string
    suitable for agent consumption."""

    sections: list[str] = []

    if parsed_data:
        sections.append("=== СТРУКТУРИРОВАННЫЕ ДАННЫЕ ===")
        sections.append(json.dumps(parsed_data, ensure_ascii=False, indent=2, default=str))

    if raw_text:
        # Truncate raw text to avoid hitting token limits.
        truncated = raw_text[:12000]
        if len(raw_text) > 12000:
            truncated += "\n... (текст обрезан)"
        sections.append("\n=== ИЗВЛЕЧЁННЫЙ ТЕКСТ ===")
        sections.append(truncated)

    return "\n".join(sections) if sections else "(Данные не предоставлены)"


async def validate_with_agents(
    parsed_data: dict,
    raw_text: str = "",
    model: str = DEFAULT_MODEL,
) -> dict:
    """Run all 5 agents in parallel, aggregate results with consensus.

    Parameters
    ----------
    parsed_data : dict
        Structured data extracted from KMD document (e.g. via kmd_parser).
    raw_text : str, optional
        Raw extracted text from the PDF (provides additional context).
    model : str, optional
        OpenRouter model identifier to use for all agents.

    Returns
    -------
    dict
        Consensus result with confirmed / probable / possible errors,
        per-agent details, and a Russian-language summary.
    """
    kmd_text = _prepare_kmd_text(parsed_data, raw_text)

    # Launch all agents concurrently.
    tasks = [
        _call_agent(
            agent_name=agent["name"],
            system_prompt=agent["prompt"],
            kmd_data=kmd_text,
            model=model,
        )
        for agent in AGENTS
    ]

    agent_results: list[dict] = await asyncio.gather(*tasks)
    return build_consensus(agent_results)


# ── CLI helper for quick testing ───────────────────────────────────────────

async def _main() -> None:
    """Quick smoke-test: validate a sample KMD payload."""
    sample = {
        "project": "Тест-КМД-001",
        "positions": [
            {
                "pos": "1",
                "type": "Окно поворотно-откидное",
                "width": 1200,
                "height": 1500,
                "qty": 4,
                "system": "Reynaers MasterLine 8 HI",
                "glass": "4-16Ar-4-16Ar-4i",
                "articles": ["123456", "234567", "345678"],
            }
        ],
        "stamp": {
            "org": "АЛЬДМЕГАЛАБ",
            "code": "2024.0312-КМД",
            "date": "15.01.2025",
            "designer": "Иванов И.И.",
            "checker": "Петров П.П.",
        },
    }
    result = await validate_with_agents(sample)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
