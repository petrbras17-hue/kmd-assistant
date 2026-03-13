"""Tests for additional API endpoints (3D, cutting, nodes, profile, versioning, projects)."""
import pytest


# ============== Nodes Library ==============

@pytest.mark.asyncio
async def test_nodes_library_list(client):
    """GET /api/nodes-library returns the catalog."""
    resp = await client.get("/api/nodes-library")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "nodes" in data
    assert isinstance(data["nodes"], list)
    if data["nodes"]:
        node = data["nodes"][0]
        assert "id" in node
        assert "name" in node
        assert "materials_count" in node


@pytest.mark.asyncio
async def test_nodes_library_detail_not_found(client):
    """GET /api/nodes-library/{type} returns 404 for unknown type."""
    resp = await client.get("/api/nodes-library/nonexistent-type-xyz")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_nodes_library_detail_existing(client):
    """GET /api/nodes-library/{type} returns details for known type."""
    # First get the list to find a valid type
    list_resp = await client.get("/api/nodes-library")
    nodes = list_resp.json()["nodes"]
    if not nodes:
        pytest.skip("No nodes in library")
    node_id = nodes[0]["id"]
    resp = await client.get(f"/api/nodes-library/{node_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "node" in data


# ============== Profile Recommendation ==============

@pytest.mark.asyncio
async def test_recommend_profile_defaults(authed_client):
    """POST /api/recommend-profile with default parameters."""
    resp = await authed_client.post("/api/recommend-profile", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "recommendations" in data
    assert len(data["recommendations"]) > 0
    top = data["recommendations"][0]
    assert "system" in top
    assert "manufacturer" in top
    assert "score" in top
    assert top["rank"] == 1


@pytest.mark.asyncio
async def test_recommend_profile_high_rise(authed_client):
    """Profile recommendation for high-rise building."""
    resp = await authed_client.post("/api/recommend-profile", json={
        "construction_type": "витраж",
        "width_mm": 3000,
        "height_mm": 4000,
        "floors": 20,
        "wind_region": "V",
        "thermal_required": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    # Should have warnings about height and wind
    assert any("15 этажей" in w or "этажей" in w for w in data.get("warnings", []))


# ============== 3D Preview ==============

@pytest.mark.asyncio
async def test_preview_3d_defaults(authed_client):
    """POST /api/preview-3d with minimal parameters."""
    resp = await authed_client.post("/api/preview-3d", json={
        "construction_type": "окно",
        "width_mm": 1200,
        "height_mm": 1500,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "scene" in data


# ============== Cutting Optimization ==============

@pytest.mark.asyncio
async def test_optimize_cutting(authed_client):
    """POST /api/optimize-cutting with valid cuts."""
    resp = await authed_client.post("/api/optimize-cutting", json={
        "stock_length_mm": 6500,
        "cuts": [
            {"article": "1234567", "length_mm": 2000, "quantity": 3},
            {"article": "7654321", "length_mm": 1500, "quantity": 4},
        ],
        "blade_width_mm": 5,
        "min_remnant_mm": 50,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "total_bars_needed" in data
    assert "waste_percent" in data
    assert data["total_bars_needed"] > 0


@pytest.mark.asyncio
async def test_optimize_cutting_single_item(authed_client):
    """Cutting optimization with a single item."""
    resp = await authed_client.post("/api/optimize-cutting", json={
        "stock_length_mm": 6500,
        "cuts": [
            {"article": "1111111", "length_mm": 3000, "quantity": 1},
        ],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["total_bars_needed"] == 1


# ============== Versioning History ==============

@pytest.mark.asyncio
async def test_versioning_history_empty(client):
    """GET /api/versioning/history returns empty list when no versions exist."""
    resp = await client.get("/api/versioning/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_versioning_history_with_filename(client):
    """GET /api/versioning/history?filename=xxx returns empty for nonexistent file."""
    resp = await client.get("/api/versioning/history?filename=nonexistent.pdf")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


# ============== Project Update Status ==============

@pytest.mark.asyncio
async def test_project_update_status(authed_client):
    """Create a project then advance its status."""
    # Create project
    create_resp = await authed_client.post("/api/projects/create", json={
        "name": "Status Test",
        "customer": "Test",
        "address": "Test",
        "positions_count": 5,
        "deadline": "2026-12-31",
    })
    assert create_resp.status_code == 200
    project_id = create_resp.json()["project"]["id"]

    # Update status
    resp = await authed_client.post(f"/api/projects/{project_id}/update-status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    # Should have moved to next stage
    assert data["project"]["status"] != "замер"


@pytest.mark.asyncio
async def test_project_update_status_not_found(authed_client):
    """Updating status of nonexistent project returns 404."""
    resp = await authed_client.post("/api/projects/9999/update-status")
    assert resp.status_code == 404
