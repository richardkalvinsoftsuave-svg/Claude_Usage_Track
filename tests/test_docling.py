"""Tests for Docling extractor fallback paths (no heavy model required)."""
from __future__ import annotations

from app.extraction.docling_extractor import extract_usage


def test_docling_missing_file_returns_empty():
    result = extract_usage("/nonexistent/screenshot.png")
    assert result["raw_text"] is None
    assert result["extracted"].session_usage_pct is None
