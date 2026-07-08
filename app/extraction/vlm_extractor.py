"""On-demand VLM extraction backend using a local Ollama instance."""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Dict, Optional

import httpx

from app.config import settings
from app.schemas import ExtractedUsage

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """You are a data extraction assistant. Look at the provided Claude Code usage screenshot and extract only the following JSON fields. Return strict JSON and nothing else.

{
  "auth_method": string or null,
  "email": string or null,
  "organization": string or null,
  "plan_tier": string or null,
  "session_usage_pct": integer 0-100 or null,
  "weekly_usage_pct": integer 0-100 or null,
  "weekly_fable_usage_pct": integer 0-100 or null,
  "session_reset_at": ISO 8601 UTC datetime string or null,
  "weekly_reset_at": ISO 8601 UTC datetime string or null,
  "weekly_fable_reset_at": ISO 8601 UTC datetime string or null
}

IMPORTANT RULES:
- Percentages must be integers (e.g. 5, not "5%")
- All datetime fields must be ISO 8601 UTC format (e.g. "2026-07-08T00:00:00Z"). Convert any timezone shown in the screenshot to UTC.
- If a timezone like "Asia/Seoul" is shown, convert accordingly (Asia/Seoul is UTC+9).
- Use the current date when inferring reset times if no year is shown.
- If a value is missing or unreadable, use null."""


def _image_to_base64(image_path: Path) -> str:
    return base64.b64encode(image_path.read_bytes()).decode("utf-8")


def _safe_parse_iso(value: Optional[str]) -> Optional[str]:
    """Return the value if it looks like an ISO datetime, else None."""
    if not value or not isinstance(value, str):
        return None
    # We keep it as a string; Pydantic will parse it into a datetime.
    return value


def extract_usage(image_path: Path | str) -> Dict[str, object]:
    """Call the configured local Ollama model and return extracted fields + raw JSON."""
    path = Path(image_path)
    image_b64 = _image_to_base64(path)

    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": _EXTRACTION_PROMPT},
            {
                "role": "user",
                "content": "Extract usage data from this screenshot.",
                "images": [image_b64],
            },
        ],
        "stream": False,
        "keep_alive": "5m",
        "format": "json",
    }

    url = f"{settings.ollama_host.rstrip('/')}/api/chat"
    raw_json_text = None
    parsed: Dict[str, Optional[object]] = {}

    try:
        response = httpx.post(url, json=payload, timeout=300)
        response.raise_for_status()
        data = response.json()
        message = data.get("message", {})
        content = message.get("content", "") if isinstance(message, dict) else ""
        raw_json_text = content.strip() or None

        if raw_json_text:
            # Ollama may wrap JSON in markdown fences.
            cleaned = raw_json_text
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            parsed = json.loads(cleaned)
    except httpx.HTTPStatusError as exc:
        logger.warning("Ollama returned error %d: %s", exc.response.status_code, exc.response.text[:300])
    except httpx.RequestError as exc:
        logger.warning("Ollama request failed: %s", exc)
    except json.JSONDecodeError as exc:
        logger.warning("Ollama returned non-JSON output: %s", exc)
    except Exception as exc:  # pragma: no cover
        logger.exception("Unexpected error calling Ollama: %s", exc)

    extracted = ExtractedUsage(
        auth_method=_to_str(parsed.get("auth_method")),
        email=_to_str(parsed.get("email")),
        organization=_to_str(parsed.get("organization")),
        plan_tier=_to_str(parsed.get("plan_tier")),
        session_usage_pct=_to_int(parsed.get("session_usage_pct")),
        weekly_usage_pct=_to_int(parsed.get("weekly_usage_pct")),
        weekly_fable_usage_pct=_to_int(parsed.get("weekly_fable_usage_pct")),
        session_reset_at=_to_datetime(parsed.get("session_reset_at")),
        weekly_reset_at=_to_datetime(parsed.get("weekly_reset_at")),
        weekly_fable_reset_at=_to_datetime(parsed.get("weekly_fable_reset_at")),
    )

    return {
        "extracted": extracted,
        "raw_text": raw_json_text,
    }


def _to_int(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        # Handle string percentages like "5%"
        raw = str(value).strip().rstrip("%")
        return max(0, min(100, int(raw)))
    except (TypeError, ValueError):
        return None


def _to_str(value: object) -> Optional[str]:
    if value is None or value == "":
        return None
    return str(value).strip() or None


def _to_datetime(value: object) -> Optional[str]:
    """Parse VLM datetime output into an ISO 8601 UTC string.

    The VLM may return:
     - Already valid ISO 8601 strings
     - Natural language like "Jul 11, 4am (Asia/Seoul)"
     - Empty strings or None
    """
    if value is None or value == "":
        return None
    raw = str(value).strip()
    # Try to parse it as a timestamp using the OCR parser's logic.
    # The OCR parser expects a "Resets" prefix, so prepend it if missing.
    from app.extraction.ocr_extractor import _parse_reset_datetimes
    if "resets" not in raw.lower():
        raw = f"Resets {raw}"
    parsed = _parse_reset_datetimes(raw)
    if parsed:
        return parsed[0].isoformat()
    # Fallback: return as-is — Pydantic will coerce if it's already ISO.
    return raw or None
