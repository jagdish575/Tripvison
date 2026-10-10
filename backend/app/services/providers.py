"""TravelDataProvider abstraction.

`SerpApiProvider` is the live implementation. `DemoProvider` (app/demo) is the only other one and is
used exclusively when DEMO_MODE=true. There is no silent fallback between them.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Literal, Protocol

from app.core.cache import get_cache
from app.core.config import Settings, get_settings
from app.core.errors import SetupRequiredError
from app.integrations.serpapi import flights as serp_flights
from app.integrations.serpapi import hotels as serp_hotels
from app.integrations.serpapi import local as serp_local
from app.integrations.serpapi import maps as serp_maps
from app.integrations.serpapi import reviews as serp_reviews
from app.integrations.serpapi import transport as serp_transport
from app.integrations.serpapi import travel as serp_travel
from app.integrations.serpapi.client import CallTracker, SerpApiClient
from app.schemas.travel import (ExploreDestination, GeoPoint, NormalizedFlight, NormalizedHotel, NormalizedPlace,
                                NormalizedRoute, NormalizedTransit, ReportedTransportRoute, ResolvedLocation,
                                ReviewBundle)
from app.services.geo import haversine_km


class TravelDataProvider(Protocol):
    mode: Literal["live", "demo"]

    def supports_route(self, origin: ResolvedLocation, destination: ResolvedLocation) -> bool: ...

    async def search_flights(self, origin: str, destination: str, outbound: date, *, adults: int, max_stops: int,
                             currency: str, tracker: CallTracker, purpose: str) -> list[NormalizedFlight]: ...

    async def search_hotels(self, query: str, check_in: date, check_out: date, *, adults: int, min_rating: float,
                            currency: str, tracker: CallTracker, purpose: str) -> list[NormalizedHotel]: ...

    async def geocode(self, query: str, *, tracker: CallTracker, near: GeoPoint | None = None,
                      purpose: str = "") -> NormalizedPlace | None: ...

    async def directions(self, start: GeoPoint | str, end: GeoPoint, *, start_label: str, end_label: str,
                         tracker: CallTracker, purpose: str = "") -> NormalizedRoute | None: ...

    async def transit_routes(self, start: str, end: GeoPoint, *, end_label: str, arrive_by: datetime,
                             utc_offset_minutes: int, wheelchair: bool, currency: str,
                             tracker: CallTracker, prefer: str | None = None) -> list[NormalizedTransit]: ...

    async def transport_options(self, mode: str, origin: str, destination: str, travel_date: date | None, *,
                                tracker: CallTracker) -> list[ReportedTransportRoute]: ...

    async def search_places(self, category_query: str, near_label: str, *, category: str, city: str,
                            tracker: CallTracker) -> list[NormalizedPlace]: ...

    async def hotel_reviews(self, hotel_name: str, city: str, *, near: GeoPoint | None,
                            tracker: CallTracker) -> ReviewBundle | None: ...

    async def explore(self, origin: str, outbound: date | None, *, currency: str,
                      tracker: CallTracker) -> list[ExploreDestination]: ...


class SerpApiProvider:
    mode: Literal["live", "demo"] = "live"

    def __init__(self, client: SerpApiClient, settings: Settings) -> None:
        self.client = client
        self.gl = settings.serpapi_gl
        self.hl = settings.serpapi_hl

    def supports_route(self, origin: ResolvedLocation, destination: ResolvedLocation) -> bool:
        return True

    async def search_flights(self, origin, destination, outbound, *, adults, max_stops, currency, tracker,
                             purpose="flights"):
        params = serp_flights.build_params(origin, destination, outbound, adults=adults, max_stops=max_stops,
                                           currency=currency, gl=self.gl, hl=self.hl)
        payload = await self.client.search(serp_flights.ENGINE, params, ttl_seconds=serp_flights.TTL_SECONDS,
                                           tracker=tracker, purpose=purpose)
        return serp_flights.parse_flights(payload, currency)

    async def search_hotels(self, query, check_in, check_out, *, adults, min_rating, currency, tracker,
                            purpose="hotels"):
        params = serp_hotels.build_params(query, check_in, check_out, adults=adults, min_rating=min_rating,
                                          currency=currency, gl=self.gl, hl=self.hl)
        payload = await self.client.search(serp_hotels.ENGINE, params, ttl_seconds=serp_hotels.TTL_SECONDS,
                                           tracker=tracker, purpose=purpose)
        return serp_hotels.parse_hotels(payload, currency)

    async def geocode(self, query, *, tracker, near=None, purpose="geocode"):
        params = serp_maps.build_search_params(query, near=near, hl=self.hl, gl=self.gl)
        payload = await self.client.search(serp_maps.SEARCH_ENGINE, params,
                                           ttl_seconds=serp_maps.GEOCODE_TTL_SECONDS, tracker=tracker, purpose=purpose)
        for place in serp_maps.parse_search(payload):
            if place.location is not None:
                return place
        return None

    async def directions(self, start, end, *, start_label, end_label, tracker, purpose="directions"):
        params = serp_maps.build_directions_params(start, end, mode="driving", hl=self.hl, gl=self.gl)
        payload = await self.client.search(serp_maps.DIRECTIONS_ENGINE, params,
                                           ttl_seconds=serp_maps.DIRECTIONS_TTL_SECONDS, tracker=tracker,
                                           purpose=purpose)
        return serp_maps.parse_directions(payload, start_label, end_label)

    async def transit_routes(self, start, end, *, end_label, arrive_by, utc_offset_minutes, wheelchair, currency,
                             tracker, prefer=None):
        local_tz = timezone(timedelta(minutes=utc_offset_minutes))
        epoch = int(arrive_by.replace(tzinfo=local_tz).timestamp())
        params = serp_maps.build_transit_params(start, end, arrive_by_epoch=epoch, wheelchair=wheelchair,
                                                prefer=prefer, hl=self.hl, gl=self.gl)
        purpose = {"bus": "buses (transit, bus preferred)", "train": "trains (transit, train preferred)"}.get(
            prefer or "", "trains & buses (transit)")
        payload = await self.client.search(serp_maps.DIRECTIONS_ENGINE, params,
                                           ttl_seconds=serp_maps.TRANSIT_TTL_SECONDS, tracker=tracker,
                                           purpose=purpose)
        return serp_maps.parse_transit(payload, arrive_by, currency)

    async def transport_options(self, mode, origin, destination, travel_date, *, tracker):
        """Google Search transport-options answer box — fares Google shows for train/bus routes, if any."""
        params = serp_transport.build_params(mode, origin, destination, travel_date, gl=self.gl, hl=self.hl)
        payload = await self.client.search(serp_transport.ENGINE, params, ttl_seconds=serp_transport.TTL_SECONDS,
                                           tracker=tracker, purpose=f"{mode} fares (Google Search transport options)")
        return serp_transport.parse_transport_options(payload)

    async def search_places(self, category_query, near_label, *, category, city, tracker):
        params = serp_local.build_params(category_query, near_label, hl=self.hl, gl=self.gl)
        payload = await self.client.search(serp_local.ENGINE, params, ttl_seconds=serp_local.TTL_SECONDS,
                                           tracker=tracker, purpose=f"places: {category}")
        return serp_local.parse_places(payload, category)

    async def hotel_reviews(self, hotel_name, city, *, near, tracker):
        place = await self.geocode(f"{hotel_name}, {city}", tracker=tracker, near=near, purpose="hotel lookup")
        if place is None or not place.data_id:
            return None
        if near is not None and place.location is not None and haversine_km(near, place.location) > 3:
            return None  # matched a different property with the same name — don't attribute its reviews
        params = serp_reviews.build_params(place.data_id, hl=self.hl)
        payload = await self.client.search(serp_reviews.ENGINE, params, ttl_seconds=serp_reviews.TTL_SECONDS,
                                           tracker=tracker, purpose="hotel reviews")
        reviews, topics, _info = serp_reviews.parse_reviews(payload)
        return ReviewBundle(place=place, reviews=reviews, topics=topics)

    async def explore(self, origin, outbound, *, currency, tracker):
        params = serp_travel.build_params(origin, outbound, currency=currency, gl=self.gl, hl=self.hl)
        payload = await self.client.search(serp_travel.ENGINE, params, ttl_seconds=serp_travel.TTL_SECONDS,
                                           tracker=tracker, purpose="explore")
        return serp_travel.parse_explore(payload)


_serp_client: SerpApiClient | None = None


def get_serpapi_client(settings: Settings | None = None) -> SerpApiClient:
    global _serp_client
    settings = settings or get_settings()
    if _serp_client is None:
        _serp_client = SerpApiClient(
            settings.serpapi_api_key,
            cache=get_cache(),
            base_url=settings.serpapi_base_url,
            timeout_seconds=settings.serpapi_timeout_seconds,
            max_retries=settings.serpapi_max_retries,
            max_concurrency=settings.serpapi_max_concurrency,
        )
    return _serp_client


def set_serpapi_client(client: SerpApiClient | None) -> None:
    global _serp_client
    _serp_client = client


def get_provider(settings: Settings | None = None) -> TravelDataProvider:
    settings = settings or get_settings()
    if settings.demo_mode:
        from app.demo.provider import DemoProvider

        return DemoProvider()
    if not settings.serpapi_configured:
        raise SetupRequiredError(
            "Live travel data isn't configured. Add SERPAPI_API_KEY to your .env file "
            "(get one at serpapi.com), or set DEMO_MODE=true to explore the labelled demo dataset.",
            details={"missing": ["SERPAPI_API_KEY"]},
        )
    return SerpApiProvider(get_serpapi_client(settings), settings)
