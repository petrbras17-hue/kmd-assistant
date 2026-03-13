"""
Async database engine, session factory, and declarative base for KMD.

DATABASE_URL is read from the environment variable.
Falls back to a local SQLite database (via aiosqlite) when the variable is not set.
"""

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# ---------------------------------------------------------------------------
# Connection URL
# ---------------------------------------------------------------------------
# Railway (and similar PaaS) expose a DATABASE_URL that typically starts with
# "postgresql://".  SQLAlchemy's async driver needs the "postgresql+asyncpg://"
# scheme, so we normalise the prefix when necessary.

_raw_url = os.getenv("DATABASE_URL", "")

if _raw_url:
    if _raw_url.startswith("postgres://"):
        _raw_url = _raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif _raw_url.startswith("postgresql://"):
        _raw_url = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    DATABASE_URL: str = _raw_url
else:
    # Local development fallback — async SQLite via aiosqlite
    DATABASE_URL = "sqlite+aiosqlite:///./kmd_local.db"

# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    # Pool settings meaningful for PostgreSQL; ignored by SQLite
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass

# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session and ensure it is closed after the request."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
