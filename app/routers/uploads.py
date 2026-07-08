"""Upload & extraction API endpoints."""
from __future__ import annotations

import io
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from PIL import Image
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.extraction import docling_extract_usage, ocr_extract_usage, vlm_extract_usage
from app.models import UsageUpload
from app.schemas import (
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
    extraction backends (PaddleOCR, Docling, Ollama VLM).
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
) -> UploadPreviewResponse:
    """Save an image and run the default extraction (OCR, or VLM if configured)."""
    full_path, filename, original_name = await _save_upload(file)

    mode = settings.extraction_mode
    if mode == "vlm_only":
        result = vlm_extract_usage(full_path)
        method = "vlm"
    elif mode.startswith("docling"):
        result = docling_extract_usage(full_path)
        method = "docling"
    else:
        result = ocr_extract_usage(full_path)
        method = "ocr"

    extracted = result["extracted"]
    raw_text = result.get("raw_text")

    return UploadPreviewResponse(
        image_path=filename,
        original_filename=original_name,
        extracted=extracted,
        raw_text=raw_text or None,
    )


@router.post("/reextract", response_model=UploadPreviewResponse)
async def reextract_upload(
    image_path: str = Query(..., description="Relative image path returned by /api/uploads"),
) -> UploadPreviewResponse:
    """Re-run extraction using the local Ollama VLM (manual trigger only)."""
    full_path = _secure_path(image_path)
    if not full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    result = vlm_extract_usage(full_path)
    return UploadPreviewResponse(
        image_path=image_path,
        original_filename=full_path.name,
        extracted=result["extracted"],
        raw_text=result.get("raw_text") or None,
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

    upload = UsageUpload(
        uploader_name=payload.uploader_name.strip(),
        image_path=payload.image_path,
        original_filename=payload.original_filename or full_path.name,
        auth_method=payload.auth_method,
        email=payload.email,
        organization=payload.organization,
        plan_tier=payload.plan_tier,
        session_usage_pct=payload.session_usage_pct,
        weekly_usage_pct=payload.weekly_usage_pct,
        weekly_fable_usage_pct=payload.weekly_fable_usage_pct,
        session_reset_at=payload.session_reset_at,
        weekly_reset_at=payload.weekly_reset_at,
        weekly_fable_reset_at=payload.weekly_fable_reset_at,
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
    user: Optional[str] = Query(None, description="Filter by uploader name"),
    from_date: Optional[str] = Query(None, alias="from", description="UTC date ISO"),
    to_date: Optional[str] = Query(None, alias="to", description="UTC date ISO"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> PaginatedUploads:
    """Filterable, paginated list of confirmed uploads."""
    query = db.query(UsageUpload)

    if user:
        query = query.filter(UsageUpload.uploader_name.ilike(f"%{user}%"))
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
