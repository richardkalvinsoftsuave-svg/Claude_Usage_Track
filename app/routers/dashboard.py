"""Dashboard aggregation & per-user history endpoints."""
from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UsageUpload
from app.schemas import (
    DailyUsage,
    DashboardCompareResponse,
    DashboardSummary,
    LeaderboardEntry,
    ResetDateUpdateRequest,
    ResetDateUpdateResponse,
    TrendPoint,
    UserComparison,
    UserDayRow,
    UserHistoryResponse,
    UserTrend,
    UsageUploadResponse,
)

router = APIRouter()

# A projection counts as "at risk" once it's forecast to reach this % of the
# weekly cap before the cycle resets.
_AT_RISK_THRESHOLD = 100


def _date_str(dt: datetime) -> str:
    """Return YYYY-MM-DD for a datetime."""
    return dt.date().isoformat()


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize a (possibly naive, e.g. from SQLite) datetime to aware UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _reset_attr(metric: str) -> str:
    return "weekly_reset_at" if metric == "weekly" else "weekly_fable_reset_at"


def _pct_attr(metric: str) -> str:
    return "weekly_usage_pct" if metric == "weekly" else "weekly_fable_usage_pct"


def _project_metric(
    rows: List[UsageUpload], metric: str, now: datetime
) -> Tuple[Optional[int], bool]:
    """Project a user's end-of-cycle % for one metric from their upload history.

    Uses only rows that share the *current* (still-active) reset datetime,
    so a reset that happened mid-window doesn't get averaged into the rate.
    Returns (None, False) when there's no active cycle or too little data
    (fewer than 2 points, or they arrived at the same instant) to compute a
    rate.
    """
    reset_attr = _reset_attr(metric)
    pct_attr = _pct_attr(metric)

    dated = sorted(rows, key=lambda r: r.uploaded_at)
    if not dated:
        return None, False

    latest_reset = _as_utc(getattr(dated[-1], reset_attr))
    if latest_reset is None or latest_reset <= now:
        return None, False  # no active cycle to project

    cycle_rows = [r for r in dated if _as_utc(getattr(r, reset_attr)) == latest_reset]
    if len(cycle_rows) < 2:
        return None, False

    first, last = cycle_rows[0], cycle_rows[-1]
    first_pct, last_pct = getattr(first, pct_attr), getattr(last, pct_attr)
    if first_pct is None or last_pct is None:
        return None, False

    elapsed_hours = (_as_utc(last.uploaded_at) - _as_utc(first.uploaded_at)).total_seconds() / 3600
    if elapsed_hours <= 0:
        return None, False

    hours_remaining = (latest_reset - now).total_seconds() / 3600
    rate_per_hour = (last_pct - first_pct) / elapsed_hours
    projected = last_pct + rate_per_hour * hours_remaining
    projected_pct = max(0, round(projected))
    return projected_pct, projected_pct >= _AT_RISK_THRESHOLD


def _projections_for(rows: List[UsageUpload], now: datetime) -> Dict[str, object]:
    """Compute both metrics' projections for one user's rows in one call."""
    weekly_pct, weekly_risk = _project_metric(rows, "weekly", now)
    fable_pct, fable_risk = _project_metric(rows, "fable", now)
    return {
        "weekly_projected_pct": weekly_pct,
        "weekly_at_risk": weekly_risk,
        "fable_projected_pct": fable_pct,
        "fable_at_risk": fable_risk,
    }


def _latest_per_email_subquery(db: Session):
    """Subquery returning the latest upload id for each email."""
    return (
        db.query(
            UsageUpload.email,
            func.max(UsageUpload.id).label("latest_id"),
        )
        .group_by(UsageUpload.email)
        .subquery()
    )


def _build_leaderboard(db: Session, now: datetime) -> List[LeaderboardEntry]:
    """Build leaderboard from latest upload per email, annotated with risk."""
    latest_sq = _latest_per_email_subquery(db)
    latest_uploads = (
        db.query(UsageUpload)
        .join(latest_sq, UsageUpload.id == latest_sq.c.latest_id)
        .all()
    )
    # A projection only ever needs the current (<= ~7 day) cycle; two weeks
    # of history is comfortably enough while keeping each per-email query cheap.
    since = now - timedelta(days=14)
    entries = []
    for u in latest_uploads:
        rows = (
            db.query(UsageUpload)
            .filter(UsageUpload.email == u.email, UsageUpload.uploaded_at >= since)
            .all()
        )
        projections = _projections_for(rows, now)
        entries.append(
            LeaderboardEntry(
                email=u.email,
                latest_weekly=u.weekly_usage_pct,
                latest_fable=u.weekly_fable_usage_pct,
                last_upload_at=u.uploaded_at,
                latest_image_path=u.image_path,
                **projections,
            )
        )
    return sorted(
        entries,
        key=lambda e: (e.weekly_at_risk or e.fable_at_risk, e.latest_weekly or 0, e.latest_fable or 0),
        reverse=True,
    )


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    """Aggregate stats for the dashboard widgets."""
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

    # Build date list
    dates = []
    current = since.date()
    end = now.date()
    while current <= end:
        dates.append(current.isoformat())
        current += timedelta(days=1)

    # Aggregate per email per day using MAX
    daily_by_email: Dict[str, Dict[str, Dict[str, Optional[int]]]] = {}
    latest_by_email: Dict[str, UsageUpload] = {}

    for row in trend_rows:
        email = row.email
        d = _date_str(row.uploaded_at)

        if email not in daily_by_email:
            daily_by_email[email] = {}
        day_bucket = daily_by_email[email].setdefault(d, {"weekly": None, "fable": None})

        if row.weekly_usage_pct is not None:
            day_bucket["weekly"] = max(
                day_bucket["weekly"] if day_bucket["weekly"] is not None else 0,
                row.weekly_usage_pct,
            )
        if row.weekly_fable_usage_pct is not None:
            day_bucket["fable"] = max(
                day_bucket["fable"] if day_bucket["fable"] is not None else 0,
                row.weekly_fable_usage_pct,
            )

        if email not in latest_by_email or row.uploaded_at > latest_by_email[email].uploaded_at:
            latest_by_email[email] = row

    # Rows per email, for burn-rate projections (reuses the already-fetched
    # trend_rows instead of issuing another query per user).
    rows_by_email: Dict[str, List[UsageUpload]] = {}
    for row in trend_rows:
        rows_by_email.setdefault(row.email, []).append(row)

    user_rows: List[UserDayRow] = []
    for email, days_map in daily_by_email.items():
        latest = latest_by_email[email]
        daily: Dict[str, DailyUsage] = {
            d: DailyUsage(weekly=v.get("weekly"), fable=v.get("fable"))
            for d, v in days_map.items()
        }
        projections = _projections_for(rows_by_email[email], now)
        user_rows.append(
            UserDayRow(
                email=email,
                organization=latest.organization,
                plan_tier=latest.plan_tier,
                daily=daily,
                latest_weekly=latest.weekly_usage_pct,
                latest_fable=latest.weekly_fable_usage_pct,
                last_upload_at=latest.uploaded_at,
                latest_image_path=latest.image_path,
                **projections,
            )
        )

    # Per-user trends
    trends_by_user: Dict[str, List[TrendPoint]] = {}
    for row in trend_rows:
        point = TrendPoint(
            uploaded_at=row.uploaded_at,
            weekly_usage_pct=row.weekly_usage_pct,
            weekly_fable_usage_pct=row.weekly_fable_usage_pct,
        )
        trends_by_user.setdefault(row.email, []).append(point)

    per_user_trends = [
        UserTrend(email=email, points=points)
        for email, points in trends_by_user.items()
    ]

    leaderboard = _build_leaderboard(db, now)

    return DashboardSummary(
        dates=dates,
        users=user_rows,
        leaderboard=leaderboard,
        uploads_today=uploads_today,
        uploads_this_week=uploads_this_week,
        per_user_trends=per_user_trends,
    )


@router.get("/compare", response_model=DashboardCompareResponse)
def dashboard_compare(
    from_date: str = Query(..., alias="from", description="Start date YYYY-MM-DD"),
    to_date: str = Query(..., alias="to", description="End date YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> DashboardCompareResponse:
    """Compare each user's usage between two dates."""
    try:
        from_dt = date_type.fromisoformat(from_date)
        to_dt = date_type.fromisoformat(to_date)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dates must be in YYYY-MM-DD format",
        )

    from_start = datetime(from_dt.year, from_dt.month, from_dt.day, tzinfo=timezone.utc)
    from_end = from_start + timedelta(days=1)
    to_start = datetime(to_dt.year, to_dt.month, to_dt.day, tzinfo=timezone.utc)
    to_end = to_start + timedelta(days=1)

    from_rows = (
        db.query(UsageUpload)
        .filter(UsageUpload.uploaded_at >= from_start)
        .filter(UsageUpload.uploaded_at < from_end)
        .all()
    )
    to_rows = (
        db.query(UsageUpload)
        .filter(UsageUpload.uploaded_at >= to_start)
        .filter(UsageUpload.uploaded_at < to_end)
        .all()
    )

    def _max_by_email(rows):
        out: Dict[str, Dict[str, object]] = {}
        for row in rows:
            bucket = out.setdefault(
                row.email,
                {"weekly": None, "fable": None, "weekly_reset_at": None, "fable_reset_at": None},
            )
            if row.weekly_usage_pct is not None:
                bucket["weekly"] = max(
                    bucket["weekly"] if bucket["weekly"] is not None else 0,
                    row.weekly_usage_pct,
                )
            if row.weekly_fable_usage_pct is not None:
                bucket["fable"] = max(
                    bucket["fable"] if bucket["fable"] is not None else 0,
                    row.weekly_fable_usage_pct,
                )
            # Track the reset date of whichever row in this bucket is latest,
            # so we can tell whether a cycle rolled over between from/to.
            current_latest_at = bucket.get("_latest_at")
            if current_latest_at is None or row.uploaded_at >= current_latest_at:
                bucket["weekly_reset_at"] = _as_utc(row.weekly_reset_at)
                bucket["fable_reset_at"] = _as_utc(row.weekly_fable_reset_at)
                bucket["_latest_at"] = row.uploaded_at
        return out

    from_by_email = _max_by_email(from_rows)
    to_by_email = _max_by_email(to_rows)
    all_emails = sorted(set(from_by_email) | set(to_by_email))

    def _delta(to_val, from_val):
        if to_val is None or from_val is None:
            return None
        return to_val - from_val

    def _reset_occurred(email: str, metric: str) -> bool:
        key = f"{metric}_reset_at"
        from_reset = from_by_email.get(email, {}).get(key)
        to_reset = to_by_email.get(email, {}).get(key)
        return from_reset is not None and to_reset is not None and from_reset != to_reset

    users = []
    for email in all_emails:
        weekly_reset_occurred = _reset_occurred(email, "weekly")
        fable_reset_occurred = _reset_occurred(email, "fable")
        users.append(
            UserComparison(
                email=email,
                weekly_from=from_by_email.get(email, {}).get("weekly"),
                weekly_to=to_by_email.get(email, {}).get("weekly"),
                weekly_delta=None if weekly_reset_occurred else _delta(
                    to_by_email.get(email, {}).get("weekly"),
                    from_by_email.get(email, {}).get("weekly"),
                ),
                weekly_reset_occurred=weekly_reset_occurred,
                fable_from=from_by_email.get(email, {}).get("fable"),
                fable_to=to_by_email.get(email, {}).get("fable"),
                fable_delta=None if fable_reset_occurred else _delta(
                    to_by_email.get(email, {}).get("fable"),
                    from_by_email.get(email, {}).get("fable"),
                ),
                fable_reset_occurred=fable_reset_occurred,
            )
        )

    return DashboardCompareResponse(
        from_date=from_date,
        to_date=to_date,
        users=users,
    )


@router.get("/users/{email}/history", response_model=UserHistoryResponse)
def user_history(
    email: str,
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> UserHistoryResponse:
    """Full history and trend for a single email."""
    uploads = (
        db.query(UsageUpload)
        .filter(UsageUpload.email == email)
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
            weekly_usage_pct=u.weekly_usage_pct,
            weekly_fable_usage_pct=u.weekly_fable_usage_pct,
        )
        for u in reversed(uploads)
    ]

    return UserHistoryResponse(
        email=email,
        total_uploads=len(uploads),
        uploads=[UsageUploadResponse.model_validate(u) for u in uploads],
        trend=trend,
    )


@router.patch("/users/{email}/reset-date", response_model=ResetDateUpdateResponse)
def update_reset_date(
    email: str,
    payload: ResetDateUpdateRequest,
    db: Session = Depends(get_db),
) -> ResetDateUpdateResponse:
    """Correct a wrongly-extracted reset date for a user's active cycle.

    This is the only place reset dates can be changed after the fact — the
    upload flow locks them once recorded (see uploads.py _active_reset_at) to
    keep a cycle's rows consistent, so a fix here has to update every row
    that shares the old value rather than just the newest one.
    """
    column = UsageUpload.weekly_reset_at if payload.metric == "weekly" else UsageUpload.weekly_fable_reset_at

    latest = (
        db.query(UsageUpload)
        .filter(UsageUpload.email == email)
        .order_by(UsageUpload.uploaded_at.desc())
        .first()
    )
    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No uploads found for this user",
        )

    old_value = latest.weekly_reset_at if payload.metric == "weekly" else latest.weekly_fable_reset_at

    query = db.query(UsageUpload).filter(UsageUpload.email == email)
    query = query.filter(column.is_(None)) if old_value is None else query.filter(column == old_value)
    rows = query.all()

    for row in rows:
        if payload.metric == "weekly":
            row.weekly_reset_at = payload.reset_at
        else:
            row.weekly_fable_reset_at = payload.reset_at
    db.commit()

    return ResetDateUpdateResponse(
        email=email,
        metric=payload.metric,
        reset_at=payload.reset_at,
        rows_updated=len(rows),
    )
