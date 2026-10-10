from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.core.cache import get_cache
from app.core.config import get_settings
from app.core.templates import all_templates
from app.services.email.providers import get_email_provider
from app.services.airports import search_airports

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict[str, Any]:
    s = get_settings()
    return {
        "status": "ok",
        "version": s.version,
        "demo_mode": s.demo_mode,
        "debug_mode": s.debug_mode,
        "google_auth": s.google_auth_configured,
        "serpapi_configured": s.serpapi_configured,
        "ai_configured": s.ai_configured,
        "ai_provider": s.ai_provider if s.ai_configured else None,
        "ai_model": s.ai_model if s.ai_configured else None,
        "database": s.database_kind,
        "cache": get_cache().name,
        "ready": s.demo_mode or s.serpapi_configured,
        "email_delivery": get_email_provider(s).name,
    }


@router.get("/templates")
def templates() -> dict[str, Any]:
    return {"templates": all_templates()}


@router.get("/airports")
def airports(q: str = Query("", max_length=40)) -> dict[str, Any]:
    return {"results": [a.model_dump() for a in search_airports(q)]}


@router.get("/locations")
def locations(q: str = Query("", max_length=60)) -> dict[str, Any]:
    """Suggestions for the From / To fields: cities and towns (with or without an airport) and airports.
    A place without an airport is a valid choice — TripMission routes through the nearest practical hub."""
    from app.services.places_reference import CITY_CENTRES

    text = q.strip().casefold()
    if len(text) < 2:
        return {"results": []}
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for airport in search_airports(q, limit=6):
        if airport.city not in seen:
            seen.add(airport.city)
            out.append({"label": airport.city, "code": airport.code, "detail": airport.name, "has_airport": True})
    for key, (city, _country, _lat, _lng) in CITY_CENTRES.items():
        if city in seen or not (key.startswith(text) or (len(text) >= 3 and text in key)):
            continue
        seen.add(city)
        out.append({"label": city, "code": None, "detail": "No airport · we'll route via the nearest hub",
                    "has_airport": False})
    return {"results": out[:8]}
