"""The signed-in traveller: trips (past / upcoming / saved), saved missions and preferences."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.database import session_scope
from app.core.errors import NotReadyError
from app.core.logging import get_logger
from app.models import Mission, SavedMission, UserPreference
from app.repositories.mission_repository import MissionRepository
from app.schemas.mission import NotificationPrefs, Priority, TravelMode
from app.services.auth import CurrentUser, require_user
from app.services.mission_service import assert_owner

log = get_logger(__name__)
router = APIRouter(tags=["me"])


def _trip(mission: Mission, saved: set[str]) -> dict[str, Any]:
    result = mission.result or {}
    rec_id = (result.get("categories") or {}).get("recommended")
    rec = next((i for i in result.get("itineraries") or [] if i.get("id") == rec_id), None)
    summary = result.get("mission") or {}
    return {
        "mission_id": mission.id, "status": mission.status, "mode": mission.mode,
        "result_status": result.get("status"), "mission_type": mission.mission_type,
        "origin": (summary.get("origin") or {}).get("city") or mission.origin_query,
        "destination": (summary.get("destination") or {}).get("city") or mission.destination_query,
        "venue": mission.venue_query, "travel_date": mission.travel_date.isoformat(),
        "arrival_deadline": mission.arrival_deadline.strftime("%H:%M"), "budget": float(mission.budget),
        "currency": mission.currency, "created_at": mission.created_at.isoformat(),
        "upcoming": mission.travel_date >= date.today(), "saved": mission.id in saved,
        "headline": result.get("headline"),
        "recommended": None if rec is None else {
            "mode": rec.get("mode"), "total_cost": (rec.get("cost") or {}).get("total"),
            "score": (rec.get("scores") or {}).get("overall"), "risk": (rec.get("risk") or {}).get("level"),
            "buffer_minutes": (rec.get("arrival") or {}).get("buffer_minutes")},
    }


@router.get("/me/trips")
def my_trips(user: CurrentUser = Depends(require_user)) -> dict[str, Any]:
    with session_scope() as session:
        saved = set(session.scalars(select(SavedMission.mission_id).where(SavedMission.user_id == user.id)))
        trips = [_trip(m, saved) for m in MissionRepository(session).for_user(user.id)]
    return {"trips": trips}


@router.post("/missions/{mission_id}/save")
async def save_mission(mission_id: str, user: CurrentUser = Depends(require_user)) -> dict[str, Any]:
    assert_owner(mission_id, user)
    with session_scope() as session:
        mission = session.get(Mission, mission_id)
        if mission is None or mission.status != "complete":
            raise NotReadyError("Only finished journeys can be saved.")
        exists = session.scalars(select(SavedMission).where(SavedMission.user_id == user.id,
                                                            SavedMission.mission_id == mission_id)).first()
        newly_saved = exists is None
        if newly_saved:
            session.add(SavedMission(user_id=user.id, mission_id=mission_id))
        prefs = session.get(UserPreference, user.id)
        pref = prefs.to_dict() if prefs else None
    email = await _subscribe_from_preferences(mission_id, user, pref) if newly_saved else None
    return {"saved": True, "email": email}


@router.delete("/missions/{mission_id}/save")
def unsave_mission(mission_id: str, user: CurrentUser = Depends(require_user)) -> dict[str, Any]:
    with session_scope() as session:
        session.execute(delete(SavedMission).where(SavedMission.user_id == user.id,
                                                   SavedMission.mission_id == mission_id))
    return {"saved": False}


async def _subscribe_from_preferences(mission_id: str, user: CurrentUser,
                                      pref: dict[str, Any] | None) -> dict[str, Any] | None:
    """Saving a journey subscribes the traveller's own email according to their email preferences.
    Email problems never fail the save."""
    if user.is_demo or not user.email or not pref or not pref["notifications"]["enabled"]:
        return None
    email = pref["email"]
    prefs = NotificationPrefs(email=user.email, trip_summary=email["trip_summary"],
                              reminder=email["departure_reminder"],
                              changes=email["journey_changes"] or email["price_changes"])
    if not (prefs.trip_summary or prefs.reminder or prefs.changes):
        return None
    from app.services.notifications import NotificationService

    try:
        out = await NotificationService().subscribe(mission_id, prefs)
    except Exception:  # noqa: BLE001 - email is best-effort here
        log.warning("auto-subscribe failed", extra={"context": {"mission_id": mission_id}})
        return {"status": "failed"}
    summary = out.get("summary")
    return {"status": summary.get("status") if isinstance(summary, dict) else "subscribed"}


class EmailPrefs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trip_summary: bool
    departure_reminder: bool
    journey_changes: bool
    price_changes: bool


class NotificationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


class TravelPrefs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    home_city: str | None = Field(default=None, max_length=80)
    priority: Priority = Priority.balanced
    modes: list[TravelMode] = Field(default_factory=lambda: list(TravelMode), min_length=1, max_length=4)
    buffer_minutes: int = Field(default=60, ge=0, le=240)


class PreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailPrefs | None = None
    notifications: NotificationSettings | None = None
    travel: TravelPrefs | None = None


def _prefs_row(session: Session, user_id: str) -> UserPreference:
    row = session.get(UserPreference, user_id)
    if row is None:
        row = UserPreference(user_id=user_id)
        session.add(row)
        session.flush()
    return row


@router.get("/me/preferences")
def get_preferences(user: CurrentUser = Depends(require_user)) -> dict[str, Any]:
    with session_scope() as session:
        return {"preferences": _prefs_row(session, user.id).to_dict(), "user": user.public()}


@router.put("/me/preferences")
def update_preferences(body: PreferencesUpdate, user: CurrentUser = Depends(require_user)) -> dict[str, Any]:
    with session_scope() as session:
        row = _prefs_row(session, user.id)
        if body.email:
            row.email_trip_summary = body.email.trip_summary
            row.email_departure_reminder = body.email.departure_reminder
            row.email_journey_changes = body.email.journey_changes
            row.email_price_changes = body.email.price_changes
        if body.notifications:
            row.notifications_enabled = body.notifications.enabled
        if body.travel:
            row.home_city = body.travel.home_city or None
            row.default_priority = str(body.travel.priority)
            row.default_modes = [str(m) for m in dict.fromkeys(body.travel.modes)]
            row.default_buffer_minutes = body.travel.buffer_minutes
        session.flush()
        return {"preferences": row.to_dict()}
