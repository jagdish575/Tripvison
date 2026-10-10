"""LocationResolutionService — turns what a traveller typed into a ResolvedLocation.

Validation asks "can we resolve this place?", never "does it have an airport?". A city without an
airport (Ujjain) is a perfectly valid destination: it gets nearby airports with estimated road
transfers, and RouteIntelligenceService decides which travel modes make sense.

Resolution order (cheapest first):
  1. Reference gazetteer of city centres (no live call)
  2. Airport table — a city name, alias or IATA code ("BLR", "Bangalore (BLR)")
  3. Live geocoding through the active provider (Google Maps via SerpApi) for any other town or landmark
"""

from __future__ import annotations

from app.core.config import Settings
from app.core.errors import ValidationAppError
from app.core.logging import get_logger
from app.integrations.serpapi.client import CallTracker, SerpApiError
from app.schemas.travel import Airport, GeoPoint, NearbyHub, ResolvedLocation
from app.services.airports import AIRPORTS, airports_within, resolve_airport
from app.services.geo import estimate_transfer_minutes, haversine_km, road_km_estimate
from app.services.places_reference import lookup_city

log = get_logger(__name__)

NEARBY_AIRPORT_SEARCH_KM = 450.0
MAX_NEARBY_AIRPORTS = 3


class LocationResolutionService:
    def __init__(self, settings: Settings, provider=None, tracker: CallTracker | None = None) -> None:
        self.settings = settings
        self.provider = provider
        self.tracker = tracker or CallTracker()

    # ------------------------------------------------------------------ public
    async def resolve(self, query: str, *, field: str) -> ResolvedLocation:
        text = query.strip()
        location = self.resolve_offline(text)
        if location is None:
            location = await self._geocode(text)
        if location is None:
            raise ValidationAppError(
                f'We couldn\'t find "{text}". Check the spelling or try the nearest town or city.',
                code="unknown_location", details={"field": field})
        return location

    def resolve_offline(self, query: str) -> ResolvedLocation | None:
        """Gazetteer, then airport table. No network."""
        city = lookup_city(query)
        if city is not None:
            name, country, lat, lng = city
            return self._with_airports(ResolvedLocation(
                query=query, city=name, name=name, country=country, location=GeoPoint(lat=lat, lng=lng),
                source="reference"), alias_airport=resolve_airport(query))
        airport = resolve_airport(query)
        if airport is not None:
            centre = lookup_city(airport.city)
            point = GeoPoint(lat=centre[2], lng=centre[3]) if centre else airport.location
            return self._with_airports(ResolvedLocation(
                query=query, city=airport.city, name=airport.city, country=airport.country, location=point,
                source="airport"), alias_airport=airport)
        return None

    # ------------------------------------------------------------------ internals
    async def _geocode(self, query: str) -> ResolvedLocation | None:
        if self.provider is None:
            return None
        try:
            place = await self.provider.geocode(query, tracker=self.tracker, purpose="resolve location")
        except SerpApiError as exc:
            log.warning("location geocode failed", extra={"context": {"code": exc.code}})
            return None
        if place is None or place.location is None:
            return None
        head = query.split(",")[0].strip()
        city = head.title() if head.islower() else head
        return self._with_airports(ResolvedLocation(
            query=query, city=city, name=place.name or city, country="IN" if self.settings.serpapi_gl == "in" else "",
            location=place.location, source="demo" if getattr(self.provider, "mode", "") == "demo" else "geocoded"),
            alias_airport=None)

    def _with_airports(self, loc: ResolvedLocation, *, alias_airport: Airport | None) -> ResolvedLocation:
        s = self.settings
        own: Airport | None = None
        if alias_airport is not None and haversine_km(alias_airport.location, loc.location) <= max(
                s.own_airport_radius_km, 60):
            own = alias_airport
        else:
            close = airports_within(loc.location, s.own_airport_radius_km)
            own = close[0][0] if close else None
        if own is not None:
            loc.code, loc.has_airport, loc.airports = own.code, True, [own]
        loc.nearby_airports = nearby_airports(loc.location, s.max_practical_airport_transfer_minutes,
                                              exclude=own.code if own else None)
        return loc


def airport_hub(airport: Airport, point: GeoPoint, max_transfer_minutes: int) -> NearbyHub:
    straight = haversine_km(point, airport.location)
    road = road_km_estimate(point, airport.location)
    minutes = estimate_transfer_minutes(road)
    return NearbyHub(kind="airport", code=airport.code, name=airport.name, city=airport.city,
                     location=airport.location, distance_km=round(straight, 1), road_km=road,
                     transfer_minutes=minutes, practical=minutes <= max_transfer_minutes)


def nearby_airports(point: GeoPoint, max_transfer_minutes: int, *, exclude: str | None = None) -> list[NearbyHub]:
    hubs = [airport_hub(a, point, max_transfer_minutes)
            for a, _ in airports_within(point, NEARBY_AIRPORT_SEARCH_KM) if a.code != exclude]
    return hubs[:MAX_NEARBY_AIRPORTS]


def airport_by_code(code: str | None) -> Airport | None:
    return AIRPORTS.get(code) if code else None
