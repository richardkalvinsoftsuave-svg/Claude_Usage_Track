"""Primary extraction backend: PaddleOCR + regex tuned to Claude Code /usage output."""
from __future__ import annotations

import base64
import logging
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.schemas import ExtractedUsage

logger = logging.getLogger(__name__)

# Lazy singleton for the OCR engine so it is created only when needed.
_ocr_engine = None

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_PLAN_TIER_PATTERN = re.compile(
    r"\b(Pro|Team|Free|Enterprise|Max\s+5x|Max\s+20x|Max\s+\d+x)\b",
    re.IGNORECASE,
)

# Match "Resets <body> (TZ)" or "Resets <body>".
# Body is greedy up to the optional " (timezone)" suffix.
# We use a greedy [^(]+ so the lazy quantifier bug can't truncate to 1 char.
_RESET_PATTERN = re.compile(
    r"Resets\s+([^(\n]+?)(?:\s+\(([^)]+)\))?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_RELATIVE_RESET_PATTERN = re.compile(
    r"Resets\s+in\s+(\d+)\s*([a-z]+)",
    re.IGNORECASE,
)

_USAGE_PCT_PATTERN = re.compile(r"(\d{1,3})%", re.IGNORECASE)

_LABELS = {
    "auth method": "auth_method",
    "email": "email",
    "organization": "organization",
    "plan": "plan_tier",
}

_DURATION_UNITS = {
    "m": "minutes",
    "min": "minutes",
    "mins": "minutes",
    "minute": "minutes",
    "minutes": "minutes",
    "h": "hours",
    "hr": "hours",
    "hrs": "hours",
    "hour": "hours",
    "hours": "hours",
    "d": "days",
    "day": "days",
    "days": "days",
    "w": "weeks",
    "week": "weeks",
    "weeks": "weeks",
}


def _run_ocr(image_path: Path) -> str:
    """Run OCR on an image and return the joined text.

    Tries PaddleOCR first (for structured result objects), falls back to
    RapidOCR if PaddleOCR's PaddleX pipeline dependencies are missing.
    """
    global _ocr_engine

    # ── PaddleOCR path (3.x with OCRResult / rec_texts) ──
    try:
        if _ocr_engine is None:
            from paddleocr import PaddleOCR  # type: ignore
            try:
                _ocr_engine = PaddleOCR(lang="en", enable_mkldnn=False)
            except (TypeError, RuntimeError):
                _ocr_engine = PaddleOCR(
                    lang="en", use_textline_orientation=False, enable_mkldnn=False
                )
        result = _ocr_engine.ocr(str(image_path))
        lines: List[str] = []
        if result and result[0]:
            first = result[0]
            # PaddleOCR 3.x returns OCRResult dict-like objects with rec_texts
            if hasattr(first, 'get') and 'rec_texts' in first:
                lines = [t for t in first['rec_texts'] if t]
            else:
                # PaddleOCR 2.x legacy: [[bbox], (text, confidence)]
                for line in first:
                    text = line[1][0] if len(line) > 1 and line[1] else ""
                    if text:
                        lines.append(text)
        return "\n".join(lines)
    except Exception:
        pass  # fall through to RapidOCR

    # ── RapidOCR fallback (always available, used by server logs) ──
    try:
        from rapidocr import RapidOCR  # type: ignore
        if _ocr_engine is None or not isinstance(_ocr_engine, RapidOCR):
            _ocr_engine = RapidOCR()
        result, _ = _ocr_engine(str(image_path))
        lines = []
        if result:
            for line in result:
                text = line[1] if len(line) > 1 and line[1] else ""
                if text:
                    lines.append(text)
        return "\n".join(lines)
    except ImportError:
        logger.warning("Neither PaddleOCR nor RapidOCR is available")
        return ""
    except Exception as exc:  # pragma: no cover
        logger.exception("OCR failed: %s", exc)
        return ""


def _parse_percentage_near_header(text: str, header: str) -> Optional[int]:
    """Find the first 'N%' on the lines immediately after *header*.

    Searches up to 5 lines after the header line so we don't bleed into
    the next section.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.search(re.escape(header), line, re.IGNORECASE):
            # Look at the next few lines only (not the whole remainder).
            for nearby in lines[i + 1 : i + 6]:
                m = _USAGE_PCT_PATTERN.search(nearby)
                if m:
                    return max(0, min(100, int(m.group(1))))
    return None


def _parse_time(time_str: str) -> Optional[Tuple[int, int]]:
    """Parse strings like '12am', '4am', '2:30pm' into (hour, minute)."""
    time_str = time_str.strip().lower().replace(" ", "")
    # "12:30pm"
    m = re.match(r"(\d{1,2}):(\d{2})(am|pm)", time_str)
    if m:
        hour, minute, ampm = int(m.group(1)), int(m.group(2)), m.group(3)
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        return hour, minute

    # "12am"
    m = re.match(r"(\d{1,2})(am|pm)", time_str)
    if m:
        hour, ampm = int(m.group(1)), m.group(2)
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        return hour, 0

    # "16:00" 24h
    m = re.match(r"(\d{1,2}):(\d{2})", time_str)
    if m:
        return int(m.group(1)), int(m.group(2))

    return None


def _parse_month_day(date_str: str) -> Optional[Tuple[int, int]]:
    """Parse 'Jul 11' / 'July 11' into (month, day); returns None if absent."""
    date_str = date_str.strip().lower()
    # Remove trailing comma.
    date_str = date_str.replace(",", "")
    m = re.match(r"([a-z]{3,})\s+(\d{1,2})", date_str)
    if not m:
        return None
    month_name = m.group(1)
    month = _MONTHS.get(month_name)
    if month is None:
        return None
    return month, int(m.group(2))


def _to_utc_datetime(
    date_part: Optional[Tuple[int, int]],
    time_part: Optional[Tuple[int, int]],
    tz_name: Optional[str],
) -> Optional[datetime]:
    """Convert parsed date/time/tz into a UTC datetime."""
    tz = ZoneInfo("UTC")
    if tz_name:
        try:
            tz = ZoneInfo(tz_name.strip())
        except ZoneInfoNotFoundError:
            logger.warning("Unknown timezone %r, falling back to UTC", tz_name)

    now_local = datetime.now(tz)
    year = now_local.year

    if date_part:
        month, day = date_part
        try:
            dt_local = datetime(year, month, day, 0, 0, tzinfo=tz)
        except ValueError:
            return None
    else:
        dt_local = datetime(year, now_local.month, now_local.day, 0, 0, tzinfo=tz)

    if time_part:
        hour, minute = time_part
        dt_local = dt_local.replace(hour=hour, minute=minute)

    # If only a time was given and the result is in the past, assume next day.
    if date_part is None and dt_local <= now_local:
        dt_local += timedelta(days=1)

    return dt_local.astimezone(ZoneInfo("UTC"))


def _parse_reset_fragments(text: str) -> List[Tuple[str, Optional[str]]]:
    """Return [(raw_reset_string, timezone_name), ...] in document order."""
    results: List[Tuple[str, Optional[str]]] = []
    for match in _RESET_PATTERN.finditer(text):
        reset_body = match.group(1).strip()
        tz_name = match.group(2).strip() if match.group(2) else None
        results.append((reset_body, tz_name))
    return results


def _parse_relative_reset(body: str) -> Optional[datetime]:
    """Parse strings like 'Resets in 16m' / 'Resets in 5d' into a UTC datetime."""
    m = _RELATIVE_RESET_PATTERN.match(body.strip())
    if not m:
        return None
    amount, unit = int(m.group(1)), m.group(2).lower()
    kwarg = _DURATION_UNITS.get(unit)
    if not kwarg:
        return None
    return datetime.now(timezone.utc) + timedelta(**{kwarg: amount})


# Matches time tokens embedded in a larger body, e.g. "4am", "12:30pm", "16:00".
_TIME_TOKEN_PATTERN = re.compile(
    r"\b(\d{1,2}(?::\d{2})?(?:am|pm))\b|\b(\d{1,2}:\d{2})\b",
    re.IGNORECASE,
)


def _parse_reset_datetimes(text: str) -> List[datetime]:
    """Return all reset datetimes found in the text, in document order."""
    datetimes: List[datetime] = []

    # Old /usage format: "Resets Jul 11, 4am (Asia/Seoul)" or "Resets 12am (Asia/Seoul)"
    for body, tz_name in _parse_reset_fragments(text):
        date_part = _parse_month_day(body)
        # Try the full body as a time first (e.g. "12am"), then extract an
        # embedded time token from a combined string like "Jul 11, 4am".
        time_part = _parse_time(body)
        if time_part is None:
            tm = _TIME_TOKEN_PATTERN.search(body)
            if tm:
                time_part = _parse_time(tm.group(0))
        dt = _to_utc_datetime(date_part, time_part, tz_name)
        if dt:
            datetimes.append(dt)
            continue
        # Account & Usage format: "Resets in 16m"
        dt = _parse_relative_reset(f"Resets {body}")
        if dt:
            datetimes.append(dt)

    return datetimes


def _parse_plan_tier(text: str) -> Optional[str]:
    """Search for known plan tier names anywhere in the text."""
    match = _PLAN_TIER_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    return None


def _normalize_lines(raw_text: str) -> List[str]:
    return [line.strip() for line in raw_text.splitlines() if line.strip()]


def _next_nonempty(lines: List[str], idx: int) -> Optional[str]:
    for line in lines[idx + 1 :]:
        if line:
            return line
    return None


def _parse_label_value(lines: List[str], label: str) -> Optional[str]:
    """Find a label and return the value on the same line or the next line."""
    label_lower = label.lower()
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if line_lower.startswith(label_lower):
            rest = line[len(label) :].strip()
            if rest:
                return rest
            return _next_nonempty(lines, i)
        if line_lower == label_lower:
            return _next_nonempty(lines, i)
    return None


def _parse_email(lines: List[str]) -> Optional[str]:
    for line in lines:
        if "@" in line and "." in line:
            # Extract the first email-like token.
            m = re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", line)
            if m:
                return m.group(0)
    return None


def _parse_pct_after_header(lines: List[str], header_keyword: str) -> Optional[int]:
    """Find the first percentage on or just after a line containing *header_keyword*."""
    for i, line in enumerate(lines):
        if header_keyword.lower() in line.lower():
            m = _USAGE_PCT_PATTERN.search(line)
            if m:
                return max(0, min(100, int(m.group(1))))
            for next_line in lines[i + 1 : i + 6]:
                m = _USAGE_PCT_PATTERN.search(next_line)
                if m:
                    return max(0, min(100, int(m.group(1))))
    return None


def _is_account_layout(lines: List[str]) -> bool:
    return any(
        "auth method" in line.lower()
        or "account & usage" in line.lower()
        or "organization" in line.lower()
        for line in lines
    )


def _parse_account_usage(text: str, lines: List[str]) -> ExtractedUsage:
    """Parse the 'Account & Usage' dialog layout."""
    auth_method = _parse_label_value(lines, "Auth method")
    email = _parse_email(lines)
    organization = _parse_label_value(lines, "Organization")
    plan_tier = _parse_label_value(lines, "Plan")

    session_pct = _parse_pct_after_header(lines, "Session")
    weekly_pct = _parse_pct_after_header(lines, "Weekly (7 day)") or _parse_pct_after_header(lines, "Weekly")
    fable_pct = _parse_pct_after_header(lines, "Weekly Fable")

    resets = _parse_reset_datetimes(text)
    session_reset = resets[0] if resets else None
    weekly_reset = resets[1] if len(resets) > 1 else None
    fable_reset = resets[2] if len(resets) > 2 else weekly_reset

    if not plan_tier:
        plan_tier = _parse_plan_tier(text)

    return ExtractedUsage(
        auth_method=auth_method,
        email=email,
        organization=organization,
        plan_tier=plan_tier,
        session_usage_pct=session_pct,
        weekly_usage_pct=weekly_pct,
        weekly_fable_usage_pct=fable_pct,
        session_reset_at=session_reset,
        weekly_reset_at=weekly_reset,
        weekly_fable_reset_at=fable_reset,
    )


def _parse_old_usage(text: str, lines: List[str]) -> ExtractedUsage:
    """Parse the classic Claude Code /usage command layout.

    Handles both the two-section layout (session + week) and the
    three-section layout that also includes a 'Current week (Fable)' row.
    """
    session_pct = _parse_percentage_near_header(text, "Current session")
    # Prefer the specific header; fall back to generic "Current week".
    weekly_pct = (
        _parse_percentage_near_header(text, "Current week (all models)")
        or _parse_percentage_near_header(text, "Current week")
    )
    fable_pct = _parse_percentage_near_header(text, "Current week (Fable)")

    if session_pct is None or weekly_pct is None:
        all_pcts = _USAGE_PCT_PATTERN.findall(text)
        int_pcts = [max(0, min(100, int(p))) for p in all_pcts]
        if session_pct is None and int_pcts:
            session_pct = int_pcts[0]
        if weekly_pct is None and len(int_pcts) > 1:
            weekly_pct = int_pcts[1]
        if fable_pct is None and len(int_pcts) > 2:
            fable_pct = int_pcts[2]

    resets = _parse_reset_datetimes(text)
    session_reset = resets[0] if resets else None
    weekly_reset = resets[1] if len(resets) > 1 else None
    fable_reset = resets[2] if len(resets) > 2 else weekly_reset
    plan_tier = _parse_plan_tier(text)

    return ExtractedUsage(
        plan_tier=plan_tier,
        session_usage_pct=session_pct,
        weekly_usage_pct=weekly_pct,
        weekly_fable_usage_pct=fable_pct,
        session_reset_at=session_reset,
        weekly_reset_at=weekly_reset,
        weekly_fable_reset_at=fable_reset,
    )


def parse_ocr_text(raw_text: str) -> ExtractedUsage:
    """Turn raw OCR text into structured usage data."""
    if not raw_text:
        return ExtractedUsage()

    lines = _normalize_lines(raw_text)
    text = "\n".join(lines)

    if _is_account_layout(lines):
        return _parse_account_usage(text, lines)
    return _parse_old_usage(text, lines)


def extract_usage(image_path: Path | str) -> Dict[str, object]:
    """Run OCR on *image_path* and return extracted fields + raw text."""
    path = Path(image_path)
    raw_text = _run_ocr(path)
    extracted = parse_ocr_text(raw_text)
    return {
        "extracted": extracted,
        "raw_text": raw_text or None,
    }


def encode_image_base64(image_path: Path | str) -> str:
    """Return a base64-encoded image string (used by the VLM fallback)."""
    return base64.b64encode(Path(image_path).read_bytes()).decode("utf-8")
