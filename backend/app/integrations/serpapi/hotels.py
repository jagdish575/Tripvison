"""Google Hotels (engine=google_hotels): request builder + normalizer."""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

from app.core.logging import get_logger
from app.integrations.serpapi.client import SerpApiMalformedResponse
from app.schemas.travel import GeoPoint, NormalizedHotel, ReviewAspect

log = get_logger(__name__)

ENGINE = "google_hotels"
TTL_SECONDS = 60 * 60


def _rating_param(min_rating: float) -> int | None:
    if min_rating >= 4.5:
        return 9
    if min_rating >= 4.0:
        return 8
    if min_rating >= 3.5:
        return 7
    return None


def build_params(query: str, check_in: date, check_out: date, *, adults: int = 1, min_rating: float = 0.0,
                 currency: str = "INR", gl: str = "in", hl: str = "en") -> dict[str, Any]:
    return {
        "q": query,
        "check_in_date": check_in.isoformat(),
        "check_out_date": check_out.isoformat(),
        "adults": adults,
        "currency": currency,
        "gl": gl,
        "hl": hl,
        "rating": _rating_param(min_rating),
    }


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _free_cancellation(item: dict[str, Any]) -> bool | None:
    if isinstance(item.get("free_cancellation"), bool):
        return item["free_cancellation"]
    texts = [str(item.get("deal_description") or ""), str(item.get("deal") or "")]
    for price in item.get("prices") or []:
        if isinstance(price, dict):
            if price.get("free_cancellation") is True:
                return True
    joined = " ".join(texts).lower()
    if "free cancellation" in joined:
        return True
    return None


def _hotel(item: dict[str, Any], currency: str) -> NormalizedHotel | None:
    name = item.get("name")
    if not name or not isinstance(name, str):
        return None
    gps = item.get("gps_coordinates") or {}
    location = None
    if isinstance(gps.get("latitude"), (int, float)) and isinstance(gps.get("longitude"), (int, float)):
        location = GeoPoint(lat=float(gps["latitude"]), lng=float(gps["longitude"]))

    images: list[str] = []
    for img in item.get("images") or []:
        if isinstance(img, dict):
            src = img.get("original_image") or img.get("thumbnail")
            if isinstance(src, str):
                images.append(src)

    breakdown = []
    for aspect in item.get("reviews_breakdown") or []:
        if isinstance(aspect, dict) and aspect.get("name"):
            breakdown.append(ReviewAspect(
                name=str(aspect.get("description") or aspect["name"]),
                positive=int(aspect.get("positive") or 0),
                negative=int(aspect.get("negative") or 0),
                neutral=int(aspect.get("neutral") or 0),
                total=int(aspect.get("total_mentioned") or 0),
            ))

    rate = item.get("rate_per_night") or {}
    total = item.get("total_rate") or {}
    token = item.get("property_token")
    ident = token or hashlib.sha1(f"{name}|{location.as_param() if location else ''}".encode()).hexdigest()[:12]
    hotel_class = item.get("extracted_hotel_class")
    rating = _number(item.get("overall_rating"))
    reviews = item.get("reviews")
    return NormalizedHotel(
        id=f"h-{ident}"[:120],
        name=name.strip(),
        rating=rating if rating and rating > 0 else None,
        reviews=int(reviews) if isinstance(reviews, (int, float)) else None,
        price_per_night=_number(rate.get("extracted_lowest")),
        total_price=_number(total.get("extracted_lowest")),
        currency=currency,
        location=location,
        address=item.get("address") if isinstance(item.get("address"), str) else None,
        amenities=[a for a in (item.get("amenities") or []) if isinstance(a, str)][:20],
        image=images[0] if images else None,
        images=images[:6],
        hotel_class=int(hotel_class) if isinstance(hotel_class, (int, float)) else None,
        free_cancellation=_free_cancellation(item),
        review_breakdown=breakdown,
        link=item.get("link") if isinstance(item.get("link"), str) else None,
        check_in_time=item.get("check_in_time"),
        check_out_time=item.get("check_out_time"),
    )


def parse_hotels(payload: Any, currency: str = "INR") -> list[NormalizedHotel]:
    if not isinstance(payload, dict):
        raise SerpApiMalformedResponse("hotels payload is not an object", engine=ENGINE)
    if payload.get("_empty"):
        return []
    properties = payload.get("properties")
    if not isinstance(properties, list):
        return []
    hotels: dict[str, NormalizedHotel] = {}
    for item in properties:
        if not isinstance(item, dict):
            continue
        try:
            hotel = _hotel(item, currency)
        except (ValueError, TypeError) as exc:
            log.debug("skipping malformed hotel", extra={"context": {"error": str(exc)}})
            continue
        if hotel and hotel.id not in hotels:
            hotels[hotel.id] = hotel
    return list(hotels.values())
