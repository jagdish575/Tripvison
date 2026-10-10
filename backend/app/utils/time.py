"""Time parsing/formatting helpers shared by parsers and engines."""

from __future__ import annotations

import re
from datetime import datetime

_DT_FORMATS = ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S")
_HOURS = re.compile(r"(\d+(?:\.\d+)?)\s*(?:hours|hour|hrs|hr|h)\b", re.IGNORECASE)
_MINUTES = re.compile(r"(\d+)\s*(?:minutes|minute|mins|min|m)\b", re.IGNORECASE)
_DAYS = re.compile(r"(\d+)\s*(?:days|day|d)\b", re.IGNORECASE)


def parse_local_datetime(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    for fmt in _DT_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_duration_text(text: str | None) -> int | None:
    """'1 hr 5 min' -> 65, '45 min' -> 45, '2 h' -> 120. Returns None if nothing parseable."""
    if not text or not isinstance(text, str):
        return None
    days = sum(int(m) for m in _DAYS.findall(text))
    hours = sum(float(m) for m in _HOURS.findall(text))
    minutes = sum(int(m) for m in _MINUTES.findall(text))
    total = days * 1440 + hours * 60 + minutes
    return int(round(total)) if total > 0 else None


def parse_duration_range_max(text: str | None) -> int | None:
    """'35 min to 1 hr 5 min' -> 65; '40–55 min' -> 55; '1–2 hr' -> 120."""
    if not text or not isinstance(text, str):
        return None
    parts = re.split(r"\s+to\s+|\s*[–—-]\s*", text.strip())
    last = parts[-1].strip()
    value = parse_duration_text(last)
    if value is None and len(parts) > 1:
        # "40–55 min": the unit belongs to the last number only — already handled; bare numbers fall through
        number = re.match(r"^(\d+)$", last)
        if number:
            unit_text = parts[0]
            value = parse_duration_text(f"{number.group(1)} {'hr' if 'h' in unit_text else 'min'}")
    return value


def minutes_between(start: datetime, end: datetime) -> int:
    return int(round((end - start).total_seconds() / 60))
