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


@pytest.fixture(autouse=True)
async def _create_tables():
    """Create DB tables before each test (mirrors the app startup event)."""
    async with db_engine.begin() as conn:
        await conn.run_sync(DBBase.metadata.create_all)
    yield
    async with db_engine.begin() as conn:
        await conn.run_sync(DBBase.metadata.drop_all)


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
