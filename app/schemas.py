"""Pydantic request/response models."""
from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Extracted usage ──────────────────────────────────────────────

class ExtractedUsage(BaseModel):
    """Usage fields extracted from a screenshot."""

    # Account information
    auth_method: Optional[str] = None
    email: Optional[str] = None
    organization: Optional[str] = None
    plan_tier: Optional[str] = None

    # Usage percentages (only weekly + Fable)
    weekly_usage_pct: Optional[int] = None
    weekly_fable_usage_pct: Optional[int] = None

    # Reset datetimes
    weekly_reset_at: Optional[datetime] = None
    weekly_fable_reset_at: Optional[datetime] = None


class UploadPreviewResponse(BaseModel):
    """Returned immediately after uploading a screenshot (before DB save)."""

    image_path: str
    original_filename: str
    extracted: ExtractedUsage
    raw_text: Optional[str] = None

    # True when the reset date shown was pulled from this email's still-active
    # cycle rather than freshly extracted from this screenshot (see uploads.py
    # _active_reset_at). Lets the frontend show a "locked" indicator.
    weekly_reset_locked: bool = False
    fable_reset_locked: bool = False


class UploadConfirmRequest(BaseModel):
    """User-confirmed / edited upload data."""

    email: str = Field(..., min_length=3, max_length=255)
    image_path: str
    original_filename: Optional[str] = None

    auth_method: Optional[str] = None
    organization: Optional[str] = None
    plan_tier: Optional[str] = None

    weekly_usage_pct: Optional[int] = Field(None, ge=0, le=100)
    weekly_fable_usage_pct: Optional[int] = Field(None, ge=0, le=100)

    weekly_reset_at: Optional[datetime] = None
    weekly_fable_reset_at: Optional[datetime] = None

    extraction_method: str = "manual"  # ocr | vlm | manual
    raw_extracted_text: Optional[str] = None
    was_manually_edited: bool = True


class UsageUploadResponse(BaseModel):
    """A persisted upload record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    uploaded_at: datetime
    image_path: str
    original_filename: str

    auth_method: Optional[str]
    email: str
    organization: Optional[str]
    plan_tier: Optional[str]

    weekly_usage_pct: Optional[int]
    weekly_fable_usage_pct: Optional[int]

    weekly_reset_at: Optional[datetime]
    weekly_fable_reset_at: Optional[datetime]

    extraction_method: str
    raw_extracted_text: Optional[str]
    was_manually_edited: bool


class PaginatedUploads(BaseModel):
    """Paginated list of uploads."""

    total: int
    skip: int
    limit: int
    items: List[UsageUploadResponse]


# ── Dashboard ────────────────────────────────────────────────────

class DailyUsage(BaseModel):
    """Aggregated usage for one user on one date."""

    weekly: Optional[int] = None
    fable: Optional[int] = None


class UserDayRow(BaseModel):
    """One user's usage across a date range."""

    email: str
    organization: Optional[str] = None
    plan_tier: Optional[str] = None
    daily: Dict[str, DailyUsage]
    latest_weekly: Optional[int] = None
    latest_fable: Optional[int] = None
    last_upload_at: Optional[datetime] = None
    latest_image_path: Optional[str] = None

    # Projected end-of-cycle % at the current burn rate, and whether that
    # projection meets/exceeds 100% before the cycle resets.
    weekly_projected_pct: Optional[int] = None
    weekly_at_risk: bool = False
    fable_projected_pct: Optional[int] = None
    fable_at_risk: bool = False


class LeaderboardEntry(BaseModel):
    """A single row in the usage leaderboard."""

    email: str
    latest_weekly: Optional[int]
    latest_fable: Optional[int]
    last_upload_at: Optional[datetime]
    latest_image_path: Optional[str] = None

    weekly_projected_pct: Optional[int] = None
    weekly_at_risk: bool = False
    fable_projected_pct: Optional[int] = None
    fable_at_risk: bool = False


class TrendPoint(BaseModel):
    """One point in a per-user trend line."""

    uploaded_at: datetime
    weekly_usage_pct: Optional[int]
    weekly_fable_usage_pct: Optional[int]


class UserTrend(BaseModel):
    """Trend data for one email."""

    email: str
    points: List[TrendPoint]


class DashboardSummary(BaseModel):
    """Aggregate stats for the dashboard widgets."""

    dates: List[str]
    users: List[UserDayRow]
    leaderboard: List[LeaderboardEntry]
    uploads_today: int
    uploads_this_week: int
    per_user_trends: List[UserTrend]


class UserComparison(BaseModel):
    """Delta for one user between two dates."""

    email: str
    weekly_from: Optional[int]
    weekly_to: Optional[int]
    weekly_delta: Optional[int]
    weekly_reset_occurred: bool = False
    fable_from: Optional[int]
    fable_to: Optional[int]
    fable_delta: Optional[int]
    fable_reset_occurred: bool = False


class DashboardCompareResponse(BaseModel):
    """Per-user comparison between two dates."""

    from_date: str
    to_date: str
    users: List[UserComparison]


class UserHistoryResponse(BaseModel):
    """Full upload history + trend for a single user."""

    email: str
    total_uploads: int
    uploads: List[UsageUploadResponse]
    trend: List[TrendPoint]


# ── Reset date correction ───────────────────────────────────────

class ResetDateUpdateRequest(BaseModel):
    """Correct a wrongly-extracted reset date for a user's active cycle."""

    metric: Literal["weekly", "fable"]
    reset_at: datetime


class ResetDateUpdateResponse(BaseModel):
    """Result of a reset-date correction."""

    email: str
    metric: str
    reset_at: datetime
    rows_updated: int
