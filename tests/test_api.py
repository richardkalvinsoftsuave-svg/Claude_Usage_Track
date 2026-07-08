"""Tests for the upload/dashboard API endpoints."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from shutil import rmtree

import pytest
from fastapi import status

from app.config import settings
from app.routers import uploads as uploads_router

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_UPLOAD_ROOT = PROJECT_ROOT / "tests" / "_test_uploads"


def _fake_ocr(image_path):
    return {
        "extracted": {
            "session_usage_pct": 5,
            "weekly_usage_pct": 5,
            "plan_tier": "Pro",
            "session_reset_at": None,
            "weekly_reset_at": None,
        },
        "raw_text": "fake ocr text",
    }


@pytest.fixture
def test_upload_dir():
    """Yield a fresh upload directory under the project root."""
    if TEST_UPLOAD_ROOT.exists():
        rmtree(TEST_UPLOAD_ROOT)
    TEST_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    yield TEST_UPLOAD_ROOT
    rmtree(TEST_UPLOAD_ROOT, ignore_errors=True)


@pytest.fixture
def sample_png(test_upload_dir: Path) -> Path:
    """Create a minimal valid PNG file for tests."""
    path = test_upload_dir / "usage.png"
    # 1x1 transparent PNG
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return path


def test_health(client):
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "ok"


def test_upload_image(client, sample_png, monkeypatch, test_upload_dir: Path):
    """Upload endpoint should accept a PNG and return an extraction preview."""
    monkeypatch.setattr(settings, "upload_dir", test_upload_dir / "uploads")
    monkeypatch.setattr(uploads_router, "ocr_extract_usage", _fake_ocr)

    with sample_png.open("rb") as f:
        response = client.post(
            "/api/uploads",
            files={"file": ("shot1.png", f, "image/png")},
        )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["image_path"]
    assert data["original_filename"] == "shot1.png"
    assert "extracted" in data


def test_confirm_upload(client, sample_png, monkeypatch, test_upload_dir: Path):
    monkeypatch.setattr(settings, "upload_dir", test_upload_dir / "uploads")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    saved_name = "test-image.png"
    (settings.upload_dir / saved_name).write_bytes(sample_png.read_bytes())

    payload = {
        "uploader_name": "Alice",
        "image_path": saved_name,
        "original_filename": "shot1.png",
        "session_usage_pct": 42,
        "weekly_usage_pct": 18,
        "plan_tier": "Pro",
        "extraction_method": "ocr",
        "was_manually_edited": False,
    }
    response = client.post("/api/uploads/confirm", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["uploader_name"] == "Alice"
    assert data["session_usage_pct"] == 42


def test_list_uploads(client, sample_png, monkeypatch, test_upload_dir: Path):
    monkeypatch.setattr(settings, "upload_dir", test_upload_dir / "uploads")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    saved_name = "test-image.png"
    (settings.upload_dir / saved_name).write_bytes(sample_png.read_bytes())

    client.post("/api/uploads/confirm", json={
        "uploader_name": "Bob",
        "image_path": saved_name,
        "session_usage_pct": 10,
        "weekly_usage_pct": 20,
        "extraction_method": "manual",
    })

    response = client.get("/api/uploads?user=Bob")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["uploader_name"] == "Bob"


def test_dashboard_summary(client, sample_png, monkeypatch, test_upload_dir: Path):
    monkeypatch.setattr(settings, "upload_dir", test_upload_dir / "uploads")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    saved_name = "test-image.png"
    (settings.upload_dir / saved_name).write_bytes(sample_png.read_bytes())

    client.post("/api/uploads/confirm", json={
        "uploader_name": "Carol",
        "image_path": saved_name,
        "session_usage_pct": 80,
        "weekly_usage_pct": 90,
        "extraction_method": "ocr",
    })

    response = client.get("/api/dashboard/summary")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["uploads_today"] >= 1
    assert data["uploads_this_week"] >= 1
    assert len(data["leaderboard"]) >= 1
