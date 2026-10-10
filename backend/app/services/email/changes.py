"""Journey snapshots and meaningful-change detection (used by change alerts and reminders).

Snapshots are built only from stored, structured mission results — never from AI text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

# Thresholds for an alert-worthy change (docs/HLD.md §Notifications)
ARRIVAL_SHIFT_MINUTES = 15
BUFFER_DROP_MINUTES = 15
COST_RISE_SHARE = 0.10
COST_RISE_MIN = 500


def recommended(result: dict[str, Any], itinerary_id: str | None = None) -> dict[str, Any] | None:
    itineraries = {i["id"]: i for i in result.get("itineraries", [])}
    if itinerary_id and itinerary_id in itineraries:
        return itineraries[itinerary_id]
    rec_id = (result.get("categories") or {}).get("recommended")
    return itineraries.get(rec_id) if rec_id else None


def snapshot(result: dict[str, Any], itinerary_id: str | None = None) -> dict[str, Any] | None:
    itin = recommended(result, itinerary_id)
    if itin is None:
        return None
    mission = result["mission"]
    main = itin["main"]
    return {
        "itinerary_id": itin["id"],
        "mode": itin["mode"],
        "title": main["title"],
        "departure": main["departure_time"],
        "departure_label": main["departure_label"],
        "arrival_main": main["arrival_time"],
        "venue_arrival": itin["arrival"]["venue_arrival"],
        "deadline": itin["arrival"]["deadline"],
        "buffer": itin["arrival"]["buffer_minutes"],
        "required_buffer": itin["arrival"]["required_buffer_minutes"],
        "risk": itin["risk"]["level"],
        "risk_score": itin["risk"]["score"],
        "score": itin["scores"]["overall"],
        "total_cost": itin["cost"]["total"],
        "budget_remaining": itin["cost"].get("budget_remaining"),
        "currency": itin["cost"]["currency"],
        "hotel": (itin.get("hotel") or {}).get("name"),
        "leave_hotel_at": itin["arrival"].get("leave_hotel_at"),
        "origin": mission["origin"]["city"],
        "destination": mission["destination"]["city"],
        "venue": mission["venue"]["name"],
        "mission_type": mission["mission_type"],
        "travel_date": mission["travel_date"],
    }


@dataclass
class Change:
    field: str
    label: str
    before: Any
    after: Any
    meaningful: bool


@dataclass
class ChangeReport:
    changes: list[Change] = field(default_factory=list)
    journey_unavailable: bool = False

    @property
    def meaningful(self) -> bool:
        return self.journey_unavailable or any(c.meaningful for c in self.changes)

    def to_dict(self) -> dict[str, Any]:
        return {"meaningful": self.meaningful, "journey_unavailable": self.journey_unavailable,
                "changes": [c.__dict__ for c in self.changes]}


def _minutes_between(a: str, b: str) -> int:
    return int((datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() // 60)


def detect_changes(before: dict[str, Any], after: dict[str, Any] | None) -> ChangeReport:
    """Compare two snapshots of the same journey. Small fluctuations are reported but not alert-worthy."""
    report = ChangeReport()
    if after is None:
        report.journey_unavailable = True
        return report
    if before["itinerary_id"] != after["itinerary_id"]:
        report.changes.append(Change("journey", "Recommended journey", before["title"], after["title"], True))

    shift = _minutes_between(before["venue_arrival"], after["venue_arrival"])
    if shift:
        report.changes.append(Change("venue_arrival", "Arrival at the venue", before["venue_arrival"],
                                     after["venue_arrival"], abs(shift) >= ARRIVAL_SHIFT_MINUTES))
    main_shift = _minutes_between(before["arrival_main"], after["arrival_main"])
    if main_shift and not shift:
        # e.g. a delayed flight the evening before — absorbed by the overnight stay
        report.changes.append(Change("arrival_main", "Arrival time (absorbed by your plan)", before["arrival_main"],
                                     after["arrival_main"], False))

    drop = before["buffer"] - after["buffer"]
    if drop:
        falls_below = after["buffer"] < after["required_buffer"] <= before["buffer"]
        report.changes.append(Change("buffer", "Arrival buffer", before["buffer"], after["buffer"],
                                     drop >= BUFFER_DROP_MINUTES or falls_below or after["buffer"] < 0))

    if before["risk"] != after["risk"]:
        worse = RISK_ORDER[after["risk"]] > RISK_ORDER[before["risk"]]
        report.changes.append(Change("risk", "Risk", before["risk"], after["risk"], worse))

    if before.get("total_cost") is not None and after.get("total_cost") is not None:
        rise = after["total_cost"] - before["total_cost"]
        if rise:
            big = rise >= COST_RISE_MIN and rise >= COST_RISE_SHARE * before["total_cost"]
            report.changes.append(Change("total_cost", "Total trip cost", before["total_cost"], after["total_cost"], big))
    return report
