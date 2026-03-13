"""Tests for project management endpoints."""
import pytest


@pytest.mark.asyncio
async def test_create_project(authed_client):
    resp = await authed_client.post("/api/projects/create", json={
        "name": "Башня Альфа",
        "customer": "ООО Строй",
        "address": "Москва, ул. Ленина 1",
        "positions_count": 50,
        "deadline": "2026-09-01",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["project"]["name"] == "Башня Альфа"
    assert data["project"]["status"] == "замер"


@pytest.mark.asyncio
async def test_create_project_missing_fields(authed_client):
    resp = await authed_client.post("/api/projects/create", json={"name": "Incomplete"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_projects(client):
    """GET endpoints do not require auth (middlewares only protect mutating methods)."""
    resp = await client.get("/api/projects/list")
    assert resp.status_code == 200
    data = resp.json()
    assert "projects" in data
    assert "stages" in data


@pytest.mark.asyncio
async def test_stats_endpoint(client):
    """GET /api/stats returns counters and recent activity."""
    resp = await client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "counters" in data
    assert "total_operations" in data
    assert "recent" in data
