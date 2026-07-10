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
            "weekly_usage_pct": 5,
            "weekly_fable_usage_pct": 2,
            "email": "alice@example.com",
            "plan_tier": "Pro",
            "weekly_reset_at": None,
            "weekly_fable_reset_at": None,
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
        "email": "alice@example.com",
        "image_path": saved_name,
        "original_filename": "shot1.png",
        "weekly_usage_pct": 42,
        "weekly_fable_usage_pct": 18,
        "plan_tier": "Pro",
        "extraction_method": "ocr",
        "was_manually_edited": False,
    }
    response = client.post("/api/uploads/confirm", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == "alice@example.com"
    assert data["weekly_usage_pct"] == 42
    assert data["weekly_fable_usage_pct"] == 18


def test_list_uploads(client, sample_png, monkeypatch, test_upload_dir: Path):
    monkeypatch.setattr(settings, "upload_dir", test_upload_dir / "uploads")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    saved_name = "test-image.png"
    (settings.upload_dir / saved_name).write_bytes(sample_png.read_bytes())

    client.post("/api/uploads/confirm", json={
        "email": "bob@example.com",
        "image_path": saved_name,
        "weekly_usage_pct": 10,
        "weekly_fable_usage_pct": 5,
        "extraction_method": "manual",
    })

    response = client.get("/api/uploads?email=bob@example.com")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["email"] == "bob@example.com"


def test_dashboard_summary(client, sample_png, monkeypatch, test_upload_dir: Path):
    monkeypatch.setattr(settings, "upload_dir", test_upload_dir / "uploads")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    saved_name = "test-image.png"
    (settings.upload_dir / saved_name).write_bytes(sample_png.read_bytes())

    client.post("/api/uploads/confirm", json={
        "email": "carol@example.com",
        "image_path": saved_name,
        "weekly_usage_pct": 80,
        "weekly_fable_usage_pct": 40,
        "extraction_method": "ocr",
    })

    response = client.get("/api/dashboard/summary")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["uploads_today"] >= 1
    assert data["uploads_this_week"] >= 1
    assert len(data["leaderboard"]) >= 1
    assert len(data["dates"]) > 0
    assert len(data["users"]) >= 1


def test_dashboard_compare(client, sample_png, monkeypatch, test_upload_dir: Path):
    monkeypatch.setattr(settings, "upload_dir", test_upload_dir / "uploads")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    saved_name = "test-image.png"
    (settings.upload_dir / saved_name).write_bytes(sample_png.read_bytes())

    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date().isoformat()

    client.post("/api/uploads/confirm", json={
        "email": "dave@example.com",
        "image_path": saved_name,
        "weekly_usage_pct": 20,
        "weekly_fable_usage_pct": 10,
        "extraction_method": "ocr",
    })

    response = client.get(f"/api/dashboard/compare?from={today}&to={today}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["from_date"] == today
    assert data["to_date"] == today
    assert any(u["email"] == "dave@example.com" for u in data["users"])


def test_reset_date_locked_within_active_cycle(client, sample_png, monkeypatch, test_upload_dir: Path):
    """A second upload in the same still-active cycle must keep the first reset date."""
    monkeypatch.setattr(settings, "upload_dir", test_upload_dir / "uploads")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    first_reset = (now + timedelta(days=5)).isoformat()
    second_reset = (now + timedelta(days=2)).isoformat()  # should be ignored

    name1 = "reset1.png"
    (settings.upload_dir / name1).write_bytes(sample_png.read_bytes())
    resp1 = client.post("/api/uploads/confirm", json={
        "email": "erin@example.com",
        "image_path": name1,
        "weekly_usage_pct": 10,
        "weekly_fable_usage_pct": 5,
        "weekly_reset_at": first_reset,
        "weekly_fable_reset_at": first_reset,
        "extraction_method": "ocr",
    })
    assert resp1.status_code == status.HTTP_201_CREATED

    name2 = "reset2.png"
    (settings.upload_dir / name2).write_bytes(sample_png.read_bytes())
    resp2 = client.post("/api/uploads/confirm", json={
        "email": "erin@example.com",
        "image_path": name2,
        "weekly_usage_pct": 20,
        "weekly_fable_usage_pct": 8,
        "weekly_reset_at": second_reset,
        "weekly_fable_reset_at": second_reset,
        "extraction_method": "ocr",
    })
    assert resp2.status_code == status.HTTP_201_CREATED
    data2 = resp2.json()
    assert data2["weekly_reset_at"].startswith(first_reset[:16])
    assert data2["weekly_fable_reset_at"].startswith(first_reset[:16])


def test_reset_date_unlocked_after_cycle_expires(client, sample_png, monkeypatch, test_upload_dir: Path):
    """Once the recorded reset date has passed, the next upload's value is trusted again."""
    monkeypatch.setattr(settings, "upload_dir", test_upload_dir / "uploads")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    expired_reset = (now - timedelta(hours=1)).isoformat()
    new_reset = (now + timedelta(days=7)).isoformat()

    name1 = "expired1.png"
    (settings.upload_dir / name1).write_bytes(sample_png.read_bytes())
    client.post("/api/uploads/confirm", json={
        "email": "frank@example.com",
        "image_path": name1,
        "weekly_usage_pct": 95,
        "weekly_fable_usage_pct": 40,
        "weekly_reset_at": expired_reset,
        "weekly_fable_reset_at": expired_reset,
        "extraction_method": "ocr",
    })

    name2 = "expired2.png"
    (settings.upload_dir / name2).write_bytes(sample_png.read_bytes())
    resp = client.post("/api/uploads/confirm", json={
        "email": "frank@example.com",
        "image_path": name2,
        "weekly_usage_pct": 3,
        "weekly_fable_usage_pct": 1,
        "weekly_reset_at": new_reset,
        "weekly_fable_reset_at": new_reset,
        "extraction_method": "ocr",
    })
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["weekly_reset_at"].startswith(new_reset[:16])


def test_upload_preview_shows_locked_reset(client, sample_png, monkeypatch, test_upload_dir: Path):
    """The preview (before confirm) should also reflect the locked reset date."""
    monkeypatch.setattr(settings, "upload_dir", test_upload_dir / "uploads")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    locked_reset = (now + timedelta(days=4)).isoformat()

    name1 = "locked1.png"
    (settings.upload_dir / name1).write_bytes(sample_png.read_bytes())
    client.post("/api/uploads/confirm", json={
        "email": "grace@example.com",
        "image_path": name1,
        "weekly_usage_pct": 30,
        "weekly_fable_usage_pct": 15,
        "weekly_reset_at": locked_reset,
        "weekly_fable_reset_at": locked_reset,
        "extraction_method": "ocr",
    })

    def _fake_ocr_no_reset(image_path):
        return {
            "extracted": {
                "email": "grace@example.com",
                "weekly_usage_pct": 45,
                "weekly_fable_usage_pct": 20,
                "weekly_reset_at": None,
                "weekly_fable_reset_at": None,
            },
            "raw_text": "fake ocr text",
        }

    monkeypatch.setattr(uploads_router, "ocr_extract_usage", _fake_ocr_no_reset)

    with sample_png.open("rb") as f:
        resp = client.post("/api/uploads", files={"file": ("shot2.png", f, "image/png")})

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["weekly_reset_locked"] is True
    assert data["fable_reset_locked"] is True
    assert data["extracted"]["weekly_reset_at"].startswith(locked_reset[:16])


def test_update_reset_date(client, sample_png, monkeypatch, test_upload_dir: Path):
    """Correcting a wrongly-extracted reset date updates the stored rows."""
    monkeypatch.setattr(settings, "upload_dir", test_upload_dir / "uploads")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    wrong_reset = (now + timedelta(days=3)).isoformat()
    corrected_reset = (now + timedelta(days=6)).isoformat()

    name1 = "correct1.png"
    (settings.upload_dir / name1).write_bytes(sample_png.read_bytes())
    client.post("/api/uploads/confirm", json={
        "email": "heidi@example.com",
        "image_path": name1,
        "weekly_usage_pct": 50,
        "weekly_fable_usage_pct": 25,
        "weekly_reset_at": wrong_reset,
        "extraction_method": "ocr",
    })

    resp = client.patch(
        "/api/dashboard/users/heidi@example.com/reset-date",
        json={"metric": "weekly", "reset_at": corrected_reset},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["rows_updated"] == 1
    assert data["reset_at"].startswith(corrected_reset[:16])

    history = client.get("/api/dashboard/users/heidi@example.com/history").json()
    assert history["uploads"][0]["weekly_reset_at"].startswith(corrected_reset[:16])


def test_dashboard_compare_detects_reset(client, db_session):
    """A cycle rollover between the two compared dates should be flagged, not diffed."""
    from datetime import datetime, timedelta, timezone
    from app.models import UsageUpload

    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    row1 = UsageUpload(
        email="ivan@example.com",
        image_path="ivan1.png",
        original_filename="ivan1.png",
        weekly_usage_pct=92,
        weekly_fable_usage_pct=40,
        weekly_reset_at=yesterday + timedelta(hours=3),
        extraction_method="ocr",
        uploaded_at=yesterday,
    )
    row2 = UsageUpload(
        email="ivan@example.com",
        image_path="ivan2.png",
        original_filename="ivan2.png",
        weekly_usage_pct=6,
        weekly_fable_usage_pct=3,
        weekly_reset_at=yesterday + timedelta(days=7, hours=3),
        extraction_method="ocr",
        uploaded_at=now,
    )
    db_session.add_all([row1, row2])
    db_session.commit()

    resp = client.get(
        f"/api/dashboard/compare?from={yesterday.date().isoformat()}&to={now.date().isoformat()}"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    entry = next(u for u in data["users"] if u["email"] == "ivan@example.com")
    assert entry["weekly_reset_occurred"] is True
    assert entry["weekly_delta"] is None


def test_leaderboard_flags_at_risk_projection(client, db_session):
    """A fast climb early in the cycle should project past 100% and be flagged."""
    from datetime import datetime, timedelta, timezone
    from app.models import UsageUpload

    now = datetime.now(timezone.utc)
    reset_at = now + timedelta(hours=6)

    # 40% -> 70% over 3 hours (10%/hour); at that pace 6h remaining overshoots 100%.
    row1 = UsageUpload(
        email="judy@example.com",
        image_path="judy1.png",
        original_filename="judy1.png",
        weekly_usage_pct=40,
        weekly_fable_usage_pct=10,
        weekly_reset_at=reset_at,
        weekly_fable_reset_at=reset_at,
        extraction_method="ocr",
        uploaded_at=now - timedelta(hours=3),
    )
    row2 = UsageUpload(
        email="judy@example.com",
        image_path="judy2.png",
        original_filename="judy2.png",
        weekly_usage_pct=70,
        weekly_fable_usage_pct=15,
        weekly_reset_at=reset_at,
        weekly_fable_reset_at=reset_at,
        extraction_method="ocr",
        uploaded_at=now,
    )
    db_session.add_all([row1, row2])
    db_session.commit()

    resp = client.get("/api/dashboard/summary")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    entry = next(u for u in data["leaderboard"] if u["email"] == "judy@example.com")
    assert entry["weekly_at_risk"] is True
    assert entry["weekly_projected_pct"] is not None
    assert entry["weekly_projected_pct"] >= 100
