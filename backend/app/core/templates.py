"""Mission templates — sensible defaults per mission type. The form applies them when a mission type is
chosen; every value stays editable. Deterministic application logic (no AI)."""

from __future__ import annotations

from typing import Any

TEMPLATES: dict[str, dict[str, Any]] = {
    "interview": {"label": "Interview", "priority": "avoid_risk", "min_buffer_minutes": 60, "max_stops": 1,
                  "hotel_required": True, "risk_tolerance": "low",
                  "highlights": ["Reliability first", "Hotel close to the venue", "60-minute buffer"]},
    "exam": {"label": "Exam", "priority": "avoid_risk", "min_buffer_minutes": 120, "max_stops": 0,
             "hotel_required": True, "risk_tolerance": "very low",
             "highlights": ["Very low risk tolerance", "Direct services only", "Two-hour buffer"]},
    "business": {"label": "Business", "priority": "save_time", "min_buffer_minutes": 45, "max_stops": 1,
                 "hotel_required": True, "risk_tolerance": "low",
                 "highlights": ["Least time away", "45-minute buffer"]},
    "conference": {"label": "Conference", "priority": "balanced", "min_buffer_minutes": 45, "max_stops": 1,
                   "hotel_required": True, "risk_tolerance": "medium",
                   "highlights": ["Balanced", "Hotel near the venue"]},
    "wedding": {"label": "Wedding", "priority": "balanced", "min_buffer_minutes": 90, "max_stops": 1,
                "hotel_required": True, "risk_tolerance": "low",
                "highlights": ["Arrive relaxed", "90-minute buffer"]},
    "medical": {"label": "Medical", "priority": "avoid_risk", "min_buffer_minutes": 60, "max_stops": 0,
                "hotel_required": True, "risk_tolerance": "very low",
                "highlights": ["Short transfers", "Direct services only", "Pharmacies nearby"]},
    "vacation": {"label": "Vacation", "priority": "balanced", "min_buffer_minutes": 30, "max_stops": 1,
                 "hotel_required": True, "risk_tolerance": "medium",
                 "highlights": ["Cost matters", "Attractions nearby"]},
    "family": {"label": "Family", "priority": "balanced", "min_buffer_minutes": 45, "max_stops": 0,
               "hotel_required": True, "risk_tolerance": "low",
               "highlights": ["Fewer changes", "Comfort over speed"]},
    "other": {"label": "Other", "priority": "balanced", "min_buffer_minutes": 60, "max_stops": 1,
              "hotel_required": True, "risk_tolerance": "medium", "highlights": ["Balanced defaults"]},
}


def all_templates() -> list[dict[str, Any]]:
    return [{"mission_type": key, **value} for key, value in TEMPLATES.items()]
