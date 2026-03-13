"""
KMD Assistant — веб-сервер для инженеров АЛЬДМЕГА ЛАБ.
FastAPI бэкенд с инструментами проверки КМД документации.
"""

import os
import sys
import re
import math
import time
import uuid
import json
import shutil
import zipfile
import tempfile
import html as _html
import base64
import hmac
import hashlib
import difflib
from pathlib import Path
from datetime import datetime
from typing import List

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel
from sqlalchemy import select, func as sa_func
from webapp.database import async_session, engine as db_engine
from webapp.models import (
    ActivityLog as ActivityLogModel,
    Base as DBBase,
    DocumentVersion,
    Project as ProjectModel,
    User,
    Workspace,
    WorkspaceMember,
)
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Depends, Security
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.security import APIKeyHeader
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

# Sprint 13: Auth, Workspaces, Permissions, API Keys
from webapp.auth import router as auth_router
from webapp.workspaces import router as workspaces_router
from webapp.api_keys import router as api_keys_router
from webapp.permissions import RoleMiddleware

# Load .env for OpenRouter API key
load_dotenv(Path(__file__).parent.parent / ".env")

# Sentry error tracking
import sentry_sdk
_sentry_dsn = os.getenv("SENTRY_DSN", "")
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
        environment=os.getenv("RAILWAY_ENVIRONMENT", "development"),
    )

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_LLM_MODEL = "google/gemini-2.0-flash-001"

# ============== API KEY AUTHENTICATION ==============
_env_api_key = os.getenv("KMD_API_KEY", "").strip()
if _env_api_key:
    KMD_API_KEY: str = _env_api_key
else:
    KMD_API_KEY = uuid.uuid4().hex
    print(f"[AUTH] Generated API key (set KMD_API_KEY env var to override): {KMD_API_KEY}")

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(_api_key_header)):
    """Dependency that validates X-API-Key header."""
    if not api_key or not hmac.compare_digest(api_key, KMD_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

# Paths exempt from API key auth
_AUTH_EXEMPT_PATHS: set[str] = {
    "/", "/docs", "/redoc", "/openapi.json", "/api/health", "/api/auth/validate",
    "/api/auth/login", "/api/auth/register", "/api/auth/refresh",
    "/api/auth/google", "/api/auth/google/callback",
    "/api/auth/yandex", "/api/auth/yandex/callback",
}
_AUTH_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/icons/", "/manifest.json", "/sw.js", "/offline.html",
    "/api/download/", "/api/download-act/", "/api/download-nc/",
    "/auth_ui.js",
)

# Добавляем tools в путь
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from compare_orders import extract_articles, compare_orders
from pdf_tools import extract_text_from_pdf
from dxf_tools import parse_dxf_for_web
from ocr_tools import (
    ocr_pil_image,
    parse_positions as ocr_parse_positions,
    parse_articles as ocr_parse_articles,
    parse_dimensions as ocr_parse_dimensions,
)
from kmd_parser import (
    parse_kmd_pdf, parse_kmd_page, extract_positions, extract_quantity,
    extract_articles as kmd_extract_articles, extract_dimensions,
    extract_dimensions_individual, extract_color, extract_handle_height,
    extract_profile_system, extract_glass_formula, classify_page,
)
from rag_engine import (
    build_rag_context, validate_article, validate_articles_batch,
    get_gost_context, get_kmd_formatting_rules, find_similar_kmd,
    validate_kmd_document,
)
from webapp.cache import cache_get, cache_set, cache_invalidate, _make_key
try:
    from kmd_rules_engine import validate_kmd_full, format_report_ru
    _RULES_ENGINE_AVAILABLE = True
except Exception:
    _RULES_ENGINE_AVAILABLE = False

try:
    from multi_validator import validate_with_agents
    _MULTI_VALIDATOR_AVAILABLE = True
except Exception:
    _MULTI_VALIDATOR_AVAILABLE = False

tags_metadata = [
    {"name": "Auth", "description": "API key authentication and validation."},
    {"name": "Documentation", "description": "KMD document parsing, comparison, validation, checklists, and cross-validation."},
    {"name": "Calculators", "description": "Engineering calculators: thermal, wind load, sash weight, glass thickness, fasteners."},
    {"name": "3D & Optimization", "description": "3D preview, cutting optimization, profile recommendation, spec generation."},
    {"name": "AI Tools", "description": "AI-powered review, notes, GOST lookup, hardware, visual compare, KMD generation, translation, and chat."},
    {"name": "Production", "description": "CNC programs, QR labels, photo reports, acceptance acts, requisitions."},
    {"name": "Analytics & Projects", "description": "Statistics, activity log, project management, versioning, nodes library, file downloads."},
]

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="KMD Assistant API",
    description=(
        "Engineering platform API for ALDMEGA LAB. "
        "Tools for KMD documentation verification, engineering calculations, "
        "AI-assisted review, 3D visualization, cutting optimization, "
        "CNC program generation, and project management. "
        "**Modules:** 32 | **Endpoints:** 46"
    ),
    version="2.0.0",
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ---------- API-key auth middleware ----------

from starlette.responses import JSONResponse as StarletteJSONResponse


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Require X-API-Key on mutating /api/* endpoints.

    Browser requests authenticated via CSRF token are exempt (the CSRF
    middleware validates them separately).  Machine-to-machine callers
    must supply X-API-Key.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        # Only protect POST/PUT/PATCH/DELETE on /api/* paths
        if method in ("POST", "PUT", "PATCH", "DELETE") and path.startswith("/api"):
            # Check exemptions
            if path not in _AUTH_EXEMPT_PATHS and not path.startswith(_AUTH_EXEMPT_PREFIXES):
                api_key = request.headers.get("X-API-Key", "")
                csrf_token = request.headers.get("X-CSRF-Token", "")
                # Allow if valid API key OR valid CSRF token (browser)
                has_valid_api_key = api_key and hmac.compare_digest(api_key, KMD_API_KEY)
                has_valid_csrf = (
                    csrf_token
                    and csrf_token in csrf_tokens
                    and csrf_tokens[csrf_token] > time.time()
                )
                if not has_valid_api_key and not has_valid_csrf:
                    return StarletteJSONResponse(
                        status_code=401,
                        content={"detail": "Invalid or missing API key"},
                    )

        return await call_next(request)


# APIKeyMiddleware is registered AFTER CSRFMiddleware (below) so that
# Starlette's inverse ordering gives us: APIKey → CSRF → route handler.


# Swagger "Authorize" button — adds X-API-Key to all try-it-out requests
_original_openapi = app.openapi


def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = _original_openapi()
    schema.setdefault("components", {}).setdefault("securitySchemes", {})["ApiKeyAuth"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": "API key for authenticated access. Pass via X-API-Key header.",
    }
    schema["security"] = [{"ApiKeyAuth": []}]
    app.openapi_schema = schema
    return schema


app.openapi = _custom_openapi


# ---------- Health & Auth endpoints ----------

@app.get("/api/health", tags=["Auth"], summary="Health check")
async def api_health():
    """Comprehensive health check — DB, Pinecone, OpenRouter."""
    checks = {}
    overall = "ok"

    # Check database
    try:
        async with async_session() as session:
            await session.execute(select(1))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)[:100]}"
        overall = "degraded"

    # Check Pinecone (quick describe index stats)
    try:
        pinecone_key = os.getenv("PINECONE_API_KEY", "")
        if pinecone_key:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://kmd-knowledge-b0hkvr1.svc.aped-4627-b74a.pinecone.io/describe_index_stats",
                    headers={"Api-Key": pinecone_key},
                )
                if resp.status_code == 200:
                    checks["pinecone"] = "ok"
                else:
                    checks["pinecone"] = f"error: HTTP {resp.status_code}"
                    overall = "degraded"
        else:
            checks["pinecone"] = "not_configured"
    except Exception as e:
        checks["pinecone"] = f"error: {str(e)[:100]}"
        overall = "degraded"

    # Check OpenRouter (just verify API key is set)
    if os.getenv("OPENROUTER_API_KEY", ""):
        checks["openrouter"] = "configured"
    else:
        checks["openrouter"] = "not_configured"
        overall = "degraded"

    # Check Redis
    try:
        from webapp.cache import get_redis
        r = await get_redis()
        if r:
            await r.ping()
            checks["redis"] = "ok"
        else:
            checks["redis"] = "not_configured"
    except Exception as e:
        checks["redis"] = f"error: {str(e)[:100]}"

    return {
        "status": overall,
        "checks": checks,
        "version": "1.0.0",
    }


@app.get("/api/auth/validate",
    "/api/auth/login", "/api/auth/register", "/api/auth/refresh",
    "/api/auth/google", "/api/auth/google/callback",
    "/api/auth/yandex", "/api/auth/yandex/callback", tags=["Auth"], summary="Validate API key")
async def api_auth_validate(api_key: str = Security(_api_key_header)):
    """Check if the provided X-API-Key header is valid."""
    if not api_key or not hmac.compare_digest(api_key, KMD_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return {"status": "ok", "message": "API key is valid"}

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

UPLOAD_DIR = Path(__file__).parent / "uploads"
RESULTS_DIR = Path(__file__).parent / "results"
VERSIONS_DIR = Path(__file__).parent / "versions"
# DEPRECATED: VERSIONS_JSON was used for file-based version storage.
# Metadata is now stored in PostgreSQL via DocumentVersion model.
# Kept for potential migration of legacy data.
VERSIONS_JSON = Path(__file__).parent / "versions.json"
UPLOAD_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)
VERSIONS_DIR.mkdir(exist_ok=True)

# ============== CSRF PROTECTION ==============

CSRF_TOKEN_TTL = 3600  # 1 hour
CSRF_MAX_TOKENS = 10_000  # prevent unbounded memory growth
csrf_tokens: dict[str, float] = {}  # token -> expiry timestamp

# Endpoints exempt from CSRF validation
_CSRF_EXEMPT_PATHS = {"/api/csrf-token"}


def _cleanup_expired_csrf_tokens():
    """Remove expired CSRF tokens from the in-memory store."""
    now = time.time()
    expired = [t for t, exp in csrf_tokens.items() if exp <= now]
    for t in expired:
        csrf_tokens.pop(t, None)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Validate X-CSRF-Token header on all mutating /api/* requests."""

    async def dispatch(self, request: Request, call_next):
        if (
            request.method in ("POST", "PUT", "PATCH", "DELETE")
            and request.url.path.startswith("/api/")
            and request.url.path not in _CSRF_EXEMPT_PATHS
        ):
            _cleanup_expired_csrf_tokens()
            token = request.headers.get("X-CSRF-Token", "")
            if not token or token not in csrf_tokens:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token missing or invalid"},
                )
            if csrf_tokens[token] <= time.time():
                csrf_tokens.pop(token, None)
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token expired"},
                )
        return await call_next(request)


app.add_middleware(CSRFMiddleware)
app.add_middleware(APIKeyMiddleware)  # registered last = executes first (outermost)
app.add_middleware(RoleMiddleware)  # Sprint 13: permission checks

# Sprint 13: подключаем роутеры аутентификации, воркспейсов, API-ключей
app.include_router(auth_router)
app.include_router(workspaces_router)
app.include_router(api_keys_router)


@app.on_event("startup")
async def _create_db_tables():
    """Auto-create database tables on startup (useful for local SQLite dev)."""
    async with db_engine.begin() as conn:
        await conn.run_sync(DBBase.metadata.create_all)


# ============== IN-MEMORY ACTIVITY LOG ==============

activity_log: list[dict] = []
MAX_ACTIVITY = 100

counters = {
    "compare": 0,
    "check_pdf": 0,
    "parse_kmd": 0,
    "checklist": 0,
    "cross_validate": 0,
    "compare_pdf": 0,
    "batch": 0,
    "generate_spec": 0,
    "recommend_profile": 0,
    "optimize_cutting": 0,
    "preview_3d": 0,
    "calc_thermal": 0,
    "calc_wind": 0,
    "calc_sash_weight": 0,
    "calc_glass": 0,
    "calc_fasteners": 0,
    "ai_review": 0,
    "ai_note": 0,
    "ai_gost": 0,
    "ai_hardware": 0,
    "ai_compare": 0,
    "ai_generate_kmd": 0,
    "ai_translate": 0,
    "versioning": 0,
    "requisition": 0,
    "projects": 0,
    "act_gen": 0,
    "cnc": 0,
    "qr_labels": 0,
    "photo_report": 0,
}

# ============== IN-MEMORY PROJECT TRACKER ==============
projects_list: list[dict] = []
PROJECT_STAGES = ["замер", "КМД", "производство", "доставка", "монтаж", "сдано"]


async def log_activity(op_type: str, filename: str, summary: str):
    """Write activity entry to database and update in-memory counters."""
    counters[op_type] = counters.get(op_type, 0) + 1
    # In-memory cache (no size cap — DB is the authoritative store)
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "type": op_type,
        "filename": filename,
        "summary": summary,
    }
    activity_log.insert(0, entry)
    del activity_log[MAX_ACTIVITY:]
    # Persist to database
    try:
        async with async_session() as session:
            db_entry = ActivityLogModel(
                operation=op_type,
                file_name=filename,
                result_summary=summary,
            )
            session.add(db_entry)
            await session.commit()
    except Exception:
        # DB write failure should not break the endpoint
        pass


def save_upload(file: UploadFile) -> Path:
    """Сохранить загруженный файл с уникальным именем."""
    # Берём только имя файла без пути для защиты от path traversal
    original_name = Path(file.filename).name
    uid = uuid.uuid4().hex[:8]
    safe_name = f"{uid}_{original_name}"
    path = UPLOAD_DIR / safe_name
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return path


# ===================== СТРАНИЦА =====================

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "index.html"
    return html_path.read_text(encoding="utf-8")


# ============== PWA ASSETS ==============

@app.get("/manifest.json")
async def pwa_manifest():
    manifest_path = Path(__file__).parent / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="manifest.json not found")
    return FileResponse(
        manifest_path,
        media_type="application/manifest+json",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/auth_ui.js")
async def auth_ui_script():
    """Отдаёт JS-модуль аутентификации."""
    js_path = Path(__file__).parent / "auth_ui.js"
    if not js_path.exists():
        raise HTTPException(status_code=404, detail="auth_ui.js not found")
    return FileResponse(js_path, media_type="application/javascript")


@app.get("/sw.js")
async def pwa_service_worker():
    sw_path = Path(__file__).parent / "sw.js"
    if not sw_path.exists():
        raise HTTPException(status_code=404, detail="sw.js not found")
    return FileResponse(
        sw_path,
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-cache",
            "Service-Worker-Allowed": "/",
        },
    )


@app.get("/offline.html")
async def pwa_offline():
    offline_path = Path(__file__).parent / "offline.html"
    if not offline_path.exists():
        raise HTTPException(status_code=404, detail="offline.html not found")
    return FileResponse(offline_path, media_type="text/html")


@app.get("/icons/{filename:path}")
async def pwa_icons(filename: str):
    icons_dir = Path(__file__).parent / "icons"
    file_path = (icons_dir / filename).resolve()
    if not str(file_path).startswith(str(icons_dir.resolve())):
        raise HTTPException(status_code=403, detail="Forbidden")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Icon not found")
    return FileResponse(
        file_path,
        headers={"Cache-Control": "public, max-age=2592000, immutable"},
    )


# ============== CSRF TOKEN ENDPOINT ==============

@limiter.limit("30/minute")
@app.get("/api/csrf-token")
async def get_csrf_token(request: Request):
    """Generate a new CSRF token (valid for 1 hour)."""
    _cleanup_expired_csrf_tokens()
    if len(csrf_tokens) >= CSRF_MAX_TOKENS:
        raise HTTPException(status_code=429, detail="Too many active CSRF tokens")
    token = uuid.uuid4().hex
    csrf_tokens[token] = time.time() + CSRF_TOKEN_TTL
    return {"csrf_token": token}


# ============== 1. СРАВНЕНИЕ СПЕЦИФИКАЦИЙ ==============

@limiter.limit("10/minute")
@app.post("/api/compare", tags=["Documentation"], summary="Compare two order specifications")
async def api_compare(
    request: Request,
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

        await log_activity("compare", f"{file_a.filename} / {file_b.filename}",
                     f"Различий: {len(diffs)}, удалено: {summary['removed']}, изменено: {summary['changed']}")

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

@limiter.limit("10/minute")
@app.post("/api/check-pdf", tags=["Documentation"], summary="Validate KMD PDF completeness")
async def api_check_pdf(request: Request, file: UploadFile = File(...)):
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

        await log_activity("check_pdf", file.filename,
                     f"Страниц: {total_pages}, позиций: {len(all_positions)}")

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

@limiter.limit("10/minute")
@app.post("/api/parse-kmd", tags=["Documentation"], summary="Parse KMD positions from PDF")
async def api_parse_kmd(request: Request, file: UploadFile = File(...)):
    """Извлечь данные из PDF чертежей КМД: позиции, артикулы, размеры."""
    path = save_upload(file)

    try:
        result = parse_kmd_pdf(str(path))

        items = []
        for pos in result["positions"]:
            items.append({
                "page": pos.get("page", 0),
                "position": pos["position"],
                "quantity": pos.get("quantity", 0),
                "articles": pos.get("articles", []),
                "dimensions": pos.get("dimensions_mm", []),
                "dim_wxh": [d["raw"] for d in pos.get("dimensions", [])],
                "handle_height": pos.get("handle_height"),
                "color": pos.get("color", ""),
                "glass": pos.get("glass", []),
            })

        await log_activity("parse_kmd", file.filename,
                     f"Позиций: {result['total_positions']}, артикулов: {result['articles_count']}")

        return {
            "status": "ok",
            "filename": file.filename,
            "items": items,
            "total_positions": result["total_positions"],
            "total_items": result["total_items"],
            "unique_articles": result["unique_articles"],
            "articles_count": result["articles_count"],
            "profile_system": result.get("profile_system"),
            "colors": result.get("colors", []),
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path.unlink(missing_ok=True)


# ============== 4. ПАРСИНГ DXF ЧЕРТЕЖЕЙ ==============

@app.post("/api/parse-dxf", tags=["Documentation"], summary="Parse DXF drawing file")
async def api_parse_dxf(file: UploadFile = File(...)):
    """Разобрать DXF чертёж AutoCAD: слои, тексты, размеры, блоки, КМД-данные."""
    if not file.filename.lower().endswith((".dxf",)):
        raise HTTPException(status_code=400, detail="Ожидается файл формата .dxf")

    path = save_upload(file)

    try:
        result = parse_dxf_for_web(str(path))

        await log_activity("parse_kmd", file.filename,
                     f"DXF: слоёв {len(result['layers'])}, текстов {len(result['texts'])}, "
                     f"размеров {len(result['dimensions'])}, блоков {len(result['blocks'])}")

        return {
            "status": "ok",
            "filename": file.filename,
            **result,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path.unlink(missing_ok=True)


# ============== 5. OCR-ПАРСИНГ СКАНИРОВАННЫХ ЧЕРТЕЖЕЙ ==============

@app.post("/api/ocr-parse", tags=["Documentation"], summary="OCR-parse scanned drawing")
async def api_ocr_parse(file: UploadFile = File(...)):
    """OCR-парсинг сканированного PDF: распознать текст, позиции, артикулы.

    Для каждой страницы:
    - Если PyMuPDF извлекает текстовый слой — использует его.
    - Если страница image-only — рендерит в изображение, прогоняет Tesseract
      (русский + английский, предобработка: grayscale, threshold, denoise).
    - Парсит позиции (Поз.X-N), артикулы (7-8 цифр), размеры.
    """
    path = save_upload(file)

    try:
        import fitz
        import io
        from PIL import Image

        doc = fitz.open(str(path))
        total_pages = len(doc)
        DPI = 300

        pages_result = []
        all_positions = []
        all_articles = set()
        ocr_page_count = 0
        text_page_count = 0

        for i in range(total_pages):
            page = doc[i]
            native_text = page.get_text().strip()

            has_text = len(native_text) > 30  # meaningful text threshold

            if has_text:
                # Страница с текстовым слоем — используем как есть
                text_page_count += 1
                ocr_text = ""
                final_text = native_text
            else:
                # Image-only страница — OCR
                ocr_page_count += 1
                mat = fitz.Matrix(DPI / 72, DPI / 72)
                pix = page.get_pixmap(matrix=mat)
                img = Image.open(io.BytesIO(pix.tobytes("png")))

                # Два прохода: block (psm 6) + sparse (psm 11)
                text_block = ocr_pil_image(img, lang="rus+eng",
                                           preprocess=True, sparse=False)
                text_sparse = ocr_pil_image(img, lang="rus+eng",
                                            preprocess=True, sparse=True)

                # Объединяем: берём более полный, добавляем уникальные строки
                if len(text_sparse) > len(text_block):
                    text_block, text_sparse = text_sparse, text_block

                base_lines = set(text_block.strip().splitlines())
                extra = [ln for ln in text_sparse.strip().splitlines()
                         if ln.strip() and ln.strip() not in base_lines]

                ocr_text = text_block.strip()
                if extra:
                    ocr_text += "\n" + "\n".join(extra)

                final_text = ocr_text

            # Парсим результаты из текста (native или OCR)
            positions = parse_positions(final_text)
            articles = parse_articles(final_text)
            dimensions = parse_dimensions(final_text)

            all_positions.extend(positions)
            all_articles.update(articles)

            pages_result.append({
                "page": i + 1,
                "has_text": has_text,
                "ocr_text": ocr_text if not has_text else "",
                "text_preview": final_text[:200] if final_text else "",
                "positions": positions,
                "articles": articles,
                "dimensions": dimensions,
            })

        doc.close()

        # Сводка
        total_qty = sum(p.get("quantity", 0) for p in all_positions)
        summary = {
            "total_pages": total_pages,
            "text_pages": text_page_count,
            "ocr_pages": ocr_page_count,
            "total_positions": len(all_positions),
            "total_quantity": total_qty,
            "unique_articles": sorted(all_articles),
            "articles_count": len(all_articles),
        }

        await log_activity("parse_kmd", file.filename,
                     f"OCR: {ocr_page_count} стр., позиций: {len(all_positions)}, "
                     f"артикулов: {len(all_articles)}")

        return {
            "status": "ok",
            "filename": file.filename,
            "pages": pages_result,
            "summary": summary,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path.unlink(missing_ok=True)


# ============== 6. ЧЕК-ЛИСТ КМД ==============

def _run_checklist(full_text: str, page_texts: list[str]) -> list[dict]:
    """
    Чек-лист КМД для алюминиевых светопрозрачных конструкций (окна, витражи, фасады).
    Основан на ГОСТ 21.502-2016, СП 426.1325800.2018, ГОСТ 21519-2022
    и реальной практике АЛЬДМЕГА ЛАБ.

    Проверки сгруппированы по 7 категориям с весами:
    - Критические (вес 3): без них производство невозможно
    - Важные (вес 2): влияют на качество/сроки
    - Рекомендуемые (вес 1): улучшают полноту документации

    Возвращает список проверок [{category, check_name, passed, details, weight}, ...].
    """

    full_lower = full_text.lower()
    checks: list[dict] = []

    def add(category: str, name: str, passed: bool, details: str = "", weight: int = 2):
        checks.append({
            "category": category,
            "check_name": name,
            "passed": passed,
            "details": details,
            "weight": weight,
        })

    # ======================================================================
    # 1. ТИТУЛЬНЫЙ ЛИСТ И РЕКВИЗИТЫ (вес: критический)
    # ======================================================================
    cat = "Титульный лист и реквизиты"

    # Проверяем первые 3 страницы на наличие ключевых реквизитов
    first_pages = "\n".join(p.lower() for p in page_texts[:3])

    # Наименование объекта (адрес, название ЖК/объекта)
    has_object = bool(re.search(
        r'(объект|жилая застройка|жилой комплекс|жк\b|корпус|по адресу|'
        r'строительств|реконструкци|здание)',
        first_pages
    ))
    add(cat, "Наименование объекта строительства", has_object,
        "Объект строительства указан" if has_object
        else "Не найдено наименование объекта в первых страницах", 3)

    # Заказчик
    has_customer = bool(re.search(r'заказчик|заказ\s*чик', first_pages))
    add(cat, "Указан заказчик", has_customer,
        "Заказчик указан" if has_customer else "Информация о заказчике не найдена", 2)

    # Договор или номер КМД
    has_contract = bool(re.search(r'договор|контракт|кмд\s*от|№\s*\d', first_pages))
    add(cat, "Номер договора / документа", has_contract,
        "Реквизиты договора найдены" if has_contract
        else "Номер договора или документа не обнаружен", 2)

    # Исполнитель (ООО, ИП, ИНН, ОГРН)
    has_executor = bool(re.search(r'(ооо|ип\s|инн\s*\d|огрн\s*\d|генеральный директор)', first_pages))
    add(cat, "Указан исполнитель (организация)", has_executor,
        "Данные исполнителя найдены" if has_executor
        else "Исполнитель (организация) не указан", 2)

    # Тип конструкций в заголовке
    has_type = bool(re.search(
        r'(алюминиев|светопрозрачн|окн[аы]|витраж|фасад|двер[ьи]|балконн|'
        r'входн[аыеой]|раздвижн)',
        first_pages
    ))
    add(cat, "Указан тип конструкций (окна/витражи/фасады)", has_type,
        "Тип конструкций определён" if has_type
        else "Тип конструкций не указан в заглавии", 3)

    # Дата документа
    has_date = bool(re.search(
        r'(\d{2}\.\d{2}\.\d{4}|\d{4}\s*г\.?|от\s*\d{2}\.\d{2})', first_pages
    ))
    add(cat, "Дата документа", has_date,
        "Дата обнаружена" if has_date else "Дата документа не найдена", 1)

    # ======================================================================
    # 2. ПОЯСНИТЕЛЬНАЯ ЗАПИСКА
    # ======================================================================
    cat = "Пояснительная записка"

    has_note = bool(re.search(r'пояснительн\w*\s+запис', full_lower))
    add(cat, "Наличие пояснительной записки", has_note,
        "Пояснительная записка найдена" if has_note
        else "Пояснительная записка не обнаружена", 2)

    # Состав документации
    has_composition = bool(re.search(
        r'(в состав|состав\s+документации|входят|разделы)',
        full_lower
    ))
    add(cat, "Описан состав документации", has_composition,
        "Состав документации описан" if has_composition
        else "Состав документации не описан", 1)

    # Указания по монтажу
    has_mounting = bool(re.search(
        r'(монтаж|при\s+монтаже|установк|сборк[аеи]|указани[яе])',
        full_lower
    ))
    add(cat, "Указания по монтажу/сборке", has_mounting,
        "Указания по монтажу найдены" if has_mounting
        else "Указания по монтажу не обнаружены", 2)

    # Профильная система
    profile_systems = [
        'reynaers', 'masterline', 'conceptwall', 'hi-finity', 'alumil',
        'schuco', 'schüco', 'alutech', 'алютех', 'vidnal', 'виднал',
        'tatprof', 'татпроф', 'agrisovglass', 'realit', 'provedal',
        'newtek', 'ньютек', 'sial', 'сиал',
    ]
    found_system = None
    for ps in profile_systems:
        if ps in full_lower:
            found_system = ps
            break
    add(cat, "Указана профильная система", found_system is not None,
        f"Профильная система: {found_system}" if found_system
        else "Профильная система не идентифицирована", 3)

    # ======================================================================
    # 3. ЧЕРТЕЖИ ИЗДЕЛИЙ (КРИТИЧЕСКИЙ РАЗДЕЛ)
    # ======================================================================
    cat = "Чертежи изделий"

    # Позиции — универсальный парсер (Поз.О-1, Витраж В-1, БФ1 и т.п.)
    pos_list = extract_positions(full_text)
    unique_positions = list({p["position"] for p in pos_list})
    add(cat, "Маркировка позиций изделий", len(unique_positions) > 0,
        f"Найдено {len(unique_positions)} уникальных позиций: {', '.join(unique_positions[:10])}"
        if unique_positions
        else "Позиции изделий не обнаружены", 3)

    # Количество при позиции — универсальный парсер
    qty_total = 0
    qty_count = 0
    for p in pos_list:
        q = extract_quantity(full_text, near_pos=p["start"])
        if q > 0:
            qty_count += 1
            qty_total += q
    add(cat, "Указано количество изделий по позициям", qty_count > 0,
        f"Найдено {qty_count} записей с количеством (сумма: {qty_total})"
        if qty_count else "Количество изделий не указано", 3)

    # Высота ручки
    handle_records = re.findall(
        r'[Вв]ысота\s+ручки\s*:?\s*(\d+)', full_text
    )
    add(cat, "Указана высота ручки", len(handle_records) > 0,
        f"Высота ручки указана для {len(handle_records)} изделий"
        if handle_records else "Высота ручки не указана", 2)

    # Размеры (3-4 значные числа, мм — габариты деталей)
    dims_mm = re.findall(r'\b(\d{3,4}(?:[,\.]\d{1,2})?)\b', full_text)
    dims_valid = [float(d.replace(',', '.')) for d in dims_mm if 50 < float(d.replace(',', '.')) < 5000]
    add(cat, "Наличие размеров деталей (мм)", len(dims_valid) > 10,
        f"Найдено {len(dims_valid)} размерных значений"
        if dims_valid else "Размеры не обнаружены", 3)

    # Виды (изнутри / снаружи)
    has_views = bool(re.search(r'вид\s+(изнутри|снаружи|спереди|сзади|сбоку)', full_lower))
    add(cat, "Указан вид (изнутри/снаружи)", has_views,
        "Ориентация вида указана" if has_views
        else "Ориентация вида (изнутри/снаружи) не указана", 2)

    # Разрезы A-A, B-B и т.п. (линии сечений на чертежах)
    sections = re.findall(r'\b([A-ZА-Я])\s*[\-–]\s*\1\b', full_text)
    add(cat, "Наличие линий сечений (A-A, B-B)", len(sections) > 0,
        f"Найдено {len(set(sections))} типов сечений" if sections
        else "Линии сечений не обнаружены", 2)

    # ======================================================================
    # 4. АРТИКУЛЫ И КОМПЛЕКТУЮЩИЕ (КРИТИЧЕСКИЙ РАЗДЕЛ)
    # ======================================================================
    cat = "Артикулы и комплектующие"

    # Артикулы профилей (7-значные номера — Reynaers, Schuco и др.)
    articles_7 = set(re.findall(r'\b(\d{7})\b', full_text))
    articles_valid = {a for a in articles_7 if int(a) > 100000}
    add(cat, "Артикулы профилей", len(articles_valid) >= 3,
        f"Найдено {len(articles_valid)} уникальных артикулов"
        if articles_valid else "Артикулы профилей не обнаружены", 3)

    # Артикулы крепежа/фурнитуры (часто формат XXXX.XXX или 6-7 цифр)
    fastener_arts = set(re.findall(r'\b(\d{4,5}\.\d{3,5})\b', full_text))
    add(cat, "Артикулы крепежа/фурнитуры", len(fastener_arts) > 0,
        f"Найдено {len(fastener_arts)} артикулов крепежа"
        if fastener_arts else "Артикулы крепежа не обнаружены (допустимо, если входят в 7-значные)", 1)

    # Крепёж (саморезы, анкеры, болты, винты)
    fasteners = re.findall(
        r'(саморез|анкер|болт|винт|дюбел|шуруп)\w*\s*\d',
        full_lower
    )
    add(cat, "Указан крепёж (саморезы, анкеры)", len(fasteners) > 0,
        f"Найдено {len(fasteners)} записей о крепеже" if fasteners
        else "Крепёж не указан", 2)

    # Уплотнители / шнуры
    seals = re.findall(
        r'(шнур|уплотнител|epdm|силикон|резин)\w*',
        full_lower
    )
    add(cat, "Указаны уплотнители/шнуры", len(seals) > 0,
        f"Найдено {len(seals)} упоминаний уплотнителей" if seals
        else "Уплотнители не указаны", 2)

    # ======================================================================
    # 5. УЗЛЫ И ПРИМЫКАНИЯ
    # ======================================================================
    cat = "Узлы и примыкания"

    # Узлы (сборки, обработки, примыкания)
    has_nodes = bool(re.search(
        r'(узел|узл[ыа]|сборк[аи]|обработк[аи]|примыкани[еяй])',
        full_lower
    ))
    add(cat, "Наличие узлов сборки/обработки", has_nodes,
        "Узлы найдены" if has_nodes else "Узлы сборки не обнаружены", 2)

    # Герметизация (силикон, ПСУЛ, вилатерм, мембрана)
    sealant_kw = ['псул', 'вилатерм', 'силикон', 'герметик', 'мембран', 'пенополиуретан', 'монтажн']
    sealants_found = [kw for kw in sealant_kw if kw in full_lower]
    add(cat, "Указана герметизация (ПСУЛ, силикон, вилатерм)", len(sealants_found) > 0,
        f"Найдено: {', '.join(sealants_found)}" if sealants_found
        else "Материалы герметизации не указаны", 2)

    # Импосты (горизонтальные/вертикальные разделители)
    has_impost = bool(re.search(r'импост', full_lower))
    add(cat, "Указаны импосты", has_impost,
        "Импосты обнаружены в документации" if has_impost
        else "Импосты не упоминаются (допустимо для простых конструкций)", 1)

    # ======================================================================
    # 6. ПОЛНОТА И КОНСИСТЕНТНОСТЬ
    # ======================================================================
    cat = "Полнота и консистентность"

    # Достаточный объём документа
    total_pages = len(page_texts)
    add(cat, "Достаточный объём документации", total_pages >= 3,
        f"Всего страниц: {total_pages}"
        + (" (слишком мало для комплекта КМД)" if total_pages < 3 else ""), 2)

    # Пустые страницы (страницы без извлекаемого текста)
    empty_pages = sum(1 for pt in page_texts if len(pt.strip()) < 5)
    # В КМД чертежи часто почти без текста — это нормально
    many_empty = empty_pages > total_pages * 0.5
    add(cat, "Доля страниц с данными", not many_empty,
        f"{total_pages - empty_pages} из {total_pages} страниц содержат текст"
        + (f" ({empty_pages} пустых — возможно, графические чертежи)" if empty_pages else ""), 1)

    # Каждая позиция имеет количество
    if unique_positions and qty_records:
        coverage = min(len(qty_records) / len(unique_positions), 1.0)
        add(cat, "Количество указано для всех позиций",
            coverage >= 0.8,
            f"Позиций: {len(unique_positions)}, записей с количеством: {len(qty_records)} "
            f"(покрытие: {coverage:.0%})", 3)
    elif unique_positions:
        add(cat, "Количество указано для всех позиций", False,
            f"Найдено {len(unique_positions)} позиций, но количество не указано", 3)

    # Все артикулы — валидные (7 цифр, > 100000)
    all_7digit = set(re.findall(r'\b(\d{7})\b', full_text))
    invalid_arts = {a for a in all_7digit if int(a) <= 100000}
    add(cat, "Все артикулы корректны (7 цифр)", len(invalid_arts) == 0,
        f"Некорректных артикулов: {len(invalid_arts)}" if invalid_arts
        else f"Все {len(articles_valid)} артикулов валидны", 1)

    # Единообразие формата позиций
    pos_formats = set()
    for p in unique_positions:
        if re.match(r'[А-ЯA-Z]{1,3}\-?\d+', p):
            pos_formats.add("БУКВЫ-ЦИФРЫ")
        elif re.match(r'\d+', p):
            pos_formats.add("ЦИФРЫ")
        else:
            pos_formats.add("ДРУГОЕ")
    add(cat, "Единообразный формат позиций", len(pos_formats) <= 2,
        f"Форматы: {', '.join(pos_formats)}" if pos_formats
        else "Позиции не найдены", 1)

    # ======================================================================
    # 7. ОФОРМЛЕНИЕ ДОКУМЕНТАЦИИ
    # ======================================================================
    cat = "Оформление документации"

    # Наличие слова КМД
    has_kmd = 'кмд' in full_lower
    add(cat, "Документ идентифицирован как КМД", has_kmd,
        "Маркировка КМД найдена" if has_kmd else "Слово «КМД» не найдено в тексте", 2)

    # Конструкторская/рабочая документация
    has_doc_type = bool(re.search(
        r'(конструкторск\w+\s+документаци|рабоч\w+\s+документаци|чертеж\w+\s+кмд)',
        full_lower
    ))
    add(cat, "Указан тип документации", has_doc_type,
        "Тип документации определён" if has_doc_type
        else "Тип документации не указан в заголовке", 1)

    # Подписи (генеральный директор, проверил, разработал)
    has_signatures = bool(re.search(
        r'(генеральный директор|директор|проверил|разработал|утвердил|гл\.\s*инженер|'
        r'нач\w*\s+отдел|[А-Я]\.\s*[А-Я]\.)',
        full_lower
    ))
    add(cat, "Наличие подписей / ответственных лиц", has_signatures,
        "Подписи/ФИО обнаружены" if has_signatures else "Подписи не обнаружены", 1)

    return checks


@limiter.limit("10/minute")
@app.post("/api/checklist", tags=["Documentation"], summary="Run KMD checklist audit")
async def api_checklist(request: Request, file: UploadFile = File(...)):
    """
    Автоматический чек-лист КМД по 8 разделам АЛЬДМЕГА ЛАБ.
    Принимает PDF-файл, извлекает текст со всех страниц (PyMuPDF),
    прогоняет проверки и возвращает результат с оценкой.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Принимаются только PDF файлы")

    path = save_upload(file)

    try:
        import fitz

        doc = fitz.open(str(path))
        page_texts = [doc[i].get_text() for i in range(len(doc))]
        full_text = "\n".join(page_texts)
        total_pages = len(doc)
        doc.close()

        if not full_text.strip():
            raise HTTPException(
                status_code=400,
                detail="PDF не содержит извлекаемого текста (возможно, это скан-копия без OCR)",
            )

        checks = _run_checklist(full_text, page_texts)
        passed_checks = sum(1 for c in checks if c["passed"])
        total_checks = len(checks)
        # Взвешенная оценка: критические проверки (вес 3) влияют сильнее
        total_weight = sum(c.get("weight", 2) for c in checks)
        passed_weight = sum(c.get("weight", 2) for c in checks if c["passed"])
        overall_score = round(passed_weight / total_weight * 100, 1) if total_weight else 0.0

        await log_activity("checklist", file.filename,
                     f"Оценка: {overall_score}%, пройдено: {passed_checks}/{total_checks}")

        return {
            "status": "ok",
            "filename": file.filename,
            "total_pages": total_pages,
            "checks": checks,
            "overall_score": overall_score,
            "total_checks": total_checks,
            "passed_checks": passed_checks,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path.unlink(missing_ok=True)


# ============== 7. КРОСС-ВАЛИДАЦИЯ ЧЕРТЁЖ vs СПЕЦИФИКАЦИЯ ==============

@limiter.limit("10/minute")
@app.post("/api/cross-validate", tags=["Documentation"], summary="Cross-validate drawing vs spec")
async def api_cross_validate(
    request: Request,
    drawing: UploadFile = File(...),
    spec: UploadFile = File(...),
):
    """Кросс-валидация: сопоставить артикулы/количества из чертежа (PDF/DXF)
    с заказной спецификацией (XLSX)."""
    drawing_path = save_upload(drawing)
    spec_path = save_upload(spec)

    try:
        import pandas as pd

        def safe_float(val, default=0.0):
            try:
                v = float(val)
                return default if (math.isnan(v) or math.isinf(v)) else v
            except (ValueError, TypeError):
                return default

        # ---- 1. Извлечь данные из чертежа ----
        drawing_name = drawing.filename.lower()
        drawing_articles: dict[str, float] = {}  # article -> total qty
        drawing_positions: list[dict] = []
        unlinked_positions: list[str] = []

        if drawing_name.endswith(".dxf"):
            # DXF
            dxf_result = parse_dxf_for_web(str(drawing_path))
            # Собираем артикулы из текстов DXF
            all_texts = " ".join(t.get("text", "") for t in dxf_result.get("texts", []))
            for m in re.finditer(r'\b(\d{7,8})\b', all_texts):
                art = m.group(1)
                if int(art) > 100000:
                    drawing_articles[art] = drawing_articles.get(art, 0) + 1

            # Позиции из kmd_data
            for item in dxf_result.get("kmd_data", {}).get("items", []):
                pos = item.get("position", "")
                qty = item.get("quantity", 0)
                arts = item.get("articles", [])
                drawing_positions.append({"position": pos, "quantity": qty, "articles": arts})
                if not arts:
                    unlinked_positions.append(pos)
                for a in arts:
                    drawing_articles[a] = drawing_articles.get(a, 0) + qty

        elif drawing_name.endswith(".pdf"):
            # PDF — тот же алгоритм, что и /api/parse-kmd
            import fitz
            doc = fitz.open(str(drawing_path))

            for i in range(len(doc)):
                text = doc[i].get_text().strip()
                if not text:
                    continue

                pos_matches = re.finditer(
                    r'Поз\.?\s*([А-Яа-яA-Za-z0-9\-\.]+)\s*,?\s*Количество\s*:?\s*(\d+)',
                    text,
                )
                for m in pos_matches:
                    pos_name = m.group(1)
                    qty = int(m.group(2))

                    page_articles: list[str] = []
                    for am in re.finditer(r'\b(\d{7,8})\b', text):
                        art = am.group(1)
                        if int(art) > 100000:
                            page_articles.append(art)

                    drawing_positions.append({
                        "position": pos_name,
                        "quantity": qty,
                        "articles": sorted(set(page_articles)),
                    })

                    if not page_articles:
                        unlinked_positions.append(pos_name)

                    for a in set(page_articles):
                        drawing_articles[a] = drawing_articles.get(a, 0) + qty

                # Также собираем артикулы без привязки к позициям (свободные)
                for am in re.finditer(r'\b(\d{7,8})\b', text):
                    art = am.group(1)
                    if int(art) > 100000 and art not in drawing_articles:
                        drawing_articles[art] = drawing_articles.get(art, 0)

            doc.close()
        else:
            raise HTTPException(
                status_code=400,
                detail="Чертёж должен быть в формате PDF или DXF",
            )

        # ---- 2. Извлечь данные из спецификации XLSX ----
        df_spec = extract_articles(str(spec_path))

        spec_articles: dict[str, float] = {}
        if not df_spec.empty:
            for _, row in df_spec.iterrows():
                art = str(row.get("Артикул_норм", "")).strip().rstrip(".")
                qty = safe_float(row.get("Количество", 0))
                if art and art != "nan":
                    spec_articles[art] = spec_articles.get(art, 0) + qty

        # Нормализация ключей чертежа (rstrip('.'))
        drawing_articles_norm: dict[str, float] = {}
        for art, qty in drawing_articles.items():
            drawing_articles_norm[art.rstrip(".")] = (
                drawing_articles_norm.get(art.rstrip("."), 0) + qty
            )

        # ---- 3. Кросс-валидация ----
        all_drawing = set(drawing_articles_norm.keys())
        all_spec = set(spec_articles.keys())

        matches = []
        qty_mismatches = []
        missing_in_spec = []
        extra_in_spec = []

        # Совпадения и расхождения по количеству
        for art in sorted(all_drawing & all_spec):
            d_qty = safe_float(drawing_articles_norm[art])
            s_qty = safe_float(spec_articles[art])
            if abs(d_qty - s_qty) < 0.01:
                matches.append({
                    "article": art,
                    "drawing_qty": d_qty,
                    "spec_qty": s_qty,
                })
            else:
                qty_mismatches.append({
                    "article": art,
                    "drawing_qty": d_qty,
                    "spec_qty": s_qty,
                    "diff": round(d_qty - s_qty, 2),
                })

        # Есть в чертеже, нет в спецификации
        for art in sorted(all_drawing - all_spec):
            d_qty = safe_float(drawing_articles_norm[art])
            missing_in_spec.append({"article": art, "drawing_qty": d_qty})

        # Есть в спецификации, нет в чертеже
        for art in sorted(all_spec - all_drawing):
            s_qty = safe_float(spec_articles[art])
            extra_in_spec.append({"article": art, "spec_qty": s_qty})

        # ---- 4. Сводка ----
        total_d = len(all_drawing)
        total_s = len(all_spec)
        matched_count = len(matches)
        match_rate = round(matched_count / total_d * 100, 1) if total_d else 0.0

        summary = {
            "total_drawing_articles": total_d,
            "total_spec_articles": total_s,
            "matched": matched_count,
            "missing_in_spec": len(missing_in_spec),
            "extra_in_spec": len(extra_in_spec),
            "qty_mismatches": len(qty_mismatches),
            "match_rate": match_rate,
        }

        await log_activity(
            "cross_validate",
            f"{drawing.filename} / {spec.filename}",
            f"Совпадений: {matched_count}, расхождений: {len(qty_mismatches)}, "
            f"нет в спец.: {len(missing_in_spec)}, лишних: {len(extra_in_spec)}",
        )

        return {
            "status": "ok",
            "drawing_file": drawing.filename,
            "spec_file": spec.filename,
            "drawing_articles": sorted(all_drawing),
            "spec_articles": sorted(all_spec),
            "matches": matches,
            "missing_in_spec": missing_in_spec,
            "extra_in_spec": extra_in_spec,
            "qty_mismatches": qty_mismatches,
            "unlinked_positions": sorted(set(unlinked_positions)),
            "summary": summary,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        drawing_path.unlink(missing_ok=True)
        spec_path.unlink(missing_ok=True)


# ============== 7.5. RAG-ВАЛИДАЦИЯ ДОКУМЕНТА ==============

@app.post("/api/rag-validate", tags=["Documentation"], summary="RAG-powered KMD validation")
async def api_rag_validate(file: UploadFile = File(...)):
    """Полная RAG-валидация КМД документа: артикулы, ГОСТ, форматирование, эталонные КМД."""
    path = save_upload(file)
    try:
        text = extract_text_from_pdf(str(path))
        articles = kmd_extract_articles(text)
        pos_list = extract_positions(text)
        positions = [{"position": p["position"],
                       "quantity": extract_quantity(text, near_pos=p["start"])}
                      for p in pos_list]

        report = await validate_kmd_document(
            extracted_text=text,
            positions=positions,
            articles=articles,
        )

        await log_activity("rag_validate", file.filename, f"RAG validation: {len(articles)} articles")

        return {
            "status": "ok",
            "filename": file.filename,
            "positions_found": len(positions),
            "articles_found": len(articles),
            "profile_system": extract_profile_system(text),
            "validation": report,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path.unlink(missing_ok=True)


@app.post("/api/validate-articles", tags=["Documentation"], summary="Validate article codes")
async def api_validate_articles(payload: dict):
    """Проверить артикулы по базе данных производителей (RAG)."""
    articles = payload.get("articles", [])
    if not articles:
        raise HTTPException(status_code=400, detail="Список артикулов пуст")

    # Check cache
    cache_key = _make_key("rag_articles", *sorted(articles[:50]))
    cached = await cache_get(cache_key)
    if cached:
        return json.loads(cached)

    results = await validate_articles_batch(articles[:50])
    valid_count = sum(1 for r in results if r.get("valid"))

    response = {
        "status": "ok",
        "total": len(results),
        "valid": valid_count,
        "invalid": len(results) - valid_count,
        "results": results,
    }

    # Cache the result
    await cache_set(cache_key, json.dumps(response, default=str))

    return response


# ============== 7b. RULE ENGINE VALIDATION ==============

@app.post("/api/rules-validate", tags=["Documentation"],
          summary="Expert rule engine KMD validation (deterministic)")
async def api_rules_validate(file: UploadFile = File(...)):
    """Детерминистическая проверка КМД экспертной системой правил.

    Кодифицирует знания инженера с 30-летним стажем:
    - Совместимость артикулов по профильным системам
    - Допуски размеров конструкций
    - Формулы стеклопакетов
    - Параметры фурнитуры
    - Комплектность документации
    - Перекрёстная валидация данных
    """
    if not _RULES_ENGINE_AVAILABLE:
        raise HTTPException(503, "Rules engine unavailable")
    suffix = Path(file.filename or "doc.pdf").suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        parsed = parse_kmd_pdf(tmp_path)
        result = validate_kmd_full(parsed)
        result["report_text"] = format_report_ru(result)
        result["parsed_summary"] = {
            "total_positions": parsed.get("total_positions", 0),
            "total_items": parsed.get("total_items", 0),
            "profile_system": parsed.get("profile_system", ""),
            "articles_count": parsed.get("articles_count", 0),
        }
        return result
    finally:
        os.unlink(tmp_path)


@app.post("/api/multi-validate", tags=["Documentation"],
          summary="Multi-agent AI validation (5 specialist agents + consensus)")
async def api_multi_validate(file: UploadFile = File(...)):
    """Проверка КМД 5 независимыми AI-агентами с механизмом консенсуса.

    Агенты: Геометрический, Материаловедческий, Нормативный,
    Конструктивный, Оформительский.

    Результат принимается только при согласии ≥3 из 5 агентов.
    """
    if not _MULTI_VALIDATOR_AVAILABLE:
        raise HTTPException(503, "Multi-validator unavailable")
    suffix = Path(file.filename or "doc.pdf").suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        parsed = parse_kmd_pdf(tmp_path)
        text = ""
        try:
            from pdf_tools import extract_text_from_pdf
            text = extract_text_from_pdf(tmp_path)
        except Exception:
            pass
        result = await validate_with_agents(parsed, raw_text=text[:10000])
        return result
    finally:
        os.unlink(tmp_path)


@app.post("/api/full-validate", tags=["Documentation"],
          summary="Full 3-level KMD validation (parser + rules + AI agents + RAG)")
async def api_full_validate(file: UploadFile = File(...)):
    """Полная 3-уровневая проверка КМД:

    Уровень 1: Парсер — извлечение данных
    Уровень 2: Экспертные правила — детерминистические проверки
    Уровень 3: AI агенты — семантический анализ + RAG контекст

    Возвращает объединённый результат всех уровней.
    """
    suffix = Path(file.filename or "doc.pdf").suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        # Уровень 1: Парсер
        parsed = parse_kmd_pdf(tmp_path)

        # Извлечь текст для AI агентов
        raw_text = ""
        try:
            from pdf_tools import extract_text_from_pdf
            raw_text = extract_text_from_pdf(tmp_path)
        except Exception:
            pass

        # Уровень 2: Экспертные правила
        if _RULES_ENGINE_AVAILABLE:
            rules_result = validate_kmd_full(parsed)
        else:
            rules_result = {"status": "unavailable", "score": 0, "errors": []}

        # Уровень 3: AI агенты (параллельно с RAG)
        import asyncio
        agents_task = None
        if _MULTI_VALIDATOR_AVAILABLE:
            agents_task = asyncio.create_task(
                validate_with_agents(parsed, raw_text=raw_text[:10000])
            )

        # RAG валидация артикулов
        rag_articles = []
        if parsed.get("unique_articles"):
            try:
                rag_articles = await validate_articles_batch(parsed["unique_articles"][:20])
            except Exception:
                pass

        if agents_task:
            agents_result = await agents_task
        else:
            agents_result = {"status": "unavailable", "confidence": 0}

        # Объединяем результаты
        combined_score = (
            rules_result.get("score", 0) * 0.4 +
            agents_result.get("confidence", 0) * 0.4 +
            (100 if not any(a.get("valid") is False for a in rag_articles) else 60) * 0.2
        )

        combined_status = "ok"
        if rules_result.get("status") == "critical" or agents_result.get("status") == "critical":
            combined_status = "critical"
        elif rules_result.get("status") == "warning" or agents_result.get("status") == "warning":
            combined_status = "warning"

        return {
            "status": combined_status,
            "combined_score": round(combined_score, 1),
            "level_1_parser": {
                "total_positions": parsed.get("total_positions", 0),
                "total_items": parsed.get("total_items", 0),
                "profile_system": parsed.get("profile_system", ""),
                "articles_count": parsed.get("articles_count", 0),
                "colors": parsed.get("colors", []),
            },
            "level_2_rules": {
                "status": rules_result.get("status"),
                "score": rules_result.get("score"),
                "errors_count": len(rules_result.get("errors", [])),
                "critical": rules_result.get("errors_by_severity", {}).get("critical", 0),
                "warnings": rules_result.get("errors_by_severity", {}).get("warning", 0),
                "errors": rules_result.get("errors", [])[:20],
                "report": format_report_ru(rules_result) if _RULES_ENGINE_AVAILABLE else "",
            },
            "level_3_agents": {
                "status": agents_result.get("status"),
                "confidence": agents_result.get("confidence"),
                "confirmed_errors": agents_result.get("confirmed_errors", []),
                "probable_errors": agents_result.get("probable_errors", []),
                "summary": agents_result.get("summary_ru", ""),
            },
            "rag_validation": {
                "articles_checked": len(rag_articles),
                "articles_valid": sum(1 for a in rag_articles if a.get("valid")),
                "results": rag_articles[:10],
            },
        }
    finally:
        os.unlink(tmp_path)


# ============== 8. СРАВНЕНИЕ ВЕРСИЙ PDF ==============

def _classify_page(text: str) -> str:
    """Определить тип страницы КМД по содержимому текста."""
    if not text or not text.strip():
        return "пустая"
    return classify_page(text)


def _extract_kmd_data(text: str):
    """Извлечь КМД-данные: позиции, артикулы, количество."""
    pos_list = extract_positions(text)
    positions = {}
    for p in pos_list:
        qty = extract_quantity(text, near_pos=p["start"])
        positions[p["position"]] = qty

    articles = set(kmd_extract_articles(text))

    return positions, articles


@limiter.limit("10/minute")
@app.post("/api/compare-pdf", tags=["Documentation"], summary="Compare two PDF versions")
async def api_compare_pdf(
    request: Request,
    file_a: UploadFile = File(...),
    file_b: UploadFile = File(...),
):
    """Сравнить две версии PDF КМД-документа и показать все различия."""
    if not file_a.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Файл А должен быть PDF")
    if not file_b.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Файл Б должен быть PDF")

    path_a = save_upload(file_a)
    path_b = save_upload(file_b)

    try:
        import fitz
        import difflib

        # --- Извлечение текста из обоих PDF ---
        doc_a = fitz.open(str(path_a))
        doc_b = fitz.open(str(path_b))
        pages_a = len(doc_a)
        pages_b = len(doc_b)

        texts_a = []
        types_a = []
        for i in range(pages_a):
            t = doc_a[i].get_text().strip()
            texts_a.append(t)
            types_a.append(_classify_page(t))

        texts_b = []
        types_b = []
        for i in range(pages_b):
            t = doc_b[i].get_text().strip()
            texts_b.append(t)
            types_b.append(_classify_page(t))

        doc_a.close()
        doc_b.close()

        # --- Сопоставление страниц по содержимому (similarity matching) ---
        SIMILARITY_THRESHOLD = 0.3

        # Вычисляем similarity matrix
        sim_pairs = []
        for ai in range(pages_a):
            if not texts_a[ai]:
                continue
            for bi in range(pages_b):
                if not texts_b[bi]:
                    continue
                ratio = difflib.SequenceMatcher(
                    None, texts_a[ai], texts_b[bi]
                ).ratio()
                if ratio >= SIMILARITY_THRESHOLD:
                    sim_pairs.append((ratio, ai, bi))

        # Greedy matching: лучшие пары первыми
        matched_a_to_b = {}  # a_idx -> (b_idx, ratio)
        matched_b = set()
        sim_pairs.sort(reverse=True)
        for ratio, ai, bi in sim_pairs:
            if ai in matched_a_to_b or bi in matched_b:
                continue
            matched_a_to_b[ai] = (bi, ratio)
            matched_b.add(bi)

        # --- Deleted pages (в A, но нет match в B) ---
        deleted_pages = []
        for ai in range(pages_a):
            if ai not in matched_a_to_b:
                deleted_pages.append({
                    "page": ai + 1,
                    "type": types_a[ai],
                    "preview": texts_a[ai][:100] if texts_a[ai] else "",
                })

        # --- Added pages (в B, но нет match из A) ---
        added_pages = []
        for bi in range(pages_b):
            if bi not in matched_b:
                added_pages.append({
                    "page": bi + 1,
                    "type": types_b[bi],
                    "preview": texts_b[bi][:100] if texts_b[bi] else "",
                })

        # --- Modified pages (matched, но similarity < 1.0) ---
        modified_pages = []
        unchanged_count = 0
        for ai, (bi, ratio) in matched_a_to_b.items():
            if ratio >= 0.9999:
                unchanged_count += 1
                continue

            # Вычисляем unified diff
            lines_a = texts_a[ai].splitlines()
            lines_b = texts_b[bi].splitlines()
            diff_lines = list(difflib.unified_diff(
                lines_a, lines_b, lineterm='',
                fromfile=f'стр.{ai+1}', tofile=f'стр.{bi+1}',
            ))

            added_text = [ln[1:] for ln in diff_lines if ln.startswith('+') and not ln.startswith('+++')]
            removed_text = [ln[1:] for ln in diff_lines if ln.startswith('-') and not ln.startswith('---')]

            changes = []
            for ln in diff_lines:
                if ln.startswith('@@') or ln.startswith('+++') or ln.startswith('---'):
                    continue
                if ln.startswith('+') or ln.startswith('-'):
                    changes.append(ln)

            modified_pages.append({
                "page_a": ai + 1,
                "page_b": bi + 1,
                "similarity": round(ratio, 4),
                "changes": changes[:20],
                "added_text": added_text[:10],
                "removed_text": removed_text[:10],
            })

        # --- KMD-specific changes ---
        full_text_a = "\n".join(texts_a)
        full_text_b = "\n".join(texts_b)

        positions_a, articles_a = _extract_kmd_data(full_text_a)
        positions_b, articles_b = _extract_kmd_data(full_text_b)

        removed_positions = sorted(set(positions_a.keys()) - set(positions_b.keys()))
        added_positions = sorted(set(positions_b.keys()) - set(positions_a.keys()))

        removed_articles = sorted(articles_a - articles_b)
        added_articles = sorted(articles_b - articles_a)

        quantity_changes = []
        for pos in sorted(set(positions_a.keys()) & set(positions_b.keys())):
            if positions_a[pos] != positions_b[pos]:
                quantity_changes.append({
                    "position": pos,
                    "old": positions_a[pos],
                    "new": positions_b[pos],
                })

        kmd_changes = {
            "removed_positions": removed_positions,
            "added_positions": added_positions,
            "removed_articles": removed_articles,
            "added_articles": added_articles,
            "quantity_changes": quantity_changes,
        }

        # --- Overall similarity ---
        if pages_a > 0 and pages_b > 0:
            all_ratios = [ratio for _, (_, ratio) in matched_a_to_b.items()]
            overall_sim = round(sum(all_ratios) / max(pages_a, pages_b), 4) if all_ratios else 0.0
        else:
            overall_sim = 0.0

        summary = {
            "deleted_pages": len(deleted_pages),
            "added_pages": len(added_pages),
            "modified_pages": len(modified_pages),
            "unchanged_pages": unchanged_count,
            "overall_similarity": overall_sim,
        }

        await log_activity(
            "compare_pdf",
            f"{file_a.filename} / {file_b.filename}",
            f"Удалено: {len(deleted_pages)}, добавлено: {len(added_pages)}, "
            f"изменено: {len(modified_pages)}, схожесть: {overall_sim:.0%}",
        )

        return {
            "status": "ok",
            "file_a": file_a.filename,
            "file_b": file_b.filename,
            "pages_a": pages_a,
            "pages_b": pages_b,
            "deleted_pages": deleted_pages,
            "added_pages": added_pages,
            "modified_pages": modified_pages,
            "kmd_changes": kmd_changes,
            "summary": summary,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path_a.unlink(missing_ok=True)
        path_b.unlink(missing_ok=True)


# ============== 9. ПАКЕТНАЯ ОБРАБОТКА ==============

MAX_ZIP_SIZE = 100 * 1024 * 1024  # 100 MB


@limiter.limit("10/minute")
@app.post("/api/batch-process", tags=["Documentation"], summary="Batch-process ZIP archive")
async def api_batch_process(request: Request, file: UploadFile = File(...)):
    """
    Пакетная обработка ZIP-архива с проектом КМД.
    Принимает ZIP с PDF, DXF, XLSX файлами, прогоняет все доступные проверки
    и возвращает единый отчёт.
    """
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Принимаются только ZIP-архивы")

    zip_path = save_upload(file)
    zip_size = zip_path.stat().st_size

    if zip_size > MAX_ZIP_SIZE:
        zip_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"Размер архива ({zip_size // 1024 // 1024} МБ) превышает лимит 100 МБ",
        )

    tmp_dir = tempfile.mkdtemp(prefix="kmd_batch_")

    try:
        import fitz

        # Распаковываем
        with zipfile.ZipFile(str(zip_path), "r") as zf:
            total_uncompressed = sum(i.file_size for i in zf.infolist())
            if total_uncompressed > MAX_ZIP_SIZE * 3:
                raise HTTPException(
                    status_code=400,
                    detail="Распакованный размер слишком велик",
                )
            # Zip-slip protection: validate all paths before extraction
            for member in zf.infolist():
                member_path = Path(tmp_dir) / member.filename
                if not member_path.resolve().is_relative_to(Path(tmp_dir).resolve()):
                    raise HTTPException(status_code=400, detail="ZIP содержит небезопасные пути")
            zf.extractall(tmp_dir)

        # Классификация файлов
        files_found = {"pdf": [], "dxf": [], "xlsx": [], "other": []}
        tmp_path = Path(tmp_dir)

        for fp in sorted(tmp_path.rglob("*")):
            if fp.is_dir():
                continue
            if fp.name.startswith(".") or fp.name.startswith("__"):
                continue
            ext = fp.suffix.lower()
            name = fp.name
            if ext == ".pdf":
                files_found["pdf"].append(name)
            elif ext == ".dxf":
                files_found["dxf"].append(name)
            elif ext in (".xlsx", ".xls"):
                files_found["xlsx"].append(name)
            else:
                files_found["other"].append(name)

        # --- PDF обработка ---
        pdf_results = []
        all_issues = []
        total_pdf_pages = 0
        all_unique_articles = set()
        all_positions_count = 0

        for pdf_name in files_found["pdf"]:
            pdf_files = list(tmp_path.rglob(pdf_name))
            if not pdf_files:
                continue
            pdf_path = pdf_files[0]

            try:
                doc = fitz.open(str(pdf_path))
                page_texts = [doc[i].get_text() for i in range(len(doc))]
                full_text = "\n".join(page_texts)
                pages = len(doc)
                doc.close()
                total_pdf_pages += pages

                if full_text.strip():
                    checks = _run_checklist(full_text, page_texts)
                    passed = sum(1 for c in checks if c["passed"])
                    total = len(checks)
                    tw = sum(c.get("weight", 2) for c in checks)
                    pw = sum(c.get("weight", 2) for c in checks if c["passed"])
                    score = round(pw / tw * 100, 1) if tw else 0.0
                else:
                    checks = []
                    passed = 0
                    total = 0
                    score = 0.0

                positions_found = set()
                articles_found = set()

                for pt in page_texts:
                    for m in re.finditer(
                        r'Поз\.?\s*([А-Яа-яA-Za-z0-9\-\.]+)', pt,
                    ):
                        positions_found.add(m.group(1))
                    for m in re.finditer(r'\b(\d{7,8})\b', pt):
                        art = m.group(1)
                        if int(art) > 100000:
                            articles_found.add(art)

                all_unique_articles.update(articles_found)
                all_positions_count += len(positions_found)

                issues = [c["check_name"] for c in checks if not c["passed"]]
                critical_keywords = [
                    "титульн", "спецификаци", "пояснительн", "позиций",
                ]
                for issue in issues:
                    issue_lower = issue.lower()
                    if any(kw in issue_lower for kw in critical_keywords):
                        all_issues.append({"file": pdf_name, "issue": issue, "severity": "critical"})
                    else:
                        all_issues.append({"file": pdf_name, "issue": issue, "severity": "warning"})

                pdf_results.append({
                    "filename": pdf_name,
                    "total_pages": pages,
                    "checklist_score": score,
                    "passed_checks": passed,
                    "total_checks": total,
                    "positions_found": len(positions_found),
                    "articles_found": len(articles_found),
                    "issues": issues,
                })

            except Exception as e:
                pdf_results.append({
                    "filename": pdf_name,
                    "total_pages": 0,
                    "checklist_score": 0,
                    "passed_checks": 0,
                    "total_checks": 0,
                    "positions_found": 0,
                    "articles_found": 0,
                    "issues": [f"Ошибка обработки: {str(e)}"],
                })
                all_issues.append({"file": pdf_name, "issue": f"Ошибка обработки: {str(e)}", "severity": "critical"})

        # --- DXF обработка ---
        dxf_results = []
        for dxf_name in files_found["dxf"]:
            dxf_files = list(tmp_path.rglob(dxf_name))
            if not dxf_files:
                continue
            dxf_path = dxf_files[0]

            try:
                result = parse_dxf_for_web(str(dxf_path))

                dxf_positions = set()
                dxf_articles = set()
                for txt_entry in result.get("texts", []):
                    txt = txt_entry.get("text", "") if isinstance(txt_entry, dict) else str(txt_entry)
                    for m in re.finditer(r'[А-ЯA-Z]\s*[\-\.]\s*\d+', txt):
                        dxf_positions.add(m.group(0).strip())
                    for m in re.finditer(r'\b(\d{7,8})\b', txt):
                        art = m.group(1)
                        if int(art) > 100000:
                            dxf_articles.add(art)
                            all_unique_articles.add(art)

                all_positions_count += len(dxf_positions)

                dxf_results.append({
                    "filename": dxf_name,
                    "layers": len(result.get("layers", [])),
                    "texts": len(result.get("texts", [])),
                    "dimensions": len(result.get("dimensions", [])),
                    "positions": sorted(dxf_positions),
                    "articles": sorted(dxf_articles),
                })

            except Exception as e:
                dxf_results.append({
                    "filename": dxf_name,
                    "layers": 0,
                    "texts": 0,
                    "dimensions": 0,
                    "positions": [],
                    "articles": [],
                    "error": str(e),
                })
                all_issues.append({"file": dxf_name, "issue": f"Ошибка DXF: {str(e)}", "severity": "warning"})

        # --- XLSX обработка ---
        xlsx_results = []
        for xlsx_name in files_found["xlsx"]:
            xlsx_files = list(tmp_path.rglob(xlsx_name))
            if not xlsx_files:
                continue
            xlsx_path = xlsx_files[0]

            try:
                df = extract_articles(str(xlsx_path))
                xlsx_articles = set()
                if not df.empty and "Артикул_норм" in df.columns:
                    xlsx_articles = set(df["Артикул_норм"].dropna().astype(str).tolist())
                    all_unique_articles.update(xlsx_articles)

                xlsx_results.append({
                    "filename": xlsx_name,
                    "total_positions": len(df),
                    "articles_count": len(xlsx_articles),
                })

            except Exception as e:
                xlsx_results.append({
                    "filename": xlsx_name,
                    "total_positions": 0,
                    "articles_count": 0,
                    "error": str(e),
                })
                all_issues.append({"file": xlsx_name, "issue": f"Ошибка XLSX: {str(e)}", "severity": "warning"})

        # --- Итоговая сводка ---
        total_files = sum(len(v) for v in files_found.values())
        scores = [r["checklist_score"] for r in pdf_results if r["checklist_score"] > 0]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
        critical_count = sum(1 for i in all_issues if i["severity"] == "critical")
        warning_count = sum(1 for i in all_issues if i["severity"] == "warning")

        await log_activity(
            "batch",
            file.filename,
            f"Файлов: {total_files}, PDF: {len(files_found['pdf'])}, "
            f"DXF: {len(files_found['dxf'])}, оценка: {avg_score}%",
        )

        return {
            "status": "ok",
            "archive_name": file.filename,
            "files_found": files_found,
            "pdf_results": pdf_results,
            "dxf_results": dxf_results,
            "xlsx_results": xlsx_results,
            "issues": all_issues,
            "overall_summary": {
                "total_files": total_files,
                "total_pdf_pages": total_pdf_pages,
                "avg_checklist_score": avg_score,
                "total_positions": all_positions_count,
                "total_unique_articles": len(all_unique_articles),
                "critical_issues": critical_count,
                "warnings": warning_count,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        zip_path.unlink(missing_ok=True)
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ============== 11. ГЕНЕРАЦИЯ СПЕЦИФИКАЦИИ ==============

def _extract_kmd_data_from_pdf(pdf_path: str) -> list[dict]:
    """Извлечь КМД-данные из PDF: позиции, артикулы, размеры, цвета."""
    result = parse_kmd_pdf(pdf_path)
    positions = []
    for pos in result["positions"]:
        positions.append({
            "position": pos["position"],
            "articles": pos.get("articles", []),
            "descriptions": {},
            "quantity": pos.get("quantity", 0),
            "dimensions": pos.get("dimensions_mm", []),
            "dim_wxh": [d["raw"] for d in pos.get("dimensions", [])],
            "color": pos.get("color", ""),
            "page": pos.get("page", 0),
            "handle_height": pos.get("handle_height"),
            "glass": pos.get("glass", []),
        })
    return positions


def _generate_spec_xlsx(positions: list[dict], source_file: str) -> Path:
    """Сгенерировать XLSX спецификацию из извлечённых позиций."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = Workbook()

    # --- Лист 1: Спецификация ---
    ws = wb.active
    ws.title = "Спецификация"

    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="212529", end_color="212529", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin", color="DEE2E6"),
        right=Side(style="thin", color="DEE2E6"),
        top=Side(style="thin", color="DEE2E6"),
        bottom=Side(style="thin", color="DEE2E6"),
    )
    alt_fill = PatternFill(start_color="F8F9FA", end_color="F8F9FA", fill_type="solid")

    headers = ["No", "Позиция", "Артикул", "Описание", "Количество",
               "Ед.изм.", "Цвет", "Размеры", "Примечание"]
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    row_num = 2
    global_idx = 0
    for pos in positions:
        articles = pos.get("articles", [])
        descriptions = pos.get("descriptions", {})
        dims_str = ", ".join(pos.get("dim_wxh", []))
        if not dims_str and pos.get("dimensions"):
            dims_str = " x ".join(str(d) for d in pos["dimensions"][:4])

        if not articles:
            global_idx += 1
            row_data = [
                global_idx, pos["position"], "", "",
                pos.get("quantity", 0) or "", "шт.",
                pos.get("color", ""), dims_str,
                f"стр. {pos.get('page', '')}",
            ]
            for col_idx, val in enumerate(row_data, 1):
                cell = ws.cell(row=row_num, column=col_idx, value=val)
                cell.border = thin_border
                cell.alignment = Alignment(vertical="center")
                if row_num % 2 == 0:
                    cell.fill = alt_fill
            row_num += 1
        else:
            for art in articles:
                global_idx += 1
                desc = descriptions.get(art, "")
                row_data = [
                    global_idx, pos["position"], art,
                    desc[:60] if desc else "",
                    pos.get("quantity", 0) or "", "шт.",
                    pos.get("color", ""), dims_str,
                    f"стр. {pos.get('page', '')}",
                ]
                for col_idx, val in enumerate(row_data, 1):
                    cell = ws.cell(row=row_num, column=col_idx, value=val)
                    cell.border = thin_border
                    cell.alignment = Alignment(vertical="center")
                    if row_num % 2 == 0:
                        cell.fill = alt_fill
                row_num += 1

    # Авто-ширина колонок
    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            try:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 8), 40)

    # --- Лист 2: Сводка ---
    ws2 = wb.create_sheet("Сводка")

    all_articles = set()
    total_qty = 0
    all_colors = set()
    all_dims = []
    for pos in positions:
        all_articles.update(pos.get("articles", []))
        total_qty += pos.get("quantity", 0) or 0
        if pos.get("color"):
            all_colors.add(pos["color"])
        all_dims.extend(pos.get("dimensions", []))

    summary_data = [
        ["Сводка по спецификации", ""],
        ["Исходный файл", source_file],
        ["Дата генерации", datetime.now().strftime("%d.%m.%Y %H:%M")],
        ["", ""],
        ["Всего позиций", len(positions)],
        ["Уникальных артикулов", len(all_articles)],
        ["Общее количество изделий", total_qty],
        ["Цвета", ", ".join(sorted(all_colors)) if all_colors else "Не указаны"],
        ["Диапазон размеров",
         f"{min(all_dims)} - {max(all_dims)} мм" if all_dims else "Не указан"],
    ]

    summary_header_font = Font(name="Arial", size=11, bold=True)
    for r_idx, (label, value) in enumerate(summary_data, 1):
        cell_a = ws2.cell(row=r_idx, column=1, value=label)
        cell_b = ws2.cell(row=r_idx, column=2, value=value)
        cell_a.border = thin_border
        cell_b.border = thin_border
        if r_idx == 1:
            cell_a.font = Font(name="Arial", size=12, bold=True, color="FFFFFF")
            cell_a.fill = header_fill
            cell_b.fill = header_fill
        else:
            cell_a.font = summary_header_font

    ws2.column_dimensions["A"].width = 30
    ws2.column_dimensions["B"].width = 40

    result_name = f"spec_{uuid.uuid4().hex[:8]}.xlsx"
    result_path = RESULTS_DIR / result_name
    wb.save(str(result_path))
    return result_path


@limiter.limit("10/minute")
@app.post("/api/generate-spec", tags=["3D & Optimization"], summary="Generate specification from drawing")
async def api_generate_spec(request: Request, file: UploadFile = File(...)):
    """Сгенерировать XLSX спецификацию из КМД чертежа (PDF или DXF)."""
    fname_lower = file.filename.lower()
    if not fname_lower.endswith((".pdf", ".dxf")):
        raise HTTPException(status_code=400, detail="Принимаются файлы PDF или DXF")

    path = save_upload(file)

    try:

        source_type = "dxf" if fname_lower.endswith(".dxf") else "pdf"

        if source_type == "pdf":
            positions = _extract_kmd_data_from_pdf(str(path))
        else:
            # DXF
            dxf_data = parse_dxf_for_web(str(path))
            positions = []
            dxf_articles = set()
            dxf_dims = []

            for t in dxf_data.get("texts", []):
                txt = t.get("text", "")
                for am in re.finditer(r'\b(\d{7,8})\b', txt):
                    art = am.group(1)
                    if int(art) > 100000:
                        dxf_articles.add(art)

            for d in dxf_data.get("dimensions", []):
                val = d.get("measurement", 0)
                if 50 <= val <= 5000:
                    dxf_dims.append(int(val))

            pos_found: dict[str, dict] = {}
            for t in dxf_data.get("texts", []):
                txt = t.get("text", "")
                pm = re.search(
                    r'Поз\.?\s*([А-Яа-яA-Za-z]{1,3}\s*[\-\.]\s*\d{1,3})', txt,
                )
                if pm:
                    pos_name = pm.group(1).replace(' ', '')
                    if pos_name not in pos_found:
                        pos_found[pos_name] = {
                            "position": pos_name,
                            "articles": [], "descriptions": {},
                            "quantity": 0, "dimensions": [],
                            "dim_wxh": [], "color": "", "page": 1,
                        }

            if pos_found:
                for pos_name, pdata in pos_found.items():
                    pdata["articles"] = sorted(dxf_articles)
                    pdata["dimensions"] = sorted(set(dxf_dims))[:8]
                positions = list(pos_found.values())
            elif dxf_articles or dxf_dims:
                positions = [{
                    "position": "DXF",
                    "articles": sorted(dxf_articles),
                    "descriptions": {}, "quantity": 0,
                    "dimensions": sorted(set(dxf_dims))[:8],
                    "dim_wxh": [], "color": "", "page": 1,
                }]

        # Генерируем XLSX
        result_path = _generate_spec_xlsx(positions, file.filename)
        result_name = result_path.name

        # Собираем сводку
        all_articles_set = set()
        total_qty = 0
        all_colors = set()
        all_dims_list = []
        for pos in positions:
            all_articles_set.update(pos.get("articles", []))
            total_qty += pos.get("quantity", 0) or 0
            if pos.get("color"):
                all_colors.add(pos["color"])
            all_dims_list.extend(pos.get("dimensions", []))

        response_positions = []
        for pos in positions:
            art_list = []
            for art in pos.get("articles", []):
                art_list.append({
                    "article": art,
                    "description": pos.get("descriptions", {}).get(art, ""),
                    "quantity": pos.get("quantity", 0),
                })
            dims_str = ", ".join(pos.get("dim_wxh", []))
            if not dims_str and pos.get("dimensions"):
                dims_str = " x ".join(str(d) for d in pos["dimensions"][:4])
            response_positions.append({
                "position": pos["position"],
                "articles": art_list,
                "dimensions": pos.get("dimensions", []),
                "dimensions_str": dims_str,
                "color": pos.get("color", ""),
                "quantity": pos.get("quantity", 0),
                "page": pos.get("page", 0),
            })

        summary = {
            "total_positions": len(positions),
            "total_articles": len(all_articles_set),
            "total_items": total_qty,
            "unique_colors": sorted(all_colors),
            "dimension_range": (
                f"{min(all_dims_list)} - {max(all_dims_list)} мм"
                if all_dims_list else ""
            ),
        }

        await log_activity(
            "generate_spec", file.filename,
            f"Позиций: {len(positions)}, артикулов: {len(all_articles_set)}, "
            f"изделий: {total_qty}",
        )

        return {
            "status": "ok",
            "source_file": file.filename,
            "source_type": source_type,
            "positions": response_positions,
            "summary": summary,
            "download": f"/api/download/{result_name}",
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path.unlink(missing_ok=True)


# ============== 3D PREVIEW ==============


def _build_scene(params: dict) -> dict:
    """Build a 3D scene description from construction parameters."""
    w = params.get("width_mm", 1500)
    h = params.get("height_mm", 2100)
    depth = params.get("frame_depth_mm", 72)
    profile_w = 65
    sections = params.get("sections", [])
    has_impost = params.get("has_impost", False)
    glass_formula = params.get("glass_formula", "4-16-4-16-4")
    color_outside = params.get("color_outside", "#7B7B7B")
    color_inside = params.get("color_inside", "#FFFFFF")

    # Parse glass thickness
    glass_parts = [int(p) for p in glass_formula.split("-") if p.strip().isdigit()]
    glass_thickness = sum(glass_parts) if glass_parts else 24

    # Build sections data
    scene_sections = []
    glass_panels = []
    handles = []
    impost_data = None

    if not sections:
        # Single section default
        sections = [{"type": "fixed", "x": 0, "y": 0, "w": w, "h": h}]

    # Auto-compute x offsets if not specified
    cur_x = 0
    for i, sec in enumerate(sections):
        sx = sec.get("x", cur_x)
        sy = sec.get("y", 0)
        sw = sec.get("w", w // len(sections))
        sh = sec.get("h", h)
        stype = sec.get("type", "fixed")

        scene_sections.append({
            "index": i,
            "type": stype,
            "x": sx,
            "y": sy,
            "width": sw,
            "height": sh,
            "label": {
                "fixed": "Глухое",
                "tilt_turn": "ПО",
                "tilt": "П",
                "turn": "О",
                "sliding": "Раздв.",
            }.get(stype, stype),
        })

        # Glass panel for this section (inset by profile width)
        glass_panels.append({
            "index": i,
            "x": sx + profile_w,
            "y": sy + profile_w,
            "width": sw - 2 * profile_w,
            "height": sh - 2 * profile_w,
            "thickness": glass_thickness,
        })

        # Handle for opening sections
        if stype in ("tilt_turn", "tilt", "turn"):
            handle_h = sec.get("handle_height_mm") or sec.get("handle_height") or sh // 2
            handles.append({
                "section_index": i,
                "x": sx + sw - profile_w - 10,
                "y": handle_h,
                "side": "right",
                "opening_type": stype,
            })

        cur_x = sx + sw

    # Impost between sections
    if has_impost and len(sections) >= 2:
        impost_x = sections[0].get("x", 0) + sections[0].get("w", w // 2)
        impost_data = {
            "x": impost_x,
            "orientation": "vertical",
            "width": 45,
            "height": h,
            "depth": depth,
        }

    return {
        "frame": {
            "width": w,
            "height": h,
            "depth": depth,
            "profile_width": profile_w,
        },
        "sections": scene_sections,
        "impost": impost_data,
        "glass_panels": glass_panels,
        "handles": handles,
        "glass_formula": glass_formula,
        "glass_thickness": glass_thickness,
        "color_outside": color_outside,
        "color_inside": color_inside,
    }


@app.post("/api/preview-3d", tags=["3D & Optimization"], summary="Generate 3D scene from parameters")
async def api_preview_3d(params: dict):
    """Build 3D scene data from manual construction parameters."""
    try:
        counters["preview_3d"] += 1
        scene = _build_scene(params)
        ctype = params.get("construction_type", "окно")
        await log_activity(
            "preview_3d", f"{ctype}",
            f"{scene['frame']['width']}x{scene['frame']['height']} мм, "
            f"секций: {len(scene['sections'])}",
        )
        return {"status": "ok", "scene": scene}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/preview-3d-from-pdf", tags=["3D & Optimization"], summary="Generate 3D scene from PDF")
async def api_preview_3d_from_pdf(file: UploadFile = File(...)):
    """Extract construction data from a KMD PDF and return 3D scene."""
    path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{file.filename}"
    try:
        data = await file.read()
        path.write_bytes(data)

        text = extract_text_from_pdf(str(path))

        # Parse dimensions (WxH patterns)
        dim_pattern = re.compile(
            r"(\d{3,5})\s*[xXхХ*×]\s*(\d{3,5})"
        )
        dims_found = dim_pattern.findall(text)

        width_mm = 1500
        height_mm = 2100
        if dims_found:
            # Take first reasonable match
            for dw, dh in dims_found:
                dw_i, dh_i = int(dw), int(dh)
                if 200 <= dw_i <= 10000 and 200 <= dh_i <= 10000:
                    width_mm = dw_i
                    height_mm = dh_i
                    break

        # Detect construction type
        construction_type = "окно"
        text_lower = text.lower()
        if "витраж" in text_lower:
            construction_type = "витраж"
        elif "дверь" in text_lower or "дверной" in text_lower:
            construction_type = "дверь"
        elif "фасад" in text_lower:
            construction_type = "фасад"

        # Detect sections
        sections = []
        has_impost = False

        # Check for impost
        if "импост" in text_lower:
            has_impost = True

        # Check for створка (opening sash)
        stvorka_count = len(re.findall(r"створк", text_lower))
        gluhoe_count = len(re.findall(r"глух", text_lower))

        # Detect handle height
        handle_pattern = re.compile(r"руч\w*\s*[:=]?\s*(\d{3,4})")
        handle_match = handle_pattern.search(text_lower)
        handle_height = int(handle_match.group(1)) if handle_match else 1050

        if has_impost or stvorka_count > 0:
            # Two-section window
            half_w = width_mm // 2
            sections = [
                {"type": "fixed", "x": 0, "y": 0, "w": half_w, "h": height_mm},
                {
                    "type": "tilt_turn", "x": half_w, "y": 0,
                    "w": width_mm - half_w, "h": height_mm,
                    "handle_height_mm": handle_height,
                },
            ]
            has_impost = True
        elif gluhoe_count > 0 and stvorka_count == 0:
            sections = [
                {"type": "fixed", "x": 0, "y": 0, "w": width_mm, "h": height_mm},
            ]
        else:
            # Default: single tilt-turn
            sections = [
                {
                    "type": "tilt_turn", "x": 0, "y": 0,
                    "w": width_mm, "h": height_mm,
                    "handle_height_mm": handle_height,
                },
            ]

        # Parse glass formula
        glass_formula = "4-16-4-16-4"
        glass_pattern = re.compile(r"(\d{1,2}[-/]\d{1,2}[-/]\d{1,2}(?:[-/]\d{1,2})*)")
        glass_match = glass_pattern.search(text)
        if glass_match:
            candidate = glass_match.group(1).replace("/", "-")
            parts = candidate.split("-")
            if len(parts) >= 3 and all(1 <= int(p) <= 50 for p in parts if p.isdigit()):
                glass_formula = candidate

        params = {
            "construction_type": construction_type,
            "width_mm": width_mm,
            "height_mm": height_mm,
            "frame_depth_mm": 72,
            "sections": sections,
            "glass_formula": glass_formula,
            "has_impost": has_impost,
            "color_outside": "#7B7B7B",
            "color_inside": "#FFFFFF",
        }

        scene = _build_scene(params)

        counters["preview_3d"] += 1
        await log_activity(
            "preview_3d", file.filename,
            f"PDF -> {construction_type} {width_mm}x{height_mm} мм, "
            f"секций: {len(sections)}",
        )

        return {
            "status": "ok",
            "source_file": file.filename,
            "extracted_params": params,
            "scene": scene,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path.unlink(missing_ok=True)


# ============== ОПТИМИЗАЦИЯ РАСКРОЯ ПРОФИЛЕЙ ==============


class CutItem(BaseModel):
    article: str
    length_mm: int
    quantity: int


class CuttingRequest(BaseModel):
    stock_length_mm: int = 6500
    cuts: List[CutItem]
    blade_width_mm: int = 5
    min_remnant_mm: int = 50


def _optimize_cutting(req: CuttingRequest) -> dict:
    """
    1D bin-packing: First Fit Decreasing (FFD) + improvement pass.
    """
    stock = req.stock_length_mm
    blade = req.blade_width_mm

    # Expand all cuts into individual items
    items = []
    for c in req.cuts:
        for _ in range(c.quantity):
            items.append({"article": c.article, "length_mm": c.length_mm})

    if not items:
        return {
            "status": "ok",
            "stock_length_mm": stock,
            "blade_width_mm": blade,
            "total_bars_needed": 0,
            "total_stock_length_mm": 0,
            "total_used_mm": 0,
            "total_waste_mm": 0,
            "waste_percent": 0.0,
            "savings_vs_naive": 0.0,
            "cutting_plan": [],
            "summary_by_article": [],
        }

    # Sort descending by length (FFD)
    items.sort(key=lambda x: x["length_mm"], reverse=True)

    # Bars: each bar tracks cuts and remaining space
    bars: list[dict] = []

    def _space_needed(bar_cuts_count: int, cut_len: int) -> int:
        """Space needed to add a cut to a bar with bar_cuts_count existing cuts."""
        if bar_cuts_count == 0:
            return cut_len
        return blade + cut_len

    # FFD pass
    for item in items:
        placed = False
        for bar in bars:
            needed = _space_needed(len(bar["cuts"]), item["length_mm"])
            if needed <= bar["remaining_mm"]:
                bar["cuts"].append(item)
                bar["remaining_mm"] -= needed
                placed = True
                break
        if not placed:
            new_bar = {"cuts": [item], "remaining_mm": stock - item["length_mm"]}
            bars.append(new_bar)

    # Improvement pass: try to move cuts from high-waste bars to others
    improved = True
    max_iters = 50
    iteration = 0
    while improved and iteration < max_iters:
        improved = False
        iteration += 1
        bars.sort(key=lambda b: b["remaining_mm"], reverse=True)
        for i in range(len(bars)):
            if not bars[i]["cuts"]:
                continue
            for ci in range(len(bars[i]["cuts"]) - 1, -1, -1):
                cut = bars[i]["cuts"][ci]
                for j in range(len(bars)):
                    if i == j:
                        continue
                    needed = _space_needed(len(bars[j]["cuts"]), cut["length_mm"])
                    if needed <= bars[j]["remaining_mm"]:
                        bars[i]["cuts"].pop(ci)
                        used_i = sum(c["length_mm"] for c in bars[i]["cuts"])
                        if bars[i]["cuts"]:
                            used_i += blade * (len(bars[i]["cuts"]) - 1)
                        bars[i]["remaining_mm"] = stock - used_i
                        bars[j]["cuts"].append(cut)
                        bars[j]["remaining_mm"] -= needed
                        improved = True
                        break
                if improved:
                    break
            if improved:
                break

    # Remove empty bars
    bars = [b for b in bars if b["cuts"]]

    # Calculate naive baseline: sequential placement without optimization
    naive_bars_seq = 0
    naive_remaining = 0
    for item in items:
        if naive_remaining >= item["length_mm"] + (blade if naive_bars_seq > 0 and naive_remaining < stock else 0):
            if naive_remaining == stock:
                naive_remaining -= item["length_mm"]
            else:
                naive_remaining -= (item["length_mm"] + blade)
        else:
            naive_bars_seq += 1
            naive_remaining = stock - item["length_mm"]
    total_cut_length = sum(item["length_mm"] for item in items)
    naive_bars_theoretical = math.ceil(total_cut_length / stock) if stock > 0 else len(bars)
    naive_bars = max(naive_bars_theoretical, naive_bars_seq)

    total_bars = len(bars)
    total_stock = total_bars * stock
    total_used = 0
    cutting_plan = []

    for idx, bar in enumerate(bars, 1):
        bar_used = sum(c["length_mm"] for c in bar["cuts"])
        if len(bar["cuts"]) > 1:
            bar_used += blade * (len(bar["cuts"]) - 1)
        bar_waste = stock - bar_used
        utilization = round(bar_used / stock * 100, 1) if stock > 0 else 0
        total_used += bar_used

        cutting_plan.append({
            "bar_number": idx,
            "cuts": [{"article": c["article"], "length_mm": c["length_mm"]} for c in bar["cuts"]],
            "used_mm": bar_used,
            "waste_mm": bar_waste,
            "utilization_percent": utilization,
        })

    total_waste = total_stock - total_used
    waste_pct = round(total_waste / total_stock * 100, 1) if total_stock > 0 else 0

    if naive_bars > 0 and naive_bars > total_bars:
        savings = round((1 - total_bars / naive_bars) * 100, 1)
    else:
        savings = 0.0

    # Summary by article
    article_summary: dict[str, dict] = {}
    for item in items:
        art = item["article"]
        if art not in article_summary:
            article_summary[art] = {"article": art, "total_cuts": 0, "total_length_mm": 0}
        article_summary[art]["total_cuts"] += 1
        article_summary[art]["total_length_mm"] += item["length_mm"]

    return {
        "status": "ok",
        "stock_length_mm": stock,
        "blade_width_mm": blade,
        "total_bars_needed": total_bars,
        "total_stock_length_mm": total_stock,
        "total_used_mm": total_used,
        "total_waste_mm": total_waste,
        "waste_percent": waste_pct,
        "savings_vs_naive": savings,
        "cutting_plan": cutting_plan,
        "summary_by_article": sorted(article_summary.values(), key=lambda x: x["article"]),
    }


@app.post("/api/optimize-cutting", tags=["3D & Optimization"], summary="Optimize linear cutting layout")
async def api_optimize_cutting(req: CuttingRequest):
    """Оптимизировать раскрой профилей (ручной ввод)."""
    try:
        result = _optimize_cutting(req)
        await log_activity(
            "optimize_cutting", "manual",
            f"Хлыстов: {result['total_bars_needed']}, отходы: {result['waste_percent']}%",
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/optimize-cutting-from-pdf", tags=["3D & Optimization"], summary="Optimize cutting from PDF")
async def api_optimize_cutting_from_pdf(
    file: UploadFile = File(...),
    stock_length_mm: int = Form(6500),
    blade_width_mm: int = Form(5),
    min_remnant_mm: int = Form(50),
):
    """Извлечь профили из PDF КМД и оптимизировать раскрой."""
    path = save_upload(file)
    try:
        text = extract_text_from_pdf(str(path))

        # Find all 7-digit articles
        articles_found = re.findall(r'\b(\d{7})\b', text)
        unique_articles = sorted(set(articles_found))

        # Find dimensions: numbers 100-6500 followed by mm
        dimensions = re.findall(r'\b(\d{3,4})\s*(?:мм|mm)\b', text, re.IGNORECASE)
        dim_values = [int(d) for d in dimensions if 50 <= int(d) <= 6500]

        # Build cuts list by pairing articles with dimensions
        cuts_list: list[dict] = []

        if unique_articles and dim_values:
            for art in unique_articles:
                art_positions = [m.start() for m in re.finditer(r'\b' + art + r'\b', text)]
                nearby_dims = set()
                for apos in art_positions:
                    snippet = text[apos:apos + 300]
                    dims_in_snippet = re.findall(r'\b(\d{3,4})\s*(?:мм|mm)?\b', snippet)
                    for d in dims_in_snippet:
                        dv = int(d)
                        if 100 <= dv <= 6500 and dv != int(art):
                            nearby_dims.add(dv)

                if nearby_dims:
                    for dim in sorted(nearby_dims):
                        qty = 1
                        for apos in art_positions:
                            snippet = text[max(0, apos - 100):apos + 300]
                            q_match = re.findall(
                                r'(?:Количество|Кол[\-\.]?\s*во|qty|кол)\s*[:\s]\s*(\d+)',
                                snippet, re.IGNORECASE,
                            )
                            if q_match:
                                qty = int(q_match[0])
                                break
                        cuts_list.append({
                            "article": art,
                            "length_mm": dim,
                            "quantity": qty,
                        })
                else:
                    if dim_values:
                        cuts_list.append({
                            "article": art,
                            "length_mm": dim_values[0],
                            "quantity": 1,
                        })

        if not cuts_list:
            raise HTTPException(
                status_code=400,
                detail="Не удалось извлечь артикулы и размеры из PDF. "
                       "Убедитесь, что документ содержит 7-значные артикулы и размеры в мм.",
            )

        cut_items = [CutItem(**c) for c in cuts_list]
        req = CuttingRequest(
            stock_length_mm=stock_length_mm,
            cuts=cut_items,
            blade_width_mm=blade_width_mm,
            min_remnant_mm=min_remnant_mm,
        )
        result = _optimize_cutting(req)

        result["extracted_articles"] = unique_articles
        result["extracted_cuts"] = cuts_list

        await log_activity(
            "optimize_cutting", file.filename,
            f"Артикулов: {len(unique_articles)}, хлыстов: {result['total_bars_needed']}, "
            f"отходы: {result['waste_percent']}%",
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path.unlink(missing_ok=True)


# ============== 12. AI ПОДБОР ПРОФИЛЬНОЙ СИСТЕМЫ ==============

PROFILE_SYSTEMS = [
    # --- Reynaers ---
    {
        "system": "Reynaers MasterLine 8",
        "manufacturer": "Reynaers Aluminium",
        "series": "MasterLine 8",
        "types": ["окна"],
        "thermal_uf_min": 1.3, "thermal_uf_max": 1.5,
        "max_sash_weight_kg": 160,
        "max_height_mm": 2800, "max_width_mm": 1400,
        "glass_max_mm": 52,
        "wind_resistance_pa": 2400,
        "fire_resistant": False,
        "budget": "премиум",
        "sound_db": 45,
        "pros": ["Высокая теплоизоляция", "Скрытая фурнитура", "Большие створки"],
        "cons": ["Высокая стоимость профиля"],
        "norms": ["ГОСТ 21519-2022", "СП 426.1325800.2018"],
        "articles_example": ["4580102", "4580183"],
    },
    {
        "system": "Reynaers MasterLine 8 HI",
        "manufacturer": "Reynaers Aluminium",
        "series": "MasterLine 8 HI",
        "types": ["окна"],
        "thermal_uf_min": 0.9, "thermal_uf_max": 1.1,
        "max_sash_weight_kg": 150,
        "max_height_mm": 2600, "max_width_mm": 1300,
        "glass_max_mm": 56,
        "wind_resistance_pa": 2200,
        "fire_resistant": False,
        "budget": "премиум",
        "sound_db": 48,
        "pros": ["Лучшая теплоизоляция в классе", "Тройное уплотнение", "Пассивный дом"],
        "cons": ["Высокая цена", "Увеличенная монтажная глубина"],
        "norms": ["ГОСТ 21519-2022", "СП 50.13330.2012"],
        "articles_example": ["4580202", "4580283"],
    },
    {
        "system": "Reynaers ConceptWall 50",
        "manufacturer": "Reynaers Aluminium",
        "series": "CW 50",
        "types": ["витражи", "фасады"],
        "thermal_uf_min": 1.5, "thermal_uf_max": 2.0,
        "max_sash_weight_kg": 0,
        "max_height_mm": 6000, "max_width_mm": 3000,
        "glass_max_mm": 44,
        "wind_resistance_pa": 3000,
        "fire_resistant": False,
        "budget": "стандарт",
        "sound_db": 42,
        "pros": ["Узкие профили 50мм", "Высокие пролёты", "Стоечно-ригельная система"],
        "cons": ["Средняя теплоизоляция", "Требует расчёта несущей способности"],
        "norms": ["ГОСТ 33079-2014", "СП 426.1325800.2018"],
        "articles_example": ["CW50-01", "CW50-02"],
    },
    {
        "system": "Reynaers ConceptWall 60",
        "manufacturer": "Reynaers Aluminium",
        "series": "CW 60",
        "types": ["витражи", "фасады"],
        "thermal_uf_min": 0.8, "thermal_uf_max": 1.2,
        "max_sash_weight_kg": 0,
        "max_height_mm": 6000, "max_width_mm": 3000,
        "glass_max_mm": 54,
        "wind_resistance_pa": 3500,
        "fire_resistant": True,
        "budget": "премиум",
        "sound_db": 48,
        "pros": ["Отличная теплоизоляция", "Большие пролёты", "Противопожарное исполнение"],
        "cons": ["Высокая стоимость", "Увеличенная видимая ширина"],
        "norms": ["ГОСТ 33079-2014", "СП 426.1325800.2018", "ГОСТ 53308-2009"],
        "articles_example": ["CW60-01", "CW60-02"],
    },
    {
        "system": "Reynaers Hi-Finity",
        "manufacturer": "Reynaers Aluminium",
        "series": "Hi-Finity",
        "types": ["раздвижные"],
        "thermal_uf_min": 1.4, "thermal_uf_max": 1.8,
        "max_sash_weight_kg": 400,
        "max_height_mm": 3500, "max_width_mm": 3000,
        "glass_max_mm": 52,
        "wind_resistance_pa": 2000,
        "fire_resistant": False,
        "budget": "премиум",
        "sound_db": 40,
        "pros": ["Минимальные рамки", "Панорамное остекление", "Створки до 400кг"],
        "cons": ["Высокая стоимость", "Сложный монтаж"],
        "norms": ["ГОСТ 21519-2022", "СП 426.1325800.2018"],
        "articles_example": ["HF-01", "HF-02"],
    },
    {
        "system": "Reynaers CS 86-HI",
        "manufacturer": "Reynaers Aluminium",
        "series": "CS 86-HI",
        "types": ["двери"],
        "thermal_uf_min": 1.0, "thermal_uf_max": 1.3,
        "max_sash_weight_kg": 200,
        "max_height_mm": 3000, "max_width_mm": 1400,
        "glass_max_mm": 52,
        "wind_resistance_pa": 2500,
        "fire_resistant": False,
        "budget": "премиум",
        "sound_db": 44,
        "pros": ["Высокая теплоизоляция", "Тяжёлые створки до 200кг", "Скрытые петли"],
        "cons": ["Высокая стоимость профиля"],
        "norms": ["ГОСТ 23747-2015", "СП 426.1325800.2018"],
        "articles_example": ["CS86-01", "CS86-02"],
    },
    # --- Schuco ---
    {
        "system": "Schüco AWS 75.SI+",
        "manufacturer": "Schüco",
        "series": "AWS 75.SI+",
        "types": ["окна"],
        "thermal_uf_min": 1.2, "thermal_uf_max": 1.6,
        "max_sash_weight_kg": 150,
        "max_height_mm": 2600, "max_width_mm": 1400,
        "glass_max_mm": 50,
        "wind_resistance_pa": 2400,
        "fire_resistant": False,
        "budget": "стандарт",
        "sound_db": 45,
        "pros": ["Оптимальное соотношение цена/качество", "Широкая линейка фурнитуры", "Проверенная система"],
        "cons": ["Стандартный дизайн"],
        "norms": ["ГОСТ 21519-2022", "СП 426.1325800.2018"],
        "articles_example": ["242480", "242485"],
    },
    {
        "system": "Schüco AWS 90.SI+",
        "manufacturer": "Schüco",
        "series": "AWS 90.SI+",
        "types": ["окна"],
        "thermal_uf_min": 0.8, "thermal_uf_max": 1.0,
        "max_sash_weight_kg": 160,
        "max_height_mm": 2700, "max_width_mm": 1400,
        "glass_max_mm": 56,
        "wind_resistance_pa": 2600,
        "fire_resistant": False,
        "budget": "премиум",
        "sound_db": 50,
        "pros": ["Лучшая теплоизоляция Schüco", "Пассивный дом", "Тройное уплотнение"],
        "cons": ["Высокая стоимость", "Монтажная глубина 90мм"],
        "norms": ["ГОСТ 21519-2022", "СП 50.13330.2012"],
        "articles_example": ["288900", "288905"],
    },
    {
        "system": "Schüco FWS 50+.SI",
        "manufacturer": "Schüco",
        "series": "FWS 50+.SI",
        "types": ["витражи", "фасады"],
        "thermal_uf_min": 1.0, "thermal_uf_max": 1.5,
        "max_sash_weight_kg": 0,
        "max_height_mm": 6000, "max_width_mm": 3000,
        "glass_max_mm": 50,
        "wind_resistance_pa": 3200,
        "fire_resistant": False,
        "budget": "стандарт",
        "sound_db": 44,
        "pros": ["Узкие видимые профили", "Высокая ветровая стойкость", "Совместимость с AWS"],
        "cons": ["Требует расчёта несущей способности"],
        "norms": ["ГОСТ 33079-2014", "СП 426.1325800.2018"],
        "articles_example": ["FWS50-01", "FWS50-02"],
    },
    {
        "system": "Schüco FWS 60+.SI",
        "manufacturer": "Schüco",
        "series": "FWS 60+.SI",
        "types": ["витражи", "фасады"],
        "thermal_uf_min": 0.7, "thermal_uf_max": 1.0,
        "max_sash_weight_kg": 0,
        "max_height_mm": 6000, "max_width_mm": 3500,
        "glass_max_mm": 58,
        "wind_resistance_pa": 3800,
        "fire_resistant": True,
        "budget": "премиум",
        "sound_db": 50,
        "pros": ["Лучшая теплоизоляция фасадов", "Противопожарное исполнение EI30/EI60", "Максимальные пролёты"],
        "cons": ["Высокая стоимость", "Увеличенная монтажная глубина"],
        "norms": ["ГОСТ 33079-2014", "СП 426.1325800.2018", "ГОСТ 53308-2009"],
        "articles_example": ["FWS60-01", "FWS60-02"],
    },
    {
        "system": "Schüco ASS 77 PD.HI",
        "manufacturer": "Schüco",
        "series": "ASS 77 PD.HI",
        "types": ["раздвижные"],
        "thermal_uf_min": 1.2, "thermal_uf_max": 1.5,
        "max_sash_weight_kg": 300,
        "max_height_mm": 3200, "max_width_mm": 3000,
        "glass_max_mm": 50,
        "wind_resistance_pa": 2200,
        "fire_resistant": False,
        "budget": "премиум",
        "sound_db": 42,
        "pros": ["Параллельно-сдвижная система", "Тяжёлые створки", "Хорошая теплоизоляция"],
        "cons": ["Высокая стоимость", "Требует ровного проёма"],
        "norms": ["ГОСТ 21519-2022", "СП 426.1325800.2018"],
        "articles_example": ["ASS77-01", "ASS77-02"],
    },
    {
        "system": "Schüco ADS 90.SI",
        "manufacturer": "Schüco",
        "series": "ADS 90.SI",
        "types": ["двери"],
        "thermal_uf_min": 0.9, "thermal_uf_max": 1.2,
        "max_sash_weight_kg": 200,
        "max_height_mm": 3000, "max_width_mm": 1400,
        "glass_max_mm": 54,
        "wind_resistance_pa": 2600,
        "fire_resistant": False,
        "budget": "премиум",
        "sound_db": 46,
        "pros": ["Высокая теплоизоляция", "Створки до 200кг", "Три контура уплотнения"],
        "cons": ["Высокая стоимость", "Монтажная глубина 90мм"],
        "norms": ["ГОСТ 23747-2015", "СП 426.1325800.2018"],
        "articles_example": ["ADS90-01", "ADS90-02"],
    },
    # --- Alutech ---
    {
        "system": "Alutech ALT W72",
        "manufacturer": "Alutech",
        "series": "ALT W72",
        "types": ["окна"],
        "thermal_uf_min": 1.4, "thermal_uf_max": 1.8,
        "max_sash_weight_kg": 120,
        "max_height_mm": 2400, "max_width_mm": 1200,
        "glass_max_mm": 44,
        "wind_resistance_pa": 2000,
        "fire_resistant": False,
        "budget": "эконом",
        "sound_db": 38,
        "pros": ["Доступная цена", "Наличие на складе", "Производство в РБ/РФ"],
        "cons": ["Ограничения по размерам створок", "Меньший выбор фурнитуры"],
        "norms": ["ГОСТ 21519-2022", "СП 426.1325800.2018"],
        "articles_example": ["ALT-W72-01", "ALT-W72-02"],
    },
    {
        "system": "Alutech ALT F50",
        "manufacturer": "Alutech",
        "series": "ALT F50",
        "types": ["витражи", "фасады"],
        "thermal_uf_min": 1.7, "thermal_uf_max": 2.2,
        "max_sash_weight_kg": 0,
        "max_height_mm": 5000, "max_width_mm": 2500,
        "glass_max_mm": 40,
        "wind_resistance_pa": 2400,
        "fire_resistant": False,
        "budget": "эконом",
        "sound_db": 38,
        "pros": ["Доступная цена", "Быстрая поставка", "Простой монтаж"],
        "cons": ["Средняя теплоизоляция", "Ограничения по высоте"],
        "norms": ["ГОСТ 33079-2014"],
        "articles_example": ["ALT-F50-01", "ALT-F50-02"],
    },
    {
        "system": "Alutech ALT F50 NL",
        "manufacturer": "Alutech",
        "series": "ALT F50 NL",
        "types": ["витражи", "фасады"],
        "thermal_uf_min": 1.5, "thermal_uf_max": 2.0,
        "max_sash_weight_kg": 0,
        "max_height_mm": 5000, "max_width_mm": 2500,
        "glass_max_mm": 44,
        "wind_resistance_pa": 2600,
        "fire_resistant": False,
        "budget": "стандарт",
        "sound_db": 40,
        "pros": ["Полуструктурное остекление", "Современный вид", "Средняя цена"],
        "cons": ["Средняя теплоизоляция", "Ограничения по пролётам"],
        "norms": ["ГОСТ 33079-2014"],
        "articles_example": ["ALT-F50NL-01", "ALT-F50NL-02"],
    },
    {
        "system": "Alutech ALT SL160",
        "manufacturer": "Alutech",
        "series": "ALT SL160",
        "types": ["раздвижные"],
        "thermal_uf_min": 1.5, "thermal_uf_max": 2.0,
        "max_sash_weight_kg": 200,
        "max_height_mm": 2800, "max_width_mm": 2500,
        "glass_max_mm": 40,
        "wind_resistance_pa": 1800,
        "fire_resistant": False,
        "budget": "стандарт",
        "sound_db": 36,
        "pros": ["Доступная раздвижная система", "Простой монтаж", "Наличие"],
        "cons": ["Средние характеристики", "Ограничения по весу створки"],
        "norms": ["ГОСТ 21519-2022"],
        "articles_example": ["ALT-SL160-01", "ALT-SL160-02"],
    },
    {
        "system": "Alutech ALT C48",
        "manufacturer": "Alutech",
        "series": "ALT C48",
        "types": ["окна", "витражи"],
        "thermal_uf_min": 5.0, "thermal_uf_max": 6.0,
        "max_sash_weight_kg": 80,
        "max_height_mm": 2200, "max_width_mm": 1200,
        "glass_max_mm": 32,
        "wind_resistance_pa": 1800,
        "fire_resistant": False,
        "budget": "эконом",
        "sound_db": 28,
        "pros": ["Минимальная цена", "Быстрая поставка", "Простой монтаж"],
        "cons": ["Холодная система без терморазрыва", "Только неотапливаемые помещения"],
        "norms": ["ГОСТ 21519-2022"],
        "articles_example": ["ALT-C48-01", "ALT-C48-02"],
    },
    # --- TATPROF ---
    {
        "system": "TATPROF ТПТ 65А",
        "manufacturer": "TATPROF",
        "series": "ТПТ 65А",
        "types": ["окна"],
        "thermal_uf_min": 1.5, "thermal_uf_max": 1.9,
        "max_sash_weight_kg": 100,
        "max_height_mm": 2200, "max_width_mm": 1200,
        "glass_max_mm": 40,
        "wind_resistance_pa": 1800,
        "fire_resistant": False,
        "budget": "эконом",
        "sound_db": 36,
        "pros": ["Российское производство", "Доступная цена", "Быстрая поставка"],
        "cons": ["Ограничения по размерам", "Базовый дизайн", "Меньший выбор фурнитуры"],
        "norms": ["ГОСТ 21519-2022"],
        "articles_example": ["TPT-65A-01", "TPT-65A-02"],
    },
    {
        "system": "TATPROF ТПТ 47А",
        "manufacturer": "TATPROF",
        "series": "ТПТ 47А",
        "types": ["окна"],
        "thermal_uf_min": 5.5, "thermal_uf_max": 7.0,
        "max_sash_weight_kg": 60,
        "max_height_mm": 2000, "max_width_mm": 1000,
        "glass_max_mm": 24,
        "wind_resistance_pa": 1500,
        "fire_resistant": False,
        "budget": "эконом",
        "sound_db": 25,
        "pros": ["Минимальная цена", "Российское производство", "Быстрая поставка"],
        "cons": ["Холодная система", "Только неотапливаемые помещения", "Малые размеры"],
        "norms": ["ГОСТ 21519-2022"],
        "articles_example": ["TPT-47A-01", "TPT-47A-02"],
    },
]

WIND_PRESSURE_BASE = {
    "I": 0.17, "II": 0.30, "III": 0.38, "IV": 0.48,
    "V": 0.60, "VI": 0.73, "VII": 0.85,
}


def _calc_wind_pressure(wind_region: str, floors: int) -> float:
    """Расчёт ветрового давления по СП 20.13330 (упрощённый)."""
    w0 = WIND_PRESSURE_BASE.get(wind_region, 0.38)
    height_m = max(floors * 3.0, 3.0)
    k_z = (height_m / 10.0) ** 0.2
    return w0 * k_z * 1.4


def _score_profile(profile: dict, params: dict, wind_pa: float) -> int:
    """Подсчёт рейтинга профильной системы 0-100."""
    score = 0.0

    # 1. Теплоизоляция (25%)
    if params.get("thermal_required"):
        uf_avg = (profile["thermal_uf_min"] + profile["thermal_uf_max"]) / 2
        if uf_avg <= 1.0:
            thermal_score = 100
        elif uf_avg <= 1.5:
            thermal_score = 85 - (uf_avg - 1.0) * 40
        elif uf_avg <= 2.0:
            thermal_score = 65 - (uf_avg - 1.5) * 50
        else:
            thermal_score = max(0, 40 - (uf_avg - 2.0) * 30)
        score += thermal_score * 0.25
    else:
        score += 80 * 0.25

    # 2. Размеры (20%)
    w = params.get("width_mm", 1500)
    h = params.get("height_mm", 2100)
    if h <= profile["max_height_mm"] and w <= profile["max_width_mm"]:
        dim_score = 100
    elif h <= profile["max_height_mm"] * 1.1 and w <= profile["max_width_mm"] * 1.1:
        dim_score = 60
    else:
        dim_score = 10
    score += dim_score * 0.20

    # 3. Ветровая нагрузка (20%)
    if profile["wind_resistance_pa"] >= wind_pa:
        wind_score = 100
    elif profile["wind_resistance_pa"] >= wind_pa * 0.8:
        wind_score = 60
    else:
        wind_score = 20
    score += wind_score * 0.20

    # 4. Бюджет (15%)
    budget = params.get("budget", "стандарт")
    p_budget = profile["budget"]
    if budget == p_budget:
        budget_score = 100
    elif (budget == "стандарт" and p_budget == "эконом") or (
        budget == "премиум" and p_budget == "стандарт"
    ):
        budget_score = 70
    elif budget == "стандарт" and p_budget == "премиум":
        budget_score = 50
    elif budget == "эконом" and p_budget == "стандарт":
        budget_score = 50
    else:
        budget_score = 30
    score += budget_score * 0.15

    # 5. Стеклопакет (10%)
    sound_db = params.get("sound_insulation_db", 35)
    glass_cap = profile["glass_max_mm"]
    if glass_cap >= 50:
        glass_score = 100
    elif glass_cap >= 44:
        glass_score = 80
    elif glass_cap >= 36:
        glass_score = 60
    else:
        glass_score = 30
    if profile["sound_db"] >= sound_db:
        glass_score = min(100, glass_score + 10)
    score += glass_score * 0.10

    # 6. Огнестойкость (10%)
    if params.get("fire_resistance"):
        fire_score = 100 if profile["fire_resistant"] else 0
    else:
        fire_score = 80
    score += fire_score * 0.10

    return max(0, min(100, round(score)))


@app.post("/api/recommend-profile", tags=["3D & Optimization"], summary="Recommend profile system")
async def api_recommend_profile(data: dict):
    """AI-подбор профильной системы по параметрам проекта."""
    try:
        construction_type = data.get("construction_type", "окна")
        width_mm = int(data.get("width_mm", 1500))
        height_mm = int(data.get("height_mm", 2100))
        floors = int(data.get("floors", 5))
        wind_region = data.get("wind_region", "III")
        thermal_required = bool(data.get("thermal_required", True))
        sound_insulation_db = int(data.get("sound_insulation_db", 35))
        fire_resistance = bool(data.get("fire_resistance", False))
        budget = data.get("budget", "стандарт")

        params = {
            "construction_type": construction_type,
            "width_mm": width_mm,
            "height_mm": height_mm,
            "floors": floors,
            "wind_region": wind_region,
            "thermal_required": thermal_required,
            "sound_insulation_db": sound_insulation_db,
            "fire_resistance": fire_resistance,
            "budget": budget,
        }

        wind_pa = _calc_wind_pressure(wind_region, floors) * 1000

        candidates = [
            p for p in PROFILE_SYSTEMS if construction_type in p["types"]
        ]
        if not candidates:
            candidates = PROFILE_SYSTEMS

        scored = []
        for p in candidates:
            s = _score_profile(p, params, wind_pa)
            uf_avg = (p["thermal_uf_min"] + p["thermal_uf_max"]) / 2

            reasons = []
            if thermal_required and uf_avg <= 1.2:
                reasons.append("высокие требования к теплоизоляции")
            if floors >= 9:
                reasons.append(f"здание {floors} этажей")
            if fire_resistance and p["fire_resistant"]:
                reasons.append("огнестойкое исполнение")
            if budget == "эконом":
                reasons.append("экономичное решение")
            elif budget == "премиум":
                reasons.append("премиальное качество")

            reason = (
                f"Оптимальный выбор для {construction_type}: "
                + ", ".join(reasons)
                if reasons
                else f"Подходящая система для {construction_type}"
            )

            scored.append({
                "system": p["system"],
                "manufacturer": p["manufacturer"],
                "series": p["series"],
                "score": s,
                "thermal_uf": round(uf_avg, 2),
                "max_sash_weight_kg": p["max_sash_weight_kg"],
                "max_height_mm": p["max_height_mm"],
                "glass_max_mm": p["glass_max_mm"],
                "pros": p["pros"],
                "cons": p["cons"],
                "reason": reason,
                "norms": p["norms"],
                "articles_example": p["articles_example"],
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        for i, item in enumerate(scored):
            item["rank"] = i + 1

        warnings = []
        if height_mm > 3000:
            warnings.append(
                "При высоте конструкции более 3м требуется индивидуальный расчёт несущей способности"
            )
        if floors >= 15:
            warnings.append(
                "При высоте более 15 этажей требуется расчёт ветровой нагрузки по СП 20.13330"
            )
        if wind_region in ("V", "VI", "VII"):
            warnings.append(
                f"Ветровой район {wind_region} — рекомендуется усиленное армирование профилей"
            )
        if fire_resistance and not any(p["fire_resistant"] for p in candidates):
            warnings.append(
                "Огнестойкие исполнения доступны не во всех системах — уточняйте у производителя"
            )

        await log_activity(
            "recommend_profile",
            f"{construction_type} {width_mm}x{height_mm}",
            f"Найдено {len(scored)} систем, лучшая: {scored[0]['system']} ({scored[0]['score']})",
        )

        return {
            "status": "ok",
            "recommendations": scored[:8],
            "parameters_used": params,
            "wind_pressure_pa": round(wind_pa),
            "warnings": warnings,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== F8. ТЕПЛОТЕХНИЧЕСКИЙ КАЛЬКУЛЯТОР ==============


@limiter.limit("30/minute")
@app.post("/api/calc-thermal", tags=["Calculators"], summary="Thermal resistance (GOST 26602.1)")
async def api_calc_thermal(request: Request, data: dict):
    """Расчёт приведённого сопротивления теплопередаче по ГОСТ 26602.1 / ГОСТ 23166."""
    try:
        # Check cache
        cache_key = _make_key("calc_thermal", **data)
        cached = await cache_get(cache_key)
        if cached:
            return json.loads(cached)

        profile_uf = float(data.get("profile_uf", 1.3))
        glass_ug = float(data.get("glass_ug", 1.0))
        glass_area_m2 = float(data.get("glass_area_m2", 2.5))
        frame_area_m2 = float(data.get("frame_area_m2", 0.8))
        psi_edge = float(data.get("psi_edge", 0.06))
        edge_length_m = float(data.get("edge_length_m", 6.0))

        total_area = frame_area_m2 + glass_area_m2
        if total_area <= 0:
            raise ValueError("Суммарная площадь должна быть > 0")

        # Uw per GOST 26602.1
        uw = (profile_uf * frame_area_m2 + glass_ug * glass_area_m2 + psi_edge * edge_length_m) / total_area
        uw = round(uw, 3)

        # Dew point approximation (Magnus formula at 50% RH, 20C indoor)
        t_indoor = 20.0
        rh = 50.0
        a_m, b_m = 17.27, 237.7
        gamma = (a_m * t_indoor) / (b_m + t_indoor) + math.log(rh / 100.0)
        dew_point = round((b_m * gamma) / (a_m - gamma), 1)

        # Classification per GOST 23166-2021
        if uw < 1.0:
            classification = "А"
            norm_limit = 1.0
        elif uw <= 1.4:
            classification = "Б"
            norm_limit = 1.4
        elif uw <= 1.8:
            classification = "В"
            norm_limit = 1.8
        elif uw <= 2.2:
            classification = "Г"
            norm_limit = 2.2
        else:
            classification = "Д"
            norm_limit = 2.6

        meets_requirement = uw <= 1.8  # typical requirement for most Russian climate zones

        await log_activity("calc_thermal", f"Uw={uw}",
                     f"Класс {classification}, Uw={uw} Вт/(м²·К)")

        result = {
            "status": "ok",
            "uw": uw,
            "uf": profile_uf,
            "ug": glass_ug,
            "dew_point": dew_point,
            "classification": classification,
            "meets_requirement": meets_requirement,
            "norm_limit": norm_limit,
            "total_area_m2": round(total_area, 2),
            "glass_fraction": round(glass_area_m2 / total_area * 100, 1),
        }

        await cache_set(cache_key, json.dumps(result, default=str))
        return result

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== F9. КАЛЬКУЛЯТОР ВЕТРОВОЙ НАГРУЗКИ ==============

# k(z) table per SP 20.13330.2016, Table 11.2
# Heights: 5, 10, 20, 40, 60, 80, 100, 150, 200, 250, 300 m
_KZ_HEIGHTS = [5, 10, 20, 40, 60, 80, 100, 150, 200, 250, 300]
_KZ_TABLE = {
    "A": [0.75, 1.0, 1.25, 1.5, 1.7, 1.85, 2.0, 2.25, 2.45, 2.65, 2.75],
    "B": [0.5, 0.65, 0.85, 1.1, 1.3, 1.45, 1.6, 1.9, 2.1, 2.3, 2.5],
    "C": [0.4, 0.4, 0.55, 0.8, 1.0, 1.15, 1.25, 1.55, 1.8, 2.0, 2.2],
}


def _interpolate_kz(height_m: float, terrain: str) -> float:
    """Линейная интерполяция k(z) по высоте."""
    table = _KZ_TABLE.get(terrain, _KZ_TABLE["B"])
    if height_m <= _KZ_HEIGHTS[0]:
        return table[0]
    if height_m >= _KZ_HEIGHTS[-1]:
        return table[-1]
    for i in range(len(_KZ_HEIGHTS) - 1):
        h1, h2 = _KZ_HEIGHTS[i], _KZ_HEIGHTS[i + 1]
        if h1 <= height_m <= h2:
            t = (height_m - h1) / (h2 - h1)
            return table[i] + t * (table[i + 1] - table[i])
    return table[-1]


@limiter.limit("30/minute")
@app.post("/api/calc-wind", tags=["Calculators"], summary="Wind load (SP 20.13330)")
async def api_calc_wind(request: Request, data: dict):
    """Расчёт ветровой нагрузки по СП 20.13330.2016."""
    try:
        # Check cache
        cache_key = _make_key("calc_wind", **data)
        cached = await cache_get(cache_key)
        if cached:
            return json.loads(cached)

        wind_region = data.get("wind_region", "III")
        terrain = data.get("terrain", "B")
        height_m = float(data.get("height_m", 36))
        building_width_m = float(data.get("building_width_m", 20))
        building_height_m = float(data.get("building_height_m", 50))
        panel_width_m = float(data.get("panel_width_m", 1.5))
        panel_height_m = float(data.get("panel_height_m", 2.1))
        zone = data.get("zone", "mid")  # "mid", "corner", "leeward"

        w0 = WIND_PRESSURE_BASE.get(wind_region, 0.38)  # kPa
        kz = round(_interpolate_kz(height_m, terrain), 3)

        # Aerodynamic coefficient per SP 20
        if zone == "corner":
            ce = -1.4
        elif zone == "leeward":
            ce = -0.6
        else:
            ce = 0.8

        # Safety factor for wind load (gamma_f)
        gamma_f = 1.4

        # Wind pressure on the panel
        wind_pressure_kpa = w0 * kz * abs(ce) * gamma_f
        wind_pressure_pa = round(wind_pressure_kpa * 1000, 1)
        wind_pressure_kgm2 = round(wind_pressure_pa / 9.81, 1)

        # Panel area and distributed load
        panel_area_m2 = panel_width_m * panel_height_m
        panel_load_n = round(wind_pressure_pa * panel_area_m2, 1)

        # Required moment of inertia for deflection limit L/300
        # For simply supported beam: I_req = 5 * q * L^4 / (384 * E * f_max)
        # q = wind_pressure_pa * panel_width_m [N/m]
        # L = panel_height_m [m]
        # E = 70000 MPa for aluminum
        # f_max = L / 300
        q_nm = wind_pressure_pa * panel_width_m  # N/m
        span_m = panel_height_m
        e_mpa = 70000  # aluminum Young's modulus
        f_max_m = span_m / 300
        if f_max_m > 0 and e_mpa > 0:
            # I_req in m^4
            i_req_m4 = (5 * q_nm * span_m ** 4) / (384 * e_mpa * 1e6 * f_max_m)
            # Convert to cm^4
            required_ix_cm4 = round(i_req_m4 * 1e8, 2)
        else:
            required_ix_cm4 = 0

        await log_activity("calc_wind", f"Район {wind_region}, h={height_m}м",
                     f"P={wind_pressure_pa} Па, F={panel_load_n} Н")

        result = {
            "status": "ok",
            "w0": w0,
            "w0_pa": round(w0 * 1000),
            "kz": kz,
            "ce": ce,
            "gamma_f": gamma_f,
            "wind_pressure_pa": wind_pressure_pa,
            "wind_pressure_kgm2": wind_pressure_kgm2,
            "panel_area_m2": round(panel_area_m2, 2),
            "panel_load_n": panel_load_n,
            "required_ix_cm4": required_ix_cm4,
            "safety_factor": gamma_f,
            "height_m": height_m,
            "terrain": terrain,
            "zone": zone,
            "wind_region": wind_region,
        }

        await cache_set(cache_key, json.dumps(result, default=str))
        return result

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== F10. КАЛЬКУЛЯТОР ВЕСА СТВОРКИ ==============

def _parse_glass_formula(formula: str) -> dict:
    """Парсинг формулы стеклопакета, напр. '4-16Ar-4-16Ar-4'."""
    parts = re.split(r'[-]', formula.strip())
    glass_thicknesses = []
    total_thickness_mm = 0
    for p in parts:
        p = p.strip()
        # Check if it's a glass layer (pure number or number + letter like 4M1)
        m = re.match(r'^(\d+(?:\.\d+)?)\s*(?:M\d*|ESG|VSG|TVG)?$', p, re.IGNORECASE)
        if m:
            t = float(m.group(1))
            glass_thicknesses.append(t)
            total_thickness_mm += t
        else:
            # It's a spacer/gap (e.g., 16Ar, 20, 16Kr)
            m2 = re.match(r'^(\d+(?:\.\d+)?)', p)
            if m2:
                total_thickness_mm += float(m2.group(1))
    return {
        "glass_thicknesses": glass_thicknesses,
        "total_thickness_mm": total_thickness_mm,
    }


# Max sash weight limits by system
_SASH_WEIGHT_LIMITS = {
    "Reynaers MasterLine 8": 160,
    "Reynaers CS 77": 130,
    "Schüco AWS 75": 130,
    "Schüco AWS 90": 150,
    "Schüco ASS 77 PD": 200,
    "Alutech W72": 100,
    "Alutech W62": 80,
    "Alutech ALT F50": 120,
    "TATPROF ТП-50": 80,
    "TATPROF ТП-65": 100,
}


@limiter.limit("30/minute")
@app.post("/api/calc-sash-weight", tags=["Calculators"], summary="Sash weight calculation")
async def api_calc_sash_weight(request: Request, data: dict):
    """Расчёт веса створки."""
    try:
        # Check cache
        cache_key = _make_key("calc_sash", **data)
        cached = await cache_get(cache_key)
        if cached:
            return json.loads(cached)

        width_mm = float(data.get("width_mm", 800))
        height_mm = float(data.get("height_mm", 1400))
        profile_weight_kg_m = float(data.get("profile_weight_kg_m", 1.8))
        glass_formula = data.get("glass_formula", "4-16Ar-4-16Ar-4")
        hardware_weight_kg = float(data.get("hardware_weight_kg", 2.5))

        # Frame perimeter and profile weight
        perimeter_m = 2 * (width_mm + height_mm) / 1000.0
        profile_weight = round(perimeter_m * profile_weight_kg_m, 2)

        # Glass weight
        parsed = _parse_glass_formula(glass_formula)
        frame_rebate_mm = 65  # typical frame rebate
        glass_w = max(0, width_mm - 2 * frame_rebate_mm)
        glass_h = max(0, height_mm - 2 * frame_rebate_mm)
        glass_area_m2 = (glass_w * glass_h) / 1e6

        # Glass density: 2.5 kg/m2 per mm of glass thickness
        total_glass_thickness = sum(parsed["glass_thicknesses"])
        glass_weight = round(glass_area_m2 * total_glass_thickness * 2.5, 2)

        total_weight = round(profile_weight + glass_weight + hardware_weight_kg, 2)

        # Check against limits
        max_allowed = {}
        warnings = []
        for system, limit in _SASH_WEIGHT_LIMITS.items():
            max_allowed[system] = limit
            if total_weight > limit:
                warnings.append(f"Превышен лимит {system}: {total_weight} кг > {limit} кг")

        # General warnings
        if total_weight > 130:
            warnings.insert(0, "Вес створки выше 130 кг — требуется усиленная фурнитура")
        if glass_area_m2 > 3.0:
            warnings.append(f"Площадь остекления {glass_area_m2:.2f} м² — проверьте допуски стеклопакета")

        await log_activity("calc_sash_weight", f"{width_mm}x{height_mm}",
                     f"Вес: {total_weight} кг, стекло: {glass_formula}")

        result = {
            "status": "ok",
            "profile_weight": profile_weight,
            "glass_weight": glass_weight,
            "hardware_weight": hardware_weight_kg,
            "total_weight": total_weight,
            "perimeter_m": round(perimeter_m, 2),
            "glass_area_m2": round(glass_area_m2, 2),
            "glass_thicknesses": parsed["glass_thicknesses"],
            "glass_unit_thickness_mm": parsed["total_thickness_mm"],
            "max_allowed": max_allowed,
            "warnings": warnings,
        }

        await cache_set(cache_key, json.dumps(result, default=str))
        return result

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== F11. КАЛЬКУЛЯТОР СТЕКЛОПАКЕТОВ ==============

_GLASS_DATABASE = [
    {"formula": "4-16Ar-4", "ug": 1.1, "rw": 30, "thickness": 24, "max_w": 2500, "max_h": 3500},
    {"formula": "4-16-4", "ug": 1.4, "rw": 29, "thickness": 24, "max_w": 2500, "max_h": 3500},
    {"formula": "4-12Ar-4-12Ar-4", "ug": 0.8, "rw": 32, "thickness": 36, "max_w": 2400, "max_h": 3200},
    {"formula": "4-16Ar-4-16Ar-4", "ug": 0.7, "rw": 34, "thickness": 44, "max_w": 2200, "max_h": 3000},
    {"formula": "6-16Ar-4-16Ar-4", "ug": 0.7, "rw": 36, "thickness": 46, "max_w": 2200, "max_h": 3000},
    {"formula": "6-16Ar-6-16Ar-6", "ug": 0.6, "rw": 38, "thickness": 50, "max_w": 2000, "max_h": 2800},
    {"formula": "6-20Ar-4-20Ar-6", "ug": 0.5, "rw": 40, "thickness": 56, "max_w": 2000, "max_h": 2800},
    {"formula": "8-16Ar-6-16Ar-8", "ug": 0.5, "rw": 42, "thickness": 54, "max_w": 1800, "max_h": 2500},
    {"formula": "4-10-4-10-4", "ug": 1.2, "rw": 30, "thickness": 32, "max_w": 2400, "max_h": 3200},
    {"formula": "6-12Ar-4-12Ar-6", "ug": 0.7, "rw": 36, "thickness": 40, "max_w": 2200, "max_h": 3000},
    {"formula": "8-12Ar-8", "ug": 1.0, "rw": 35, "thickness": 28, "max_w": 2200, "max_h": 3000},
    {"formula": "8-20Ar-8-20Ar-8", "ug": 0.5, "rw": 44, "thickness": 64, "max_w": 1600, "max_h": 2200},
    {"formula": "6-14Ar-4-14Ar-6", "ug": 0.6, "rw": 37, "thickness": 44, "max_w": 2200, "max_h": 3000},
    {"formula": "4-16Kr-4-16Kr-4", "ug": 0.6, "rw": 34, "thickness": 44, "max_w": 2200, "max_h": 3000},
    {"formula": "10-16Ar-6-16Ar-10", "ug": 0.5, "rw": 46, "thickness": 58, "max_w": 1600, "max_h": 2200},
    {"formula": "33.1-16Ar-4-16Ar-4", "ug": 0.7, "rw": 38, "thickness": 47, "max_w": 2000, "max_h": 2800},
    {"formula": "44.1-16Ar-4-16Ar-44.1", "ug": 0.6, "rw": 42, "thickness": 57, "max_w": 1800, "max_h": 2500},
]


@limiter.limit("30/minute")
@app.post("/api/calc-glass", tags=["Calculators"], summary="Glass package selection")
async def api_calc_glass(request: Request, data: dict):
    """Подбор оптимального стеклопакета по параметрам."""
    try:
        # Check cache
        cache_key = _make_key("calc_glass", **data)
        cached = await cache_get(cache_key)
        if cached:
            return json.loads(cached)

        width_mm = int(data.get("width_mm", 1200))
        height_mm = int(data.get("height_mm", 1800))
        wind_pressure_pa = float(data.get("wind_pressure_pa", 800))
        thermal_required_ug = float(data.get("thermal_required_ug", 1.0))
        sound_required_db = int(data.get("sound_required_db", 38))
        safety_required = bool(data.get("safety_required", False))

        recommendations = []
        for g in _GLASS_DATABASE:
            score = 0
            pros = []
            cons = []

            # 1. Thermal score (30 pts)
            if g["ug"] <= thermal_required_ug:
                thermal_score = 30
                pros.append(f"Ug={g['ug']} — соответствует требованию ({thermal_required_ug})")
            elif g["ug"] <= thermal_required_ug * 1.2:
                thermal_score = 15
                cons.append(f"Ug={g['ug']} — близко к требованию ({thermal_required_ug})")
            else:
                thermal_score = 0
                cons.append(f"Ug={g['ug']} — не соответствует ({thermal_required_ug})")
            score += thermal_score

            # 2. Sound score (25 pts)
            if g["rw"] >= sound_required_db:
                sound_score = 25
                pros.append(f"Rw={g['rw']} дБ — соответствует ({sound_required_db} дБ)")
            elif g["rw"] >= sound_required_db - 3:
                sound_score = 12
                cons.append(f"Rw={g['rw']} дБ — незначительно ниже ({sound_required_db} дБ)")
            else:
                sound_score = 0
                cons.append(f"Rw={g['rw']} дБ — не соответствует ({sound_required_db} дБ)")
            score += sound_score

            # 3. Wind resistance by thickness (20 pts)
            # Thicker glass = better wind resistance
            total_glass = sum(float(x) for x in re.findall(r'(?:^|-)(\d+)(?:\.\d+)?(?:$|-)', g["formula"]))
            if wind_pressure_pa <= 600:
                wind_score = 20 if total_glass >= 8 else 15 if total_glass >= 6 else 10
            elif wind_pressure_pa <= 1000:
                wind_score = 20 if total_glass >= 12 else 15 if total_glass >= 10 else 5
            else:
                wind_score = 20 if total_glass >= 16 else 10 if total_glass >= 12 else 0
            score += wind_score
            if wind_score >= 15:
                pros.append("Достаточная ветровая стойкость")

            # 4. Size compatibility (15 pts)
            if width_mm <= g["max_w"] and height_mm <= g["max_h"]:
                score += 15
                pros.append(f"Размер в пределах допуска ({g['max_w']}x{g['max_h']})")
            elif width_mm <= g["max_w"] * 1.1 and height_mm <= g["max_h"] * 1.1:
                score += 5
                cons.append("Размер на границе допуска — требуется проверка")
            else:
                cons.append(f"Превышен макс. размер ({g['max_w']}x{g['max_h']} мм)")

            # 5. Weight/practicality (10 pts)
            if g["thickness"] <= 44:
                score += 10
                pros.append("Стандартная монтажная ширина")
            elif g["thickness"] <= 56:
                score += 5
                cons.append("Увеличенная монтажная ширина")
            else:
                cons.append("Требуется широкий профиль (60+ мм)")

            # Safety check
            if safety_required:
                is_safety = "33.1" in g["formula"] or "44.1" in g["formula"] or "55.1" in g["formula"]
                if is_safety:
                    score += 10
                    pros.append("Триплекс/закалённое — безопасное стекло")
                else:
                    score -= 10
                    cons.append("Не содержит безопасного стекла (триплекс/закалённое)")

            recommendations.append({
                "formula": g["formula"],
                "thickness_mm": g["thickness"],
                "ug": g["ug"],
                "rw_db": g["rw"],
                "score": max(0, min(100, score)),
                "pros": pros,
                "cons": cons,
            })

        recommendations.sort(key=lambda x: x["score"], reverse=True)

        warnings = []
        if width_mm > 2500 or height_mm > 3500:
            warnings.append("При размерах более 2500x3500 мм требуется индивидуальный расчёт стеклопакета")
        if safety_required:
            warnings.append("Для безопасного остекления рекомендуется триплекс (33.1, 44.1) или закалённое стекло ESG")
        if wind_pressure_pa > 1200:
            warnings.append("При ветровом давлении > 1200 Па рекомендуется утолщённое стекло (8+ мм)")

        await log_activity("calc_glass", f"{width_mm}x{height_mm}",
                     f"Лучшее: {recommendations[0]['formula']} (score={recommendations[0]['score']})")

        result = {
            "status": "ok",
            "recommendations": recommendations[:8],
            "total_variants": len(_GLASS_DATABASE),
            "warnings": warnings,
            "params": {
                "width_mm": width_mm,
                "height_mm": height_mm,
                "wind_pressure_pa": wind_pressure_pa,
                "thermal_required_ug": thermal_required_ug,
                "sound_required_db": sound_required_db,
                "safety_required": safety_required,
            },
        }

        await cache_set(cache_key, json.dumps(result, default=str))
        return result

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== F12. КАЛЬКУЛЯТОР КРЕПЕЖА ==============

_ANCHOR_CAPACITY = {
    "бетон": {"capacity_kn": 8.0, "anchor": "рамный 10x132", "min_depth_mm": 80},
    "кирпич": {"capacity_kn": 5.0, "anchor": "рамный 10x152", "min_depth_mm": 100},
    "газобетон": {"capacity_kn": 2.0, "anchor": "специальный для газобетона 10x160", "min_depth_mm": 120},
    "пустотелый кирпич": {"capacity_kn": 3.5, "anchor": "химический анкер + шпилька M10", "min_depth_mm": 110},
    "дерево": {"capacity_kn": 4.0, "anchor": "шуруп по дереву 7.5x132", "min_depth_mm": 80},
}


@limiter.limit("30/minute")
@app.post("/api/calc-fasteners", tags=["Calculators"], summary="Fastener calculation (GOST 30971)")
async def api_calc_fasteners(request: Request, data: dict):
    """Расчёт крепежа оконной/дверной рамы по ГОСТ."""
    try:
        # Check cache
        cache_key = _make_key("calc_fasteners", **data)
        cached = await cache_get(cache_key)
        if cached:
            return json.loads(cached)

        frame_width_mm = float(data.get("frame_width_mm", 1500))
        frame_height_mm = float(data.get("frame_height_mm", 2100))
        weight_kg = float(data.get("weight_kg", 85))
        wind_pressure_pa = float(data.get("wind_pressure_pa", 600))
        wall_type = data.get("wall_type", "бетон")
        anchor_type = data.get("anchor_type", "рамный")

        # Perimeter in mm
        perimeter_mm = 2 * (frame_width_mm + frame_height_mm)
        # Max spacing 700mm per GOST 30971
        max_spacing_mm = 700
        # Min anchors = perimeter / max_spacing, but also min 2 per side
        n_from_spacing = math.ceil(perimeter_mm / max_spacing_mm)
        # At least 2 per side (corner anchors at 150-200mm from corner)
        n_min_sides = 2 * 2 + 2 * max(2, math.ceil(frame_width_mm / max_spacing_mm))
        total_anchors = max(n_from_spacing, n_min_sides, 4)

        actual_spacing = round(perimeter_mm / total_anchors, 0)

        # Frame area
        frame_area_m2 = (frame_width_mm * frame_height_mm) / 1e6

        # Forces
        wind_force_n = wind_pressure_pa * frame_area_m2
        gravity_force_n = weight_kg * 9.81
        safety_factor = 1.5

        # Total design force (vector sum approximation)
        total_force_n = math.sqrt(wind_force_n ** 2 + gravity_force_n ** 2) * safety_factor
        force_per_anchor_n = round(total_force_n / total_anchors, 1)

        # Anchor capacity
        wall_info = _ANCHOR_CAPACITY.get(wall_type, _ANCHOR_CAPACITY["бетон"])
        anchor_capacity_n = wall_info["capacity_kn"] * 1000  # kN to N

        safety_margin = round(anchor_capacity_n / force_per_anchor_n, 2) if force_per_anchor_n > 0 else 99.0

        warnings = []
        if safety_margin < 1.0:
            warnings.append(f"ВНИМАНИЕ: Нагрузка на анкер ({force_per_anchor_n:.0f} Н) превышает допуск ({anchor_capacity_n:.0f} Н)!")
            warnings.append("Увеличьте количество анкеров или используйте более мощный тип")
        elif safety_margin < 1.5:
            warnings.append("Запас прочности менее 1.5 — рекомендуется увеличить количество анкеров")

        if wall_type == "газобетон":
            warnings.append("Для газобетона рекомендуется использовать химические анкеры для повышенной надёжности")
        if weight_kg > 100:
            warnings.append("При весе конструкции > 100 кг обязательно использование нижних опорных подкладок")
        if frame_height_mm > 2500:
            warnings.append("При высоте рамы > 2.5 м рекомендуется дополнительное промежуточное крепление")

        await log_activity("calc_fasteners", f"{frame_width_mm}x{frame_height_mm}, {wall_type}",
                     f"Анкеров: {total_anchors}, запас: {safety_margin}x")

        result = {
            "status": "ok",
            "total_anchors": total_anchors,
            "spacing_mm": actual_spacing,
            "force_per_anchor_n": force_per_anchor_n,
            "anchor_capacity_n": anchor_capacity_n,
            "safety_margin": safety_margin,
            "recommended_anchor": wall_info["anchor"],
            "min_embed_depth_mm": wall_info["min_depth_mm"],
            "wind_force_n": round(wind_force_n, 1),
            "gravity_force_n": round(gravity_force_n, 1),
            "total_design_force_n": round(total_force_n, 1),
            "wall_type": wall_type,
            "wall_type_warnings": warnings,
            "frame_area_m2": round(frame_area_m2, 2),
        }

        await cache_set(cache_key, json.dumps(result, default=str))
        return result

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== AI HELPER ==============

async def _call_llm(messages: list[dict], model: str = DEFAULT_LLM_MODEL, max_tokens: int = 4000) -> str:
    """Call OpenRouter API and return the response text."""
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=503, detail="OpenRouter API key не настроен. Добавьте OPENROUTER_API_KEY в .env")
    async with httpx.AsyncClient(timeout=120.0) as client:
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
        return data["choices"][0]["message"]["content"]


def _pdf_pages_to_base64(pdf_path: str, max_pages: int = 3) -> list[str]:
    """Render first N pages of a PDF to base64-encoded PNG images."""
    import fitz
    doc = fitz.open(pdf_path)
    images = []
    for i in range(min(max_pages, len(doc))):
        page = doc[i]
        pixmap = page.get_pixmap(dpi=150)
        img_b64 = base64.b64encode(pixmap.tobytes("png")).decode()
        images.append(img_b64)
    doc.close()
    return images


# ============== F1: AI DRAWING REVIEW ==============

@limiter.limit("10/minute")
@app.post("/api/ai-review", tags=["AI Tools"], summary="AI review of KMD drawing")
async def api_ai_review(request: Request, file: UploadFile = File(...)):
    """AI review of a KMD drawing PDF with RAG-powered validation."""
    path = save_upload(file)
    try:
        text = extract_text_from_pdf(str(path))
        images_b64 = _pdf_pages_to_base64(str(path), max_pages=3)

        # RAG: get relevant context from knowledge base
        rag_context = ""
        try:
            rag_context = await build_rag_context(
                query=text[:500],
                max_tokens=2000,
                top_k=6,
            )
        except Exception:
            pass  # Graceful degradation if Pinecone unavailable

        # RAG: validate articles found in document
        articles = kmd_extract_articles(text)
        articles_report = ""
        if articles:
            try:
                validations = await validate_articles_batch(articles[:20])
                invalid = [v for v in validations if not v.get("valid")]
                if invalid:
                    articles_report = "\n\nПРОВЕРКА АРТИКУЛОВ ПО БАЗЕ ДАННЫХ:\n"
                    for v in invalid:
                        articles_report += f"- Артикул {v['article_code']}: {v['description'][:100]}\n"
            except Exception:
                pass

        content_parts = [
            {
                "type": "text",
                "text": (
                    "Ты эксперт по КМД алюминиевых конструкций. Проанализируй этот чертёж и найди:\n"
                    "1. Пропущенные размеры\n"
                    "2. Ошибки маркировки позиций\n"
                    "3. Несоответствия артикулов\n"
                    "4. Отсутствующие узлы или сечения\n"
                    "5. Проблемы с оформлением по ГОСТ 21.502\n\n"
                    "Дай структурированный ответ с категориями: критические ошибки, предупреждения, рекомендации.\n\n"
                    f"{rag_context}\n"
                    f"{articles_report}\n"
                    f"Извлечённый текст из PDF:\n{text[:3000]}"
                ),
            }
        ]
        for img_b64 in images_b64:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_b64}"},
            })

        messages = [{"role": "user", "content": content_parts}]
        model = DEFAULT_LLM_MODEL
        review_text = await _call_llm(messages, model=model, max_tokens=4000)

        await log_activity("ai_review", file.filename or "unknown.pdf", "AI ревью чертежа")
        return {"status": "ok", "review_text": review_text, "model_used": model}

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"OpenRouter API error: {e.response.status_code} — {e.response.text[:300]}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path.unlink(missing_ok=True)


# ============== F2: AI EXPLANATORY NOTE GENERATOR ==============

@limiter.limit("10/minute")
@app.post("/api/ai-generate-note", tags=["AI Tools"], summary="AI engineering note generation")
async def api_ai_generate_note(request: Request, file: UploadFile = File(...)):
    """AI-generated explanatory note (пояснительная записка) from a KMD PDF."""
    path = save_upload(file)
    try:
        text = extract_text_from_pdf(str(path))
        images_b64 = _pdf_pages_to_base64(str(path), max_pages=3)

        content_parts = [
            {
                "type": "text",
                "text": (
                    "Ты эксперт по КМД алюминиевых конструкций. На основе данных чертежа "
                    "сгенерируй полную пояснительную записку (ПЗ) по ГОСТ. Включи:\n"
                    "1. Наименование объекта, заказчик (извлеки из чертежа)\n"
                    "2. Состав документации\n"
                    "3. Указания по монтажу\n"
                    "4. Материалы и профильная система\n"
                    "5. Требования к качеству\n"
                    "6. Требования безопасности\n\n"
                    "Используй формальный стиль, соответствующий ГОСТ 21.502.\n\n"
                    f"Извлечённый текст из PDF:\n{text[:4000]}"
                ),
            }
        ]
        for img_b64 in images_b64:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_b64}"},
            })

        messages = [{"role": "user", "content": content_parts}]
        model = DEFAULT_LLM_MODEL
        note_text = await _call_llm(messages, model=model, max_tokens=6000)

        await log_activity("ai_note", file.filename or "unknown.pdf", "AI пояснительная записка")
        return {"status": "ok", "note_text": note_text, "model_used": model}

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"OpenRouter API error: {e.response.status_code} — {e.response.text[:300]}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path.unlink(missing_ok=True)


# ============== F3: AI GOST ASSISTANT ==============

@limiter.limit("10/minute")
@app.post("/api/ai-gost", tags=["AI Tools"], summary="AI GOST/standard consultant")
async def api_ai_gost(request: Request, payload: dict):
    """AI GOST assistant — answers questions about norms and standards for aluminum constructions."""
    question = payload.get("question", "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Вопрос не может быть пустым")

    try:
        # RAG: get relevant GOST context from knowledge base
        rag_context = ""
        try:
            rag_context = await build_rag_context(
                query=question,
                namespaces=["gost-standards", "kmd-formatting-rules"],
                max_tokens=2000,
                top_k=8,
            )
        except Exception:
            pass

        system_prompt = (
            "Ты — эксперт-консультант по нормативной документации для алюминиевых конструкций (КМД). "
            "Отвечай точно, со ссылками на конкретные пункты следующих нормативов:\n"
            "- ГОСТ 21.502-2016 (правила выполнения рабочей документации)\n"
            "- ГОСТ 21519-2022 (окна и двери из алюминиевых сплавов)\n"
            "- ГОСТ 23166-2021 (блоки оконные, общие ТУ)\n"
            "- СП 426.1325800.2018 (конструкции из алюминия)\n"
            "- СП 50.13330 (тепловая защита)\n"
            "- СП 20.13330 (нагрузки и воздействия)\n"
            "- ГОСТ 30674 (блоки оконные из ПВХ)\n"
            "- ГОСТ 24700 (блоки оконные деревянные)\n"
            "- ГОСТ 22233-2018 (профили из алюминия)\n\n"
            "Всегда указывай номер пункта/раздела. Если вопрос выходит за рамки этих нормативов, "
            "укажи релевантный ГОСТ/СП и объясни, где искать ответ.\n\n"
            f"{rag_context}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]
        model = DEFAULT_LLM_MODEL
        answer = await _call_llm(messages, model=model, max_tokens=4000)

        # Extract referenced norms from the answer
        norm_patterns = [
            r'ГОСТ\s+[\d\.\-]+(?:\-\d{4})?',
            r'СП\s+[\d\.\-]+(?:\.\d+)?',
        ]
        norms = set()
        for pat in norm_patterns:
            for m in re.finditer(pat, answer):
                norms.add(m.group())

        await log_activity("ai_gost", "question", f"AI ГОСТ: {question[:50]}")
        return {
            "status": "ok",
            "answer": answer,
            "norms_referenced": sorted(norms),
            "model_used": model,
        }

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"OpenRouter API error: {e.response.status_code} — {e.response.text[:300]}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== F4: AI HARDWARE SELECTOR ==============

@limiter.limit("10/minute")
@app.post("/api/ai-hardware", tags=["AI Tools"], summary="AI hardware recommendation")
async def api_ai_hardware(request: Request, payload: dict):
    """AI hardware recommendation for aluminum constructions."""
    try:
        construction_type = payload.get("construction_type", "окно")
        profile_system = payload.get("profile_system", "Reynaers")
        sash_weight = payload.get("sash_weight_kg", 80)
        sash_width = payload.get("sash_width_mm", 800)
        sash_height = payload.get("sash_height_mm", 1400)
        opening_type = payload.get("opening_type", "поворотно-откидное")
        security_class = payload.get("security_class", "RC1")

        prompt = (
            f"Ты эксперт по фурнитуре для алюминиевых окон и дверей.\n\n"
            f"Подбери комплект фурнитуры для:\n"
            f"- Тип конструкции: {construction_type}\n"
            f"- Профильная система: {profile_system}\n"
            f"- Вес створки: {sash_weight} кг\n"
            f"- Размер створки: {sash_width}x{sash_height} мм\n"
            f"- Тип открывания: {opening_type}\n"
            f"- Класс безопасности: {security_class}\n\n"
            "Для каждого компонента укажи:\n"
            "1. Название компонента\n"
            "2. Конкретный артикул (Roto, Siegenia, Maco, GU, Winkhaus, Giesse, AGB)\n"
            "3. Производитель\n"
            "4. Причину выбора\n\n"
            "Ответ дай в формате JSON-массива: "
            '[{"component": "...", "article": "...", "manufacturer": "...", "reason": "..."}]\n'
            "После JSON-массива добавь общие рекомендации по монтажу фурнитуры."
        )

        messages = [{"role": "user", "content": prompt}]
        model = DEFAULT_LLM_MODEL
        raw = await _call_llm(messages, model=model, max_tokens=4000)

        # Try to extract JSON array from the response
        recommendations = []
        json_match = re.search(r'\[.*?\]', raw, re.DOTALL)
        if json_match:
            try:
                recommendations = json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        await log_activity("ai_hardware", "params", f"AI фурнитура: {construction_type} {profile_system}")
        return {
            "status": "ok",
            "recommendations": recommendations,
            "raw_text": raw,
            "model_used": model,
        }

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"OpenRouter API error: {e.response.status_code} — {e.response.text[:300]}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== F5: AI VISUAL DRAWING COMPARISON ==============

@limiter.limit("10/minute")
@app.post("/api/ai-compare-visual", tags=["AI Tools"], summary="AI visual drawing comparison")
async def api_ai_compare_visual(
    request: Request,
    file_a: UploadFile = File(...),
    file_b: UploadFile = File(...),
):
    """AI visual comparison of two KMD drawing PDFs."""
    path_a = save_upload(file_a)
    path_b = save_upload(file_b)
    try:
        images_a = _pdf_pages_to_base64(str(path_a), max_pages=3)
        images_b = _pdf_pages_to_base64(str(path_b), max_pages=3)

        text_a = extract_text_from_pdf(str(path_a))
        text_b = extract_text_from_pdf(str(path_b))

        content_parts = [
            {
                "type": "text",
                "text": (
                    "Сравни два чертежа КМД. Найди ВСЕ визуальные отличия:\n"
                    "- Изменённые размеры\n"
                    "- Добавленные/удалённые элементы\n"
                    "- Изменённые позиции\n"
                    "- Различия в узлах и сечениях\n"
                    "- Изменения в спецификации\n\n"
                    "Первый набор изображений — чертёж A, второй — чертёж B.\n\n"
                    f"Текст чертежа A:\n{text_a[:2000]}\n\n"
                    f"Текст чертежа B:\n{text_b[:2000]}"
                ),
            }
        ]
        for img in images_a:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img}"},
            })
        for img in images_b:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img}"},
            })

        messages = [{"role": "user", "content": content_parts}]
        model = DEFAULT_LLM_MODEL
        comparison_text = await _call_llm(messages, model=model, max_tokens=4000)

        await log_activity("ai_compare", f"{file_a.filename} vs {file_b.filename}", "AI сравнение чертежей")
        return {"status": "ok", "comparison_text": comparison_text, "model_used": model}

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"OpenRouter API error: {e.response.status_code} — {e.response.text[:300]}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path_a.unlink(missing_ok=True)
        path_b.unlink(missing_ok=True)


# ============== F6: AI KMD GENERATION ==============

@limiter.limit("10/minute")
@app.post("/api/ai-generate-kmd", tags=["AI Tools"], summary="AI KMD document generation")
async def api_ai_generate_kmd(request: Request, payload: dict):
    """AI generation of KMD documentation from a technical brief."""
    try:
        object_name = payload.get("object_name", "")
        customer = payload.get("customer", "")
        construction_type = payload.get("construction_type", "")
        profile_system = payload.get("profile_system", "")
        glass_formula = payload.get("glass_formula", "")
        color_ral = payload.get("color_ral", "")
        notes = payload.get("notes", "")
        positions = payload.get("positions", [])

        if not object_name or not positions:
            raise HTTPException(status_code=400, detail="Укажите название объекта и хотя бы одну позицию")

        positions_text = ""
        for p in positions:
            pos_line = f"  - {p.get('id', '?')}: тип={p.get('type', '?')}, {p.get('width', '?')}x{p.get('height', '?')} мм, кол-во={p.get('quantity', 1)}, открывание={p.get('opening', 'глухое')}"
            if p.get("handle_height"):
                pos_line += f", высота ручки={p['handle_height']} мм"
            positions_text += pos_line + "\n"

        user_brief = (
            f"Объект: {object_name}\n"
            f"Заказчик: {customer}\n"
            f"Тип конструкций: {construction_type}\n"
            f"Профильная система: {profile_system}\n"
            f"Формула стеклопакета: {glass_formula}\n"
            f"Цвет RAL: {color_ral}\n"
            f"Позиции:\n{positions_text}"
            f"Примечания: {notes}"
        )

        system_prompt = (
            "Ты ведущий инженер-конструктор КМД алюминиевых светопрозрачных конструкций с 20-летним опытом. "
            "Составь полный черновой комплект КМД документации на основании технического задания. "
            "Документ должен включать следующие разделы:\n\n"
            "1. ТИТУЛЬНЫЙ ЛИСТ — название объекта, заказчик, шифр проекта (сгенерируй), дата, стадия «Р» (рабочая документация)\n\n"
            "2. ПОЯСНИТЕЛЬНАЯ ЗАПИСКА:\n"
            "   - Основание для разработки\n"
            "   - Нормативные документы: ГОСТ 21.502-2016 (правила оформления КМД), ГОСТ 21519-2022 (окна и двери), "
            "СП 426.1325800.2018 (светопрозрачные конструкции), ГОСТ 30674-99, ГОСТ 30970-2014, "
            "СП 20.13330.2016 (нагрузки), СП 50.13330.2012 (теплозащита)\n"
            "   - Описание конструктивных решений\n"
            "   - Требования к материалам\n\n"
            "3. СПЕЦИФИКАЦИЯ ПРОФИЛЕЙ — таблица с артикулами выбранной профильной системы: "
            "рама, створка, импост, штапик, соединители, усилители. "
            "Укажи реальные артикулы для указанной системы если знаешь, иначе укажи типовые обозначения.\n\n"
            "4. ОПИСАНИЕ ПОЗИЦИЙ — для каждой позиции из ТЗ:\n"
            "   - Маркировка, размеры (ширина × высота)\n"
            "   - Тип открывания, высота ручки\n"
            "   - Формула стеклопакета\n"
            "   - Схема членения (текстовое описание)\n"
            "   - Особые требования\n\n"
            "5. ВЕДОМОСТЬ ЭЛЕМЕНТОВ — сводная таблица: позиция, наименование, артикул, длина, количество\n\n"
            "6. УКАЗАНИЯ ПО МОНТАЖУ:\n"
            "   - Последовательность монтажа\n"
            "   - Допуски по ГОСТ 30971-2012\n"
            "   - Требования к монтажным швам\n"
            "   - Крепление к проёму\n\n"
            "7. РЕКОМЕНДАЦИИ ПО КРЕПЕЖУ И ГЕРМЕТИЗАЦИИ:\n"
            "   - Тип и шаг анкерных креплений\n"
            "   - Герметики (наружный, внутренний)\n"
            "   - Пароизоляция и гидроизоляция монтажного шва\n\n"
            "Форматируй как готовый документ с чёткими заголовками разделов. "
            "Используй профессиональную терминологию КМД. Все размеры в мм."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_brief},
        ]
        model = DEFAULT_LLM_MODEL
        kmd_document = await _call_llm(messages, model=model, max_tokens=8000)

        await log_activity("ai_generate_kmd", object_name, f"AI генерация КМД ({len(positions)} позиций)")
        return {
            "status": "ok",
            "kmd_document": kmd_document,
            "positions_count": len(positions),
            "model_used": model,
        }

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"OpenRouter API error: {e.response.status_code} — {e.response.text[:300]}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== F7: AI KMD TRANSLATOR ==============

@limiter.limit("10/minute")
@app.post("/api/ai-translate", tags=["AI Tools"], summary="AI GOST/EN translation")
async def api_ai_translate(request: Request, payload: dict):
    """AI translation of KMD documentation between GOST and EN standards."""
    try:
        text = payload.get("text", "").strip()
        direction = payload.get("direction", "gost_to_en")

        if not text:
            raise HTTPException(status_code=400, detail="Введите текст для перевода")
        if direction not in ("gost_to_en", "en_to_gost"):
            raise HTTPException(status_code=400, detail="direction должен быть 'gost_to_en' или 'en_to_gost'")

        if direction == "gost_to_en":
            direction_instruction = (
                "Переведи документацию с русского на английский, заменив российские стандарты на европейские/международные аналоги."
            )
            standards_mapping = (
                "Используй следующую таблицу соответствия стандартов:\n"
                "- ГОСТ 21519-2022 (окна и двери алюминиевые) → EN 14351-1 (Windows and doors — Product standard)\n"
                "- ГОСТ 30674-99 (блоки оконные ПВХ) → EN 14351-1\n"
                "- ГОСТ 21.502-2016 (правила оформления КМД) → EN ISO 7200 (Technical product documentation)\n"
                "- СП 20.13330.2016 (нагрузки и воздействия) → EN 1991-1-4 (Eurocode 1: Wind actions)\n"
                "- СП 50.13330.2012 (теплозащита зданий) → EN ISO 10077-1 (Thermal transmittance of windows)\n"
                "- СП 426.1325800.2018 (светопрозрачные конструкции) → EN 13830 (Curtain walling)\n"
                "- ГОСТ 30970-2014 (соединения узловые) → EN 12412-2 (Thermal performance — Determination of Uf)\n"
                "- ГОСТ 30971-2012 (монтажные швы) → EN 1026 (Air permeability) + EN 1027 (Watertightness)\n"
                "- ГОСТ 111-2014 (стекло листовое) → EN 572-1 (Glass in building — Basic soda lime silicate)\n"
                "- ГОСТ 24866-2014 (стеклопакеты) → EN 1279 (Glass in building — Insulating glass units)\n"
                "- ГОСТ 30826-2014 (стекло многослойное) → EN ISO 12543 (Laminated glass)\n"
                "- ГОСТ 30698-2014 (стекло закалённое) → EN 12150-1 (Thermally toughened soda lime silicate safety glass)\n"
                "- СП 52.13330.2016 (естественное освещение) → EN 17037 (Daylight in buildings)\n"
                "- ГОСТ 21.501-2018 (правила оформления архитектурных чертежей) → EN ISO 4157 (Designation systems)\n"
                "- ГОСТ Р 56926-2016 (фурнитура) → EN 13126 (Hardware for windows)\n"
                "- ГОСТ 538-2014 (замки и защёлки) → EN 1303 (Cylinders for locks)\n"
                "- СП 112.13330.2011 (пожарная безопасность) → EN 13501-1 (Fire classification)\n"
            )
        else:
            direction_instruction = (
                "Переведи документацию с английского на русский, заменив европейские/международные стандарты на российские аналоги."
            )
            standards_mapping = (
                "Используй следующую таблицу соответствия стандартов:\n"
                "- EN 14351-1 (Windows and doors) → ГОСТ 21519-2022 (окна и двери алюминиевые)\n"
                "- EN ISO 7200 (Technical product documentation) → ГОСТ 21.502-2016 (правила оформления КМД)\n"
                "- EN 1991-1-4 (Eurocode 1: Wind actions) → СП 20.13330.2016 (нагрузки и воздействия)\n"
                "- EN ISO 10077-1 (Thermal transmittance) → СП 50.13330.2012 (теплозащита зданий)\n"
                "- EN 13830 (Curtain walling) → СП 426.1325800.2018 (светопрозрачные конструкции)\n"
                "- EN 12412-2 (Thermal performance Uf) → ГОСТ 30970-2014 (соединения узловые)\n"
                "- EN 1026 / EN 1027 (Air/Water permeability) → ГОСТ 30971-2012 (монтажные швы)\n"
                "- EN 572-1 (Basic soda lime silicate glass) → ГОСТ 111-2014 (стекло листовое)\n"
                "- EN 1279 (Insulating glass units) → ГОСТ 24866-2014 (стеклопакеты)\n"
                "- EN ISO 12543 (Laminated glass) → ГОСТ 30826-2014 (стекло многослойное)\n"
                "- EN 12150-1 (Toughened safety glass) → ГОСТ 30698-2014 (стекло закалённое)\n"
                "- EN 17037 (Daylight in buildings) → СП 52.13330.2016 (естественное освещение)\n"
                "- EN ISO 4157 (Designation systems) → ГОСТ 21.501-2018 (правила оформления)\n"
                "- EN 13126 (Hardware for windows) → ГОСТ Р 56926-2016 (фурнитура)\n"
                "- EN 1303 (Cylinders for locks) → ГОСТ 538-2014 (замки и защёлки)\n"
                "- EN 13501-1 (Fire classification) → СП 112.13330.2011 (пожарная безопасность)\n"
            )

        system_prompt = (
            "Ты эксперт-переводчик строительной документации КМД (конструкции из алюминиевых профилей). "
            f"{direction_instruction}\n\n"
            "Правила перевода:\n"
            "1. Замени все ссылки на стандарты на эквиваленты целевой системы\n"
            "2. Сохрани техническую терминологию: профили, артикулы, размеры\n"
            "3. Адаптируй единицы измерения если нужно (мм остаются мм)\n"
            "4. Сохрани структуру и форматирование документа\n"
            "5. Технические термины переводи точно: створка=sash, импост=mullion/transom, "
            "штапик=glazing bead, рама=frame, стеклопакет=insulated glass unit (IGU), "
            "фурнитура=hardware, уплотнитель=gasket/seal, откос=reveal, подоконник=window sill, "
            "отлив=drip cap/sill flashing, монтажный шов=installation joint, "
            "поворотно-откидное=tilt-and-turn, глухое=fixed, раздвижное=sliding\n\n"
            f"{standards_mapping}\n"
            "В конце ответа добавь раздел 'MAPPED STANDARDS:' со списком замён в формате:\n"
            "ORIGINAL_STANDARD → REPLACEMENT_STANDARD (по одной паре на строку)"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]
        model = DEFAULT_LLM_MODEL
        result_text = await _call_llm(messages, model=model, max_tokens=8000)

        # Parse mapped standards from the response
        standards_mapped = []
        if "MAPPED STANDARDS:" in result_text:
            parts = result_text.split("MAPPED STANDARDS:")
            translated_text = parts[0].strip()
            mapping_lines = parts[1].strip().split("\n")
            for line in mapping_lines:
                line = line.strip().lstrip("- ")
                if "→" in line or "->" in line:
                    sep = "→" if "→" in line else "->"
                    frm, to = line.split(sep, 1)
                    standards_mapped.append({"from": frm.strip(), "to": to.strip()})
        else:
            translated_text = result_text

        await log_activity("ai_translate", direction, f"AI перевод КМД ({direction})")
        return {
            "status": "ok",
            "translated_text": translated_text,
            "direction": direction,
            "standards_mapped": standards_mapped,
            "model_used": model,
        }

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"OpenRouter API error: {e.response.status_code} — {e.response.text[:300]}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== F13. KMD VERSIONING ==============

async def _load_versions_for_file(filename: str) -> list[dict]:
    """Load all versions of a file from DB."""
    async with async_session() as session:
        stmt = select(DocumentVersion).where(
            DocumentVersion.filename == filename
        ).order_by(DocumentVersion.version)
        result = await session.execute(stmt)
        return [
            {
                "version": v.version,
                "filename": v.filename,
                "stored_as": Path(v.file_path).name,
                "date": v.created_at.isoformat(timespec="seconds") if v.created_at else "",
                "text_hash": v.file_hash or "",
            }
            for v in result.scalars().all()
        ]


async def _load_all_versions() -> dict[str, list[dict]]:
    """Load all versions grouped by filename from DB."""
    async with async_session() as session:
        stmt = select(DocumentVersion).order_by(
            DocumentVersion.filename, DocumentVersion.version
        )
        result = await session.execute(stmt)
        grouped: dict[str, list[dict]] = {}
        for v in result.scalars().all():
            entry = {
                "version": v.version,
                "filename": v.filename,
                "stored_as": Path(v.file_path).name,
                "date": v.created_at.isoformat(timespec="seconds") if v.created_at else "",
                "text_hash": v.file_hash or "",
            }
            grouped.setdefault(v.filename, []).append(entry)
        return grouped


async def _save_version_to_db(filename: str, version_num: int, file_path: str, file_hash: str, project_id: int = None):
    """Save a new version entry to DB."""
    async with async_session() as session:
        entry = DocumentVersion(
            filename=filename,
            version=version_num,
            file_path=file_path,
            file_hash=file_hash,
            project_id=project_id,
        )
        session.add(entry)
        await session.commit()
        return entry


@app.post("/api/versioning/upload", tags=["Analytics & Projects"], summary="Upload document version")
async def api_versioning_upload(file: UploadFile = File(...)):
    """Upload a new version of a KMD document."""
    import fitz

    path = save_upload(file)
    try:
        original_name = Path(file.filename).name
        doc = fitz.open(str(path))
        page_count = len(doc)
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        doc.close()

        text_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()[:16]

        versions = await _load_versions_for_file(original_name)
        version_num = len(versions) + 1

        versioned_filename = f"v{version_num}_{uuid.uuid4().hex[:6]}_{original_name}"
        dest = VERSIONS_DIR / versioned_filename
        shutil.copy2(str(path), str(dest))

        await _save_version_to_db(
            filename=original_name,
            version_num=version_num,
            file_path=str(dest),
            file_hash=text_hash,
        )

        version_entry = {
            "version": version_num,
            "filename": original_name,
            "stored_as": versioned_filename,
            "date": datetime.now().isoformat(timespec="seconds"),
            "text_hash": text_hash,
            "page_count": page_count,
            "text_length": len(full_text),
        }

        await log_activity("versioning", original_name, f"Версия {version_num} загружена, {page_count} стр.")

        return {"status": "ok", "version": version_num, "entry": version_entry}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path.unlink(missing_ok=True)


@limiter.limit("30/minute")
@app.get("/api/versioning/history", tags=["Analytics & Projects"], summary="Get version history")
async def api_versioning_history(request: Request, filename: str = ""):
    """Return version history for a file or all files."""
    if filename:
        versions = await _load_versions_for_file(filename)
        return {"status": "ok", "filename": filename, "versions": versions}
    # Return all files with their versions
    db = await _load_all_versions()
    result = []
    for fname, versions in db.items():
        result.append({"filename": fname, "versions_count": len(versions), "versions": versions})
    return {"status": "ok", "files": result}


@app.get("/api/versioning/diff/{v1}/{v2}", tags=["Analytics & Projects"], summary="Diff two versions")
async def api_versioning_diff(v1: str, v2: str, filename: str = ""):
    """Compare text of two versions. v1 and v2 are version numbers."""
    import fitz

    if not filename:
        raise HTTPException(status_code=400, detail="Укажите filename параметр")

    versions = await _load_versions_for_file(filename)
    v1_num, v2_num = int(v1), int(v2)

    entry1 = next((v for v in versions if v["version"] == v1_num), None)
    entry2 = next((v for v in versions if v["version"] == v2_num), None)

    if not entry1 or not entry2:
        raise HTTPException(status_code=404, detail="Версия не найдена")

    def extract_text(stored_as):
        fp = VERSIONS_DIR / stored_as
        if not fp.exists():
            raise HTTPException(status_code=404, detail=f"Файл {stored_as} не найден")
        doc = fitz.open(str(fp))
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text

    text1 = extract_text(entry1["stored_as"])
    text2 = extract_text(entry2["stored_as"])

    lines1 = text1.splitlines(keepends=True)
    lines2 = text2.splitlines(keepends=True)

    diff = list(difflib.unified_diff(lines1, lines2,
                                      fromfile=f"v{v1_num} ({entry1['date']})",
                                      tofile=f"v{v2_num} ({entry2['date']})",
                                      lineterm=""))

    added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))

    return {
        "status": "ok",
        "v1": v1_num, "v2": v2_num, "filename": filename,
        "diff_text": "\n".join(diff),
        "lines_added": added,
        "lines_removed": removed,
        "hash_v1": entry1["text_hash"],
        "hash_v2": entry2["text_hash"],
        "identical": entry1["text_hash"] == entry2["text_hash"],
    }


# ============== F14. AUTO MATERIAL REQUISITION ==============

@app.post("/api/generate-requisition", tags=["Production"], summary="Generate material requisition")
async def api_generate_requisition(file: UploadFile = File(...)):
    """Extract articles from KMD PDF and generate material requisition XLSX."""
    import fitz
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    path = save_upload(file)
    try:
        doc = fitz.open(str(path))
        full_text = ""
        for page in doc:
            full_text += page.get_text() + "\n"
        doc.close()

        # Extract articles and quantities from the KMD text
        articles = []
        seen = {}

        # Pattern: article number (digits, possibly with dots/dashes), optional description, quantity
        patterns = [
            re.compile(r'(?:арт(?:икул)?\.?\s*[:\s]?\s*)(\d[\d\.\-]{3,})\s+(.{5,60}?)\s+(\d+(?:[.,]\d+)?)\s*(?:шт|м\.?п\.?|м\.?|пог|компл)', re.IGNORECASE),
            re.compile(r'(\d{5,})\s+(.{5,60}?)\s+(\d+(?:[.,]\d+)?)\s*(?:шт|м\.?п\.?|м\.?|пог|компл)', re.IGNORECASE),
            re.compile(r'(\d{5,})\s+(.{5,60}?)\s+(\d+(?:[.,]\d+)?)\s+(\d+(?:[.,]\d+)?)', re.IGNORECASE),
        ]

        for pat in patterns:
            for m in pat.finditer(full_text):
                art_num = m.group(1).strip()
                if art_num in seen:
                    continue
                desc = m.group(2).strip()
                qty_str = m.group(3).replace(",", ".")
                qty = float(qty_str)
                seen[art_num] = True

                # Try to detect length from description
                length_match = re.search(r'(\d{3,5})\s*мм', desc)
                length_mm = int(length_match.group(1)) if length_match else 0

                # Detect unit
                unit = "шт."
                if re.search(r'м\.?п\.?|пог', m.group(0), re.IGNORECASE):
                    unit = "м.п."

                articles.append({
                    "article": art_num,
                    "description": desc[:50],
                    "length_mm": length_mm,
                    "quantity": qty,
                    "unit": unit,
                    "note": "",
                })

        # If no articles found via regex, try simpler extraction
        if not articles:
            for line in full_text.split("\n"):
                m = re.match(r'^\s*(\d{4,})\s+(.+?)\s+(\d+(?:[.,]\d+)?)\s*$', line.strip())
                if m:
                    art_num = m.group(1)
                    if art_num not in seen:
                        seen[art_num] = True
                        articles.append({
                            "article": art_num,
                            "description": m.group(2).strip()[:50],
                            "length_mm": 0,
                            "quantity": float(m.group(3).replace(",", ".")),
                            "unit": "шт.",
                            "note": "",
                        })

        # Generate XLSX
        wb = Workbook()
        ws = wb.active
        ws.title = "Заявка на материалы"

        # Header styling
        header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="2A2A22", end_color="2A2A22", fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        thin_border = Border(
            left=Side(style="thin"), right=Side(style="thin"),
            top=Side(style="thin"), bottom=Side(style="thin"),
        )

        # Title row
        ws.merge_cells("A1:G1")
        ws["A1"] = f"Заявка на материалы — {file.filename}"
        ws["A1"].font = Font(name="Arial", size=14, bold=True)
        ws["A1"].alignment = Alignment(horizontal="center")

        ws.merge_cells("A2:G2")
        ws["A2"] = f"Дата: {datetime.now().strftime('%d.%m.%Y')}"
        ws["A2"].font = Font(name="Arial", size=10, italic=True)
        ws["A2"].alignment = Alignment(horizontal="center")

        # Headers
        headers = ["No п/п", "Артикул", "Наименование", "Длина мм", "Количество", "Ед.изм.", "Примечание"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = thin_border

        # Data rows
        total_qty = 0
        for i, art in enumerate(articles, 1):
            row = i + 4
            ws.cell(row=row, column=1, value=i).border = thin_border
            ws.cell(row=row, column=2, value=art["article"]).border = thin_border
            ws.cell(row=row, column=2).font = Font(name="Arial", size=10, bold=True)
            ws.cell(row=row, column=3, value=art["description"]).border = thin_border
            ws.cell(row=row, column=4, value=art["length_mm"] if art["length_mm"] > 0 else "").border = thin_border
            ws.cell(row=row, column=5, value=art["quantity"]).border = thin_border
            ws.cell(row=row, column=6, value=art["unit"]).border = thin_border
            ws.cell(row=row, column=7, value=art["note"]).border = thin_border
            total_qty += art["quantity"]

        # Summary row
        summary_row = len(articles) + 5
        ws.merge_cells(f"A{summary_row}:C{summary_row}")
        ws.cell(row=summary_row, column=1, value="ИТОГО:").font = Font(name="Arial", size=11, bold=True)
        ws.cell(row=summary_row, column=1).border = thin_border
        ws.cell(row=summary_row, column=4).border = thin_border
        ws.cell(row=summary_row, column=5, value=total_qty).font = Font(name="Arial", size=11, bold=True)
        ws.cell(row=summary_row, column=5).border = thin_border
        ws.cell(row=summary_row, column=6).border = thin_border
        ws.cell(row=summary_row, column=7).border = thin_border

        # Auto-width
        col_widths = [8, 15, 40, 12, 12, 10, 20]
        for i, w in enumerate(col_widths, 1):
            ws.column_dimensions[chr(64 + i)].width = w

        result_name = f"requisition_{uuid.uuid4().hex[:8]}.xlsx"
        result_path = RESULTS_DIR / result_name
        wb.save(str(result_path))

        await log_activity("requisition", file.filename, f"Найдено {len(articles)} артикулов")

        return {
            "status": "ok",
            "articles_count": len(articles),
            "articles": articles,
            "total_quantity": total_qty,
            "download": f"/api/download/{result_name}",
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        path.unlink(missing_ok=True)


# ============== F15. PROJECT TRACKER ==============


def _project_to_dict(p: ProjectModel) -> dict:
    """Convert a ProjectModel ORM instance to a frontend-compatible dict."""
    extra = p.stages or {}
    return {
        "id": p.id,
        "name": p.name,
        "customer": p.customer or "",
        "address": p.address or "",
        "positions_count": extra.get("positions_count", 0),
        "deadline": extra.get("deadline", ""),
        "status": p.status,
        "status_index": PROJECT_STAGES.index(p.status) if p.status in PROJECT_STAGES else 0,
        "created_at": p.created_at.isoformat(timespec="seconds") if p.created_at else "",
        "status_history": extra.get("status_history", []),
    }


@app.post("/api/projects/create", tags=["Analytics & Projects"], summary="Create project")
async def api_project_create(data: dict):
    """Create a new project."""
    required = ["name", "customer", "address", "positions_count", "deadline"]
    for field in required:
        if field not in data:
            raise HTTPException(status_code=400, detail=f"Поле '{field}' обязательно")

    now_ts = datetime.now().isoformat(timespec="seconds")
    status_history = [{"stage": PROJECT_STAGES[0], "timestamp": now_ts}]

    db_project = ProjectModel(
        name=data["name"],
        customer=data["customer"],
        address=data["address"],
        status=PROJECT_STAGES[0],
        stages={
            "positions_count": int(data["positions_count"]),
            "deadline": data["deadline"],
            "status_history": status_history,
        },
    )

    async with async_session() as session:
        session.add(db_project)
        await session.commit()
        await session.refresh(db_project)

    project = _project_to_dict(db_project)

    # Update in-memory cache for backward compat
    projects_list.insert(0, project)
    if len(projects_list) > 500:
        projects_list.pop()
    await log_activity("projects", data["name"], f"Проект создан: {data['customer']}")
    return {"status": "ok", "project": project}


@limiter.limit("30/minute")
@app.get("/api/projects/list", tags=["Analytics & Projects"], summary="List all projects")
async def api_projects_list(request: Request):
    """Return all projects with statuses."""
    async with async_session() as session:
        result = await session.execute(
            select(ProjectModel).order_by(ProjectModel.created_at.desc())
        )
        db_projects = result.scalars().all()

    projects = [_project_to_dict(p) for p in db_projects]

    # Sync in-memory cache
    projects_list.clear()
    projects_list.extend(projects)

    return {"status": "ok", "projects": projects, "stages": PROJECT_STAGES}


@app.post("/api/projects/{project_id}/update-status", tags=["Analytics & Projects"], summary="Update project status")
async def api_project_update_status(project_id: int):
    """Move project to next stage."""
    async with async_session() as session:
        db_project = await session.get(ProjectModel, project_id)
        if not db_project:
            raise HTTPException(status_code=404, detail="Проект не найден")

        current_idx = PROJECT_STAGES.index(db_project.status) if db_project.status in PROJECT_STAGES else 0
        if current_idx >= len(PROJECT_STAGES) - 1:
            return {"status": "ok", "message": "Проект уже завершён", "project": _project_to_dict(db_project)}

        next_idx = current_idx + 1
        db_project.status = PROJECT_STAGES[next_idx]

        stages_data = dict(db_project.stages or {})  # copy to ensure new identity
        history = list(stages_data.get("status_history", []))
        history.append({
            "stage": PROJECT_STAGES[next_idx],
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        stages_data["status_history"] = history
        db_project.stages = stages_data  # new dict = triggers SQLAlchemy change detection

        await session.commit()
        await session.refresh(db_project)

    project = _project_to_dict(db_project)

    # Update in-memory cache
    for i, p in enumerate(projects_list):
        if p.get("id") == project_id:
            projects_list[i] = project
            break

    await log_activity("projects", project["name"], f"Статус: {PROJECT_STAGES[next_idx]}")
    return {"status": "ok", "project": project}


# ============== F16. ACT GENERATOR (KC-2) ==============

@app.post("/api/generate-act", tags=["Production"], summary="Generate acceptance act")
async def api_generate_act(data: dict):
    """Generate KS-2 style act document."""
    from docx import Document
    from docx.shared import Pt, Cm, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT

    required = ["project_name", "customer", "contract_number", "contract_date", "works", "executor_name", "executor_position"]
    for field in required:
        if field not in data:
            raise HTTPException(status_code=400, detail=f"Поле '{field}' обязательно")

    works = data["works"]
    if not works or len(works) == 0:
        raise HTTPException(status_code=400, detail="Добавьте хотя бы одну работу")

    # Generate act text
    total_sum = sum(w.get("quantity", 0) * w.get("price", 0) for w in works)

    act_lines = []
    act_lines.append(f"АКТ о приемке выполненных работ (КС-2)")
    act_lines.append(f"")
    act_lines.append(f"Объект: {data['project_name']}")
    act_lines.append(f"Заказчик: {data['customer']}")
    act_lines.append(f"Договор No {data['contract_number']} от {data['contract_date']}")
    act_lines.append(f"Дата составления: {datetime.now().strftime('%d.%m.%Y')}")
    act_lines.append(f"")
    act_lines.append(f"{'No':<5} {'Наименование работ':<40} {'Ед.изм.':<10} {'Кол-во':<10} {'Цена':<12} {'Сумма':<12}")
    act_lines.append("-" * 89)

    for i, w in enumerate(works, 1):
        name = w.get("name", "")[:38]
        unit = w.get("unit", "шт.")
        qty = w.get("quantity", 0)
        price = w.get("price", 0)
        total = qty * price
        act_lines.append(f"{i:<5} {name:<40} {unit:<10} {qty:<10.2f} {price:<12.2f} {total:<12.2f}")

    act_lines.append("-" * 89)
    act_lines.append(f"{'ИТОГО:':<67} {total_sum:>12.2f} руб.")
    act_lines.append(f"")
    act_lines.append(f"Сдал: {data['executor_position']} {data['executor_name']}")
    act_lines.append(f"Принял: _____________________ / _____________________")

    act_text = "\n".join(act_lines)

    # Generate DOCX
    doc = Document()

    # Title
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("АКТ\nо приемке выполненных работ")
    run.font.size = Pt(16)
    run.bold = True

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("(форма КС-2)")
    run.font.size = Pt(11)
    run.italic = True

    # Details
    doc.add_paragraph(f"Объект: {data['project_name']}")
    doc.add_paragraph(f"Заказчик: {data['customer']}")
    doc.add_paragraph(f"Договор No {data['contract_number']} от {data['contract_date']}")
    doc.add_paragraph(f"Дата составления: {datetime.now().strftime('%d.%m.%Y')}")
    doc.add_paragraph("")

    # Table
    table = doc.add_table(rows=1, cols=6)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr_cells = table.rows[0].cells
    headers = ["No", "Наименование работ", "Ед.изм.", "Кол-во", "Цена, руб.", "Сумма, руб."]
    for i, h in enumerate(headers):
        hdr_cells[i].text = h
        for p in hdr_cells[i].paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(9)

    for i, w in enumerate(works, 1):
        row_cells = table.add_row().cells
        qty = w.get("quantity", 0)
        price = w.get("price", 0)
        row_cells[0].text = str(i)
        row_cells[1].text = w.get("name", "")
        row_cells[2].text = w.get("unit", "шт.")
        row_cells[3].text = f"{qty:.2f}"
        row_cells[4].text = f"{price:.2f}"
        row_cells[5].text = f"{qty * price:.2f}"

    # Total row
    total_row = table.add_row().cells
    total_row[0].text = ""
    total_row[1].text = "ИТОГО:"
    for p in total_row[1].paragraphs:
        for r in p.runs:
            r.bold = True
    total_row[5].text = f"{total_sum:.2f}"
    for p in total_row[5].paragraphs:
        for r in p.runs:
            r.bold = True

    doc.add_paragraph("")
    doc.add_paragraph(f"Сдал: {data['executor_position']} _________________ {data['executor_name']}")
    doc.add_paragraph("")
    doc.add_paragraph("Принял: _____________________ / _____________________")

    result_name = f"act_ks2_{uuid.uuid4().hex[:8]}.docx"
    result_path = RESULTS_DIR / result_name
    doc.save(str(result_path))

    await log_activity("act_gen", data["project_name"], f"Акт КС-2: {len(works)} работ, {total_sum:.2f} руб.")

    return {
        "status": "ok",
        "act_text": act_text,
        "works_count": len(works),
        "total_sum": total_sum,
        "download": f"/api/download-act/{result_name}",
    }


@app.get("/api/download-act/{filename}", tags=["Production"], summary="Download act file")
async def download_act(filename: str):
    safe_name = Path(filename).name
    path = (RESULTS_DIR / safe_name).resolve()
    if not path.is_relative_to(RESULTS_DIR.resolve()) or not path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path, filename=safe_name,
                       media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


# ============== F17. CNC PROGRAM GENERATOR ==============

@app.post("/api/generate-cnc", tags=["Production"], summary="Generate CNC program")
async def api_generate_cnc(data: dict):
    """Generate CNC program for aluminum cutting."""
    cuts = data.get("cuts", [])
    machine_type = data.get("machine_type", "miter_saw")

    if not cuts:
        raise HTTPException(status_code=400, detail="Добавьте хотя бы одну нарезку")

    program_lines = []
    total_operations = 0

    if machine_type == "miter_saw":
        program_lines.append("; === ПРОГРАММА ТОРЦЕВОЙ ПИЛЫ ===")
        program_lines.append(f"; Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        program_lines.append(f"; Кол-во позиций: {len(cuts)}")
        program_lines.append(";")
        program_lines.append("; ФОРМАТ: ПОЗИЦИЯ | АРТИКУЛ | ДЛИНА | ОПЕРАЦИИ")
        program_lines.append("; ========================================")
        program_lines.append("")

        pos = 0
        for cut in cuts:
            article = cut.get("article", "N/A")
            length_mm = int(cut.get("length_mm", 0))
            quantity = int(cut.get("quantity", 1))
            operations = cut.get("operations", ["cut"])

            for q in range(quantity):
                pos += 1
                program_lines.append(f"; --- Деталь {pos}: {article} x {length_mm}мм ---")

                if "cut" in operations:
                    program_lines.append(f"M03 S3000        ; Пуск шпинделя")
                    program_lines.append(f"G01 X{length_mm:.1f} F500  ; Установить упор на {length_mm}мм")
                    program_lines.append(f"G01 Z-60 F200     ; Рез вниз")
                    program_lines.append(f"G00 Z10           ; Возврат")
                    total_operations += 1

                if "drill" in operations:
                    program_lines.append(f"M06 T02           ; Смена на сверло")
                    program_lines.append(f"G81 X{length_mm/2:.1f} Y0 Z-15 R5 F150 ; Сверление по центру")
                    program_lines.append(f"G80                ; Отмена цикла")
                    total_operations += 1

                if "mill" in operations:
                    program_lines.append(f"M06 T03           ; Смена на фрезу")
                    program_lines.append(f"G01 X10 Y-5 F300  ; Фрезеровка паз")
                    program_lines.append(f"G01 X{length_mm - 10:.1f} Y-5")
                    program_lines.append(f"G00 Y0 Z10        ; Возврат")
                    total_operations += 1

                program_lines.append("")

        program_lines.append("M05               ; Стоп шпинделя")
        program_lines.append("M30               ; Конец программы")

    else:  # cnc_router
        program_lines.append("%")
        program_lines.append(f"O0001 (CNC ROUTER PROGRAM)")
        program_lines.append(f"(DATE: {datetime.now().strftime('%d.%m.%Y %H:%M')})")
        program_lines.append(f"(POSITIONS: {len(cuts)})")
        program_lines.append("")
        program_lines.append("G90 G21           (Absolute, Metric)")
        program_lines.append("G17               (XY Plane)")
        program_lines.append("")

        pos = 0
        y_offset = 0
        for cut in cuts:
            article = cut.get("article", "N/A")
            length_mm = int(cut.get("length_mm", 0))
            quantity = int(cut.get("quantity", 1))
            operations = cut.get("operations", ["cut"])

            for q in range(quantity):
                pos += 1
                program_lines.append(f"(PART {pos}: {article} L={length_mm})")

                # Safe height
                program_lines.append(f"G00 Z25.0")

                if "cut" in operations:
                    program_lines.append(f"G00 X0 Y{y_offset:.1f}")
                    program_lines.append(f"M03 S12000")
                    program_lines.append(f"G00 Z5.0")
                    program_lines.append(f"G01 Z-3.0 F1000")
                    program_lines.append(f"G01 X{length_mm:.1f} F2000")
                    program_lines.append(f"G00 Z25.0")
                    total_operations += 1

                if "drill" in operations:
                    drill_positions = [length_mm * 0.25, length_mm * 0.5, length_mm * 0.75]
                    for dx in drill_positions:
                        program_lines.append(f"G00 X{dx:.1f} Y{y_offset + 20:.1f}")
                        program_lines.append(f"G81 Z-12.0 R5.0 F500")
                        program_lines.append(f"G80")
                        total_operations += 1

                if "mill" in operations:
                    program_lines.append(f"M06 T02 (End mill)")
                    program_lines.append(f"M03 S10000")
                    program_lines.append(f"G00 X5.0 Y{y_offset + 10:.1f}")
                    program_lines.append(f"G01 Z-2.0 F800")
                    program_lines.append(f"G01 X{length_mm - 5:.1f} F1500")
                    program_lines.append(f"G01 Y{y_offset + 30:.1f}")
                    program_lines.append(f"G01 X5.0")
                    program_lines.append(f"G00 Z25.0")
                    total_operations += 1

                program_lines.append("")
                y_offset += 60

        program_lines.append("M05")
        program_lines.append("G00 X0 Y0 Z50.0")
        program_lines.append("M30")
        program_lines.append("%")

    program_text = "\n".join(program_lines)

    # Save as .nc file
    result_name = f"cnc_program_{uuid.uuid4().hex[:8]}.nc"
    result_path = RESULTS_DIR / result_name
    result_path.write_text(program_text, encoding="utf-8")

    await log_activity("cnc", f"{len(cuts)} позиций", f"ЧПУ программа: {total_operations} операций, {machine_type}")

    return {
        "status": "ok",
        "program_text": program_text,
        "total_operations": total_operations,
        "machine_type": machine_type,
        "positions": len(cuts),
        "download": f"/api/download-nc/{result_name}",
    }


@app.get("/api/download-nc/{filename}", tags=["Production"], summary="Download NC file")
async def download_nc(filename: str):
    safe_name = Path(filename).name
    path = (RESULTS_DIR / safe_name).resolve()
    if not path.is_relative_to(RESULTS_DIR.resolve()) or not path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path, filename=safe_name, media_type="application/octet-stream")


# ============== F18. QR / LABEL GENERATOR ==============

@app.post("/api/generate-qr", tags=["Production"], summary="Generate QR labels")
async def api_generate_qr(data: dict):
    """Generate printable labels with position data."""
    positions = data.get("positions", [])
    if not positions:
        raise HTTPException(status_code=400, detail="Добавьте хотя бы одну позицию")

    # Generate HTML labels for printing
    labels_html = """<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
    @media print { body { margin: 0; } .label { page-break-inside: avoid; } }
    body { font-family: Arial, sans-serif; padding: 10mm; }
    .labels-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 5mm; }
    .label {
        border: 1px solid #333; border-radius: 4px; padding: 4mm;
        text-align: center; min-height: 35mm;
    }
    .label-id { font-size: 18pt; font-weight: bold; margin-bottom: 2mm; }
    .label-desc { font-size: 8pt; color: #555; margin-bottom: 2mm; }
    .label-article { font-size: 10pt; font-family: monospace; margin-bottom: 2mm; }
    .label-qty { font-size: 9pt; }
    .label-barcode {
        font-family: monospace; font-size: 14pt; letter-spacing: 3px;
        border-top: 1px solid #ccc; padding-top: 2mm; margin-top: 2mm;
    }
    .label-data { font-size: 6pt; color: #999; margin-top: 1mm; word-break: break-all; }
</style>
</head><body>
<div class="labels-grid">
"""

    for pos in positions:
        pos_id = _html.escape(str(pos.get("id", "N/A")))
        desc = _html.escape(str(pos.get("description", "")))
        article = _html.escape(str(pos.get("article", "")))
        qty = int(pos.get("quantity", 1))
        data_str = json.dumps({"id": pos_id, "art": article, "qty": qty}, ensure_ascii=False)
        # Simple barcode-style representation using article digits
        barcode_repr = "".join(f"{'|' if int(c) % 2 == 0 else ':'}" for c in article if c.isdigit()) if article else "|||::|||"

        labels_html += f"""<div class="label">
    <div class="label-id">{pos_id}</div>
    <div class="label-desc">{desc}</div>
    <div class="label-article">Арт. {article}</div>
    <div class="label-qty">Кол-во: {qty} шт.</div>
    <div class="label-barcode">{barcode_repr}</div>
    <div class="label-data">{data_str}</div>
</div>
"""

    labels_html += "</div></body></html>"

    await log_activity("qr_labels", f"{len(positions)} позиций", f"Маркировка: {len(positions)} этикеток")

    return {
        "status": "ok",
        "labels_count": len(positions),
        "labels_html": labels_html,
    }


# ============== F19. PHOTO REPORT TEMPLATE ==============

@app.post("/api/generate-photo-report", tags=["Production"], summary="Generate photo report template")
async def api_generate_photo_report(data: dict):
    """Generate photo report template as XLSX."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    project_name = data.get("project_name", "Проект")
    report_date = data.get("date", datetime.now().strftime("%d.%m.%Y"))
    positions = data.get("positions", [])

    if not positions:
        raise HTTPException(status_code=400, detail="Добавьте хотя бы одну позицию")

    wb = Workbook()
    ws = wb.active
    ws.title = "Фотоотчёт"

    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    # Title
    ws.merge_cells("A1:F1")
    ws["A1"] = f"ФОТООТЧЁТ — {project_name}"
    ws["A1"].font = Font(name="Arial", size=16, bold=True)
    ws["A1"].alignment = Alignment(horizontal="center")

    ws.merge_cells("A2:F2")
    ws["A2"] = f"Дата: {report_date}"
    ws["A2"].font = Font(name="Arial", size=11)
    ws["A2"].alignment = Alignment(horizontal="center")

    ws.merge_cells("A3:F3")
    ws["A3"] = "Инспектор: _________________________"
    ws["A3"].font = Font(name="Arial", size=10, italic=True)

    # Headers
    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="2A2A22", end_color="2A2A22", fill_type="solid")
    headers = ["Позиция", "Описание", "Статус", "Фото (вставить)", "Замечания", "Подпись"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=5, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    # Status colors
    status_fills = {
        "установлено": PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"),
        "в процессе": PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid"),
        "не начато": PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"),
    }

    for i, pos in enumerate(positions):
        row = i + 6
        ws.row_dimensions[row].height = 80  # Space for photo

        ws.cell(row=row, column=1, value=pos.get("id", f"П-{i+1}")).border = thin_border
        ws.cell(row=row, column=1).alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=row, column=1).font = Font(name="Arial", size=11, bold=True)

        ws.cell(row=row, column=2, value=pos.get("description", "")).border = thin_border
        ws.cell(row=row, column=2).alignment = Alignment(vertical="center", wrap_text=True)

        status = pos.get("status", "не начато")
        status_cell = ws.cell(row=row, column=3, value=status)
        status_cell.border = thin_border
        status_cell.alignment = Alignment(horizontal="center", vertical="center")
        if status in status_fills:
            status_cell.fill = status_fills[status]

        ws.cell(row=row, column=4, value="[Вставить фото]").border = thin_border
        ws.cell(row=row, column=4).alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=row, column=4).font = Font(name="Arial", size=9, italic=True, color="999999")

        ws.cell(row=row, column=5, value="").border = thin_border
        ws.cell(row=row, column=6, value="").border = thin_border

    # Column widths
    col_widths = {"A": 12, "B": 30, "C": 15, "D": 25, "E": 20, "F": 15}
    for col, w in col_widths.items():
        ws.column_dimensions[col].width = w

    result_name = f"photo_report_{uuid.uuid4().hex[:8]}.xlsx"
    result_path = RESULTS_DIR / result_name
    wb.save(str(result_path))

    await log_activity("photo_report", project_name, f"Фотоотчёт: {len(positions)} позиций")

    return {
        "status": "ok",
        "positions_count": len(positions),
        "download": f"/api/download/{result_name}",
    }


# ============== F20. STANDARD NODES LIBRARY ==============

NODES_LIBRARY = {
    "top_connection": {
        "id": "top_connection",
        "name": "Узел верхнего примыкания",
        "description": "Узел крепления алюминиевой конструкции к верхнему перекрытию. Обеспечивает компенсацию прогиба перекрытия и герметичность.",
        "materials": [
            "Кронштейн Г-образный 120x80x4мм",
            "Анкер забивной М10x60",
            "Винт самонарезающий 6.3x19",
            "EPDM уплотнитель 20x5мм",
            "Утеплитель минвата 50мм",
            "Пароизоляционная лента",
            "Герметик силиконовый нейтральный",
        ],
        "installation_steps": [
            "Разметить линию крепления по проекту",
            "Установить кронштейны с шагом 400мм на анкеры",
            "Закрепить верхний профиль рамы к кронштейнам",
            "Оставить зазор 15-20мм для компенсации прогиба",
            "Заполнить зазор утеплителем",
            "Наклеить пароизоляционную ленту изнутри",
            "Нанести герметик по наружному контуру",
        ],
        "warnings": [
            "Зазор для компенсации прогиба обязателен (мин. 15мм)",
            "Не допускать жёсткого защемления конструкции",
            "Пароизоляция только с внутренней стороны",
        ],
        "applicable_systems": ["Reynaers CW 50", "Schuco FWS 50", "Alutech ALT F50", "Vidnal V-FW50"],
        "svg_schematic": """<svg viewBox="0 0 300 200" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="0" width="300" height="30" fill="#C0C0C0" stroke="#666" stroke-width="1"/>
  <text x="150" y="20" text-anchor="middle" font-size="10" fill="#444">Перекрытие</text>
  <rect x="80" y="30" width="8" height="40" fill="#888" stroke="#444" stroke-width="0.5"/>
  <rect x="212" y="30" width="8" height="40" fill="#888" stroke="#444" stroke-width="0.5"/>
  <text x="60" y="55" text-anchor="end" font-size="8" fill="#666">Кронштейн</text>
  <line x1="62" y1="53" x2="78" y2="50" stroke="#666" stroke-width="0.5"/>
  <rect x="70" y="70" width="160" height="12" fill="#4A6FA5" stroke="#333" stroke-width="1"/>
  <text x="150" y="80" text-anchor="middle" font-size="8" fill="white">Рама (верх)</text>
  <path d="M 70 30 L 70 70" stroke="#E8A030" stroke-width="2" stroke-dasharray="3,2"/>
  <text x="55" y="52" text-anchor="end" font-size="7" fill="#E8A030">Зазор</text>
  <rect x="85" y="35" width="130" height="32" fill="#FFE0A0" opacity="0.5" stroke="none"/>
  <text x="150" y="55" text-anchor="middle" font-size="7" fill="#996600">Утеплитель</text>
  <rect x="70" y="82" width="160" height="50" fill="#B0D4F1" opacity="0.3" stroke="#4A6FA5" stroke-width="0.5" stroke-dasharray="2,2"/>
  <text x="150" y="110" text-anchor="middle" font-size="8" fill="#4A6FA5">Стеклопакет</text>
  <circle cx="84" cy="40" r="3" fill="#A14242"/>
  <circle cx="216" cy="40" r="3" fill="#A14242"/>
  <text x="250" y="42" font-size="7" fill="#A14242">Анкер</text>
</svg>""",
    },
    "bottom_connection": {
        "id": "bottom_connection",
        "name": "Узел нижнего примыкания",
        "description": "Узел крепления конструкции к нижнему основанию (плита, парапет). Включает гидроизоляцию и отвод воды.",
        "materials": [
            "Подставочный профиль 30x40мм",
            "Анкер клиновой М10x80",
            "Гидроизоляционная мембрана",
            "Подоконный отлив оцинкованный",
            "ПСУЛ 20x30",
            "Монтажная пена",
            "Герметик бутиловый",
        ],
        "installation_steps": [
            "Подготовить основание, выровнять плоскость",
            "Уложить гидроизоляционную мембрану",
            "Установить подставочный профиль на анкеры",
            "Закрепить раму к подставочному профилю",
            "Установить наружный отлив с уклоном",
            "Запенить монтажный шов",
            "Загерметизировать стыки",
        ],
        "warnings": [
            "Обязателен уклон отлива от фасада (мин. 3°)",
            "Гидроизоляция должна заходить под конструкцию мин. 50мм",
            "Монтажная пена — только изнутри помещения",
        ],
        "applicable_systems": ["Reynaers CW 50", "Schuco FWS 50", "Alutech ALT F50", "Vidnal V-FW50"],
        "svg_schematic": """<svg viewBox="0 0 300 200" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="140" width="300" height="60" fill="#C0C0C0" stroke="#666" stroke-width="1"/>
  <text x="150" y="175" text-anchor="middle" font-size="10" fill="#444">Основание / Плита</text>
  <rect x="70" y="120" width="160" height="20" fill="#8B7355" stroke="#444" stroke-width="1"/>
  <text x="150" y="134" text-anchor="middle" font-size="8" fill="white">Подставочный профиль</text>
  <rect x="70" y="60" width="160" height="60" fill="#B0D4F1" opacity="0.3" stroke="#4A6FA5" stroke-width="0.5" stroke-dasharray="2,2"/>
  <text x="150" y="95" text-anchor="middle" font-size="8" fill="#4A6FA5">Стеклопакет</text>
  <rect x="68" y="55" width="164" height="12" fill="#4A6FA5" stroke="#333" stroke-width="1"/>
  <text x="150" y="65" text-anchor="middle" font-size="8" fill="white">Рама (низ)</text>
  <path d="M 40 138 L 70 138 L 70 125 L 30 125 L 25 140 Z" fill="#999" stroke="#666" stroke-width="0.5"/>
  <text x="35" y="120" font-size="7" fill="#666">Отлив</text>
  <line x1="70" y1="140" x2="230" y2="140" stroke="#2196F3" stroke-width="2"/>
  <text x="260" y="143" font-size="7" fill="#2196F3">Гидроизол.</text>
  <circle cx="100" cy="135" r="3" fill="#A14242"/>
  <circle cx="200" cy="135" r="3" fill="#A14242"/>
</svg>""",
    },
    "side_connection": {
        "id": "side_connection",
        "name": "Узел бокового примыкания",
        "description": "Узел крепления боковой стойки к откосу или стене. Обеспечивает герметичность и теплоизоляцию бокового шва.",
        "materials": [
            "Анкерная пластина 150x30x2мм",
            "Анкер рамный 10x132",
            "ПСУЛ 20x40",
            "Пароизоляционная лента ВС",
            "Монтажная пена профессиональная",
            "Герметик нейтральный",
            "Нащельник 40мм",
        ],
        "installation_steps": [
            "Установить анкерные пластины на раму с шагом 400мм",
            "Выставить раму в проёме по уровню",
            "Закрепить анкерные пластины к стене",
            "Наклеить ПСУЛ по наружному контуру",
            "Запенить монтажный шов послойно",
            "Установить пароизоляционную ленту изнутри",
            "Установить нащельник снаружи",
        ],
        "warnings": [
            "Монтажный зазор: 15-20мм с каждой стороны",
            "Пена наносить послойно (макс. 30мм за проход)",
            "ПСУЛ устанавливать до запенивания",
        ],
        "applicable_systems": ["Reynaers CW 50", "Schuco FWS 50", "Alutech ALT F50", "Vidnal V-FW50", "СИАЛ КП 50"],
        "svg_schematic": """<svg viewBox="0 0 300 200" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="0" width="60" height="200" fill="#C0C0C0" stroke="#666" stroke-width="1"/>
  <text x="30" y="100" text-anchor="middle" font-size="9" fill="#444" transform="rotate(-90,30,100)">Стена / Откос</text>
  <rect x="60" y="30" width="12" height="140" fill="#4A6FA5" stroke="#333" stroke-width="1"/>
  <text x="66" y="105" text-anchor="middle" font-size="7" fill="white" transform="rotate(-90,66,105)">Стойка рамы</text>
  <rect x="72" y="30" width="80" height="140" fill="#B0D4F1" opacity="0.3" stroke="#4A6FA5" stroke-width="0.5" stroke-dasharray="2,2"/>
  <text x="112" y="105" text-anchor="middle" font-size="8" fill="#4A6FA5">Стеклопакет</text>
  <rect x="55" y="50" width="18" height="6" fill="#E8A030" stroke="#996600" stroke-width="0.5"/>
  <rect x="55" y="100" width="18" height="6" fill="#E8A030" stroke="#996600" stroke-width="0.5"/>
  <rect x="55" y="145" width="18" height="6" fill="#E8A030" stroke="#996600" stroke-width="0.5"/>
  <text x="40" y="55" text-anchor="end" font-size="6" fill="#996600">Пластина</text>
  <path d="M 56 60 C 58 70, 58 90, 56 95" fill="#FFD700" opacity="0.4" stroke="#E8A030" stroke-width="0.5"/>
  <text x="42" y="80" text-anchor="end" font-size="6" fill="#E8A030">Пена</text>
  <circle cx="50" cy="53" r="2.5" fill="#A14242"/>
  <circle cx="50" cy="103" r="2.5" fill="#A14242"/>
  <circle cx="50" cy="148" r="2.5" fill="#A14242"/>
</svg>""",
    },
    "mullion_transom": {
        "id": "mullion_transom",
        "name": "Узел стойка-ригель",
        "description": "Соединение вертикальной стойки с горизонтальным ригелем в фасадной системе. Ключевой несущий узел.",
        "materials": [
            "Соединитель стойка-ригель (комплект)",
            "Прижимная планка",
            "Уплотнитель EPDM наружный",
            "Уплотнитель EPDM внутренний",
            "Винт самонарезающий 6.3x25",
            "Декоративная крышка ригеля",
            "Термовкладыш полиамидный",
        ],
        "installation_steps": [
            "Подготовить стойку: вырезать паз под ригель",
            "Установить термовкладыш в стойку",
            "Вставить соединитель в ригель",
            "Закрепить ригель к стойке через соединитель",
            "Установить уплотнители (наружный и внутренний)",
            "Закрепить прижимную планку",
            "Установить декоративную крышку",
        ],
        "warnings": [
            "Соединитель должен соответствовать серии профилей",
            "Обязательно использовать термовкладыш для терморазрыва",
            "Момент затяжки по рекомендации производителя",
        ],
        "applicable_systems": ["Reynaers CW 50", "Schuco FWS 50+", "Alutech ALT F50", "Hueck L50"],
        "svg_schematic": """<svg viewBox="0 0 300 200" xmlns="http://www.w3.org/2000/svg">
  <rect x="130" y="0" width="40" height="200" fill="#4A6FA5" stroke="#333" stroke-width="1"/>
  <text x="150" y="15" text-anchor="middle" font-size="8" fill="white">Стойка</text>
  <rect x="0" y="85" width="130" height="30" fill="#5A8FB5" stroke="#333" stroke-width="1"/>
  <rect x="170" y="85" width="130" height="30" fill="#5A8FB5" stroke="#333" stroke-width="1"/>
  <text x="65" y="104" text-anchor="middle" font-size="8" fill="white">Ригель</text>
  <text x="235" y="104" text-anchor="middle" font-size="8" fill="white">Ригель</text>
  <rect x="135" y="88" width="30" height="24" fill="#E8A030" stroke="#996600" stroke-width="0.5" rx="2"/>
  <text x="150" y="103" text-anchor="middle" font-size="6" fill="#663300">Соединитель</text>
  <rect x="125" y="80" width="50" height="4" fill="#4A7C59" opacity="0.7"/>
  <rect x="125" y="116" width="50" height="4" fill="#4A7C59" opacity="0.7"/>
  <text x="100" y="80" text-anchor="end" font-size="6" fill="#4A7C59">Уплотнитель</text>
  <rect x="0" y="30" width="128" height="50" fill="#B0D4F1" opacity="0.2" stroke="#4A6FA5" stroke-width="0.5" stroke-dasharray="2,2"/>
  <rect x="172" y="30" width="128" height="50" fill="#B0D4F1" opacity="0.2" stroke="#4A6FA5" stroke-width="0.5" stroke-dasharray="2,2"/>
  <rect x="0" y="120" width="128" height="50" fill="#B0D4F1" opacity="0.2" stroke="#4A6FA5" stroke-width="0.5" stroke-dasharray="2,2"/>
  <rect x="172" y="120" width="128" height="50" fill="#B0D4F1" opacity="0.2" stroke="#4A6FA5" stroke-width="0.5" stroke-dasharray="2,2"/>
  <text x="64" y="58" text-anchor="middle" font-size="7" fill="#4A6FA5">Стекло</text>
</svg>""",
    },
    "corner_joint": {
        "id": "corner_joint",
        "name": "Угловое соединение",
        "description": "Соединение двух стоек фасадной системы под углом (90° или произвольный). Обеспечивает герметичность угла.",
        "materials": [
            "Угловой соединитель 90°",
            "Угловая стойка специальная",
            "Угловой уплотнитель EPDM",
            "Герметик силиконовый структурный",
            "Винт самонарезающий 6.3x19",
            "Угловая декоративная крышка",
            "Термовкладыш угловой",
        ],
        "installation_steps": [
            "Подготовить угловую стойку по размерам",
            "Установить термовкладыш",
            "Закрепить стойки к угловому соединителю",
            "Установить угловые уплотнители",
            "Нанести структурный герметик в угловой шов",
            "Установить стеклопакеты в угловые ячейки",
            "Смонтировать декоративные крышки",
        ],
        "warnings": [
            "Угловой стеклопакет требует специального заказа",
            "Структурный герметик — только сертифицированный",
            "Для углов отличных от 90° — специальные профили",
        ],
        "applicable_systems": ["Reynaers CW 50", "Schuco FWS 50", "Alutech ALT F50"],
        "svg_schematic": """<svg viewBox="0 0 300 200" xmlns="http://www.w3.org/2000/svg">
  <rect x="130" y="0" width="15" height="200" fill="#4A6FA5" stroke="#333" stroke-width="1"/>
  <rect x="145" y="85" width="155" height="15" fill="#4A6FA5" stroke="#333" stroke-width="1" transform="rotate(0)"/>
  <rect x="138" y="80" width="25" height="25" fill="#E8A030" stroke="#996600" stroke-width="1" rx="3"/>
  <text x="150" y="96" text-anchor="middle" font-size="6" fill="#663300">Угл.</text>
  <rect x="10" y="10" width="118" height="70" fill="#B0D4F1" opacity="0.2" stroke="#4A6FA5" stroke-width="0.5" stroke-dasharray="2,2"/>
  <rect x="10" y="105" width="118" height="85" fill="#B0D4F1" opacity="0.2" stroke="#4A6FA5" stroke-width="0.5" stroke-dasharray="2,2"/>
  <rect x="165" y="105" width="125" height="85" fill="#B0D4F1" opacity="0.2" stroke="#4A6FA5" stroke-width="0.5" stroke-dasharray="2,2"/>
  <text x="70" y="50" text-anchor="middle" font-size="8" fill="#4A6FA5">Стекло</text>
  <text x="150" y="30" text-anchor="middle" font-size="8" fill="white" transform="rotate(-90,143,30)">Стойка</text>
  <text x="220" y="95" text-anchor="middle" font-size="8" fill="white">Стойка</text>
  <path d="M 130 80 Q 140 85, 145 85" fill="none" stroke="#4A7C59" stroke-width="2"/>
  <text x="120" y="78" text-anchor="end" font-size="6" fill="#4A7C59">90°</text>
</svg>""",
    },
    "expansion_joint": {
        "id": "expansion_joint",
        "name": "Деформационный шов",
        "description": "Узел компенсации температурных и осадочных деформаций между секциями фасада. Критически важен для длинных фасадов.",
        "materials": [
            "Деформационный профиль (компенсатор)",
            "Уплотнитель деформационного шва",
            "Герметик полиуретановый эластичный",
            "Утеплитель вспененный (Вилатерм)",
            "Нащельник деформационный 80мм",
            "Крепёж нержавеющий",
        ],
        "installation_steps": [
            "Разметить деформационный шов по проекту",
            "Установить деформационные профили с зазором",
            "Заложить утеплитель Вилатерм в шов",
            "Нанести полиуретановый герметик",
            "Установить наружный нащельник",
            "Проверить свободу перемещения",
        ],
        "warnings": [
            "Шов располагать через каждые 6-8м фасада",
            "Минимальная ширина шва: 20мм",
            "Запрещено заполнять жёстким герметиком",
            "Учитывать температурное расширение алюминия: 0.024мм/м/°C",
        ],
        "applicable_systems": ["Reynaers CW 50", "Schuco FWS 50", "Alutech ALT F50", "Vidnal V-FW50", "СИАЛ КП 50"],
        "svg_schematic": """<svg viewBox="0 0 300 200" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="20" width="120" height="160" fill="#4A6FA5" opacity="0.3" stroke="#333" stroke-width="1"/>
  <rect x="180" y="20" width="120" height="160" fill="#4A6FA5" opacity="0.3" stroke="#333" stroke-width="1"/>
  <text x="60" y="105" text-anchor="middle" font-size="9" fill="#4A6FA5">Секция A</text>
  <text x="240" y="105" text-anchor="middle" font-size="9" fill="#4A6FA5">Секция B</text>
  <rect x="120" y="20" width="10" height="160" fill="#4A6FA5" stroke="#333" stroke-width="1"/>
  <rect x="170" y="20" width="10" height="160" fill="#4A6FA5" stroke="#333" stroke-width="1"/>
  <rect x="133" y="25" width="34" height="150" fill="#FFE0A0" opacity="0.5"/>
  <text x="150" y="100" text-anchor="middle" font-size="7" fill="#996600" transform="rotate(-90,150,100)">Утеплитель</text>
  <line x1="150" y1="20" x2="150" y2="180" stroke="#A14242" stroke-width="1" stroke-dasharray="5,3"/>
  <text x="150" y="190" text-anchor="middle" font-size="7" fill="#A14242">Ось деф. шва</text>
  <path d="M 130 30 L 133 30" stroke="#E8A030" stroke-width="2"/>
  <path d="M 167 30 L 170 30" stroke="#E8A030" stroke-width="2"/>
  <text x="150" y="15" text-anchor="middle" font-size="7" fill="#E8A030">20-40мм</text>
  <line x1="130" y1="10" x2="130" y2="18" stroke="#E8A030" stroke-width="0.5"/>
  <line x1="170" y1="10" x2="170" y2="18" stroke="#E8A030" stroke-width="0.5"/>
  <line x1="130" y1="12" x2="170" y2="12" stroke="#E8A030" stroke-width="0.5" marker-start="url(#arrowL)" marker-end="url(#arrowR)"/>
</svg>""",
    },
    "sill_connection": {
        "id": "sill_connection",
        "name": "Узел подоконника",
        "description": "Узел установки внутреннего подоконника и его примыкания к раме конструкции. Включает теплоизоляцию подоконного пространства.",
        "materials": [
            "Подоконник ПВХ/камень/дерево",
            "Подставочный профиль",
            "Монтажная пена",
            "Герметик акриловый",
            "Заглушки торцевые",
            "Крепёжные клипсы",
        ],
        "installation_steps": [
            "Проверить установку подставочного профиля",
            "Подготовить подоконник по размерам (выступ 30-50мм)",
            "Установить подоконник с уклоном внутрь помещения (2-3°)",
            "Запенить пространство под подоконником",
            "Загерметизировать примыкание к раме",
            "Установить торцевые заглушки",
        ],
        "warnings": [
            "Подоконник не должен перекрывать радиатор более чем на 50%",
            "Обязателен уклон от окна (2-3°)",
            "Герметик наносить после полной полимеризации пены",
        ],
        "applicable_systems": ["Все оконные системы", "Reynaers MasterLine 8", "Schuco AWS 75", "Alutech ALT W72"],
        "svg_schematic": """<svg viewBox="0 0 300 200" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="120" width="300" height="80" fill="#C0C0C0" stroke="#666" stroke-width="1"/>
  <text x="150" y="165" text-anchor="middle" font-size="9" fill="#444">Стена</text>
  <rect x="100" y="70" width="15" height="50" fill="#4A6FA5" stroke="#333" stroke-width="1"/>
  <text x="107" y="100" text-anchor="middle" font-size="6" fill="white" transform="rotate(-90,107,100)">Рама</text>
  <rect x="100" y="108" width="15" height="14" fill="#8B7355" stroke="#444" stroke-width="0.5"/>
  <text x="107" y="118" text-anchor="middle" font-size="5" fill="white">ПП</text>
  <rect x="30" y="105" width="85" height="15" fill="#DEB887" stroke="#8B7355" stroke-width="1"/>
  <text x="72" y="116" text-anchor="middle" font-size="8" fill="#5C4033">Подоконник</text>
  <line x1="30" y1="105" x2="115" y2="103" stroke="#8B7355" stroke-width="0.5" stroke-dasharray="3,2"/>
  <text x="20" y="100" font-size="6" fill="#8B7355">2-3°</text>
  <rect x="35" y="120" width="75" height="20" fill="#FFE0A0" opacity="0.4"/>
  <text x="72" y="133" text-anchor="middle" font-size="6" fill="#996600">Пена</text>
  <rect x="115" y="70" width="50" height="35" fill="#B0D4F1" opacity="0.3" stroke="#4A6FA5" stroke-width="0.5" stroke-dasharray="2,2"/>
  <text x="140" y="92" text-anchor="middle" font-size="7" fill="#4A6FA5">Стекло</text>
</svg>""",
    },
    "threshold": {
        "id": "threshold",
        "name": "Узел порога",
        "description": "Узел нижнего примыкания дверной конструкции с порогом. Обеспечивает теплоизоляцию, водоотведение и доступность.",
        "materials": [
            "Порог алюминиевый с терморазрывом",
            "Уплотнитель порога щёточный",
            "Гидроизоляционная мембрана",
            "Дренажные отверстия (заглушки)",
            "Анкер рамный 10x132",
            "Герметик полиуретановый",
            "Противоскользящая накладка",
        ],
        "installation_steps": [
            "Подготовить основание с уклоном наружу",
            "Уложить гидроизоляционную мембрану",
            "Установить порог на анкеры",
            "Проверить дренажные отверстия",
            "Установить щёточный уплотнитель",
            "Загерметизировать боковые примыкания",
            "Установить противоскользящую накладку",
        ],
        "warnings": [
            "Дренажные отверстия не должны быть перекрыты",
            "Для маломобильных групп: высота порога макс. 20мм",
            "Обязательна гидроизоляция под порогом",
        ],
        "applicable_systems": ["Reynaers CP 155", "Schuco ASS 77 PD", "Alutech ALT SL160", "Vidnal V-SD60"],
        "svg_schematic": """<svg viewBox="0 0 300 200" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="150" width="300" height="50" fill="#C0C0C0" stroke="#666" stroke-width="1"/>
  <text x="150" y="180" text-anchor="middle" font-size="9" fill="#444">Основание</text>
  <rect x="60" y="130" width="180" height="20" fill="#B8963B" stroke="#8A7030" stroke-width="1"/>
  <text x="150" y="144" text-anchor="middle" font-size="8" fill="white">Порог алюминиевый</text>
  <rect x="60" y="0" width="12" height="130" fill="#4A6FA5" stroke="#333" stroke-width="1"/>
  <rect x="228" y="0" width="12" height="130" fill="#4A6FA5" stroke="#333" stroke-width="1"/>
  <text x="66" y="70" text-anchor="middle" font-size="7" fill="white" transform="rotate(-90,66,70)">Стойка</text>
  <text x="234" y="70" text-anchor="middle" font-size="7" fill="white" transform="rotate(-90,234,70)">Стойка</text>
  <rect x="72" y="10" width="156" height="110" fill="#B0D4F1" opacity="0.2" stroke="#4A6FA5" stroke-width="0.5" stroke-dasharray="2,2"/>
  <text x="150" y="70" text-anchor="middle" font-size="9" fill="#4A6FA5">Дверное полотно</text>
  <line x1="60" y1="148" x2="240" y2="148" stroke="#2196F3" stroke-width="2"/>
  <text x="30" y="148" text-anchor="end" font-size="6" fill="#2196F3">Гидроизол.</text>
  <rect x="140" y="135" width="4" height="10" fill="#333"/>
  <rect x="155" y="135" width="4" height="10" fill="#333"/>
  <text x="150" y="128" text-anchor="middle" font-size="6" fill="#333">Дренаж</text>
  <path d="M 60 126 L 58 130 L 62 130 Z" fill="#4A7C59"/>
  <path d="M 240 126 L 238 130 L 242 130 Z" fill="#4A7C59"/>
  <text x="55" y="122" text-anchor="end" font-size="6" fill="#4A7C59">Уплотн.</text>
</svg>""",
    },
}


@limiter.limit("30/minute")
@app.get("/api/nodes-library", tags=["Analytics & Projects"], summary="Get standard nodes catalog")
async def api_nodes_library(request: Request):
    """Return list of all standard nodes."""
    nodes_list = []
    for node_id, node in NODES_LIBRARY.items():
        nodes_list.append({
            "id": node["id"],
            "name": node["name"],
            "description": node["description"],
            "materials_count": len(node["materials"]),
            "steps_count": len(node["installation_steps"]),
            "applicable_systems": node["applicable_systems"],
        })
    return {"status": "ok", "nodes": nodes_list}


@limiter.limit("30/minute")
@app.get("/api/nodes-library/{node_type}", tags=["Analytics & Projects"], summary="Get nodes by type")
async def api_node_detail(request: Request, node_type: str):
    """Return detailed info about a specific node."""
    node = NODES_LIBRARY.get(node_type)
    if not node:
        raise HTTPException(status_code=404, detail=f"Узел '{node_type}' не найден")
    return {"status": "ok", "node": node}


# ============== 13. СТАТИСТИКА / ДАШБОРД ==============

@limiter.limit("30/minute")
@app.get("/api/stats", tags=["Analytics & Projects"], summary="Get usage statistics")
async def api_stats(request: Request):
    """Вернуть счётчики и последние операции (из БД с пагинацией)."""
    page = int(request.query_params.get("page", 1))
    per_page = min(int(request.query_params.get("per_page", 20)), 100)
    offset = (page - 1) * per_page

    try:
        async with async_session() as session:
            # Get counters from DB grouped by operation
            stmt = select(
                ActivityLogModel.operation,
                sa_func.count(ActivityLogModel.id),
            ).group_by(ActivityLogModel.operation)
            result = await session.execute(stmt)
            db_counters = dict(result.all())

            # Total rows for pagination metadata
            total_stmt = select(sa_func.count(ActivityLogModel.id))
            total_result = await session.execute(total_stmt)
            total_rows = total_result.scalar() or 0

            # Recent entries with pagination
            stmt = (
                select(ActivityLogModel)
                .order_by(ActivityLogModel.timestamp.desc())
                .offset(offset)
                .limit(per_page)
            )
            result = await session.execute(stmt)
            recent = [
                {
                    "timestamp": row.timestamp.isoformat(timespec="seconds"),
                    "type": row.operation,
                    "filename": row.file_name or "",
                    "summary": row.result_summary or "",
                }
                for row in result.scalars().all()
            ]
    except Exception:
        # Fallback to in-memory data if DB is unavailable
        db_counters = {}
        total_rows = len(activity_log)
        recent = activity_log[offset : offset + per_page]

    # Merge in-memory counters with DB counters
    merged = {**counters}
    for k, v in db_counters.items():
        merged[k] = max(merged.get(k, 0), v)

    return {
        "counters": merged,
        "total_operations": sum(merged.values()),
        "recent": recent,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total_rows,
        },
    }


# ============== СКАЧИВАНИЕ РЕЗУЛЬТАТОВ ==============

@app.get("/api/download/{filename}", tags=["Analytics & Projects"], summary="Download result file")
async def download_result(filename: str):
    # Защита от path traversal: берём только имя файла
    safe_name = Path(filename).name
    path = (RESULTS_DIR / safe_name).resolve()
    if not path.is_relative_to(RESULTS_DIR.resolve()) or not path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path, filename=safe_name,
                       media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@limiter.limit("10/minute")
@app.post("/api/export-zip", tags=["Analytics & Projects"], summary="Bulk download results as ZIP")
async def export_zip(request: Request, payload: dict):
    """Download multiple result files as a single ZIP archive."""
    filenames = payload.get("filenames", [])
    if not filenames:
        raise HTTPException(status_code=400, detail="Укажите список файлов")
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False, dir=str(RESULTS_DIR)) as tmp:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            for fn in filenames:
                safe = Path(fn).name
                fpath = (RESULTS_DIR / safe).resolve()
                if fpath.is_relative_to(RESULTS_DIR.resolve()) and fpath.exists():
                    zf.write(fpath, safe)
        return FileResponse(tmp.name, filename="kmd_results.zip", media_type="application/zip")


# ============== AI CHAT ASSISTANT ==============

MODULE_DESCRIPTIONS = {
    "compare": "Сравнение двух заказных спецификаций XLSX. Находит расхождения по артикулам, количеству, цветам.",
    "check": "Проверка комплектности PDF чертежей КМД — определяет типы страниц, наличие спецификаций, позиций.",
    "parse": "Парсинг КМД из PDF/DXF — извлечение позиций, артикулов, размеров, штампов чертежей.",
    "crossval": "Кросс-валидация: сверка данных из чертежа PDF/DXF со спецификацией XLSX.",
    "comparepdf": "Сравнение двух версий PDF — находит текстовые различия между ревизиями чертежей.",
    "genspec": "Генерация спецификации XLSX из PDF чертежа — автоматическое создание ведомости.",
    "batch": "Пакетная обработка ZIP-архива с чертежами — анализ всех PDF/DXF/XLSX разом.",
    "checklist": "Чек-лист КМД по 31 критерию в 7 категориях — оценка качества документации с весами.",
    "thermal": "Расчёт приведённого сопротивления теплопередаче Uw по ГОСТ 26602.1 / SP 50.13330.",
    "wind": "Расчёт ветровой нагрузки по SP 20.13330.2016 с учётом района, местности, высоты, зоны.",
    "sashweight": "Расчёт массы створки — профили, стеклопакет, фурнитура. Проверка ограничений.",
    "glass": "Подбор формулы стеклопакета по нагрузке, теплотехнике, звукоизоляции. 17 формул.",
    "fasteners": "Расчёт крепежа — анкеры/кронштейны по ГОСТ 30971 для бетона/кирпича/газобетона.",
    "preview3d": "3D визуализация конструкции в Three.js — окна, витражи, двери с размерами.",
    "cutting": "Оптимизация раскроя профиля — алгоритм FFD, карты реза, статистика отходов.",
    "profileai": "Подбор профильной системы — 18 реальных систем (Reynaers, Schuco, Alutech, TATPROF).",
    "aireview": "AI ревью чертежа — vision-модель находит ошибки, пропуски, несоответствия ГОСТ.",
    "ainote": "AI генерация пояснительной записки (ПЗ) по ГОСТ 21.502 из чертежа.",
    "aigost": "AI консультант по ГОСТ/СП/СНиП — отвечает на вопросы по нормативам.",
    "aihardware": "AI подбор фурнитуры по параметрам створки — Roto, Siegenia, Maco, GU.",
    "aicompare": "AI визуальное сравнение двух чертежей — находит все отличия.",
    "aigenkmd": "AI генерация КМД документации из технического задания.",
    "aitranslate": "AI перевод КМД терминологии ГОСТ <-> EN (Eurocode).",
    "versioning": "Версионирование КМД — загрузка ревизий, сравнение версий, история изменений.",
    "requisition": "Автоматическая заявка на материалы из PDF чертежа — XLSX ведомость.",
    "projects": "Трекер проектов — канбан от замера до сдачи объекта.",
    "actgen": "Генерация актов приёмки-сдачи работ в DOCX.",
    "cnc": "Генерация программ ЧПУ (G-code) для пильных и фрезерных центров.",
    "qrlabels": "Маркировка позиций — генерация этикеток с данными для печати.",
    "photoreport": "Шаблон фотоотчёта XLSX для мобильной фиксации монтажа.",
    "nodeslibrary": "Библиотека стандартных узлов — 8 типов с SVG схемами и описаниями.",
    "dashboard": "Дашборд — счётчики операций, последние действия, статистика использования.",
}

_MODULE_CONTEXT_STR = "\n".join(f"- {k}: {v}" for k, v in MODULE_DESCRIPTIONS.items())


@limiter.limit("10/minute")
@app.post("/api/ai-chat", tags=["AI Tools"], summary="AI chat assistant")
async def api_ai_chat(request: Request, payload: dict):
    """AI chat assistant that explains modules and answers KMD questions."""
    question = payload.get("question", "").strip()
    context_tab = payload.get("context", "")

    if not question:
        raise HTTPException(status_code=400, detail="Введите вопрос")

    current_module = MODULE_DESCRIPTIONS.get(context_tab, "")

    messages = [{"role": "user", "content": (
        "Ты AI-помощник платформы KMD Assistant от ALDMEGA LAB для инженеров алюминиевых конструкций. "
        "Отвечай кратко, по делу, на русском. Ты эксперт в КМД, ГОСТ, алюминиевых окнах/витражах/фасадах.\n\n"
        f"Доступные модули платформы:\n{_MODULE_CONTEXT_STR}\n\n"
        f"Пользователь сейчас на вкладке: {context_tab} — {current_module}\n\n"
        f"Вопрос пользователя: {question}"
    )}]

    try:
        answer = await _call_llm(messages, model=DEFAULT_LLM_MODEL, max_tokens=2000)
        return {"status": "ok", "answer": answer}
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"OpenRouter: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
