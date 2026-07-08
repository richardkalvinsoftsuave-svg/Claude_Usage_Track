"""Pydantic request/response models."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ExtractedUsage(BaseModel):
    """Usage fields extracted from a screenshot."""

    # Account information
    auth_method: Optional[str] = None
    email: Optional[str] = None
    organization: Optional[str] = None
    plan_tier: Optional[str] = None

    # Usage percentages
    session_usage_pct: Optional[int] = None
    weekly_usage_pct: Optional[int] = None
    weekly_fable_usage_pct: Optional[int] = None

    # Reset datetimes
    session_reset_at: Optional[datetime] = None
    weekly_reset_at: Optional[datetime] = None
    weekly_fable_reset_at: Optional[datetime] = None


class UploadPreviewResponse(BaseModel):
    """Returned immediately after uploading a screenshot (before DB save)."""

    image_path: str
    original_filename: str
    extracted: ExtractedUsage
    raw_text: Optional[str] = None


class UploadConfirmRequest(BaseModel):
    """User-confirmed / edited upload data."""

    uploader_name: str = Field(..., min_length=1, max_length=120)
    image_path: str
    original_filename: Optional[str] = None

    auth_method: Optional[str] = None
    email: Optional[str] = None
    organization: Optional[str] = None
    plan_tier: Optional[str] = None

    session_usage_pct: Optional[int] = Field(None, ge=0, le=100)
    weekly_usage_pct: Optional[int] = Field(None, ge=0, le=100)
    weekly_fable_usage_pct: Optional[int] = Field(None, ge=0, le=100)

    session_reset_at: Optional[datetime] = None
    weekly_reset_at: Optional[datetime] = None
    weekly_fable_reset_at: Optional[datetime] = None

    extraction_method: str = "manual"  # ocr | vlm | manual
    raw_extracted_text: Optional[str] = None
    was_manually_edited: bool = True


class UsageUploadResponse(BaseModel):
    """A persisted upload record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    uploader_name: str
    uploaded_at: datetime
    image_path: str
    original_filename: str
    auth_method: Optional[str]
    email: Optional[str]
    organization: Optional[str]
    plan_tier: Optional[str]

    session_usage_pct: Optional[int]
    weekly_usage_pct: Optional[int]
    weekly_fable_usage_pct: Optional[int]

    session_reset_at: Optional[datetime]
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


class LeaderboardEntry(BaseModel):
    """A single row in the "closest to limit" leaderboard."""

    uploader_name: str
    latest_session_pct: Optional[int]
    latest_weekly_pct: Optional[int]
    last_upload_at: Optional[datetime]


class TrendPoint(BaseModel):
    """One point in a per-user trend line."""

    uploaded_at: datetime
    session_usage_pct: Optional[int]
    weekly_usage_pct: Optional[int]


class UserTrend(BaseModel):
    """Trend data for one uploader."""

    uploader_name: str
    points: List[TrendPoint]


class DashboardSummary(BaseModel):
    """Aggregate stats for the dashboard widgets."""

    team_avg_session_usage: Optional[float]
    team_avg_weekly_usage: Optional[float]
    leaderboard: List[LeaderboardEntry]
    uploads_today: int
    uploads_this_week: int
    per_user_trends: List[UserTrend]


class UserHistoryResponse(BaseModel):
    """Full upload history + trend for a single user."""

    uploader_name: str
    total_uploads: int
    uploads: List[UsageUploadResponse]
    trend: List[TrendPoint]
