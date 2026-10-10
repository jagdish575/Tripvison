"""Google Maps Reviews (engine=google_maps_reviews): request builder + normalizer."""

from __future__ import annotations

from typing import Any

from app.integrations.serpapi.client import SerpApiMalformedResponse
from app.schemas.travel import NormalizedReview, ReviewTopic

ENGINE = "google_maps_reviews"
TTL_SECONDS = 24 * 3600


def build_params(data_id: str, *, hl: str = "en", sort_by: str = "newestFirst") -> dict[str, Any]:
    return {"data_id": data_id, "hl": hl, "sort_by": sort_by}


def parse_reviews(payload: Any) -> tuple[list[NormalizedReview], list[ReviewTopic], dict[str, Any]]:
    if not isinstance(payload, dict):
        raise SerpApiMalformedResponse("reviews payload is not an object", engine=ENGINE)
    if payload.get("_empty"):
        return [], [], {}
    reviews: list[NormalizedReview] = []
    for raw in payload.get("reviews") or []:
        if not isinstance(raw, dict):
            continue
        text = raw.get("snippet")
        extracted = raw.get("extracted_snippet")
        if not text and isinstance(extracted, dict):
            text = extracted.get("original")
        if not isinstance(text, str) or not text.strip():
            continue
        user = raw.get("user") if isinstance(raw.get("user"), dict) else {}
        rating = raw.get("rating")
        reviews.append(NormalizedReview(
            rating=float(rating) if isinstance(rating, (int, float)) else None,
            text=text.strip(),
            date=raw.get("date") if isinstance(raw.get("date"), str) else None,
            author=user.get("name") if isinstance(user.get("name"), str) else None,
        ))
    topics = []
    for raw in payload.get("topics") or []:
        if isinstance(raw, dict) and raw.get("keyword") and isinstance(raw.get("mentions"), (int, float)):
            topics.append(ReviewTopic(keyword=str(raw["keyword"]), mentions=int(raw["mentions"])))
    place_info = payload.get("place_info") if isinstance(payload.get("place_info"), dict) else {}
    return reviews, topics, place_info
