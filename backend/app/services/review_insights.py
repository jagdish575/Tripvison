"""Turns review data returned by the APIs into aspect-level signals.

Only two inputs are used: Google Hotels `reviews_breakdown` counts and Google Maps review texts/topics.
Quotes are verbatim sentences from those reviews. Nothing is generated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.schemas.result import ReviewInsights, ReviewQuote, ReviewSignal
from app.schemas.travel import NormalizedHotel, ReviewBundle

ASPECTS: dict[str, tuple[str, ...]] = {
    "Location": ("location", "located", "close to", "nearby", "walking distance", "convenient", "near the"),
    "Cleanliness": ("clean", "spotless", "hygien", "dirty", "stain", "smell", "dust", "cockroach"),
    "Staff": ("staff", "service", "friendly", "helpful", "rude", "reception", "manager"),
    "Noise": ("noise", "noisy", "quiet", "loud", "honking", "soundproof", "peaceful"),
    "Check-in": ("check-in", "check in", "checkin", "front desk", "early check"),
    "Breakfast": ("breakfast", "buffet"),
    "Wi-Fi": ("wifi", "wi-fi", "internet"),
    "Room": ("room", "bed", "bathroom", "shower", "air condition", " ac "),
    "Value": ("value", "worth", "overpriced", "pricey", "affordable"),
}
KEY_ASPECTS = {"Cleanliness", "Noise", "Staff", "Check-in"}

_NEUTRALISE = ("no issue", "no problem", "not bad", "no complaint", "nothing to complain")
_NEGATIVE = ("dirty", "rude", "noisy", "loud", "slow", "delay", "waited", "waiting", "poor", "bad", "worst",
             "smell", "broken", "overpriced", "unhelpful", "disappoint", "issue", "problem", "terrible",
             "didn't", "did not", "wasn't", "was not", "too long", "honking", "stain", "cockroach", "not clean",
             "not working", "uncomfortable", "pricey")
_POSITIVE = ("great", "excellent", "good", "clean", "friendly", "helpful", "quiet", "comfortable", "convenient",
             "perfect", "amazing", "nice", "walking distance", "spotless", "quick", "smooth", "lovely", "peaceful",
             "recommend", "best", "affordable", "worth")
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass
class _Tally:
    positive: int = 0
    negative: int = 0
    quotes: list[tuple[str, str, float | None, str | None]] = field(default_factory=list)


def _sentiment(sentence: str, rating: float | None) -> str:
    text = f" {sentence.lower()} "
    for phrase in _NEUTRALISE:
        text = text.replace(phrase, " ")
    neg = sum(1 for cue in _NEGATIVE if cue in text)
    pos = sum(1 for cue in _POSITIVE if cue in text)
    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    if rating is not None:
        return "positive" if rating >= 4 else "negative" if rating <= 2 else "neutral"
    return "neutral"


def _trim(sentence: str, limit: int = 180) -> str:
    sentence = " ".join(sentence.split())
    if len(sentence) <= limit:
        return sentence
    cut = sentence[:limit].rsplit(" ", 1)[0]
    return f"{cut}…"


def build_insights(hotel: NormalizedHotel, bundle: ReviewBundle | None) -> ReviewInsights | None:
    tallies: dict[str, _Tally] = {name: _Tally() for name in ASPECTS}
    sources: list[str] = []
    review_count = 0

    if bundle and bundle.reviews:
        sources.append("google_maps_reviews")
        review_count = len(bundle.reviews)
        for review in bundle.reviews:
            for sentence in _SENTENCE.split(review.text):
                lowered = f" {sentence.lower()} "
                if len(sentence.strip()) < 12:
                    continue
                for aspect, cues in ASPECTS.items():
                    if any(cue in lowered for cue in cues):
                        mood = _sentiment(sentence, review.rating)
                        tally = tallies[aspect]
                        if mood == "positive":
                            tally.positive += 1
                        elif mood == "negative":
                            tally.negative += 1
                        if mood != "neutral":
                            tally.quotes.append((sentence.strip(), mood, review.rating, review.date))

    signals: dict[str, ReviewSignal] = {}
    for aspect, tally in tallies.items():
        if tally.positive or tally.negative:
            signals[aspect] = ReviewSignal(aspect=aspect, mentions=tally.positive + tally.negative,
                                           positive=tally.positive, negative=tally.negative,
                                           source="google_maps_reviews")

    if hotel.review_breakdown:
        sources.append("google_hotels")
        for item in hotel.review_breakdown:
            name = item.name.strip()
            total = item.positive + item.negative
            if total <= 0:
                continue
            existing = signals.get(name)
            if existing:  # merge counts from both sources
                existing.positive += item.positive
                existing.negative += item.negative
                existing.mentions += total
                existing.source = "google_hotels + google_maps_reviews"
            else:
                signals[name] = ReviewSignal(aspect=name, mentions=total, positive=item.positive,
                                             negative=item.negative, source="google_hotels")

    if not signals and not (bundle and bundle.topics):
        return None

    strengths = sorted((s for s in signals.values() if s.positive >= 2 and s.positive > s.negative),
                       key=lambda s: s.positive, reverse=True)[:5]
    concerns = sorted((s for s in signals.values()
                       if s.mentions >= 2 and (s.negative >= 2 or s.negative / s.mentions >= 0.25)),
                      key=lambda s: s.negative, reverse=True)[:4]

    quotes: list[ReviewQuote] = []
    for signal in strengths[:1]:
        for text, mood, rating, when in tallies.get(signal.aspect, _Tally()).quotes:
            if mood == "positive":
                quotes.append(ReviewQuote(text=_trim(text), rating=rating, date=when, aspect=signal.aspect,
                                          sentiment="positive"))
                break
    for signal in concerns[:2]:
        for text, mood, rating, when in tallies.get(signal.aspect, _Tally()).quotes:
            if mood == "negative":
                quotes.append(ReviewQuote(text=_trim(text), rating=rating, date=when, aspect=signal.aspect,
                                          sentiment="negative"))
                break

    return ReviewInsights(
        hotel_id=hotel.id,
        hotel_name=hotel.name,
        strengths=strengths,
        concerns=concerns,
        quotes=quotes,
        topics=[{"keyword": t.keyword, "mentions": t.mentions} for t in (bundle.topics if bundle else [])][:8],
        review_count=review_count,
        rating=hotel.rating,
        sources=sources,
    )


def key_aspect_warning(insights: ReviewInsights | None) -> str | None:
    """Used by the risk engine: a key aspect with >= 30% negative mentions."""
    if not insights:
        return None
    for concern in insights.concerns:
        if concern.aspect in KEY_ASPECTS and concern.mentions and concern.negative / concern.mentions >= 0.3:
            return concern.aspect
    return None
