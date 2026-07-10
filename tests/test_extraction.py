"""Tests for OCR text parsing (no heavy PaddleOCR import required)."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.extraction.ocr_extractor import parse_ocr_text


SAMPLE_OCR = """Claude Code v2.1.201
Settings Status Config Usage Stats
Session
Total cost: $0.0000
Total duration (API): 0s
Total duration (wall): 5s
Total code changes: 0 lines added, 0 lines removed
Usage: 0 input, 0 output, 0 cache read, 0 cache write
Current session
5% used
Resets 12am (Asia/Seoul)
Current week (all models)
5% used
Resets Jul 11, 4am (Asia/Seoul)
Current week (Fable)
9% used
Resets Jul 11, 4am (Asia/Seoul)
"""


def test_parse_weekly_and_fable_percentages():
    result = parse_ocr_text(SAMPLE_OCR)
    assert result.weekly_usage_pct == 5
    assert result.weekly_fable_usage_pct == 9


def test_parse_resets_to_utc():
    result = parse_ocr_text(SAMPLE_OCR)
    assert result.weekly_reset_at is not None
    assert result.weekly_fable_reset_at is not None
    assert result.weekly_reset_at.tzinfo == ZoneInfo("UTC")
    assert result.weekly_fable_reset_at.tzinfo == ZoneInfo("UTC")


def test_parse_plan_tier():
    text = "Current session\n42% used\nMax 5x\nResets 12am (UTC)"
    result = parse_ocr_text(text)
    assert result.plan_tier == "Max 5x"


def test_parse_empty_text():
    result = parse_ocr_text("")
    assert result.weekly_usage_pct is None
    assert result.weekly_fable_usage_pct is None


ACCOUNT_OCR = """Account & Usage
ACCOUNT
Auth method
Claude AI
Email
ragul@phoenixtechnologies.io
Organization
Phoenix Team Plan
Plan
Claude team
USAGE
Session (5hr)
Resets in 16m
39%
Weekly (7 day)
Resets in 5d
8%
Weekly Fable
Resets in 5d
5%
"""


def test_parse_account_layout():
    result = parse_ocr_text(ACCOUNT_OCR)
    assert result.auth_method == "Claude AI"
    assert result.email == "ragul@phoenixtechnologies.io"
    assert result.organization == "Phoenix Team Plan"
    assert result.plan_tier == "Claude team"
    assert result.weekly_usage_pct == 8
    assert result.weekly_fable_usage_pct == 5
    assert result.weekly_reset_at is not None
    assert result.weekly_fable_reset_at is not None
