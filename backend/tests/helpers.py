"""Builders for hand-made normalized models used by the pure engine tests."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.engines.context import MissionContext
from app.engines.itinerary_engine import ItineraryEngine
from app.engines.risk_engine import RiskEngine
from app.engines.scoring_engine import ScoringEngine
from app.schemas.mission import MissionRequest
from app.schemas.result import Itinerary, VenueInfo
from app.schemas.travel import GeoPoint, Layover, NormalizedFlight, NormalizedHotel, NormalizedRoute, ReviewAspect
from app.services.airports import resolve_airport

MISSION_DAY = date.today() + timedelta(days=5)


def request(**overrides) -> MissionRequest:
    base = dict(origin="Indore", destination="Bangalore", venue="Manyata Tech Park", mission_type="interview",
                travel_date=MISSION_DAY, arrival_deadline=time(10, 0), budget=10000, min_buffer_minutes=60,
                max_ground_minutes=90, hotel_required=True, min_hotel_rating=3.5, max_stops=1)
    base.update(overrides)
    return MissionRequest(**base)


def context(**overrides) -> MissionContext:
    req = request(**overrides)
    return MissionContext(request=req, origin=resolve_airport("IDR"), destination=resolve_airport("BLR"),
                          venue=VenueInfo(name="Manyata Tech Park", location=GeoPoint(lat=13.0475, lng=77.6205),
                                          resolved=True))


def flight(dep: str, arr: str, *, day: date = MISSION_DAY, price: float | None = 5000, stops: int = 0,
           delayed: bool = False, layover: int = 90, number: str = "6E 100") -> NormalizedFlight:
    dep_t = datetime.combine(day, time.fromisoformat(dep))
    arr_t = datetime.combine(day, time.fromisoformat(arr))
    return NormalizedFlight(
        id=f"f-{number}-{dep}-{day}", airline="IndiGo", flight_numbers=[number], departure_airport="IDR",
        arrival_airport="BLR", departure_time=dep_t, arrival_time=arr_t,
        duration_minutes=int((arr_t - dep_t).total_seconds() // 60), stops=stops,
        layovers=[Layover(airport="HYD", duration_minutes=layover)] * stops, price=price, often_delayed=delayed)


def hotel(name: str = "Near Hotel", *, distance: float | None = 1.2, rating: float | None = 4.3,
          price: float | None = 3000, reviews: int | None = 1500, breakdown=None) -> NormalizedHotel:
    return NormalizedHotel(
        id=f"h-{name.replace(' ', '-').lower()}", name=name, rating=rating, reviews=reviews, price_per_night=price,
        total_price=price, location=GeoPoint(lat=13.04, lng=77.61), distance_km=distance,
        review_breakdown=breakdown or [ReviewAspect(name="Location", positive=90, negative=10, total=100)])


def route(minutes: int, km: float, typical: int | None = None, estimated: bool = False) -> NormalizedRoute:
    return NormalizedRoute(origin_label="A", destination_label="B", distance_km=km, duration_minutes=minutes,
                           typical_max_minutes=typical, estimated=estimated)


def build(ctx: MissionContext, f: NormalizedFlight, h: NormalizedHotel | None = None, *,
          a2h=None, h2v=None, a2v=None) -> Itinerary:
    itin = ItineraryEngine(ctx).build(f, hotel=h, airport_to_hotel=a2h or route(45, 26),
                                      hotel_to_venue=h2v or route(8, 1.5), airport_to_venue=a2v or route(50, 27))
    assert itin is not None
    return itin


def evaluate(ctx: MissionContext, itins: list[Itinerary]) -> list[Itinerary]:
    fastest = min(i.total_travel_minutes for i in itins)
    for i in itins:
        i.scores = ScoringEngine(ctx).score(i, fastest)
        i.risk = RiskEngine(ctx).assess(i)
    return itins
