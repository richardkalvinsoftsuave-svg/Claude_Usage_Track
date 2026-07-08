"""Docling-based vision extractor for Claude usage screenshots.

Docling is a local vision/document model. This extractor:
1. Sends the screenshot to Docling.
2. Treats the returned markdown/text as OCR output.
3. Runs the same parser as the OCR extractor.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.extraction.ocr_extractor import parse_ocr_text

logger = logging.getLogger(__name__)

# Reusable converter instance cached at module level.
_converter = None


def _get_converter():
    """Lazy-init the Docling converter for image inputs."""
    global _converter
    if _converter is None:
        # Import docling lazily so the rest of the app starts even when
        # docling is not installed or only OCR/VLM modes are used.
        from docling.datamodel.base_models import InputFormat
        from docling.document_converter import DocumentConverter

        # Restrict to images only; default pipeline options work out of the box.
        _converter = DocumentConverter(allowed_formats=[InputFormat.IMAGE])
    return _converter


def extract_usage(image_path: str | Path) -> dict:
    """Extract usage fields from a screenshot using Docling.

    Returns the same shape as the OCR extractor:
    {
        "extracted": ExtractedUsage,
        "raw_text": <raw markdown/text or None>,
    }
    """
    image_path = Path(image_path)
    if not image_path.exists():
        logger.warning("Docling: file not found: %s", image_path)
        return {"extracted": parse_ocr_text(""), "raw_text": None}

    try:
        converter = _get_converter()
        result = converter.convert(str(image_path))
        text = result.document.export_to_markdown() if result.document else ""
        # Ensure text is a plain str (export_to_markdown returns str, but be safe).
        if not isinstance(text, str):
            text = str(text)
    except Exception as exc:  # pragma: no cover - docling may not be installed
        logger.warning("Docling extraction failed: %s", exc)
        return {"extracted": parse_ocr_text(""), "raw_text": None}

    extracted = parse_ocr_text(text)
    return {"extracted": extracted, "raw_text": text or None}
