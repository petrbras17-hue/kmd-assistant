"""
OAuth2 + JWT аутентификация для KMD.

Поддерживает:
- Локальная регистрация/вход (email + пароль)
- Google OAuth2
- Yandex OAuth2
- JWT access/refresh токены
"""

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.database import get_db
from webapp.models import User

# ---------------------------------------------------------------------------
# Настройки
# ---------------------------------------------------------------------------

_jwt_env = os.getenv("JWT_SECRET", "").strip()
if _jwt_env:
    JWT_SECRET: str = _jwt_env
else:
    JWT_SECRET = secrets.token_urlsafe(64)
    import logging as _logging
    _logging.getLogger("kmd.auth").warning(
        "JWT_SECRET не задан — сгенерирован временный ключ. "
        "Токены будут невалидны после перезапуска!"
    )
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

OAUTH_REDIRECT_BASE_URL: str = os.getenv("OAUTH_REDIRECT_BASE_URL", "http://localhost:8000")

# ---------------------------------------------------------------------------
# Хэширование паролей
# ---------------------------------------------------------------------------

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------------------------------------------------------------------
# OAuth2 провайдеры (authlib)
# ---------------------------------------------------------------------------

oauth = OAuth()

# Google
_google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
_google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
if _google_client_id and _google_client_secret:
    oauth.register(
        name="google",
        client_id=_google_client_id,
        client_secret=_google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

# Yandex
_yandex_client_id = os.getenv("YANDEX_CLIENT_ID", "")
_yandex_client_secret = os.getenv("YANDEX_CLIENT_SECRET", "")
if _yandex_client_id and _yandex_client_secret:
    oauth.register(
        name="yandex",
        client_id=_yandex_client_id,
        client_secret=_yandex_client_secret,
        authorize_url="https://oauth.yandex.ru/authorize",
        access_token_url="https://oauth.yandex.ru/token",
        client_kwargs={"scope": "login:email login:info login:avatar"},
    )

# ---------------------------------------------------------------------------
# FastAPI OAuth2 scheme (Bearer)
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# ---------------------------------------------------------------------------
# Pydantic-схемы
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    """Запрос на регистрацию локального пользователя."""
    username: str = Field(..., min_length=2, max_length=256)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Запрос на вход (email + пароль)."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Пара access + refresh токенов."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60


class RefreshRequest(BaseModel):
    """Запрос на обновление access-токена."""
    refresh_token: str


class UserResponse(BaseModel):
    """Публичный профиль пользователя."""
    id: int
    username: str
    email: Optional[str] = None
    avatar: Optional[str] = None
    provider: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    """Простое текстовое сообщение."""
    message: str


# ---------------------------------------------------------------------------
# JWT-утилиты
# ---------------------------------------------------------------------------


def _create_token(data: dict, expires_delta: timedelta) -> str:
    """Создать подписанный JWT с заданным сроком жизни."""
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    payload["iat"] = datetime.now(timezone.utc)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_access_token(user_id: int, role: str) -> str:
    return _create_token(
        {"sub": str(user_id), "role": role, "type": "access"},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: int) -> str:
    return _create_token(
        {"sub": str(user_id), "type": "refresh"},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )


def create_token_pair(user: User) -> TokenResponse:
    """Сгенерировать пару access + refresh для пользователя."""
    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id),
    )


def decode_token(token: str) -> dict:
    """Декодировать и проверить JWT. Бросает JWTError при невалидном токене."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Извлечь текущего пользователя из Bearer-токена. 401 если не авторизован."""
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise JWTError("Неверный тип токена")
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный или просроченный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден или деактивирован",
        )
    return user


async def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Вернуть пользователя если токен предоставлен, иначе None."""
    if token is None:
        return None
    try:
        return await get_current_user(token=token, db=db)
    except HTTPException:
        return None


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


async def _get_or_create_oauth_user(
    db: AsyncSession,
    *,
    email: str,
    username: str,
    provider: str,
    provider_id: str,
    avatar: Optional[str] = None,
) -> User:
    """
    Найти пользователя по email или provider+provider_id.
    Если не существует — создать нового.
    Обновить last_login.
    """
    # Поиск по provider + provider_id
    result = await db.execute(
        select(User).where(User.provider == provider, User.provider_id == provider_id)
    )
    user = result.scalar_one_or_none()

    if user is None and email:
        # Поиск по email (пользователь мог зарегистрироваться локально ранее)
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is not None:
            # Если аккаунт уже привязан к другому провайдеру — не перезаписываем
            if user.provider != "local" and user.provider != provider:
                raise HTTPException(
                    status_code=409,
                    detail="Этот email уже связан с другим способом входа",
                )
            # Привязать OAuth-провайдер к локальному аккаунту
            user.provider = provider
            user.provider_id = provider_id

    if user is None:
        # Убедимся что username уникален
        base_username = username
        suffix = 0
        max_attempts = 100
        while suffix < max_attempts:
            candidate = f"{base_username}_{suffix}" if suffix else base_username
            existing = await db.execute(
                select(User).where(User.username == candidate)
            )
            if existing.scalar_one_or_none() is None:
                username = candidate
                break
            suffix += 1
        else:
            # Fallback: random suffix to guarantee uniqueness
            username = f"{base_username}_{secrets.token_hex(4)}"

        user = User(
            username=username,
            email=email,
            provider=provider,
            provider_id=provider_id,
            avatar=avatar,
            role="engineer",
            is_active=True,
        )
        db.add(user)

    # Обновить данные при каждом входе
    user.last_login = datetime.now(timezone.utc)
    if avatar and not user.avatar:
        user.avatar = avatar

    await db.flush()
    return user


# ---------------------------------------------------------------------------
# Роутер
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/auth", tags=["auth"])


# --- Локальная регистрация ---

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Регистрация нового пользователя (email + пароль)."""
    # Проверка уникальности email
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким email уже существует",
        )

    # Проверка уникальности username
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким username уже существует",
        )

    user = User(
        username=body.username,
        email=body.email,
        password_hash=pwd_context.hash(body.password),
        provider="local",
        role="engineer",
        is_active=True,
        last_login=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()

    return create_token_pair(user)


# --- Локальный вход ---

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Вход по email + пароль."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )

    if not pwd_context.verify(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт деактивирован",
        )

    user.last_login = datetime.now(timezone.utc)
    await db.flush()

    return create_token_pair(user)


# --- Обновление токена ---

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Обменять refresh-токен на новую пару access + refresh."""
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise JWTError("Неверный тип токена")
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный или просроченный refresh-токен",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден или деактивирован",
        )

    return create_token_pair(user)


# --- Текущий пользователь ---

@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    """Информация о текущем авторизованном пользователе."""
    return current_user


# --- Logout (клиентский — просто подтверждение) ---

@router.post("/logout", response_model=MessageResponse)
async def logout(current_user: User = Depends(get_current_user)):
    """
    Выход из системы.
    JWT — stateless, поэтому фактическое удаление токена происходит на клиенте.
    При необходимости можно добавить blacklist токенов через Redis.
    """
    return MessageResponse(message="Выход выполнен. Удалите токен на стороне клиента.")


# ---------------------------------------------------------------------------
# Google OAuth2
# ---------------------------------------------------------------------------

@router.get("/google")
async def google_login(request: Request):
    """Перенаправить пользователя на страницу авторизации Google."""
    google_client = oauth.create_client("google")
    if google_client is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth не настроен. Задайте GOOGLE_CLIENT_ID и GOOGLE_CLIENT_SECRET.",
        )
    redirect_uri = f"{OAUTH_REDIRECT_BASE_URL}/api/auth/google/callback"
    return await google_client.authorize_redirect(request, redirect_uri)


@router.get("/google/callback", response_model=TokenResponse)
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Обработать callback от Google OAuth, создать/обновить пользователя, вернуть JWT."""
    google_client = oauth.create_client("google")
    if google_client is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth не настроен",
        )

    try:
        token_data = await google_client.authorize_access_token(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ошибка авторизации через Google",
        )

    userinfo = token_data.get("userinfo")
    if userinfo is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не удалось получить данные пользователя от Google",
        )

    email = userinfo.get("email", "")
    if not userinfo.get("email_verified", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email не подтверждён в Google аккаунте",
        )
    name = userinfo.get("name") or email.split("@")[0]
    picture = userinfo.get("picture")
    google_id = userinfo.get("sub", "")

    user = await _get_or_create_oauth_user(
        db,
        email=email,
        username=name,
        provider="google",
        provider_id=google_id,
        avatar=picture,
    )

    tokens = create_token_pair(user)
    # Редирект на фронтенд с токенами во фрагменте URL (безопаснее query params)
    redirect_url = (
        f"{OAUTH_REDIRECT_BASE_URL}/#access_token={tokens['access_token']}"
        f"&refresh_token={tokens['refresh_token']}"
        f"&token_type=bearer"
    )
    return RedirectResponse(url=redirect_url, status_code=302)


# ---------------------------------------------------------------------------
# Yandex OAuth2
# ---------------------------------------------------------------------------

@router.get("/yandex")
async def yandex_login(request: Request):
    """Перенаправить пользователя на страницу авторизации Яндекс."""
    yandex_client = oauth.create_client("yandex")
    if yandex_client is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Yandex OAuth не настроен. Задайте YANDEX_CLIENT_ID и YANDEX_CLIENT_SECRET.",
        )
    redirect_uri = f"{OAUTH_REDIRECT_BASE_URL}/api/auth/yandex/callback"
    return await yandex_client.authorize_redirect(request, redirect_uri)


@router.get("/yandex/callback", response_model=TokenResponse)
async def yandex_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Обработать callback от Яндекс OAuth, создать/обновить пользователя, вернуть JWT."""
    yandex_client = oauth.create_client("yandex")
    if yandex_client is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Yandex OAuth не настроен",
        )

    try:
        token_data = await yandex_client.authorize_access_token(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ошибка авторизации через Яндекс",
        )

    # Яндекс не возвращает userinfo в токене — нужно запросить отдельно
    access_token = token_data.get("access_token", "")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://login.yandex.ru/info",
            params={"format": "json"},
            headers={"Authorization": f"OAuth {access_token}"},
        )
        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Не удалось получить данные пользователя от Яндекс",
            )
        userinfo = resp.json()

    email = userinfo.get("default_email", "")
    name = userinfo.get("login") or userinfo.get("display_name") or email.split("@")[0]
    yandex_id = str(userinfo.get("id", ""))
    avatar_id = userinfo.get("default_avatar_id")
    avatar_url = (
        f"https://avatars.yandex.net/get-yapic/{avatar_id}/islands-200"
        if avatar_id
        else None
    )

    user = await _get_or_create_oauth_user(
        db,
        email=email,
        username=name,
        provider="yandex",
        provider_id=yandex_id,
        avatar=avatar_url,
    )

    tokens = create_token_pair(user)
    redirect_url = (
        f"{OAUTH_REDIRECT_BASE_URL}/#access_token={tokens['access_token']}"
        f"&refresh_token={tokens['refresh_token']}"
        f"&token_type=bearer"
    )
    return RedirectResponse(url=redirect_url, status_code=302)
