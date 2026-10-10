"""Google Local (engine=google_local): request builder + normalizer."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.integrations.serpapi.client import SerpApiMalformedResponse
from app.schemas.travel import GeoPoint, NormalizedPlace

ENGINE = "google_local"
TTL_SECONDS = 24 * 3600

_COMPACT = re.compile(r"([\d.]+)\s*([KkMm]?)")


def build_params(category_query: str, near_label: str, *, location: str | None = None,
                 hl: str = "en", gl: str = "in") -> dict[str, Any]:
    params: dict[str, Any] = {"q": f"{category_query} near {near_label}", "hl": hl, "gl": gl}
    if location:
        params["location"] = location
    return params


def _review_count(raw: dict[str, Any]) -> int | None:
    value = raw.get("reviews")
    if isinstance(value, (int, float)):
        return int(value)
    text = raw.get("reviews_original") or (value if isinstance(value, str) else None)
    if isinstance(text, str):
        match = _COMPACT.search(text.replace(",", ""))
        if match:
            number = float(match.group(1))
            suffix = match.group(2).lower()
            return int(number * (1000 if suffix == "k" else 1_000_000 if suffix == "m" else 1))
    return None


def parse_places(payload: Any, category: str) -> list[NormalizedPlace]:
    if not isinstance(payload, dict):
        raise SerpApiMalformedResponse("local payload is not an object", engine=ENGINE)
    if payload.get("_empty"):
        return []
    results = payload.get("local_results")
    if isinstance(results, dict):  # some layouts nest under {"places": [...]}
        results = results.get("places")
    if not isinstance(results, list):
        return []
    places = []
    for raw in results:
        if not isinstance(raw, dict) or not raw.get("title"):
            continue
        gps = raw.get("gps_coordinates") or {}
        location = None
        if isinstance(gps.get("latitude"), (int, float)) and isinstance(gps.get("longitude"), (int, float)):
            location = GeoPoint(lat=float(gps["latitude"]), lng=float(gps["longitude"]))
        rating = raw.get("rating")
        ident = raw.get("place_id") or hashlib.sha1(f"{raw['title']}|{raw.get('address')}".encode()).hexdigest()[:12]
        places.append(NormalizedPlace(
            id=f"l-{ident}"[:120],
            name=str(raw["title"]),
            category=category,
            rating=float(rating) if isinstance(rating, (int, float)) else None,
            reviews=_review_count(raw),
            address=raw.get("address") if isinstance(raw.get("address"), str) else None,
            location=location,
            hours=raw.get("hours") if isinstance(raw.get("hours"), str) else None,
            thumbnail=raw.get("thumbnail") if isinstance(raw.get("thumbnail"), str) else None,
            price=raw.get("price") if isinstance(raw.get("price"), str) else None,
            place_id=raw.get("place_id"),
            source=ENGINE,
        ))
    return places
