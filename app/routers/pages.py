"""Server-rendered HTML pages and HTMX partials."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.extraction import ocr_extract_usage, vlm_extract_usage
from app.models import UsageUpload
from app.routers.uploads import _save_upload, _secure_path

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["urlencode"] = lambda value: quote(str(value), safe="")

def _format_datetime_local(dt: Optional[datetime]) -> Optional[str]:
    """Format a UTC datetime for an HTML datetime-local input."""
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M")


@router.get("/")
def upload_page(request: Request, db: Session = Depends(get_db)):
    recent = (
        db.query(UsageUpload)
        .order_by(UsageUpload.uploaded_at.desc())
        .limit(10)
        .all()
    )
    names = sorted(
        {u.uploader_name for u in db.query(UsageUpload.uploader_name).distinct()}
    )
    return templates.TemplateResponse(
        request,
        "upload.html",
        {
            "active": "upload",
            "recent": recent,
            "names": names,
            "max_file_size": settings.max_file_size,
        },
    )


@router.post("/partials/upload-preview")
async def upload_preview(request: Request, file: UploadFile = File(...)):
    full_path, filename, original_name = await _save_upload(file)
    result = ocr_extract_usage(full_path)
    method = "ocr"
    extracted = result["extracted"]
    return templates.TemplateResponse(
        request,
        "_upload_preview.html",
        {
            "image_path": filename,
            "original_filename": original_name,
            "extracted": extracted,
            "raw_text": result.get("raw_text") or "",
            "method": method,
        },
    )


@router.post("/partials/reextract")
async def reextract_preview(request: Request, image_path: str = Form(...)):
    full_path = _secure_path(image_path)
    result = vlm_extract_usage(full_path)
    extracted = result["extracted"]
    return templates.TemplateResponse(
        request,
        "_upload_preview.html",
        {
            "image_path": image_path,
            "original_filename": full_path.name,
            "extracted": extracted,
            "raw_text": result.get("raw_text") or "",
            "method": "vlm",
        },
    )


@router.post("/partials/confirm")
def confirm_upload(
    request: Request,
    uploader_name: str = Form(...),
    image_path: str = Form(...),
    original_filename: str = Form(default=""),
    auth_method: Optional[str] = Form(default=None),
    email: Optional[str] = Form(default=None),
    organization: Optional[str] = Form(default=None),
    plan_tier: Optional[str] = Form(default=None),
    session_usage_pct: Optional[int] = Form(default=None),
    weekly_usage_pct: Optional[int] = Form(default=None),
    weekly_fable_usage_pct: Optional[int] = Form(default=None),
    session_reset_at: Optional[str] = Form(default=None),
    weekly_reset_at: Optional[str] = Form(default=None),
    weekly_fable_reset_at: Optional[str] = Form(default=None),
    extraction_method: str = Form(default="manual"),
    raw_extracted_text: Optional[str] = Form(default=None),
    was_manually_edited: bool = Form(default=True),
    db: Session = Depends(get_db),
):
    def _parse_dt(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            # datetime-local values are naive; treat them as UTC for storage.
            return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    upload = UsageUpload(
        uploader_name=uploader_name.strip(),
        image_path=image_path,
        original_filename=original_filename or image_path,
        auth_method=auth_method,
        email=email,
        organization=organization,
        plan_tier=plan_tier,
        session_usage_pct=session_usage_pct,
        weekly_usage_pct=weekly_usage_pct,
        weekly_fable_usage_pct=weekly_fable_usage_pct,
        session_reset_at=_parse_dt(session_reset_at),
        weekly_reset_at=_parse_dt(weekly_reset_at),
        weekly_fable_reset_at=_parse_dt(weekly_fable_reset_at),
        extraction_method=extraction_method,
        raw_extracted_text=raw_extracted_text,
        was_manually_edited=was_manually_edited,
    )
    db.add(upload)
    db.commit()

    recent = (
        db.query(UsageUpload)
        .order_by(UsageUpload.uploaded_at.desc())
        .limit(10)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "_recent_uploads.html",
        {"recent": recent, "confirmed": True},
    )


@router.get("/dashboard")
def dashboard(
    request: Request,
    user: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: Session = Depends(get_db),
):
    # Summary data
    latest_per_user = (
        db.query(
            UsageUpload.uploader_name,
            UsageUpload.session_usage_pct,
            UsageUpload.weekly_usage_pct,
            UsageUpload.weekly_fable_usage_pct,
            UsageUpload.uploaded_at,
        )
        .distinct(UsageUpload.uploader_name)
        .order_by(UsageUpload.uploader_name, UsageUpload.uploaded_at.desc())
        .all()
    )
    session_values = [r.session_usage_pct for r in latest_per_user if r.session_usage_pct is not None]
    weekly_values = [r.weekly_usage_pct for r in latest_per_user if r.weekly_usage_pct is not None]
    fable_values = [r.weekly_fable_usage_pct for r in latest_per_user if r.weekly_fable_usage_pct is not None]
    team_avg_session = sum(session_values) / len(session_values) if session_values else None
    team_avg_weekly = sum(weekly_values) / len(weekly_values) if weekly_values else None
    team_avg_fable = sum(fable_values) / len(fable_values) if fable_values else None

    leaderboard = sorted(
        latest_per_user,
        key=lambda r: (r.weekly_usage_pct or 0, r.weekly_fable_usage_pct or 0, r.session_usage_pct or 0),
        reverse=True,
    )

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    uploads_today = db.query(UsageUpload).filter(UsageUpload.uploaded_at >= today_start).count()
    uploads_this_week = db.query(UsageUpload).filter(UsageUpload.uploaded_at >= week_start).count()

    # Trend data (last 30 days)
    since = now - timedelta(days=30)
    trend_rows = (
        db.query(UsageUpload)
        .filter(UsageUpload.uploaded_at >= since)
        .order_by(UsageUpload.uploaded_at.asc())
        .all()
    )
    trends_by_user: dict[str, list[dict]] = {}
    for row in trend_rows:
        trends_by_user.setdefault(row.uploader_name, []).append(
            {
                "uploaded_at": row.uploaded_at.isoformat(),
                "session_usage_pct": row.session_usage_pct,
                "weekly_usage_pct": row.weekly_usage_pct,
                "weekly_fable_usage_pct": row.weekly_fable_usage_pct,
            }
        )

    # Filtered uploads list
    query = db.query(UsageUpload)
    if user:
        query = query.filter(UsageUpload.uploader_name.ilike(f"%{user}%"))
    if from_date:
        query = query.filter(UsageUpload.uploaded_at >= from_date)
    if to_date:
        query = query.filter(UsageUpload.uploaded_at <= to_date)
    uploads = query.order_by(UsageUpload.uploaded_at.desc()).limit(200).all()

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "active": "dashboard",
            "team_avg_session": team_avg_session,
            "team_avg_weekly": team_avg_weekly,
            "team_avg_fable": team_avg_fable,
            "leaderboard": leaderboard,
            "uploads_today": uploads_today,
            "uploads_this_week": uploads_this_week,
            "trends": trends_by_user,
            "uploads": uploads,
            "filter_user": user,
            "filter_from": from_date,
            "filter_to": to_date,
        },
    )


@router.get("/dashboard/user/{uploader_name}")
def user_detail(request: Request, uploader_name: str, db: Session = Depends(get_db)):
    uploads = (
        db.query(UsageUpload)
        .filter(UsageUpload.uploader_name == uploader_name)
        .order_by(UsageUpload.uploaded_at.desc())
        .limit(200)
        .all()
    )
    trend = [
        {
            "uploaded_at": u.uploaded_at.isoformat(),
            "session_usage_pct": u.session_usage_pct,
            "weekly_usage_pct": u.weekly_usage_pct,
            "weekly_fable_usage_pct": u.weekly_fable_usage_pct,
        }
        for u in reversed(uploads)
    ]
    return templates.TemplateResponse(
        request,
        "user_detail.html",
        {
            "active": "dashboard",
            "uploader_name": uploader_name,
            "uploads": uploads,
            "trend": trend,
        },
    )
