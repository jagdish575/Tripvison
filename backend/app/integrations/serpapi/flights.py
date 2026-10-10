"""Google Flights (engine=google_flights): request builder + normalizer."""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

from app.core.logging import get_logger
from app.integrations.serpapi.client import SerpApiMalformedResponse
from app.schemas.travel import FlightSegment, Layover, NormalizedFlight
from app.utils.time import minutes_between, parse_local_datetime

log = get_logger(__name__)

ENGINE = "google_flights"
TTL_SECONDS = 30 * 60

# SerpApi `stops`: 0 any, 1 nonstop only, 2 one stop or fewer, 3 two stops or fewer
_STOPS_PARAM = {0: 1, 1: 2, 2: 3}


def build_params(origin: str, destination: str, outbound: date, *, adults: int = 1, max_stops: int = 2,
                 currency: str = "INR", gl: str = "in", hl: str = "en") -> dict[str, Any]:
    return {
        "departure_id": origin,
        "arrival_id": destination,
        "outbound_date": outbound.isoformat(),
        "type": 2,
        "adults": adults,
        "stops": _STOPS_PARAM.get(max_stops, 0),
        "currency": currency,
        "gl": gl,
        "hl": hl,
    }


def _segment(raw: dict[str, Any]) -> FlightSegment | None:
    dep = raw.get("departure_airport") or {}
    arr = raw.get("arrival_airport") or {}
    dep_time = parse_local_datetime(dep.get("time"))
    arr_time = parse_local_datetime(arr.get("time"))
    if not (dep.get("id") and arr.get("id") and dep_time and arr_time):
        return None
    duration = raw.get("duration")
    if not isinstance(duration, (int, float)):
        duration = max(minutes_between(dep_time, arr_time), 0)
    return FlightSegment(
        airline=str(raw.get("airline") or "Unknown airline"),
        flight_number=str(raw.get("flight_number") or "").strip() or "—",
        departure_airport=dep["id"],
        departure_airport_name=dep.get("name"),
        arrival_airport=arr["id"],
        arrival_airport_name=arr.get("name"),
        departure_time=dep_time,
        arrival_time=arr_time,
        duration_minutes=int(duration),
        often_delayed=bool(raw.get("often_delayed_by_over_30_min")),
        airplane=raw.get("airplane"),
    )


def _flight(item: dict[str, Any], currency: str) -> NormalizedFlight | None:
    raw_segments = item.get("flights")
    if not isinstance(raw_segments, list) or not raw_segments:
        return None
    segments = [s for s in (_segment(r) for r in raw_segments if isinstance(r, dict)) if s]
    if len(segments) != len(raw_segments):
        return None  # a journey with an unparseable leg cannot be timed reliably

    layovers = []
    for lay in item.get("layovers") or []:
        if isinstance(lay, dict) and isinstance(lay.get("duration"), (int, float)):
            layovers.append(Layover(airport=str(lay.get("id") or ""), airport_name=lay.get("name"),
                                    duration_minutes=int(lay["duration"]), overnight=bool(lay.get("overnight"))))
    first, last = segments[0], segments[-1]
    total = item.get("total_duration")
    if not isinstance(total, (int, float)):
        total = minutes_between(first.departure_time, last.arrival_time)

    airlines = list(dict.fromkeys(s.airline for s in segments))
    numbers = [s.flight_number for s in segments]
    price = item.get("price")
    ident = hashlib.sha1(f"{'|'.join(numbers)}|{first.departure_time.isoformat()}".encode()).hexdigest()[:12]
    return NormalizedFlight(
        id=f"f-{ident}",
        airline=" + ".join(airlines),
        airline_logo=item.get("airline_logo") or (raw_segments[0].get("airline_logo") if raw_segments else None),
        flight_numbers=numbers,
        departure_airport=first.departure_airport,
        arrival_airport=last.arrival_airport,
        departure_time=first.departure_time,
        arrival_time=last.arrival_time,
        duration_minutes=int(total),
        stops=len(segments) - 1,
        layovers=layovers,
        segments=segments,
        price=float(price) if isinstance(price, (int, float)) else None,
        currency=currency,
        often_delayed=any(s.often_delayed for s in segments),
        booking_token=item.get("booking_token") or item.get("departure_token"),
    )


def parse_flights(payload: Any, currency: str = "INR") -> list[NormalizedFlight]:
    if not isinstance(payload, dict):
        raise SerpApiMalformedResponse("flights payload is not an object", engine=ENGINE)
    if payload.get("_empty"):
        return []
    items: list[Any] = []
    for key in ("best_flights", "other_flights"):
        value = payload.get(key)
        if isinstance(value, list):
            items.extend(value)
    flights: dict[str, NormalizedFlight] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            flight = _flight(item, currency)
        except (ValueError, TypeError) as exc:
            log.debug("skipping malformed flight", extra={"context": {"error": str(exc)}})
            continue
        if flight and flight.id not in flights:
            flights[flight.id] = flight
    return list(flights.values())
