#!/usr/bin/env python3
"""
Index ALL available KMD training data into Pinecone for RAG.

Data sources:
  1. Error examples (3 DOCX files) -> kmd-formatting-rules + real-kmd-documents
  2. AI description document       -> kmd-formatting-rules
  3. KMD checklist answers (XLSX)  -> kmd-formatting-rules
  4. Task pairs A/B (XLSX)         -> real-kmd-documents
  5. Results (XLSX)                -> real-kmd-documents
  6. Error explanations (DOCX)     -> real-kmd-documents
"""

import os
import sys
from pathlib import Path

# Ensure tools/ is on path so we can import rag_indexer
sys.path.insert(0, str(Path(__file__).resolve().parent))

import openpyxl
import docx
from rag_indexer import (
    upsert_records,
    chunk_text,
    index_text_document,
    make_id,
    NS_KMD_RULES,
    NS_REAL_KMD,
)

ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = ROOT / "Задания от АльдМЕгаЛаб"
RESULTS_DIR = ROOT / "Результаты"

# Global stats
STATS = {"total_records": 0, "total_errors": 0, "sections": {}}


def log(msg: str):
    print(f"  {msg}")


def record_stats(section: str, result: dict):
    upserted = result.get("upserted", 0)
    errors = result.get("errors", [])
    STATS["total_records"] += upserted
    STATS["total_errors"] += len(errors)
    STATS["sections"][section] = STATS["sections"].get(section, 0) + upserted
    if errors:
        for e in errors:
            log(f"  ERROR: {e}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def read_docx(path: Path) -> str:
    """Read a .docx file and return full text."""
    doc = docx.Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def read_xlsx_sheet_as_text(ws) -> str:
    """Convert an openpyxl worksheet to readable text."""
    lines = []
    for row in ws.iter_rows(values_only=True):
        cells = [str(c) if c is not None else "" for c in row]
        # Skip completely empty rows
        if any(c.strip() for c in cells):
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def read_xlsx_all_sheets(path: Path) -> dict[str, str]:
    """Read all sheets from an xlsx file. Returns {sheet_name: text}."""
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    result = {}
    for name in wb.sheetnames:
        ws = wb[name]
        text = read_xlsx_sheet_as_text(ws)
        if text.strip():
            result[name] = text
    wb.close()
    return result


# ---------------------------------------------------------------------------
# 1. Error Examples
# ---------------------------------------------------------------------------
def index_error_examples():
    print("\n[1/6] Indexing error examples (3 DOCX files)...")

    examples = [
        {
            "file": ROOT / "Пример 1. Описание ошибок..docx",
            "num": 1,
            "errors": "удалены листы 3, 6, 17, 19",
            "error_type": "missing_sheet",
        },
        {
            "file": ROOT / "Пример 2. Описание ошибок..docx",
            "num": 2,
            "errors": "удалены листы 1, 3, 6, 12",
            "error_type": "missing_sheet",
        },
        {
            "file": ROOT / "Пример 3. Описание ошибок..docx",
            "num": 3,
            "errors": "удалён титульный лист, элементы на листе 4",
            "error_type": "deleted_items",
        },
    ]

    for ex in examples:
        path = ex["file"]
        if not path.exists():
            log(f"SKIP (not found): {path.name}")
            continue

        text = read_docx(path)
        log(f"{path.name}: {len(text)} chars, {len(text.split())} words")

        meta = {
            "type": "error_example",
            "example_number": ex["num"],
            "error_type": ex["error_type"],
            "error_description": ex["errors"],
        }

        # Index to kmd-formatting-rules (as training rules)
        res = index_text_document(
            text=text,
            namespace=NS_KMD_RULES,
            source=path.name,
            category="error_example",
            title=f"Пример {ex['num']} — описание ошибок КМД",
            extra_metadata=meta,
        )
        record_stats("error_examples_rules", res)
        log(f"  -> kmd-formatting-rules: {res['upserted']} records")

        # Index to real-kmd-documents (as ground truth)
        res2 = index_text_document(
            text=text,
            namespace=NS_REAL_KMD,
            source=path.name,
            category="error_example",
            title=f"Пример {ex['num']} — описание ошибок КМД",
            extra_metadata=meta,
        )
        record_stats("error_examples_real", res2)
        log(f"  -> real-kmd-documents: {res2['upserted']} records")


# ---------------------------------------------------------------------------
# 2. AI Description Document
# ---------------------------------------------------------------------------
def index_ai_description():
    print("\n[2/6] Indexing AI description document...")

    path = ROOT / "ИИ_описание.docx"
    if not path.exists():
        log("SKIP (not found): ИИ_описание.docx")
        return

    text = read_docx(path)
    log(f"{path.name}: {len(text)} chars, {len(text.split())} words")

    res = index_text_document(
        text=text,
        namespace=NS_KMD_RULES,
        source="ИИ_описание.docx",
        category="domain_knowledge",
        title="Описание задач ИИ для ALDMEGALAB — входные/выходные документы, проверки, ошибки",
        extra_metadata={"type": "ai_description", "scope": "full_workflow"},
    )
    record_stats("ai_description", res)
    log(f"  -> kmd-formatting-rules: {res['upserted']} records")


# ---------------------------------------------------------------------------
# 3. KMD Checklist Answers (8 sheets)
# ---------------------------------------------------------------------------
def index_checklist():
    print("\n[3/6] Indexing KMD checklist answers (8 sheets)...")

    path = ROOT / "Чек-лист_КМД_ALDMEGALAB_Ответы.xlsx"
    if not path.exists():
        log("SKIP (not found): Чек-лист_КМД_ALDMEGALAB_Ответы.xlsx")
        return

    sheet_topics = {
        0: "Входные данные — требования",
        1: "Первичный анализ — процесс",
        2: "Выбор профильной системы",
        3: "Создание КМД — процесс",
        4: "Проверка и согласование",
        5: "Интеграция с ЧПУ",
        6: "Статистика и метрики",
        7: "Топ-5 проблем + идеальный сценарий ИИ",
    }

    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    for idx, name in enumerate(wb.sheetnames):
        ws = wb[name]
        text = read_xlsx_sheet_as_text(ws)
        if not text.strip():
            continue

        topic = sheet_topics.get(idx, f"Лист {idx+1}")
        log(f"Sheet '{name}' ({topic}): {len(text.split())} words")

        res = index_text_document(
            text=text,
            namespace=NS_KMD_RULES,
            source="Чек-лист_КМД_ALDMEGALAB_Ответы.xlsx",
            category="checklist_qa",
            title=f"Чек-лист КМД — {topic}",
            extra_metadata={
                "type": "checklist",
                "sheet_number": idx + 1,
                "sheet_name": name,
                "topic": topic,
            },
        )
        record_stats("checklist", res)
        log(f"  -> kmd-formatting-rules: {res['upserted']} records")

    wb.close()


# ---------------------------------------------------------------------------
# 4. Task Pairs A/B
# ---------------------------------------------------------------------------
def index_task_pairs():
    print("\n[4/6] Indexing task pairs A/B from Задания от АльдМЕгаЛаб...")

    if not TASKS_DIR.exists():
        log("SKIP: directory not found")
        return

    # Index error explanations docx first
    expl_path = TASKS_DIR / "Пояснение и допущенные ошибки.docx"
    if expl_path.exists():
        text = read_docx(expl_path)
        log(f"Пояснение и допущенные ошибки.docx: {len(text.split())} words")
        res = index_text_document(
            text=text,
            namespace=NS_REAL_KMD,
            source="Пояснение и допущенные ошибки.docx",
            category="error_explanation",
            title="Пояснение и допущенные ошибки в заданиях",
            extra_metadata={"type": "error_explanation"},
        )
        record_stats("error_explanations", res)
        log(f"  -> real-kmd-documents: {res['upserted']} records")

    # Collect task files by number
    task_files = {}
    for f in sorted(TASKS_DIR.iterdir()):
        if not f.name.endswith(('.xlsx', '.xlsx.xlsx')):
            continue
        name = f.name
        # Extract task number from the beginning
        num = ""
        for ch in name:
            if ch.isdigit():
                num += ch
            else:
                break
        if not num:
            continue
        task_num = int(num)

        # Determine variant (a or b)
        # Check near the end of filename for Cyrillic а/б after the digit "1"
        # "б" is unambiguous; "а" appears in words like "задание", so check
        # specifically for patterns like "1а" or "1 а" or "-1 а"
        import re as _re
        name_lower = name.lower()
        if _re.search(r'1\s*б', name_lower):
            variant = "b"
        elif _re.search(r'1\s*а', name_lower):
            variant = "a"
        else:
            variant = "unknown"

        task_files.setdefault(task_num, {})[variant] = f

    for task_num in sorted(task_files.keys()):
        variants = task_files[task_num]
        for variant, fpath in sorted(variants.items()):
            try:
                sheets = read_xlsx_all_sheets(fpath)
            except Exception as e:
                log(f"ERROR reading {fpath.name}: {e}")
                continue

            all_text_parts = []
            for sheet_name, sheet_text in sheets.items():
                all_text_parts.append(f"--- Лист: {sheet_name} ---\n{sheet_text}")

            combined = "\n\n".join(all_text_parts)
            words = len(combined.split())
            log(f"Task {task_num}{variant}: {fpath.name} ({words} words, {len(sheets)} sheets)")

            variant_label = "Вариант А (исходный)" if variant == "a" else "Вариант Б (с изменениями)"
            res = index_text_document(
                text=combined,
                namespace=NS_REAL_KMD,
                source=fpath.name,
                category="task_pair",
                title=f"Задание {task_num} — {variant_label} — спецификация материалов",
                extra_metadata={
                    "type": "task_pair",
                    "task_number": task_num,
                    "variant": variant,
                    "sheets_count": len(sheets),
                },
                use_sections=False,
            )
            record_stats("task_pairs", res)
            log(f"  -> real-kmd-documents: {res['upserted']} records")


# ---------------------------------------------------------------------------
# 5. Results
# ---------------------------------------------------------------------------
def index_results():
    print("\n[5/6] Indexing results from Результаты/...")

    if not RESULTS_DIR.exists():
        log("SKIP: directory not found")
        return

    for fpath in sorted(RESULTS_DIR.iterdir()):
        if not fpath.name.endswith('.xlsx'):
            continue

        # Extract task number
        num = ""
        for ch in fpath.stem:
            if ch.isdigit():
                num += ch
        if not num:
            continue
        task_num = int(num)

        try:
            sheets = read_xlsx_all_sheets(fpath)
        except Exception as e:
            log(f"ERROR reading {fpath.name}: {e}")
            continue

        all_text_parts = []
        for sheet_name, sheet_text in sheets.items():
            all_text_parts.append(f"--- Лист: {sheet_name} ---\n{sheet_text}")

        combined = "\n\n".join(all_text_parts)
        words = len(combined.split())
        log(f"{fpath.name}: {words} words, {len(sheets)} sheets")

        res = index_text_document(
            text=combined,
            namespace=NS_REAL_KMD,
            source=fpath.name,
            category="task_result",
            title=f"Задание {task_num} — правильный результат сравнения",
            extra_metadata={
                "type": "task_result",
                "task_number": task_num,
                "sheets_count": len(sheets),
            },
            use_sections=False,
        )
        record_stats("results", res)
        log(f"  -> real-kmd-documents: {res['upserted']} records")


# ---------------------------------------------------------------------------
# 6. Print final stats
# ---------------------------------------------------------------------------
def print_stats():
    print("\n" + "=" * 60)
    print("INDEXING COMPLETE")
    print("=" * 60)
    print(f"Total records upserted: {STATS['total_records']}")
    print(f"Total errors:           {STATS['total_errors']}")
    print("\nBy section:")
    for section, count in sorted(STATS["sections"].items()):
        print(f"  {section:30s} {count:5d} records")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("KMD Training Data Indexer")
    print("Indexing all available training data into Pinecone")
    print("=" * 60)

    index_error_examples()
    index_ai_description()
    index_checklist()
    index_task_pairs()
    index_results()
    print_stats()


if __name__ == "__main__":
    main()
