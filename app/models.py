"""SQLAlchemy ORM models."""
from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func

from app.database import Base


class UsageUpload(Base):
    """A single screenshot upload and its extracted usage data."""

    __tablename__ = "usage_uploads"

    id = Column(Integer, primary_key=True, index=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    image_path = Column(String(500), nullable=False)
    original_filename = Column(String(255), nullable=False)

    # Account fields
    auth_method = Column(String(120), nullable=True)
    email = Column(String(255), nullable=False, index=True)
    organization = Column(String(255), nullable=True)
    plan_tier = Column(String(120), nullable=True)

    # Usage fields (only weekly + Fable)
    weekly_usage_pct = Column(Integer, nullable=True)
    weekly_fable_usage_pct = Column(Integer, nullable=True)

    weekly_reset_at = Column(DateTime(timezone=True), nullable=True)
    weekly_fable_reset_at = Column(DateTime(timezone=True), nullable=True)

    extraction_method = Column(String(50), default="ocr", nullable=False)  # ocr | vlm | manual
    raw_extracted_text = Column(Text, nullable=True)
    was_manually_edited = Column(Boolean, default=False, nullable=False)
