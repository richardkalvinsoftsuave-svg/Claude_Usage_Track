"""Pydantic request/response models."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Org Hierarchy ────────────────────────────────────────────────

class ManagerCreate(BaseModel):
    """Create a new manager."""
    name: str = Field(..., min_length=1, max_length=120)


class ManagerUpdate(BaseModel):
    """Update a manager's name."""
    name: str = Field(..., min_length=1, max_length=120)


class ManagerRead(BaseModel):
    """A persisted manager record."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class TeamCreate(BaseModel):
    """Create a new team."""
    name: str = Field(..., min_length=1, max_length=120)
    manager_id: int


class TeamUpdate(BaseModel):
    """Update a team."""
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    manager_id: Optional[int] = None


class TeamRead(BaseModel):
    """A persisted team record."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    manager_id: int


class TeamMemberCreate(BaseModel):
    """Create a new team member."""
    name: str = Field(..., min_length=1, max_length=120)
    team_id: int


class TeamMemberUpdate(BaseModel):
    """Update a team member."""
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    team_id: Optional[int] = None


class TeamMemberRead(BaseModel):
    """A persisted team member record."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    team_id: int


# ── Extracted usage ──────────────────────────────────────────────

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

    # Org hierarchy
    manager_id: Optional[int] = None
    team_id: Optional[int] = None

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

    manager_id: Optional[int] = None
    team_id: Optional[int] = None

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


# ── Dashboard ────────────────────────────────────────────────────

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


class ManagerSummary(BaseModel):
    """Aggregated stats for one manager's team."""

    manager_id: int
    manager_name: str
    team_count: int = 0
    avg_weekly_pct: Optional[float] = None
    avg_session_pct: Optional[float] = None


class TeamSummary(BaseModel):
    """Aggregated stats for one team."""

    team_id: int
    team_name: str
    manager_name: str
    member_count: int = 0
    avg_weekly_pct: Optional[float] = None
    avg_session_pct: Optional[float] = None


class DashboardSummary(BaseModel):
    """Aggregate stats for the dashboard widgets."""

    team_avg_session_usage: Optional[float]
    team_avg_weekly_usage: Optional[float]
    leaderboard: List[LeaderboardEntry]
    uploads_today: int
    uploads_this_week: int
    per_user_trends: List[UserTrend]
    by_manager: List[ManagerSummary] = []
    by_team: List[TeamSummary] = []


class UserHistoryResponse(BaseModel):
    """Full upload history + trend for a single user."""

    uploader_name: str
    total_uploads: int
    uploads: List[UsageUploadResponse]
    trend: List[TrendPoint]
