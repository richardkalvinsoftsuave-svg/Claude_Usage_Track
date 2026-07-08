"""Dashboard aggregation & per-user history endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UsageUpload
from app.schemas import (
    DashboardSummary,
    LeaderboardEntry,
    TrendPoint,
    UserHistoryResponse,
    UserTrend,
    UsageUploadResponse,
)

router = APIRouter()


def _latest_per_user(db: Session):
    """Subquery returning the latest upload id for each uploader."""
    return (
        db.query(
            UsageUpload.uploader_name,
            func.max(UsageUpload.id).label("latest_id"),
        )
        .group_by(UsageUpload.uploader_name)
        .subquery()
    )


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    """Aggregate stats for the dashboard widgets."""
    latest_sq = _latest_per_user(db)
    latest_uploads = (
        db.query(UsageUpload)
        .join(latest_sq, UsageUpload.id == latest_sq.c.latest_id)
        .all()
    )

    session_values = [u.session_usage_pct for u in latest_uploads if u.session_usage_pct is not None]
    weekly_values = [u.weekly_usage_pct for u in latest_uploads if u.weekly_usage_pct is not None]

    leaderboard = sorted(
        [
            LeaderboardEntry(
                uploader_name=u.uploader_name,
                latest_session_pct=u.session_usage_pct,
                latest_weekly_pct=u.weekly_usage_pct,
                last_upload_at=u.uploaded_at,
            )
            for u in latest_uploads
        ],
        key=lambda e: (e.latest_weekly_pct or 0, e.latest_session_pct or 0),
        reverse=True,
    )

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

    uploads_today = db.query(UsageUpload).filter(UsageUpload.uploaded_at >= today_start).count()
    uploads_this_week = db.query(UsageUpload).filter(UsageUpload.uploaded_at >= week_start).count()

    since = now - timedelta(days=days)
    trend_rows = (
        db.query(UsageUpload)
        .filter(UsageUpload.uploaded_at >= since)
        .order_by(UsageUpload.uploaded_at.asc())
        .all()
    )

    trends_by_user: dict[str, List[TrendPoint]] = {}
    for row in trend_rows:
        point = TrendPoint(
            uploaded_at=row.uploaded_at,
            session_usage_pct=row.session_usage_pct,
            weekly_usage_pct=row.weekly_usage_pct,
        )
        trends_by_user.setdefault(row.uploader_name, []).append(point)

    per_user_trends = [
        UserTrend(uploader_name=name, points=points)
        for name, points in trends_by_user.items()
    ]

    return DashboardSummary(
        team_avg_session_usage=sum(session_values) / len(session_values) if session_values else None,
        team_avg_weekly_usage=sum(weekly_values) / len(weekly_values) if weekly_values else None,
        leaderboard=leaderboard,
        uploads_today=uploads_today,
        uploads_this_week=uploads_this_week,
        per_user_trends=per_user_trends,
    )


@router.get("/users/{uploader_name}/history", response_model=UserHistoryResponse)
def user_history(
    uploader_name: str,
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> UserHistoryResponse:
    """Full history and trend for a single uploader."""
    uploads = (
        db.query(UsageUpload)
        .filter(UsageUpload.uploader_name == uploader_name)
        .order_by(UsageUpload.uploaded_at.desc())
        .limit(limit)
        .all()
    )
    if not uploads:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No uploads found for this user",
        )

    trend = [
        TrendPoint(
            uploaded_at=u.uploaded_at,
            session_usage_pct=u.session_usage_pct,
            weekly_usage_pct=u.weekly_usage_pct,
        )
        for u in reversed(uploads)
    ]

    return UserHistoryResponse(
        uploader_name=uploader_name,
        total_uploads=len(uploads),
        uploads=[UsageUploadResponse.model_validate(u) for u in uploads],
        trend=trend,
    )
