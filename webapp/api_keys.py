"""
Управление API-ключами с привязкой к рабочим пространствам (workspace).

Роутер предоставляет CRUD-операции для API-ключей, расширенную валидацию
с проверкой лимитов, срока действия и разрешений, а также обратную
совместимость с устаревшим механизмом KMD_API_KEY.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.database import get_db
from webapp.models import ApiKey

logger = logging.getLogger("kmd.api_keys")

# ---------------------------------------------------------------------------
# Pydantic-схемы запросов / ответов
# ---------------------------------------------------------------------------


class ApiKeyCreateRequest(BaseModel):
    """Запрос на создание нового API-ключа."""
    name: str = Field(..., min_length=1, max_length=256, description="Название ключа")
    description: Optional[str] = Field(None, max_length=2048, description="Описание назначения ключа")
    permissions: Optional[List[str]] = Field(None, description="Список разрешённых операций")
    expires_at: Optional[datetime] = Field(None, description="Дата истечения срока действия (UTC)")


class ApiKeyUpdateRequest(BaseModel):
    """Запрос на обновление существующего API-ключа."""
    name: Optional[str] = Field(None, min_length=1, max_length=256)
    description: Optional[str] = Field(None, max_length=2048)
    permissions: Optional[List[str]] = None
    rate_limit: Optional[int] = Field(None, ge=1, le=10000, description="Запросов в минуту")


class ApiKeyResponse(BaseModel):
    """Публичное представление API-ключа (без хеша)."""
    id: int
    name: Optional[str]
    description: Optional[str]
    key_prefix: str = Field(..., description="Первые 8 символов ключа")
    permissions: Optional[List[str]]
    rate_limit: int
    is_active: bool
    usage_count: int
    last_ip: Optional[str]
    created_at: datetime
    last_used: Optional[datetime]
    expires_at: Optional[datetime]
    workspace_id: Optional[int]

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Ответ при создании — содержит plaintext-ключ (показывается один раз)."""
    plain_key: str = Field(..., description="Полный API-ключ (показывается только при создании)")


class ApiKeyStatsResponse(BaseModel):
    """Статистика использования ключа."""
    id: int
    name: Optional[str]
    usage_count: int
    last_used: Optional[datetime]
    last_ip: Optional[str]
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime]
    is_expired: bool
    rate_limit: int


class ApiKeyRevokedResponse(BaseModel):
    """Ответ при отзыве ключа."""
    id: int
    is_active: bool
    message: str


class ApiKeyRegeneratedResponse(BaseModel):
    """Ответ при перегенерации — содержит новый plaintext-ключ."""
    id: int
    plain_key: str
    message: str


# ---------------------------------------------------------------------------
# Вспомогательные утилиты
# ---------------------------------------------------------------------------

_KEY_PREFIX = "kmd_"  # Префикс для идентификации ключей KMD


def _hash_key(plain_key: str) -> str:
    """SHA-256 хеш API-ключа."""
    return hashlib.sha256(plain_key.encode()).hexdigest()


def _generate_key() -> str:
    """Генерация криптографически стойкого API-ключа."""
    return f"{_KEY_PREFIX}{secrets.token_urlsafe(32)}"


def _mask_key(key_hash: str) -> str:
    """Маскировка: первые 8 символов хеша + '...'"""
    return key_hash[:8] + "..."


def _key_to_response(key: ApiKey, prefix: Optional[str] = None) -> dict:
    """Преобразование ORM-объекта в словарь для ответа."""
    return {
        "id": key.id,
        "name": key.name,
        "description": key.description,
        "key_prefix": prefix or _mask_key(key.key_hash),
        "permissions": key.permissions,
        "rate_limit": key.rate_limit,
        "is_active": key.is_active,
        "usage_count": key.usage_count,
        "last_ip": key.last_ip,
        "created_at": key.created_at,
        "last_used": key.last_used,
        "expires_at": key.expires_at,
        "workspace_id": key.workspace_id,
    }


# ---------------------------------------------------------------------------
# Rate limiter (in-memory, per-workspace)
# ---------------------------------------------------------------------------

class WorkspaceRateLimiter:
    """
    Счётчик запросов в минуту по workspace_id.

    Использует скользящее окно (60 секунд). Если доступен Redis —
    можно заменить на распределённый вариант.
    """

    def __init__(self) -> None:
        # workspace_id -> list of timestamps
        self._requests: Dict[int, list] = defaultdict(list)

    def check(self, workspace_id: int, limit: int) -> tuple[bool, int]:
        """
        Проверить лимит. Возвращает (allowed, retry_after_seconds).
        retry_after_seconds == 0 если запрос разрешён.
        """
        now = time.monotonic()
        window_start = now - 60.0
        timestamps = self._requests[workspace_id]

        # Очистка устаревших записей
        self._requests[workspace_id] = [t for t in timestamps if t > window_start]
        timestamps = self._requests[workspace_id]

        if len(timestamps) >= limit:
            oldest = min(timestamps) if timestamps else now
            retry_after = max(1, int(oldest - window_start) + 1)
            return False, retry_after

        timestamps.append(now)
        return True, 0

    def record(self, workspace_id: int) -> None:
        """Зафиксировать запрос (вызывается после успешной проверки)."""
        # Уже зафиксирован в check(), но можно вызвать отдельно при необходимости
        pass


_rate_limiter = WorkspaceRateLimiter()


# ---------------------------------------------------------------------------
# Зависимости аутентификации
# ---------------------------------------------------------------------------

from webapp.auth import get_current_user
from webapp.models import User


async def get_current_user_id(
    current_user: User = Depends(get_current_user),
) -> int:
    """Извлекает ID текущего пользователя из JWT-токена."""
    return current_user.id


async def get_current_workspace_id(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> Optional[int]:
    """Получает ID текущего рабочего пространства из заголовка или профиля."""
    ws_header = request.headers.get("X-Workspace-Id")
    if ws_header:
        try:
            return int(ws_header)
        except ValueError:
            pass
    return current_user.workspace_id


# ---------------------------------------------------------------------------
# Расширенная валидация API-ключа (v2)
# ---------------------------------------------------------------------------

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_legacy_api_key = os.getenv("KMD_API_KEY", "").strip()


async def verify_api_key_v2(
    request: Request,
    api_key: Optional[str] = Security(_api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Optional[ApiKey]:
    """
    Расширенная зависимость валидации API-ключа.

    1. Проверяет ключ по базе данных (SHA-256 хеш).
    2. Проверяет is_active, срок действия (expires_at).
    3. Обновляет usage_count, last_used, last_ip.
    4. Проверяет rate limit для workspace.
    5. При отсутствии совпадения в БД — fallback на legacy KMD_API_KEY.
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="API-ключ не предоставлен")

    # --- Поиск в базе данных ---
    key_hash = _hash_key(api_key)
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash)
    )
    db_key: Optional[ApiKey] = result.scalar_one_or_none()

    if db_key is not None:
        # Проверка активности
        if not db_key.is_active:
            raise HTTPException(status_code=401, detail="API-ключ отозван")

        # Проверка срока действия
        if db_key.expires_at and db_key.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Срок действия API-ключа истёк")

        # Rate limit по workspace
        if db_key.workspace_id is not None:
            allowed, retry_after = _rate_limiter.check(
                db_key.workspace_id, db_key.rate_limit
            )
            if not allowed:
                return JSONResponse(  # type: ignore[return-value]
                    status_code=429,
                    content={"detail": "Превышен лимит запросов"},
                    headers={"Retry-After": str(retry_after)},
                )

        # Обновление статистики
        client_ip = request.client.host if request.client else None
        db_key.usage_count = (db_key.usage_count or 0) + 1
        db_key.last_used = datetime.now(timezone.utc)
        db_key.last_ip = client_ip
        await db.flush()

        # Прокидываем контекст в request.state
        request.state.api_key_id = db_key.id
        request.state.user_id = db_key.user_id
        request.state.workspace_id = db_key.workspace_id
        request.state.permissions = db_key.permissions

        return db_key

    # --- Fallback: legacy KMD_API_KEY из env ---
    if _legacy_api_key and hmac.compare_digest(api_key, _legacy_api_key):
        logger.info("Аутентификация через legacy KMD_API_KEY (env)")
        return None  # None означает legacy-ключ без записи в БД

    raise HTTPException(status_code=401, detail="Недействительный API-ключ")


# ---------------------------------------------------------------------------
# FastAPI Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/keys", tags=["API Keys"])


@router.post("", response_model=ApiKeyCreatedResponse, status_code=201)
async def create_api_key(
    body: ApiKeyCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
    workspace_id: Optional[int] = Depends(get_current_workspace_id),
) -> Any:
    """Создать новый API-ключ для текущего рабочего пространства."""
    plain_key = _generate_key()
    key_hash = _hash_key(plain_key)

    db_key = ApiKey(
        key_hash=key_hash,
        user_id=user_id,
        workspace_id=workspace_id,
        name=body.name,
        description=body.description,
        permissions=body.permissions,
        expires_at=body.expires_at,
        rate_limit=100,
        is_active=True,
        usage_count=0,
    )
    db.add(db_key)
    await db.flush()
    await db.refresh(db_key)

    response_data = _key_to_response(db_key, prefix=plain_key[:8] + "...")
    response_data["plain_key"] = plain_key

    logger.info(
        "API-ключ создан: id=%s, workspace=%s, user=%s",
        db_key.id, workspace_id, user_id,
    )
    return response_data


@router.get("", response_model=List[ApiKeyResponse])
async def list_api_keys(
    request: Request,
    db: AsyncSession = Depends(get_db),
    workspace_id: Optional[int] = Depends(get_current_workspace_id),
) -> Any:
    """Список API-ключей текущего рабочего пространства (ключи замаскированы)."""
    query = select(ApiKey).where(ApiKey.is_active == True)  # noqa: E712
    if workspace_id is not None:
        query = query.where(ApiKey.workspace_id == workspace_id)
    query = query.order_by(ApiKey.created_at.desc())

    result = await db.execute(query)
    keys = result.scalars().all()

    return [_key_to_response(k) for k in keys]


@router.get("/{key_id}/stats", response_model=ApiKeyStatsResponse)
async def get_api_key_stats(
    key_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    workspace_id: Optional[int] = Depends(get_current_workspace_id),
) -> Any:
    """Статистика использования API-ключа."""
    db_key = await _get_key_or_404(db, key_id, workspace_id)

    now = datetime.now(timezone.utc)
    is_expired = bool(db_key.expires_at and db_key.expires_at < now)

    return {
        "id": db_key.id,
        "name": db_key.name,
        "usage_count": db_key.usage_count,
        "last_used": db_key.last_used,
        "last_ip": db_key.last_ip,
        "is_active": db_key.is_active,
        "created_at": db_key.created_at,
        "expires_at": db_key.expires_at,
        "is_expired": is_expired,
        "rate_limit": db_key.rate_limit,
    }


@router.put("/{key_id}", response_model=ApiKeyResponse)
async def update_api_key(
    key_id: int,
    body: ApiKeyUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    workspace_id: Optional[int] = Depends(get_current_workspace_id),
) -> Any:
    """Обновить название, описание, разрешения или лимит API-ключа."""
    db_key = await _get_key_or_404(db, key_id, workspace_id)

    if body.name is not None:
        db_key.name = body.name
    if body.description is not None:
        db_key.description = body.description
    if body.permissions is not None:
        db_key.permissions = body.permissions
    if body.rate_limit is not None:
        db_key.rate_limit = body.rate_limit

    await db.flush()
    await db.refresh(db_key)

    logger.info("API-ключ обновлён: id=%s", db_key.id)
    return _key_to_response(db_key)


@router.delete("/{key_id}", response_model=ApiKeyRevokedResponse)
async def revoke_api_key(
    key_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    workspace_id: Optional[int] = Depends(get_current_workspace_id),
) -> Any:
    """Отозвать API-ключ (soft delete — is_active=False)."""
    db_key = await _get_key_or_404(db, key_id, workspace_id)

    db_key.is_active = False
    await db.flush()

    logger.info("API-ключ отозван: id=%s", db_key.id)
    return {
        "id": db_key.id,
        "is_active": False,
        "message": "API-ключ успешно отозван",
    }


@router.post("/{key_id}/regenerate", response_model=ApiKeyRegeneratedResponse)
async def regenerate_api_key(
    key_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    workspace_id: Optional[int] = Depends(get_current_workspace_id),
) -> Any:
    """Перегенерировать API-ключ: старый инвалидируется, возвращается новый."""
    db_key = await _get_key_or_404(db, key_id, workspace_id)

    new_plain = _generate_key()
    db_key.key_hash = _hash_key(new_plain)
    db_key.usage_count = 0
    db_key.last_used = None
    db_key.last_ip = None
    await db.flush()

    logger.info("API-ключ перегенерирован: id=%s", db_key.id)
    return {
        "id": db_key.id,
        "plain_key": new_plain,
        "message": "API-ключ перегенерирован. Сохраните новый ключ — он больше не будет показан.",
    }


# ---------------------------------------------------------------------------
# Внутренние хелперы
# ---------------------------------------------------------------------------

async def _get_key_or_404(
    db: AsyncSession,
    key_id: int,
    workspace_id: Optional[int],
) -> ApiKey:
    """Получить ключ по ID с проверкой принадлежности к workspace."""
    query = select(ApiKey).where(ApiKey.id == key_id)
    if workspace_id is not None:
        query = query.where(ApiKey.workspace_id == workspace_id)

    result = await db.execute(query)
    db_key = result.scalar_one_or_none()

    if db_key is None:
        raise HTTPException(status_code=404, detail="API-ключ не найден")

    return db_key
