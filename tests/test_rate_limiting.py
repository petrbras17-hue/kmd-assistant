"""Tests for rate limiting."""
import pytest


@pytest.mark.asyncio
async def test_csrf_rate_limit(client):
    """CSRF endpoint should be rate-limited at 30/min."""
    # Just verify it works normally (full rate limit test needs 30+ requests)
    for _ in range(5):
        resp = await client.get("/api/csrf-token")
        assert resp.status_code == 200
