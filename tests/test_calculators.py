"""Tests for calculator endpoints (thermal, wind, sash weight, glass, fasteners)."""
import pytest


@pytest.mark.asyncio
async def test_calc_thermal_defaults(authed_client):
    """Thermal calculator with default parameters."""
    resp = await authed_client.post("/api/calc-thermal", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "uw" in data
    assert "classification" in data
    assert "dew_point" in data
    assert data["classification"] in ("А", "Б", "В", "Г", "Д")


@pytest.mark.asyncio
async def test_calc_thermal_custom(authed_client):
    """Thermal calculator with custom parameters."""
    resp = await authed_client.post("/api/calc-thermal", json={
        "profile_uf": 1.0,
        "glass_ug": 0.6,
        "glass_area_m2": 3.0,
        "frame_area_m2": 0.5,
        "psi_edge": 0.04,
        "edge_length_m": 8.0,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["uw"] < 1.0  # Should be class A with these values
    assert data["classification"] == "А"
    assert data["meets_requirement"] is True


@pytest.mark.asyncio
async def test_calc_thermal_zero_area(authed_client):
    """Thermal calculator rejects zero total area."""
    resp = await authed_client.post("/api/calc-thermal", json={
        "glass_area_m2": 0,
        "frame_area_m2": 0,
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_calc_wind_defaults(authed_client):
    """Wind load calculator with default parameters."""
    resp = await authed_client.post("/api/calc-wind", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "wind_pressure_pa" in data
    assert "panel_load_n" in data
    assert "required_ix_cm4" in data
    assert data["wind_pressure_pa"] > 0


@pytest.mark.asyncio
async def test_calc_wind_corner_zone(authed_client):
    """Wind load at corner zone (higher aerodynamic coefficient)."""
    resp = await authed_client.post("/api/calc-wind", json={
        "wind_region": "V",
        "terrain": "A",
        "height_m": 60,
        "zone": "corner",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["ce"] == -1.4
    assert data["zone"] == "corner"


@pytest.mark.asyncio
async def test_calc_wind_leeward_zone(authed_client):
    """Wind load at leeward zone."""
    resp = await authed_client.post("/api/calc-wind", json={
        "zone": "leeward",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["ce"] == -0.6


@pytest.mark.asyncio
async def test_calc_sash_weight_defaults(authed_client):
    """Sash weight calculator with default parameters."""
    resp = await authed_client.post("/api/calc-sash-weight", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "total_weight" in data
    assert "profile_weight" in data
    assert "glass_weight" in data
    assert "max_allowed" in data
    assert data["total_weight"] > 0


@pytest.mark.asyncio
async def test_calc_sash_weight_custom(authed_client):
    """Sash weight calculator with custom glass formula."""
    resp = await authed_client.post("/api/calc-sash-weight", json={
        "width_mm": 1200,
        "height_mm": 2000,
        "glass_formula": "6-16Ar-6-16Ar-6",
        "hardware_weight_kg": 3.0,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert len(data["glass_thicknesses"]) == 3  # triple glass


@pytest.mark.asyncio
async def test_calc_glass_defaults(authed_client):
    """Glass package selection with default parameters."""
    resp = await authed_client.post("/api/calc-glass", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "recommendations" in data
    assert len(data["recommendations"]) > 0
    # Results should be sorted by score descending
    scores = [r["score"] for r in data["recommendations"]]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_calc_glass_safety_required(authed_client):
    """Glass selection with safety glass requirement."""
    resp = await authed_client.post("/api/calc-glass", json={
        "safety_required": True,
        "width_mm": 1500,
        "height_mm": 2500,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert any("безопасн" in w.lower() or "триплекс" in w.lower()
               for w in data.get("warnings", []))


@pytest.mark.asyncio
async def test_calc_fasteners_defaults(authed_client):
    """Fastener calculator with default parameters."""
    resp = await authed_client.post("/api/calc-fasteners", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "total_anchors" in data
    assert "safety_margin" in data
    assert "recommended_anchor" in data
    assert data["total_anchors"] >= 4  # minimum 4 anchors


@pytest.mark.asyncio
async def test_calc_fasteners_aerated_concrete(authed_client):
    """Fastener calculator for aerated concrete (gas concrete) wall."""
    resp = await authed_client.post("/api/calc-fasteners", json={
        "wall_type": "газобетон",
        "frame_width_mm": 2000,
        "frame_height_mm": 2500,
        "weight_kg": 120,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["wall_type"] == "газобетон"
    # Should have warnings about aerated concrete and heavy weight
    warnings = data["wall_type_warnings"]
    assert any("газобетон" in w.lower() for w in warnings)
    assert any("100 кг" in w for w in warnings)
