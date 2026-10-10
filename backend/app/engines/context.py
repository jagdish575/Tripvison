"""Immutable per-mission context shared by the engines."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from app.schemas.mission import MissionRequest
from app.schemas.result import RoutePlan, VenueInfo
from app.schemas.travel import Airport, ResolvedLocation


def as_location(place: Airport | ResolvedLocation) -> ResolvedLocation:
    if isinstance(place, ResolvedLocation):
        return place
    return ResolvedLocation(query=place.code, city=place.city, name=place.city, country=place.country,
                            location=place.location, code=place.code, has_airport=True, airports=[place],
                            source="airport")


@dataclass(frozen=True)
class JourneyAssumptions:
    airport_exit_minutes: int = 25
    hotel_stop_minutes: int = 15
    night_before_extra_margin_minutes: int = 15
    taxi_base_fare: float = 100.0
    taxi_per_km: float = 18.0
    # Estimated fares where no live fare exists (docs/SCORING_ENGINE.md §Cost model)
    train_fare_per_km: float = 1.25      # ~ Indian Railways 3AC, per traveller
    train_min_fare: float = 300.0
    bus_fare_per_km: float = 1.8         # ~ AC sleeper intercity bus, per traveller
    local_transit_fare: float = 40.0     # metro / city bus segment, per traveller
    outstation_cab_per_km: float = 13.0  # one-way outstation cab, per vehicle
    driver_allowance_per_day: float = 300.0
    max_practical_drive_minutes: int = 16 * 60
    airport_checkin_minutes: int = 75     # arrive this early before a domestic departure


@dataclass
class MissionContext:
    """`origin` / `destination` are the places the traveller named (they may have no airport).
    `origin_airport` / `destination_airport` are the airports used for flights — the city's own or the
    nearest practical one — or None when flights aren't evaluated."""

    request: MissionRequest
    origin: ResolvedLocation
    destination: ResolvedLocation
    venue: VenueInfo
    assumptions: JourneyAssumptions = field(default_factory=JourneyAssumptions)
    origin_airport: Airport | None = None
    destination_airport: Airport | None = None
    plan: RoutePlan | None = None

    def __post_init__(self) -> None:
        # Backwards compatible: passing Airport objects means "this city, flying from/to its own airport".
        if isinstance(self.origin, Airport):
            self.origin_airport = self.origin_airport or self.origin
            self.origin = as_location(self.origin)
        if isinstance(self.destination, Airport):
            self.destination_airport = self.destination_airport or self.destination
            self.destination = as_location(self.destination)

    @property
    def deadline(self) -> datetime:
        return datetime.combine(self.request.travel_date, self.request.arrival_deadline)

    @property
    def mission_date(self) -> date:
        return self.request.travel_date

    @property
    def day_before(self) -> date:
        return self.request.travel_date - timedelta(days=1)

    @property
    def required_buffer(self) -> int:
        return self.request.min_buffer_minutes

    @property
    def currency(self) -> str:
        return self.request.currency
