"""DemoProvider — implements TravelDataProvider from the labelled demo dataset (DEMO_MODE only)."""

from __future__ import annotations

import json
import time as _time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

from app.core.errors import ValidationAppError
from app.demo import dataset, ujjain
from app.integrations.serpapi.client import CallTracker
from app.schemas.travel import (ExploreDestination, FlightSegment, GeoPoint, Layover, NormalizedFlight,
                                NormalizedHotel, NormalizedPlace, NormalizedReview, NormalizedRoute, ReviewAspect,
                                ReviewBundle)
from app.integrations.serpapi.maps import parse_transit
from app.services.geo import estimate_route
from app.services.places_reference import lookup_city

_TRANSIT_FILE = Path(__file__).with_name("transit_idr_blr.json")


class DemoRouteUnsupported(ValidationAppError):
    code = "demo_route_unsupported"


def _dt(day: date, hhmm: str) -> datetime:
    h, m = hhmm.split(":")
    return datetime.combine(day, datetime.min.time()).replace(hour=int(h), minute=int(m))


# Demo scenarios, by (origin city, destination city)
SCENARIOS = {("indore", "bengaluru"): "Indore → Bengaluru (interview at Manyata Tech Park)",
             ("indore", "ujjain"): "Indore → Ujjain (visit to Mahakal Mandir)"}
_PLACES = {**dataset.PLACES, **ujjain.PLACES}
_HOTELS_BY_CITY = {"bengaluru": dataset.HOTELS, "ujjain": ujjain.HOTELS}
_ALL_HOTELS = [h for hotels in _HOTELS_BY_CITY.values() for h in hotels]
_REVIEWS = {**dataset.REVIEWS, **ujjain.REVIEWS}


def _hotels_for(query: str) -> list[dict]:
    q = query.casefold()
    return ujjain.HOTELS if ujjain.CITY in q or "mahakal" in q else dataset.HOTELS


class DemoProvider:
    mode: Literal["live", "demo"] = "demo"

    def __init__(self, delays: dict[str, int] | None = None) -> None:
        # flight number or transit option id -> minutes of simulated delay (DEMO_MODE re-check only)
        self.delays = delays or {}

    def supports_route(self, origin, destination) -> bool:
        return (origin.city.casefold(), destination.city.casefold()) in SCENARIOS

    @staticmethod
    def _track(tracker: CallTracker, api: str, purpose: str) -> float:
        return _time.perf_counter()

    @staticmethod
    def _done(tracker: CallTracker, api: str, purpose: str, started: float) -> None:
        tracker.record(api, purpose, cached=False, ok=True, ms=int((_time.perf_counter() - started) * 1000))

    async def search_flights(self, origin, destination, outbound, *, adults, max_stops, currency, tracker,
                             purpose="flights"):
        started = self._track(tracker, "google_flights", purpose)
        if (origin, destination) not in dataset.SUPPORTED_ROUTES:
            raise DemoRouteUnsupported("Demo mode only contains the Indore → Bengaluru scenario.")
        flights: list[NormalizedFlight] = []
        for airline, legs, price, delayed in dataset.FLIGHTS:
            dep_day = outbound
            segments = []
            for number, frm, to, dep, arr, arr_off in legs:
                dep_t = _dt(dep_day, dep)
                arr_t = _dt(dep_day + timedelta(days=arr_off), arr)
                segments.append(FlightSegment(
                    airline=airline, flight_number=number, departure_airport=frm,
                    departure_airport_name=dataset.AIRPORT_NAMES.get(frm), arrival_airport=to,
                    arrival_airport_name=dataset.AIRPORT_NAMES.get(to), departure_time=dep_t, arrival_time=arr_t,
                    duration_minutes=int((arr_t - dep_t).total_seconds() // 60), often_delayed=delayed,
                    airplane="Airbus A320neo"))
            layovers = [Layover(airport=a.arrival_airport, airport_name=a.arrival_airport_name,
                                duration_minutes=int((b.departure_time - a.arrival_time).total_seconds() // 60))
                        for a, b in zip(segments, segments[1:])]
            if len(segments) - 1 > max_stops:
                continue
            delay = self.delays.get(segments[0].flight_number, 0)
            if delay:
                last_seg = segments[-1]
                segments[-1] = last_seg.model_copy(update={
                    "arrival_time": last_seg.arrival_time + timedelta(minutes=delay),
                    "duration_minutes": last_seg.duration_minutes + delay})
            first, last = segments[0], segments[-1]
            flights.append(NormalizedFlight(
                id=f"demo-{first.flight_number.replace(' ', '')}-{dep_day.isoformat()}",
                airline=airline, flight_numbers=[s.flight_number for s in segments],
                departure_airport=first.departure_airport, arrival_airport=last.arrival_airport,
                departure_time=first.departure_time, arrival_time=last.arrival_time,
                duration_minutes=int((last.arrival_time - first.departure_time).total_seconds() // 60),
                stops=len(segments) - 1, layovers=layovers, segments=segments,
                price=float(price * adults), currency=currency, often_delayed=delayed, source="demo"))
        self._done(tracker, "google_flights", purpose, started)
        return flights

    async def search_hotels(self, query, check_in, check_out, *, adults, min_rating, currency, tracker,
                            purpose="hotels"):
        started = self._track(tracker, "google_hotels", purpose)
        nights = max(1, (check_out - check_in).days)
        weekend_factor = 1.08 if check_in.weekday() >= 4 else 1.0
        hotels = []
        for h in _hotels_for(query):
            if h["rating"] < min_rating and min_rating >= 3.5:
                continue  # mirrors the Google Hotels `rating` filter
            per_night = round(h["price"] * weekend_factor)
            hotels.append(NormalizedHotel(
                id=h["id"], name=h["name"], rating=h["rating"], reviews=h["reviews"], price_per_night=per_night,
                total_price=per_night * nights, currency=currency, location=GeoPoint(lat=h["lat"], lng=h["lng"]),
                address=h["address"], amenities=h["amenities"], image=h["image"], images=[],
                hotel_class=h["class"], free_cancellation=h["free_cancellation"],
                review_breakdown=[ReviewAspect(name=n, positive=p, negative=q, total=p + q) for n, p, q in h["breakdown"]],
                check_in_time="2:00 PM", check_out_time="12:00 PM", source="demo"))
        self._done(tracker, "google_hotels", purpose, started)
        return hotels

    async def geocode(self, query, *, tracker, near=None, purpose="geocode"):
        started = self._track(tracker, "google_maps", purpose)
        key = query.split(",")[0].strip().casefold()
        result = None
        for name, (label, address, lat, lng) in _PLACES.items():
            if key == name or key.startswith(name) or name.startswith(key) and len(key) >= 4:
                result = NormalizedPlace(id=f"demo-place-{name}", name=label, address=address,
                                         location=GeoPoint(lat=lat, lng=lng), source="demo")
                break
        if result is None:
            for h in _ALL_HOTELS:
                if h["name"].casefold() == key:
                    result = NormalizedPlace(id=f"demo-place-{h['id']}", name=h["name"], address=h["address"],
                                             location=GeoPoint(lat=h["lat"], lng=h["lng"]), data_id=h["id"],
                                             source="demo")
        self._done(tracker, "google_maps", purpose, started)
        return result

    async def directions(self, start, end, *, start_label, end_label, tracker, purpose="directions"):
        started = self._track(tracker, "google_maps_directions", purpose)
        if isinstance(start, str):  # a city name: use the reference city centre
            city = lookup_city(start)
            if city is None:
                return None
            start = GeoPoint(lat=city[2], lng=city[3])
        route = estimate_route(start, end, start_label, end_label)
        self._done(tracker, "google_maps_directions", purpose, started)
        return NormalizedRoute(**{**route.model_dump(), "estimated": False, "source": "demo",
                                  "via": "Outer Ring Road" if route.distance_km > 10 else None})

    async def transit_routes(self, start, end, *, end_label, arrive_by, utc_offset_minutes, wheelchair, currency,
                             tracker, prefer=None):
        started = self._track(tracker, "google_maps_directions", "trains & buses (transit)")
        to_ujjain = abs(end.lat - ujjain.PLACES["ujjain"][2]) < 0.3 and abs(end.lng - ujjain.PLACES["ujjain"][3]) < 0.3
        payload = (ujjain.transit_payload(arrive_by, prefer) if to_ujjain
                   else json.loads(_TRANSIT_FILE.read_text(encoding="utf-8")))
        options = parse_transit(payload, arrive_by, currency)
        for option in options:
            option.source = "demo"
            if option.fare is not None:
                option.fare_source = "demo"
            delay = self.delays.get(option.id, 0)
            if delay:
                option.arrival_time += timedelta(minutes=delay)
                option.duration_minutes += delay
        self._done(tracker, "google_maps_directions", "trains & buses (transit)", started)
        return options

    async def transport_options(self, mode, origin, destination, travel_date, *, tracker):
        """The demo dataset has no Google Search fares — demo journeys keep their labelled demo/estimated fares
        rather than mixing in anything that looks live."""
        return []

    async def search_places(self, category_query, near_label, *, category, city, tracker):
        started = self._track(tracker, "google_local", f"places: {category}")
        anchor_key = near_label.split(",")[0].strip().casefold()
        anchor = _PLACES.get(anchor_key) or _PLACES.get(city.casefold()) or _PLACES["bengaluru city centre"]
        _, _, lat, lng = anchor
        items = []
        for idx, (name, dlat, dlng, rating, reviews, kind, hours) in enumerate(dataset.LOCAL.get(category, [])):
            items.append(NormalizedPlace(
                id=f"demo-{category}-{idx}", name=name, category=category, rating=rating, reviews=reviews,
                address=f"Near {anchor[0]}, {city}", location=GeoPoint(lat=lat + dlat, lng=lng + dlng),
                hours=hours, source="demo"))
        self._done(tracker, "google_local", f"places: {category}", started)
        return items

    async def hotel_reviews(self, hotel_name, city, *, near, tracker):
        place = await self.geocode(hotel_name, tracker=tracker, purpose="hotel lookup")
        if place is None or not place.data_id:
            return None
        started = self._track(tracker, "google_maps_reviews", "hotel reviews")
        raw = _REVIEWS.get(place.data_id, [])
        reviews = [NormalizedReview(rating=r, date=d, text=t, author="Demo guest") for r, d, t in raw]
        self._done(tracker, "google_maps_reviews", "hotel reviews", started)
        return ReviewBundle(place=place, reviews=reviews, topics=[], source="demo")

    async def explore(self, origin, outbound, *, currency, tracker) -> list[ExploreDestination]:
        return []
