"""Shared fixtures for KMD tests."""
import os
import pytest
from httpx import AsyncClient, ASGITransport

# Set test env vars BEFORE importing the app
os.environ["DATABASE_URL"] = ""  # Use SQLite fallback (file-based)
os.environ["KMD_API_KEY"] = "test-api-key-12345"
os.environ["OPENROUTER_API_KEY"] = "test-key"

from webapp.server import app  # noqa: E402
from webapp.database import engine as db_engine  # noqa: E402
from webapp.models import Base as DBBase  # noqa: E402


@pytest.fixture
def api_key():
    return "test-api-key-12345"


@pytest.fixture(autouse=True, scope="session")
def _create_tables_sync():
    """Create DB tables once for the entire test session."""
    import asyncio

    async def _setup():
        async with db_engine.begin() as conn:
            await conn.run_sync(DBBase.metadata.create_all)

    async def _teardown():
        async with db_engine.begin() as conn:
            await conn.run_sync(DBBase.metadata.drop_all)

    asyncio.get_event_loop().run_until_complete(_setup())
    yield
    try:
        asyncio.get_event_loop().run_until_complete(_teardown())
    except Exception:
        pass


@pytest.fixture
async def client():
    """Async test client for FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def authed_client(client, api_key):
    """Client with API key and CSRF token pre-set.

    Both APIKeyMiddleware and CSRFMiddleware must be satisfied for
    mutating (POST/PUT/PATCH/DELETE) requests. API key alone is not
    enough because CSRFMiddleware runs independently and requires a
    valid CSRF token on every mutating /api/* request.
    """
    # Get a valid CSRF token first
    resp = await client.get("/api/csrf-token")
    token = resp.json()["csrf_token"]
    client.headers["X-API-Key"] = api_key
    client.headers["X-CSRF-Token"] = token
    yield client


@pytest.fixture
async def csrf_client(client):
    """Client with valid CSRF token (no API key)."""
    resp = await client.get("/api/csrf-token")
    token = resp.json()["csrf_token"]
    client.headers["X-CSRF-Token"] = token
    yield client
