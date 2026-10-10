"""Mission input validation."""

from __future__ import annotations

from datetime import date, time, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MissionType(StrEnum):
    interview = "interview"
    exam = "exam"
    business = "business"
    conference = "conference"
    wedding = "wedding"
    medical = "medical"
    vacation = "vacation"
    family = "family"
    other = "other"


TIME_CRITICAL = {MissionType.interview, MissionType.exam, MissionType.medical, MissionType.business,
                 MissionType.conference}
LEISURE = {MissionType.vacation, MissionType.family}


class Priority(StrEnum):
    balanced = "balanced"
    save_money = "save_money"
    save_time = "save_time"
    avoid_risk = "avoid_risk"


class TravelMode(StrEnum):
    flight = "flight"
    train = "train"
    bus = "bus"
    ground = "ground"


class AccessibilityNeed(StrEnum):
    wheelchair = "wheelchair"
    elevator = "elevator"
    accessible_hotel = "accessible_hotel"
    accessible_transport = "accessible_transport"


class NotificationPrefs(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    email: str = Field(min_length=5, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    trip_summary: bool = True
    reminder: bool = True
    changes: bool = True


class Preference(StrEnum):
    prefer_direct = "prefer_direct"
    avoid_early_departure = "avoid_early_departure"
    night_before_preferred = "night_before_preferred"
    same_day_only = "same_day_only"
    breakfast_included = "breakfast_included"
    free_cancellation = "free_cancellation"


MAX_DAYS_AHEAD = 330
DEFAULT_FOOD_PER_DAY = 500


class MissionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    origin: str = Field(min_length=2, max_length=80)
    destination: str = Field(min_length=2, max_length=80)
    venue: str | None = Field(default=None, max_length=160)
    mission_type: MissionType = MissionType.interview
    travel_date: date
    arrival_deadline: time
    travelers: int = Field(default=1, ge=1, le=9)
    budget: float = Field(gt=0, le=10_000_000)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    min_buffer_minutes: int = Field(default=60, ge=0, le=240)
    max_ground_minutes: int = Field(default=90, ge=15, le=300)
    hotel_required: bool = True
    min_hotel_rating: float = Field(default=3.5, ge=0, le=5)
    max_stops: int = Field(default=1, ge=0, le=2)
    allow_previous_day: bool = True
    preferences: list[Preference] = Field(default_factory=list, max_length=6)
    priority: Priority = Priority.balanced
    modes: list[TravelMode] = Field(default_factory=lambda: list(TravelMode), min_length=1, max_length=4)
    stay_nights: int = Field(default=1, ge=1, le=14)
    food_per_day: float = Field(default=500, ge=0, le=100_000)
    accessibility: list[AccessibilityNeed] = Field(default_factory=list, max_length=4)
    notifications: NotificationPrefs | None = None

    @field_validator("venue")
    @classmethod
    def _blank_venue(cls, value: str | None) -> str | None:
        return value or None

    @field_validator("travel_date")
    @classmethod
    def _date_window(cls, value: date) -> date:
        today = date.today()
        if value < today:
            raise ValueError("Travel date is in the past.")
        if value > today + timedelta(days=MAX_DAYS_AHEAD):
            raise ValueError(f"Travel date must be within {MAX_DAYS_AHEAD} days — flight prices aren't published further out.")
        return value

    @model_validator(mode="after")
    def _consistency(self) -> MissionRequest:
        if self.origin.casefold() == self.destination.casefold():
            raise ValueError("Origin and destination must be different.")
        self.preferences = list(dict.fromkeys(self.preferences))
        self.modes = list(dict.fromkeys(self.modes))
        self.accessibility = list(dict.fromkeys(self.accessibility))
        if Preference.same_day_only in self.preferences:
            self.allow_previous_day = False
        return self

    @property
    def is_time_critical(self) -> bool:
        return self.mission_type in TIME_CRITICAL


class MissionCreated(BaseModel):
    mission_id: str
    status: str
    mode: str


class MissionStatus(BaseModel):
    mission_id: str
    status: str
    mode: str
    progress: dict[str, Any]
    input: dict[str, Any]
    error: dict[str, Any] | None = None
    created_at: str
