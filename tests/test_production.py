"""Tests for production endpoints (act, CNC, QR labels, photo report)."""
import pytest


# ============== Generate Act (KS-2) ==============

@pytest.mark.asyncio
async def test_generate_act(authed_client):
    """Generate acceptance act with valid data."""
    resp = await authed_client.post("/api/generate-act", json={
        "project_name": "Башня Альфа",
        "customer": "ООО Строй",
        "contract_number": "123/2026",
        "contract_date": "01.01.2026",
        "executor_name": "Иванов И.И.",
        "executor_position": "Прораб",
        "works": [
            {"name": "Монтаж витражей", "unit": "м²", "quantity": 100, "price": 5000},
            {"name": "Монтаж окон", "unit": "шт.", "quantity": 20, "price": 15000},
        ],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["works_count"] == 2
    assert data["total_sum"] == 100 * 5000 + 20 * 15000
    assert "act_text" in data
    assert "download" in data


@pytest.mark.asyncio
async def test_generate_act_missing_fields(authed_client):
    """Generating act without required fields returns 400."""
    resp = await authed_client.post("/api/generate-act", json={
        "project_name": "Test",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_generate_act_no_works(authed_client):
    """Generating act with empty works list returns 400."""
    resp = await authed_client.post("/api/generate-act", json={
        "project_name": "Test",
        "customer": "Test",
        "contract_number": "1",
        "contract_date": "01.01.2026",
        "executor_name": "Test",
        "executor_position": "Test",
        "works": [],
    })
    assert resp.status_code == 400


# ============== Generate CNC ==============

@pytest.mark.asyncio
async def test_generate_cnc_miter_saw(authed_client):
    """Generate CNC program for miter saw."""
    resp = await authed_client.post("/api/generate-cnc", json={
        "machine_type": "miter_saw",
        "cuts": [
            {"article": "1234567", "length_mm": 2000, "quantity": 2, "operations": ["cut"]},
            {"article": "7654321", "length_mm": 1500, "quantity": 1, "operations": ["cut", "drill"]},
        ],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["machine_type"] == "miter_saw"
    assert data["total_operations"] > 0
    assert data["positions"] == 2
    assert "program_text" in data
    assert "download" in data


@pytest.mark.asyncio
async def test_generate_cnc_router(authed_client):
    """Generate CNC program for CNC router."""
    resp = await authed_client.post("/api/generate-cnc", json={
        "machine_type": "cnc_router",
        "cuts": [
            {"article": "1111111", "length_mm": 3000, "quantity": 1,
             "operations": ["cut", "drill", "mill"]},
        ],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["machine_type"] == "cnc_router"
    assert data["total_operations"] == 5  # cut(1) + drill(3 positions) + mill(1)


@pytest.mark.asyncio
async def test_generate_cnc_no_cuts(authed_client):
    """CNC with empty cuts returns 400."""
    resp = await authed_client.post("/api/generate-cnc", json={"cuts": []})
    assert resp.status_code == 400


# ============== Generate QR Labels ==============

@pytest.mark.asyncio
async def test_generate_qr_labels(authed_client):
    """Generate QR labels for positions."""
    resp = await authed_client.post("/api/generate-qr", json={
        "positions": [
            {"id": "В-1", "description": "Витраж входной", "article": "1234567", "quantity": 2},
            {"id": "О-1", "description": "Окно", "article": "7654321", "quantity": 1},
        ],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["labels_count"] == 2
    assert "labels_html" in data
    assert "В-1" in data["labels_html"]
    assert "1234567" in data["labels_html"]


@pytest.mark.asyncio
async def test_generate_qr_no_positions(authed_client):
    """QR labels with empty positions returns 400."""
    resp = await authed_client.post("/api/generate-qr", json={"positions": []})
    assert resp.status_code == 400


# ============== Generate Photo Report ==============

@pytest.mark.asyncio
async def test_generate_photo_report(authed_client):
    """Generate photo report template."""
    resp = await authed_client.post("/api/generate-photo-report", json={
        "project_name": "Объект Альфа",
        "date": "15.03.2026",
        "positions": [
            {"id": "В-1", "description": "Витраж", "status": "установлено"},
            {"id": "О-1", "description": "Окно", "status": "в процессе"},
            {"id": "Д-1", "description": "Дверь", "status": "не начато"},
        ],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["positions_count"] == 3
    assert "download" in data


@pytest.mark.asyncio
async def test_generate_photo_report_no_positions(authed_client):
    """Photo report with empty positions returns 400."""
    resp = await authed_client.post("/api/generate-photo-report", json={
        "project_name": "Test",
        "positions": [],
    })
    assert resp.status_code == 400
