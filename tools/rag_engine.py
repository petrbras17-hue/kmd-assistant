"""
KMD Knowledge Base — RAG Query Engine
Семантический поиск по базе знаний для валидации КМД документации.
Используется всеми функциями server.py для повышения точности.
"""

import os
import re
from typing import Optional

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_HOST = os.getenv(
    "PINECONE_HOST", "kmd-knowledge-b0hkvr1.svc.aped-4627-b74a.pinecone.io"
)

if not PINECONE_API_KEY:
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "PINECONE_API_KEY is not set — RAG search will be unavailable"
    )

# Import namespace constants — try both import paths (tools.X and direct X)
try:
    from tools.rag_indexer import (
        NS_GOST, NS_ARTICLES_REYNAERS, NS_ARTICLES_SCHUCO, NS_ARTICLES_ALUTECH,
        NS_ARTICLES_TATPROF, NS_ARTICLES_OTHER, NS_HARDWARE, NS_THERMAL,
        NS_WIND, NS_KMD_RULES, NS_SCIENTIFIC, NS_REAL_KMD, NS_GLASS, NS_SEALS,
    )
except ImportError:
    try:
        from rag_indexer import (
            NS_GOST, NS_ARTICLES_REYNAERS, NS_ARTICLES_SCHUCO, NS_ARTICLES_ALUTECH,
            NS_ARTICLES_TATPROF, NS_ARTICLES_OTHER, NS_HARDWARE, NS_THERMAL,
            NS_WIND, NS_KMD_RULES, NS_SCIENTIFIC, NS_REAL_KMD, NS_GLASS, NS_SEALS,
        )
    except ImportError:
        # Fallback constants if rag_indexer unavailable
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


# ---------------------------------------------------------------------------
# Core search
# ---------------------------------------------------------------------------
async def search(
    query: str,
    namespace: str,
    top_k: int = 10,
    filter_dict: Optional[dict] = None,
    min_score: float = 0.3,
) -> list[dict]:
    """
    Semantic search in Pinecone using integrated embedding.
    Returns list of {id, score, content, ...metadata} sorted by relevance.
    """
    url = f"https://{PINECONE_HOST}/records/namespaces/{namespace}/search"
    headers = {
        "Api-Key": PINECONE_API_KEY,
        "Content-Type": "application/json",
        "X-Pinecone-API-Version": "2025-01",
    }

    body = {
        "query": {"top_k": top_k, "inputs": {"text": query}},
    }
    if filter_dict:
        body["query"]["filter"] = filter_dict

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=body, headers=headers)
        if resp.status_code != 200:
            return []
        data = resp.json()

    results = []
    for hit in data.get("result", {}).get("hits", []):
        score = hit.get("_score", 0)
        if score < min_score:
            continue
        fields = hit.get("fields", {})
        results.append({
            "id": hit.get("_id", ""),
            "score": score,
            "content": fields.get("content", ""),
            "source": fields.get("source", ""),
            "category": fields.get("category", ""),
            "title": fields.get("title", ""),
            **{k: v for k, v in fields.items()
               if k not in ("content", "source", "category", "title")},
        })

    return results


async def multi_search(
    query: str,
    namespaces: list[str],
    top_k: int = 5,
    min_score: float = 0.3,
) -> list[dict]:
    """Search across multiple namespaces and merge results by score."""
    all_results = []
    for ns in namespaces:
        results = await search(query, ns, top_k=top_k, min_score=min_score)
        all_results.extend(results)
    all_results.sort(key=lambda x: x["score"], reverse=True)
    return all_results[:top_k * 2]


# ---------------------------------------------------------------------------
# Domain-specific queries
# ---------------------------------------------------------------------------
async def validate_article(article_code: str) -> dict:
    """
    Validate a 7-digit article code against manufacturer catalogs.
    Returns: {valid: bool, manufacturer: str, system: str, description: str, confidence: float}
    """
    query = f"артикул {article_code} профиль алюминий"
    namespaces = [
        NS_ARTICLES_REYNAERS, NS_ARTICLES_SCHUCO, NS_ARTICLES_ALUTECH,
        NS_ARTICLES_TATPROF, NS_ARTICLES_OTHER,
    ]

    results = await multi_search(query, namespaces, top_k=5, min_score=0.5)

    if not results:
        return {
            "valid": False,
            "article_code": article_code,
            "manufacturer": "unknown",
            "system": "unknown",
            "description": "Артикул не найден в базе данных",
            "confidence": 0.0,
        }

    best = results[0]
    # Check if the article code appears literally in the content
    code_in_content = article_code in best["content"]

    return {
        "valid": code_in_content and best["score"] > 0.6,
        "article_code": article_code,
        "manufacturer": best.get("manufacturer", "unknown"),
        "system": best.get("system", "unknown"),
        "description": best["content"][:200],
        "confidence": best["score"] if code_in_content else best["score"] * 0.5,
        "similar_articles": [
            {"code": r.get("article_code", ""), "desc": r["content"][:100], "score": r["score"]}
            for r in results[1:4]
        ],
    }


async def validate_articles_batch(article_codes: list[str]) -> list[dict]:
    """Validate multiple articles in parallel."""
    import asyncio
    tasks = [validate_article(code) for code in article_codes]
    return await asyncio.gather(*tasks)


async def get_gost_context(query: str, top_k: int = 5) -> list[dict]:
    """
    Get relevant GOST/SP standard sections for a given query.
    Used to validate compliance and provide normative references.
    """
    return await search(query, NS_GOST, top_k=top_k, min_score=0.35)


async def get_thermal_reference(
    profile_system: str = "",
    glass_type: str = "",
    climate_zone: str = "",
) -> list[dict]:
    """Get thermal calculation reference data."""
    query_parts = ["расчёт теплопередачи алюминиевые окна"]
    if profile_system:
        query_parts.append(f"система {profile_system}")
    if glass_type:
        query_parts.append(f"стеклопакет {glass_type}")
    if climate_zone:
        query_parts.append(f"климатическая зона {climate_zone}")

    return await search(" ".join(query_parts), NS_THERMAL, top_k=5)


async def get_wind_reference(
    height_m: float = 0,
    wind_region: str = "",
) -> list[dict]:
    """Get wind load calculation reference data."""
    query = f"ветровая нагрузка расчёт давление"
    if height_m:
        query += f" высота {height_m} м"
    if wind_region:
        query += f" район {wind_region}"

    return await search(query, NS_WIND, top_k=5)


async def get_hardware_for_system(
    profile_system: str,
    construction_type: str = "окна",
    sash_weight_kg: float = 0,
) -> list[dict]:
    """Get compatible hardware for a given profile system."""
    query = f"фурнитура {profile_system} {construction_type}"
    if sash_weight_kg:
        query += f" створка {sash_weight_kg} кг"

    return await search(query, NS_HARDWARE, top_k=10)


async def get_kmd_formatting_rules(document_type: str = "") -> list[dict]:
    """Get KMD formatting rules and requirements."""
    query = f"правила оформления КМД документации {document_type}"
    return await search(query, NS_KMD_RULES, top_k=10)


async def find_similar_kmd(
    text_excerpt: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Find similar sections in real KMD documents.
    Used for learning correct formatting from ground truth.
    """
    return await search(text_excerpt, NS_REAL_KMD, top_k=top_k, min_score=0.4)


async def get_position_format_examples(
    construction_type: str = "",
) -> list[dict]:
    """
    Get examples of position naming formats from real KMD documents.
    Helps parser recognize different formats: Поз.О-1, В-1, БФ1, etc.
    """
    query = f"позиция маркировка изделие {construction_type} количество"
    results = await search(query, NS_REAL_KMD, top_k=10, min_score=0.3)
    results.extend(await search(query, NS_KMD_RULES, top_k=5, min_score=0.3))
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:10]


# ---------------------------------------------------------------------------
# RAG context builder for LLM prompts
# ---------------------------------------------------------------------------
async def build_rag_context(
    query: str,
    namespaces: list[str] = None,
    max_tokens: int = 3000,
    top_k: int = 8,
) -> str:
    """
    Build a context string from Pinecone search results for LLM prompts.
    Returns formatted text ready to inject into system prompts.
    """
    if namespaces is None:
        namespaces = [NS_GOST, NS_KMD_RULES, NS_ARTICLES_REYNAERS]

    results = await multi_search(query, namespaces, top_k=top_k, min_score=0.35)

    if not results:
        return ""

    context_parts = []
    total_chars = 0
    char_limit = max_tokens * 4  # ~4 chars per token

    for r in results:
        entry = (
            f"[{r.get('source', '')} | {r.get('title', '')} | "
            f"score={r['score']:.2f}]\n{r['content']}\n"
        )
        if total_chars + len(entry) > char_limit:
            break
        context_parts.append(entry)
        total_chars += len(entry)

    if not context_parts:
        return ""

    return (
        "=== КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ КМД ===\n"
        "Используй эту информацию для точной валидации. "
        "Не выдумывай данные — опирайся только на факты ниже.\n\n"
        + "\n---\n".join(context_parts)
        + "\n=== КОНЕЦ КОНТЕКСТА ===\n"
    )


# ---------------------------------------------------------------------------
# Comprehensive validation pipeline
# ---------------------------------------------------------------------------
async def validate_kmd_document(
    extracted_text: str,
    positions: list[dict] = None,
    articles: list[str] = None,
) -> dict:
    """
    Full RAG-powered validation of a KMD document.
    Checks articles, formatting, compliance with standards.
    Returns structured validation report.
    """
    import asyncio

    report = {
        "articles_validation": [],
        "gost_compliance": [],
        "formatting_issues": [],
        "similar_documents": [],
        "confidence": 0.0,
    }

    tasks = []

    # 1. Validate articles
    if articles:
        tasks.append(("articles", validate_articles_batch(articles[:50])))

    # 2. Check GOST compliance
    tasks.append(("gost", get_gost_context(
        f"требования КМД алюминиевые конструкции: {extracted_text[:500]}"
    )))

    # 3. Get formatting rules
    tasks.append(("rules", get_kmd_formatting_rules()))

    # 4. Find similar real KMD
    tasks.append(("similar", find_similar_kmd(extracted_text[:500])))

    # Execute all in parallel
    results_map = {}
    coros = [(name, coro) for name, coro in tasks]
    gathered = await asyncio.gather(*[c for _, c in coros], return_exceptions=True)

    for (name, _), result in zip(coros, gathered):
        if isinstance(result, Exception):
            results_map[name] = []
        else:
            results_map[name] = result

    # Build report
    if "articles" in results_map:
        report["articles_validation"] = results_map["articles"]
        valid_count = sum(1 for a in results_map["articles"] if a.get("valid"))
        total = len(results_map["articles"])
        report["articles_accuracy"] = valid_count / total if total > 0 else 0

    report["gost_compliance"] = results_map.get("gost", [])
    report["formatting_rules"] = results_map.get("rules", [])
    report["similar_documents"] = results_map.get("similar", [])

    # Overall confidence based on data availability
    data_points = sum(
        1 for v in results_map.values()
        if isinstance(v, list) and len(v) > 0
    )
    report["confidence"] = min(data_points / 4.0, 1.0)

    return report
