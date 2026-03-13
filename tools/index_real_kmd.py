"""
Index real KMD documents from project folder into Pinecone.
Ground truth data for the RAG system.
"""

import fitz  # PyMuPDF
import re
import sys
import os

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_here))
sys.path.insert(0, _here)
from rag_indexer import (
    index_real_kmd, index_text_document, index_kmd_rules,
    NS_REAL_KMD, NS_KMD_RULES, NS_ARTICLES_REYNAERS,
    upsert_records, make_id, get_index_stats,
)


def extract_pdf_text(filepath: str) -> tuple[str, list[dict]]:
    """Extract text from PDF, return (full_text, page_data)."""
    doc = fitz.open(filepath)
    pages = []
    full_text_parts = []

    for i, page in enumerate(doc):
        text = page.get_text().strip()
        pages.append({"page": i + 1, "text": text, "chars": len(text)})
        full_text_parts.append(f"\n--- Страница {i+1} ---\n{text}")

    doc.close()
    return "\n".join(full_text_parts), pages


def extract_positions_and_articles(text: str) -> tuple[list[str], list[str]]:
    """Extract position codes and article numbers from KMD text."""
    # Multiple position formats
    pos_patterns = [
        r'Поз[\.\s]*([А-Яа-яA-Za-z]{0,4}[\-\.]?\d+)',       # Поз.О-1, Поз.БФ1
        r'((?:Угловой\s+)?витраж\s+[А-Яа-яA-Za-z]+[\-\.]\d+(?:\.\d+)?)',  # витраж В-1, В-1.1
        r'((?:Балконная\s+)?дверь\s+[А-Яа-яA-Za-z]+[\-\.]\d+)',  # дверь БД-1
    ]
    positions = set()
    for pat in pos_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            positions.add(m.group(1) if m.lastindex else m.group(0))

    # 7-digit articles
    articles = set()
    for m in re.finditer(r'\b(\d{7})\b', text):
        val = int(m.group(1))
        if val > 100000:
            articles.add(m.group(1))

    return sorted(positions), sorted(articles)


def index_pdf_document(filepath: str, project_name: str, doc_type: str):
    """Full pipeline: extract + index a PDF."""
    print(f"\n{'='*60}")
    print(f"Indexing: {os.path.basename(filepath)}")
    print(f"Project: {project_name} | Type: {doc_type}")
    print(f"{'='*60}")

    full_text, pages = extract_pdf_text(filepath)
    positions, articles = extract_positions_and_articles(full_text)

    print(f"  Pages: {len(pages)}")
    print(f"  Total chars: {len(full_text):,}")
    print(f"  Positions found: {len(positions)} — {positions[:10]}")
    print(f"  Articles found: {len(articles)} — {articles[:10]}")

    # 1. Index full document as ground truth
    result1 = index_real_kmd(
        text=full_text,
        project_name=project_name,
        document_type=doc_type,
        positions=positions,
        articles=articles,
    )
    print(f"  Ground truth indexed: {result1['upserted']} chunks")

    # 2. Index each page separately for fine-grained search
    page_records = []
    for pg in pages:
        if len(pg["text"]) < 20:
            continue

        # Detect page type
        page_type = classify_page(pg["text"])
        page_positions, page_articles = extract_positions_and_articles(pg["text"])

        record = {
            "_id": make_id(NS_REAL_KMD, f"{project_name}_p{pg['page']}", 0),
            "content": (
                f"Проект: {project_name}. {doc_type}. Страница {pg['page']}. "
                f"Тип: {page_type}. "
                f"Позиции: {', '.join(page_positions[:5])}. "
                f"Артикулы: {', '.join(page_articles[:10])}.\n\n"
                f"{pg['text'][:2000]}"
            ),
            "source": project_name,
            "category": "real_kmd_page",
            "title": f"{project_name} — {doc_type} — стр.{pg['page']}",
            "page_number": pg["page"],
            "page_type": page_type,
            "document_type": doc_type,
        }
        page_records.append(record)

    if page_records:
        result2 = upsert_records(page_records, NS_REAL_KMD)
        print(f"  Pages indexed: {result2['upserted']}")
        if result2["errors"]:
            for e in result2["errors"]:
                print(f"    ERROR: {e}")

    # 3. Index articles found as catalog entries
    if articles:
        art_records = []
        for art_code in articles:
            # Find context around article in text
            context = find_article_context(full_text, art_code)
            record = {
                "_id": f"real_{project_name.lower().replace(' ','_')}_{art_code}",
                "content": (
                    f"Артикул {art_code} найден в реальном КМД проекта {project_name}. "
                    f"Тип документа: {doc_type}. Контекст: {context}"
                ),
                "article_code": art_code,
                "source": project_name,
                "category": "real_article_usage",
            }
            art_records.append(record)

        result3 = upsert_records(art_records, NS_ARTICLES_REYNAERS)
        print(f"  Articles indexed: {result3['upserted']}")

    # 4. Extract and index formatting patterns as rules
    patterns = extract_formatting_patterns(full_text, pages)
    if patterns:
        result4 = index_kmd_rules(
            text=patterns,
            source=f"Реальный КМД: {project_name}",
            title=f"Паттерны форматирования — {project_name} ({doc_type})",
        )
        print(f"  Formatting patterns indexed: {result4['upserted']} chunks")

    print(f"  DONE\n")


def classify_page(text: str) -> str:
    """Classify page type by content."""
    text_lower = text.lower()
    if any(w in text_lower for w in ["титульный", "договор оказания", "заказчик"]):
        return "титульный лист"
    if any(w in text_lower for w in ["пояснительная", "записка"]):
        return "пояснительная записка"
    if any(w in text_lower for w in ["спецификация", "ведомость"]):
        return "спецификация"
    if re.search(r'Поз[\.\s]', text) or re.search(r'витраж\s+[А-Я]', text, re.IGNORECASE):
        return "чертёж изделия"
    if any(w in text_lower for w in ["обработка", "фрезеровка", "сборка"]):
        return "чертёж обработки"
    if any(w in text_lower for w in ["узел", "сечение", "примыкание"]):
        return "узел/сечение"
    if any(w in text_lower for w in ["спецификация", "ведомость материалов"]):
        return "спецификация материалов"
    return "другое"


def find_article_context(text: str, article_code: str, window: int = 300) -> str:
    """Find text context around an article code."""
    idx = text.find(article_code)
    if idx < 0:
        return ""
    start = max(0, idx - window)
    end = min(len(text), idx + len(article_code) + window)
    context = text[start:end].replace("\n", " ").strip()
    return context[:500]


def extract_formatting_patterns(full_text: str, pages: list[dict]) -> str:
    """Extract formatting patterns from real KMD for rule learning."""
    patterns = []

    # Position format patterns
    pos_formats = set()
    for m in re.finditer(r'(Поз[\.\s]*[А-Яа-яA-Za-z]{0,4}[\-\.]?\d+)', full_text):
        pos_formats.add(m.group(1).strip())
    for m in re.finditer(
        r'((?:Угловой\s+)?витраж\s+[А-Яа-яA-Za-z]+[\-\.]\d+(?:\.\d+)?)',
        full_text, re.IGNORECASE
    ):
        pos_formats.add(m.group(1).strip())

    if pos_formats:
        patterns.append(
            "## Форматы позиций изделий\n"
            "В реальных КМД используются следующие форматы маркировки:\n"
            + "\n".join(f"- `{p}`" for p in sorted(pos_formats))
        )

    # Quantity formats
    qty_formats = set()
    for m in re.finditer(r'(Количество\s*:?\s*\d+)', full_text, re.IGNORECASE):
        qty_formats.add(m.group(1).strip())
    for m in re.finditer(r'(Кол[\-\.\s]*во\s*:?\s*\d+\s*шт\.?)', full_text, re.IGNORECASE):
        qty_formats.add(m.group(1).strip())

    if qty_formats:
        patterns.append(
            "## Форматы количества\n"
            "Количество изделий указывается в форматах:\n"
            + "\n".join(f"- `{q}`" for q in sorted(qty_formats)[:20])
        )

    # Title block patterns
    title_patterns = []
    for pg in pages[:5]:
        text = pg["text"]
        if re.search(r'(Стадия|Лист|Листов|№док)', text):
            lines = [l.strip() for l in text.split('\n') if l.strip()][:15]
            title_patterns.append(
                f"### Штамп (стр.{pg['page']}):\n" + "\n".join(f"  {l}" for l in lines)
            )

    if title_patterns:
        patterns.append(
            "## Основная надпись (штамп)\n"
            "Типовая структура штампа в реальных КМД:\n"
            + "\n\n".join(title_patterns[:3])
        )

    # Profile system detection patterns
    profiles = set()
    for m in re.finditer(
        r'((?:Reynaers|Schüco|Schuco|Alutech|Алютех|TATPROF|Татпроф|Vidnal)\s+[\w\s\d\.\-]+)',
        full_text, re.IGNORECASE,
    ):
        profiles.add(m.group(1).strip()[:60])

    if profiles:
        patterns.append(
            "## Профильные системы\n"
            "Упоминания профильных систем:\n"
            + "\n".join(f"- {p}" for p in sorted(profiles))
        )

    return "\n\n".join(patterns) if patterns else ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Real KMD documents
    kmd_dir = os.path.join(base, "Реальные КМД АЛЬДМЕГА ЛАБ и ДОНСТРОЙ ОСТРОВ")

    documents = [
        (os.path.join(kmd_dir, "КМД Остров 2 Витражи.pdf"), "Остров 2", "витражи"),
        (os.path.join(kmd_dir, "КМД Остров 2 Окна.pdf"), "Остров 2", "окна"),
        (os.path.join(kmd_dir, "Техническое задание Остров 6.pdf"), "Остров 6", "техническое задание"),
    ]

    # Also check for task files
    tasks_dir = os.path.join(base, "Задания от АльдМЕгаЛаб")
    if os.path.isdir(tasks_dir):
        for f in os.listdir(tasks_dir):
            if f.endswith(('.pdf', '.PDF')):
                documents.append((os.path.join(tasks_dir, f), "АЛЬДМЕГА ЛАБ Задания", f))

    # Check for example documents
    for pattern_name in ["Пример 1", "Пример 2", "Пример 3"]:
        for ext in [".pdf", ".docx"]:
            for suffix in [
                " Описание ошибок.",
                " Ошибочный вариант.",
                " Правильный вариант.",
            ]:
                filepath = os.path.join(base, f"{pattern_name}{suffix}{ext}")
                if os.path.exists(filepath) and ext == ".pdf":
                    documents.append((filepath, pattern_name, suffix.strip(". ")))

    print(f"Found {len(documents)} documents to index\n")

    for filepath, project, doc_type in documents:
        if os.path.exists(filepath):
            index_pdf_document(filepath, project, doc_type)
        else:
            print(f"  SKIP (not found): {filepath}")

    # Print stats
    print("\n" + "=" * 60)
    print("INDEX STATS:")
    print("=" * 60)
    try:
        stats = get_index_stats()
        print(f"Total vectors: {stats.get('totalRecordCount', stats.get('total_vector_count', '?'))}")
        for ns, ns_stats in stats.get("namespaces", {}).items():
            count = ns_stats.get("recordCount", ns_stats.get("vector_count", 0))
            print(f"  {ns}: {count} vectors")
    except Exception as e:
        print(f"  Error getting stats: {e}")
