"""
KMD Knowledge Base — RAG Indexer
Загружает данные в Pinecone для семантического поиска.
Поддерживает: ГОСТ стандарты, каталоги производителей, научные статьи,
таблицы расчётов, эталонные КМД документы.
"""

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Optional

from pinecone import Pinecone

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PINECONE_API_KEY = os.getenv(
    "PINECONE_API_KEY",
    "pcsk_2X7jCg_ALmUcQBnEtwva5v5Q1cHjDLxuuuWFhowD6mb9eQzz6DoTQjYvHsDvxh3LkoGfgv",
)
PINECONE_INDEX = "kmd-knowledge"
PINECONE_HOST = "kmd-knowledge-b0hkvr1.svc.aped-4627-b74a.pinecone.io"

# Singleton client
_pc = Pinecone(api_key=PINECONE_API_KEY)
_index = _pc.Index(PINECONE_INDEX)

# Namespaces for logical separation
NS_GOST = "gost-standards"
NS_ARTICLES_REYNAERS = "articles-reynaers"
NS_ARTICLES_SCHUCO = "articles-schuco"
NS_ARTICLES_ALUTECH = "articles-alutech"
NS_ARTICLES_TATPROF = "articles-tatprof"
NS_ARTICLES_OTHER = "articles-other"
NS_HARDWARE = "hardware-fittings"
NS_THERMAL = "thermal-calculations"
NS_WIND = "wind-calculations"
NS_KMD_RULES = "kmd-formatting-rules"
NS_SCIENTIFIC = "scientific-articles"
NS_REAL_KMD = "real-kmd-documents"
NS_GLASS = "glass-specifications"
NS_SEALS = "seals-gaskets"

ALL_NAMESPACES = [
    NS_GOST, NS_ARTICLES_REYNAERS, NS_ARTICLES_SCHUCO, NS_ARTICLES_ALUTECH,
    NS_ARTICLES_TATPROF, NS_ARTICLES_OTHER, NS_HARDWARE, NS_THERMAL,
    NS_WIND, NS_KMD_RULES, NS_SCIENTIFIC, NS_REAL_KMD, NS_GLASS, NS_SEALS,
]

# Chunking parameters
CHUNK_SIZE = 600        # words per chunk
CHUNK_OVERLAP = 100     # overlap in words
MAX_BATCH = 96          # Pinecone batch limit for integrated embedding


# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------
def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """Split text into overlapping chunks by word count."""
    words = text.split()
    if len(words) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def chunk_by_sections(text: str, max_words: int = CHUNK_SIZE) -> list[str]:
    """Split text by markdown headers, keeping sections intact if possible."""
    sections = re.split(r'\n(?=#{1,4}\s)', text)
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        words = section.split()
        if len(words) <= max_words:
            chunks.append(section)
        else:
            chunks.extend(chunk_text(section, max_words, CHUNK_OVERLAP))
    return chunks


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------
def make_id(namespace: str, content: str, idx: int = 0) -> str:
    """Deterministic ID from namespace + content hash + index."""
    h = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
    return f"{namespace}_{h}_{idx}"


# ---------------------------------------------------------------------------
# Pinecone upsert (integrated embedding — text goes as record field)
# ---------------------------------------------------------------------------
def upsert_records(
    records: list[dict],
    namespace: str,
) -> dict:
    """
    Upsert records to Pinecone with integrated embedding (SDK).
    Each record: {"_id": str, "content": str, ...metadata}
    The 'content' field is auto-embedded by Pinecone (field_map.text = "content").
    """
    results = {"upserted": 0, "errors": []}

    for i in range(0, len(records), MAX_BATCH):
        batch = records[i : i + MAX_BATCH]
        try:
            _index.upsert_records(namespace=namespace, records=batch)
            results["upserted"] += len(batch)
        except Exception as e:
            results["errors"].append(f"Batch {i//MAX_BATCH}: {e}")

        # Rate limit respect
        if i + MAX_BATCH < len(records):
            time.sleep(0.3)

    return results


# ---------------------------------------------------------------------------
# High-level indexing functions
# ---------------------------------------------------------------------------
def index_text_document(
    text: str,
    namespace: str,
    source: str,
    category: str,
    title: str = "",
    extra_metadata: Optional[dict] = None,
    use_sections: bool = True,
) -> dict:
    """
    Index a text document into Pinecone.
    Chunks the text, adds metadata, upserts.
    """
    if use_sections:
        chunks = chunk_by_sections(text)
    else:
        chunks = chunk_text(text)

    if not chunks:
        return {"upserted": 0, "errors": ["Empty text"]}

    records = []
    for i, chunk in enumerate(chunks):
        record = {
            "_id": make_id(namespace, chunk, i),
            "content": chunk,
            "source": source,
            "category": category,
            "title": title,
            "chunk_index": i,
            "total_chunks": len(chunks),
        }
        if extra_metadata:
            record.update(extra_metadata)
        records.append(record)

    return upsert_records(records, namespace)


def index_article_catalog(
    articles: list[dict],
    namespace: str,
    manufacturer: str,
    system_name: str = "",
) -> dict:
    """
    Index product articles. Each article becomes one record.
    article: {"code": "4080102", "description": "Рама MasterLine 8", "type": "frame", ...}
    """
    records = []
    for art in articles:
        code = str(art.get("code", ""))
        desc = art.get("description", "")
        art_type = art.get("type", "")
        specs = art.get("specs", "")

        content = (
            f"Артикул {code} — {desc}. "
            f"Производитель: {manufacturer}. Система: {system_name}. "
            f"Тип: {art_type}. {specs}"
        )

        record = {
            "_id": f"art_{manufacturer.lower()}_{code}",
            "content": content,
            "article_code": code,
            "manufacturer": manufacturer,
            "system": system_name,
            "article_type": art_type,
            "category": "article_catalog",
        }
        records.append(record)

    return upsert_records(records, namespace)


def index_gost_standard(
    text: str,
    standard_id: str,
    title: str,
) -> dict:
    """Index a GOST/SP standard document."""
    return index_text_document(
        text=text,
        namespace=NS_GOST,
        source=f"ГОСТ/СП {standard_id}",
        category="standard",
        title=title,
        extra_metadata={"standard_id": standard_id},
    )


def index_thermal_data(text: str, source: str, title: str) -> dict:
    """Index thermal calculation data (tables, formulas, values)."""
    return index_text_document(
        text=text,
        namespace=NS_THERMAL,
        source=source,
        category="thermal_calculation",
        title=title,
    )


def index_wind_data(text: str, source: str, title: str) -> dict:
    """Index wind load calculation data."""
    return index_text_document(
        text=text,
        namespace=NS_WIND,
        source=source,
        category="wind_calculation",
        title=title,
    )


def index_hardware(text: str, manufacturer: str, title: str) -> dict:
    """Index hardware/fittings data."""
    return index_text_document(
        text=text,
        namespace=NS_HARDWARE,
        source=manufacturer,
        category="hardware",
        title=title,
        extra_metadata={"manufacturer": manufacturer},
    )


def index_scientific_article(
    text: str,
    authors: str,
    title: str,
    year: str = "",
    source_url: str = "",
) -> dict:
    """Index a scientific article or technical paper."""
    return index_text_document(
        text=text,
        namespace=NS_SCIENTIFIC,
        source=source_url or "research",
        category="scientific_article",
        title=title,
        extra_metadata={"authors": authors, "year": year},
    )


def index_real_kmd(
    text: str,
    project_name: str,
    document_type: str,
    positions: list[str] = None,
    articles: list[str] = None,
) -> dict:
    """
    Index real KMD document as ground truth.
    This teaches the system what correct KMD looks like.
    """
    return index_text_document(
        text=text,
        namespace=NS_REAL_KMD,
        source=project_name,
        category="real_kmd",
        title=f"{project_name} — {document_type}",
        extra_metadata={
            "document_type": document_type,
            "positions_count": len(positions) if positions else 0,
            "articles_count": len(articles) if articles else 0,
        },
    )


def index_kmd_rules(text: str, source: str, title: str) -> dict:
    """Index KMD formatting rules and requirements."""
    return index_text_document(
        text=text,
        namespace=NS_KMD_RULES,
        source=source,
        category="kmd_rules",
        title=title,
    )


# ---------------------------------------------------------------------------
# Bulk indexing from structured data files
# ---------------------------------------------------------------------------
def index_from_json(filepath: str) -> dict:
    """
    Index data from a structured JSON file.
    Expected format:
    {
        "namespace": "gost-standards",
        "documents": [
            {
                "title": "ГОСТ 21.502-2016",
                "source": "Росстандарт",
                "category": "standard",
                "text": "...",
                "metadata": {...}
            }
        ]
    }
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    namespace = data.get("namespace", NS_KMD_RULES)
    total = {"upserted": 0, "errors": []}

    for doc in data.get("documents", []):
        result = index_text_document(
            text=doc["text"],
            namespace=namespace,
            source=doc.get("source", ""),
            category=doc.get("category", ""),
            title=doc.get("title", ""),
            extra_metadata=doc.get("metadata"),
        )
        total["upserted"] += result["upserted"]
        total["errors"].extend(result["errors"])

    return total


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------
def get_index_stats() -> dict:
    """Get Pinecone index statistics."""
    return _index.describe_index_stats()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python rag_indexer.py stats")
        print("  python rag_indexer.py index-json <file.json>")
        print("  python rag_indexer.py index-text <file.txt> <namespace> <source> <title>")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "stats":
        stats = get_index_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    elif cmd == "index-json":
        result = index_from_json(sys.argv[2])
        print(f"Upserted: {result['upserted']}, Errors: {len(result['errors'])}")
        for e in result["errors"]:
            print(f"  ERROR: {e}")

    elif cmd == "index-text":
        text = Path(sys.argv[2]).read_text(encoding="utf-8")
        result = index_text_document(
            text=text,
            namespace=sys.argv[3],
            source=sys.argv[4],
            category="manual",
            title=sys.argv[5] if len(sys.argv) > 5 else "",
        )
        print(f"Upserted: {result['upserted']}, Errors: {len(result['errors'])}")
