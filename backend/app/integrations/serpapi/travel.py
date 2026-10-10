"""Google Travel Explore (engine=google_travel_explore) — experimental, powers GET /explore only."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.integrations.serpapi.client import SerpApiMalformedResponse
from app.schemas.travel import ExploreDestination

ENGINE = "google_travel_explore"
TTL_SECONDS = 6 * 3600


def build_params(origin: str, outbound: date | None = None, *, currency: str = "INR",
                 gl: str = "in", hl: str = "en") -> dict[str, Any]:
    params: dict[str, Any] = {"departure_id": origin, "currency": currency, "gl": gl, "hl": hl}
    if outbound:
        params["outbound_date"] = outbound.isoformat()
    return params


def parse_explore(payload: Any) -> list[ExploreDestination]:
    if not isinstance(payload, dict):
        raise SerpApiMalformedResponse("explore payload is not an object", engine=ENGINE)
    results = []
    for raw in payload.get("destinations") or []:
        if not isinstance(raw, dict) or not raw.get("name"):
            continue
        airport = raw.get("destination_airport") or raw.get("airport") or {}
        results.append(ExploreDestination(
            name=str(raw["name"]),
            country=raw.get("country"),
            airport=airport.get("code") if isinstance(airport, dict) else None,
            flight_price=raw.get("flight_price") if isinstance(raw.get("flight_price"), (int, float)) else None,
            hotel_price=raw.get("hotel_price") if isinstance(raw.get("hotel_price"), (int, float)) else None,
            start_date=raw.get("start_date"),
            end_date=raw.get("end_date"),
            stops=raw.get("number_of_stops") if isinstance(raw.get("number_of_stops"), int) else None,
            flight_duration_minutes=raw.get("flight_duration") if isinstance(raw.get("flight_duration"), int) else None,
            thumbnail=raw.get("thumbnail"),
        ))
    return results
