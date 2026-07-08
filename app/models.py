"""SQLAlchemy ORM models."""
from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Manager(Base):
    """A manager in the org hierarchy."""

    __tablename__ = "managers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), unique=True, nullable=False, index=True)

    teams = relationship("Team", back_populates="manager", cascade="all, delete-orphan")


class Team(Base):
    """A team reporting to a manager."""

    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), unique=True, nullable=False, index=True)
    manager_id = Column(Integer, ForeignKey("managers.id"), nullable=False, index=True)

    manager = relationship("Manager", back_populates="teams")
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")


class TeamMember(Base):
    """A team member belonging to a team."""

    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), unique=True, nullable=False, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)

    team = relationship("Team", back_populates="members")


class UsageUpload(Base):
    """A single screenshot upload and its extracted usage data."""

    __tablename__ = "usage_uploads"

    id = Column(Integer, primary_key=True, index=True)
    uploader_name = Column(String(120), index=True, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    image_path = Column(String(500), nullable=False)
    original_filename = Column(String(255), nullable=False)

    # Org hierarchy references (nullable — existing rows will be NULL)
    manager_id = Column(Integer, ForeignKey("managers.id"), nullable=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True, index=True)

    # Account fields
    auth_method = Column(String(120), nullable=True)
    email = Column(String(255), nullable=True)
    organization = Column(String(255), nullable=True)
    plan_tier = Column(String(120), nullable=True)

    # Usage fields
    session_usage_pct = Column(Integer, nullable=True)
    weekly_usage_pct = Column(Integer, nullable=True)
    weekly_fable_usage_pct = Column(Integer, nullable=True)

    session_reset_at = Column(DateTime(timezone=True), nullable=True)
    weekly_reset_at = Column(DateTime(timezone=True), nullable=True)
    weekly_fable_reset_at = Column(DateTime(timezone=True), nullable=True)

    extraction_method = Column(String(50), default="ocr", nullable=False)  # ocr | vlm | manual
    raw_extracted_text = Column(Text, nullable=True)
    was_manually_edited = Column(Boolean, default=False, nullable=False)

    # Relationships for easy navigation
    manager = relationship("Manager")
    team = relationship("Team")
