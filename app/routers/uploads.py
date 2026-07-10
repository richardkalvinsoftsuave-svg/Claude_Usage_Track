"""Upload & extraction API endpoints."""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from PIL import Image
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.extraction import ocr_extract_usage, vlm_extract_usage
from app.models import UsageUpload
from app.schemas import (
    ExtractedUsage,
    PaginatedUploads,
    UploadConfirmRequest,
    UploadPreviewResponse,
    UsageUploadResponse,
)

router = APIRouter()

_ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
# Map PIL-detected formats to file extensions.
_FORMAT_TO_EXT = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}


def _active_reset_at(db: Session, email: str, metric: str) -> Optional[datetime]:
    """Return the still-active reset datetime for *email*'s current cycle, if any.

    A reset date is only trusted the first time it's seen for a cycle; once
    recorded, later uploads within the same cycle must keep showing that same
    value instead of whatever a fresh (possibly noisier) extraction produces.
    Returns None once the recorded reset time has passed, since that means a
    new cycle has started and the freshly extracted value should be trusted.
    """
    latest = (
        db.query(UsageUpload)
        .filter(UsageUpload.email == email)
        .order_by(UsageUpload.uploaded_at.desc())
        .first()
    )
    if latest is None:
        return None
    reset_at = latest.weekly_reset_at if metric == "weekly" else latest.weekly_fable_reset_at
    if reset_at is None:
        return None
    if reset_at.tzinfo is None:
        reset_at = reset_at.replace(tzinfo=timezone.utc)
    return reset_at if reset_at > datetime.now(timezone.utc) else None


def _secure_path(image_path: str) -> Path:
    """Resolve an image path inside the configured upload directory."""
    base = settings.upload_dir.resolve()
    target = (base / image_path).resolve()
    # Prevent directory traversal outside the upload folder.
    if base not in target.parents and target != base:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image path",
        )
    return target


async def _save_upload(file: UploadFile) -> tuple[Path, str, str]:
    """Validate and save an uploaded image, returning (full_path, filename, original_name).

    The image is always saved as PNG to ensure broad compatibility with all
    extraction backends (PaddleOCR/RapidOCR, Ollama VLM).
    """
    original_name = file.filename or "upload.png"
    ext = Path(original_name).suffix.lower()
    content_type = file.content_type or ""

    if content_type not in _ALLOWED_CONTENT_TYPES and ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {content_type or ext}",
        )

    contents = await file.read()
    if len(contents) > settings.max_file_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.max_file_size} bytes",
        )

    # Verify the actual image format and convert to PNG.
    try:
        image = Image.open(io.BytesIO(contents))
        actual_format = image.format  # e.g. "PNG", "JPEG", "WEBP"
        if actual_format not in _FORMAT_TO_EXT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported image format: {actual_format}",
            )
        # Always save as PNG for maximum compatibility with extraction backends.
        # This also fixes files that have a misleading extension (e.g. WEBP saved as .png).
        png_buf = io.BytesIO()
        # Convert to RGB if necessary (RGBA/LA → RGB for JPEG-incompatible modes).
        if image.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            background.paste(
                image, mask=image.split()[-1] if image.mode == "RGBA" else None
            )
            image = background
        elif image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        image.save(png_buf, format="PNG")
        contents = png_buf.getvalue()
        ext = ".png"
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot read image: {exc}",
        ) from exc

    filename = f"{uuid.uuid4().hex}{ext}"
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    full_path = settings.upload_dir / filename
    full_path.write_bytes(contents)
    return full_path, filename, original_name


@router.post("", response_model=UploadPreviewResponse)
async def create_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> UploadPreviewResponse:
    """Save an image and run OCR extraction (RapidOCR primary, PaddleOCR fallback)."""
    full_path, filename, original_name = await _save_upload(file)

    result = ocr_extract_usage(full_path)
    extracted = result["extracted"]
    if isinstance(extracted, dict):
        extracted = ExtractedUsage(**extracted)
    raw_text = result.get("raw_text")

    weekly_locked = False
    fable_locked = False
    if extracted.email:
        email = extracted.email.strip().lower()
        active_weekly = _active_reset_at(db, email, "weekly")
        if active_weekly is not None:
            extracted.weekly_reset_at = active_weekly
            weekly_locked = True
        active_fable = _active_reset_at(db, email, "fable")
        if active_fable is not None:
            extracted.weekly_fable_reset_at = active_fable
            fable_locked = True

    return UploadPreviewResponse(
        image_path=filename,
        original_filename=original_name,
        extracted=extracted,
        raw_text=raw_text or None,
        weekly_reset_locked=weekly_locked,
        fable_reset_locked=fable_locked,
    )


@router.post("/reextract", response_model=UploadPreviewResponse)
async def reextract_upload(
    image_path: str = Query(..., description="Relative image path returned by /api/uploads"),
    db: Session = Depends(get_db),
) -> UploadPreviewResponse:
    """Re-run extraction using the local Ollama VLM (manual trigger only)."""
    full_path = _secure_path(image_path)
    if not full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    result = vlm_extract_usage(full_path)
    extracted = result["extracted"]
    if isinstance(extracted, dict):
        extracted = ExtractedUsage(**extracted)

    weekly_locked = False
    fable_locked = False
    if extracted.email:
        email = extracted.email.strip().lower()
        active_weekly = _active_reset_at(db, email, "weekly")
        if active_weekly is not None:
            extracted.weekly_reset_at = active_weekly
            weekly_locked = True
        active_fable = _active_reset_at(db, email, "fable")
        if active_fable is not None:
            extracted.weekly_fable_reset_at = active_fable
            fable_locked = True

    return UploadPreviewResponse(
        image_path=image_path,
        original_filename=full_path.name,
        extracted=extracted,
        raw_text=result.get("raw_text") or None,
        weekly_reset_locked=weekly_locked,
        fable_reset_locked=fable_locked,
    )


@router.post("/confirm", response_model=UsageUploadResponse, status_code=status.HTTP_201_CREATED)
def confirm_upload(
    payload: UploadConfirmRequest,
    db: Session = Depends(get_db),
) -> UsageUploadResponse:
    """Persist a user-confirmed upload."""
    full_path = _secure_path(payload.image_path)
    if not full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    email = payload.email.strip().lower()
    # Re-derive the lock server-side rather than trusting whatever reset
    # dates arrive in the payload: if this email's cycle is still active,
    # keep the reset date that was already recorded for it.
    weekly_reset_at = _active_reset_at(db, email, "weekly") or payload.weekly_reset_at
    fable_reset_at = _active_reset_at(db, email, "fable") or payload.weekly_fable_reset_at

    upload = UsageUpload(
        email=email,
        image_path=payload.image_path,
        original_filename=payload.original_filename or full_path.name,
        auth_method=payload.auth_method,
        organization=payload.organization,
        plan_tier=payload.plan_tier,
        weekly_usage_pct=payload.weekly_usage_pct,
        weekly_fable_usage_pct=payload.weekly_fable_usage_pct,
        weekly_reset_at=weekly_reset_at,
        weekly_fable_reset_at=fable_reset_at,
        extraction_method=payload.extraction_method,
        raw_extracted_text=payload.raw_extracted_text,
        was_manually_edited=payload.was_manually_edited,
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)
    return UsageUploadResponse.model_validate(upload)


@router.get("", response_model=PaginatedUploads)
def list_uploads(
    email: Optional[str] = Query(None, description="Filter by email"),
    from_date: Optional[str] = Query(None, alias="from", description="UTC date ISO"),
    to_date: Optional[str] = Query(None, alias="to", description="UTC date ISO"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> PaginatedUploads:
    """Filterable, paginated list of confirmed uploads."""
    query = db.query(UsageUpload)

    if email:
        query = query.filter(UsageUpload.email.ilike(f"%{email}%"))
    if from_date:
        query = query.filter(UsageUpload.uploaded_at >= from_date)
    if to_date:
        query = query.filter(UsageUpload.uploaded_at <= to_date)

    total = query.count()
    items = (
        query.order_by(UsageUpload.uploaded_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return PaginatedUploads(
        total=total,
        skip=skip,
        limit=limit,
        items=[UsageUploadResponse.model_validate(item) for item in items],
    )


@router.get("/{upload_id}", response_model=UsageUploadResponse)
def get_upload(upload_id: int, db: Session = Depends(get_db)) -> UsageUploadResponse:
    """Single upload detail."""
    item = db.query(UsageUpload).filter(UsageUpload.id == upload_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")
    return UsageUploadResponse.model_validate(item)
