"""Thin, cached search endpoints over the active provider (useful for debugging and judges).
They return normalized models only — never raw SerpApi JSON."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from fastapi import APIRouter, Query, Request

from app.core.config import get_settings
from app.core.errors import ValidationAppError
from app.core.rate_limit import client_key, limiter
from app.integrations.serpapi.client import CallTracker
from app.schemas.travel import GeoPoint
from app.services.airports import resolve_airport
from app.services.providers import get_provider

router = APIRouter(tags=["search"])

_LATLNG = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


def _guard(request: Request) -> None:
    limiter.check("search", client_key(request), get_settings().search_rate_limit_per_minute)


def _airport(value: str, field: str) -> str:
    airport = resolve_airport(value)
    if airport is None:
        raise ValidationAppError(f'Unknown airport or city "{value}".', code="unknown_location", details={"field": field})
    return airport.code


@router.get("/flights/search")
async def search_flights(request: Request, origin: str, destination: str, date: date,
                         travelers: int = Query(1, ge=1, le=9), max_stops: int = Query(2, ge=0, le=2),
                         currency: str = Query("INR", pattern=r"^[A-Z]{3}$")) -> dict[str, Any]:
    _guard(request)
    tracker = CallTracker()
    results = await get_provider().search_flights(_airport(origin, "origin"), _airport(destination, "destination"),
                                                  date, adults=travelers, max_stops=max_stops, currency=currency,
                                                  tracker=tracker, purpose="flights")
    return {"results": [r.model_dump(mode="json") for r in results], "calls": [c.model_dump() for c in tracker.calls]}


@router.get("/hotels/search")
async def search_hotels(request: Request, q: str = Query(min_length=2, max_length=160), check_in: date = Query(),
                        check_out: date = Query(), travelers: int = Query(1, ge=1, le=9),
                        min_rating: float = Query(0, ge=0, le=5),
                        currency: str = Query("INR", pattern=r"^[A-Z]{3}$")) -> dict[str, Any]:
    _guard(request)
    if check_out <= check_in:
        raise ValidationAppError("check_out must be after check_in.")
    tracker = CallTracker()
    results = await get_provider().search_hotels(q, check_in, check_out, adults=travelers, min_rating=min_rating,
                                                 currency=currency, tracker=tracker, purpose="hotels")
    return {"results": [r.model_dump(mode="json") for r in results], "calls": [c.model_dump() for c in tracker.calls]}


@router.get("/places/search")
async def search_places(request: Request, q: str = Query(min_length=2, max_length=80),
                        near: str = Query(min_length=2, max_length=160)) -> dict[str, Any]:
    _guard(request)
    tracker = CallTracker()
    results = await get_provider().search_places(q, near, category=q, city=near.split(",")[-1].strip(),
                                                 tracker=tracker)
    return {"results": [r.model_dump(mode="json") for r in results], "calls": [c.model_dump() for c in tracker.calls]}


async def _point(value: str, tracker: CallTracker) -> tuple[GeoPoint, str]:
    match = _LATLNG.match(value)
    if match:
        return GeoPoint(lat=float(match.group(1)), lng=float(match.group(2))), value
    place = await get_provider().geocode(value, tracker=tracker, purpose="geocode")
    if place is None or place.location is None:
        raise ValidationAppError(f'Couldn\'t locate "{value}".', code="unknown_location")
    return place.location, place.name


@router.get("/directions")
async def directions(request: Request, from_: str = Query(alias="from", min_length=2, max_length=160),
                     to: str = Query(min_length=2, max_length=160)) -> dict[str, Any]:
    _guard(request)
    tracker = CallTracker()
    start, start_label = await _point(from_, tracker)
    end, end_label = await _point(to, tracker)
    route = await get_provider().directions(start, end, start_label=start_label, end_label=end_label, tracker=tracker)
    return {"route": route.model_dump(mode="json") if route else None, "calls": [c.model_dump() for c in tracker.calls]}


@router.get("/reviews")
async def reviews(request: Request, place: str = Query(min_length=2, max_length=160)) -> dict[str, Any]:
    _guard(request)
    tracker = CallTracker()
    name, _, city = place.rpartition(",")
    bundle = await get_provider().hotel_reviews(name.strip() or place, city.strip(), near=None, tracker=tracker)
    return {"place": bundle.place.model_dump(mode="json") if bundle and bundle.place else None,
            "reviews": [r.model_dump(mode="json") for r in (bundle.reviews if bundle else [])],
            "topics": [t.model_dump() for t in (bundle.topics if bundle else [])],
            "calls": [c.model_dump() for c in tracker.calls]}


@router.get("/explore")
async def explore(request: Request, origin: str, date: date | None = None,
                  currency: str = Query("INR", pattern=r"^[A-Z]{3}$")) -> dict[str, Any]:
    _guard(request)
    tracker = CallTracker()
    results = await get_provider().explore(_airport(origin, "origin"), date, currency=currency, tracker=tracker)
    return {"results": [r.model_dump(mode="json") for r in results], "experimental": True}
