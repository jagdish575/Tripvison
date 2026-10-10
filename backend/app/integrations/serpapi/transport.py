"""Google Search "transport options" answer box (SerpApi engine=google) — train/bus schedules with fares.

For queries like "train from Indore to Ujjain", Google Search can show a transport-options box and SerpApi
returns it as `answer_box` with `type: "transport_options"` (serpapi.com/direct-answer-box-api, added
July 2026). Each route has `time`, `duration`, `fare`, `changes`, an `itinerary` of segments (`service_by`,
`transport_number`, `departure_time`, …; transfers are `{"mode": "Change"}`) and `tickets_details`
(`company`, `url`, optional `price`).

It is NOT a booking/inventory API: no seat availability, no stations' coordinates, and some routes say
"Price unavailable". TripMission uses it only to replace an *estimated* fare with the fare Google shows,
when a route clearly matches a Google Maps transit option (see MissionEngine._attach_reported_fares).
The box only appears for some routes, so an empty result is normal.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.integrations.serpapi.client import SerpApiMalformedResponse
from app.schemas.travel import ReportedTransportRoute
from app.utils.time import parse_duration_text

ENGINE = "google"
TTL_SECONDS = 6 * 3600

_CLOCK = re.compile(r"(\d{1,2}):(\d{2})\s*([AaPp]\.?[Mm]\.?)?")
_NUMBER = re.compile(r"\b(\d{4,5})\b")  # train numbers (India: 5 digits; elsewhere often 4)
_MONEY = re.compile(r"(₹|Rs\.?|INR|US\$|\$|€|EUR|£|GBP)\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*(₹|INR|EUR|€|£|GBP|USD)")
_SYMBOLS = {"₹": "INR", "rs": "INR", "rs.": "INR", "inr": "INR", "$": "USD", "us$": "USD", "usd": "USD",
            "€": "EUR", "eur": "EUR", "£": "GBP", "gbp": "GBP"}
_WORD = {"train": "trains", "bus": "buses"}


def build_params(mode: str, origin: str, destination: str, travel_date: date | None, *, gl: str = "in",
                 hl: str = "en") -> dict[str, Any]:
    q = f"{_WORD.get(mode, mode)} from {origin} to {destination}"
    if travel_date is not None:
        q += f" on {travel_date.day} {travel_date:%B %Y}"
    return {"q": q, "gl": gl, "hl": hl}


def _clock(text: Any) -> tuple[int, int] | None:
    if not isinstance(text, str):
        return None
    match = _CLOCK.search(text.replace(" ", " "))
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    meridiem = (match.group(3) or "").lower().replace(".", "")
    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    return (hour, minute) if hour < 24 and minute < 60 else None


def _clocks(text: Any) -> list[tuple[int, int]]:
    if not isinstance(text, str):
        return []
    found = []
    for part in re.split(r"[–—-]", text.replace(" ", " ")):
        c = _clock(part)
        if c:
            found.append(c)
    return found


def parse_money(text: Any) -> tuple[float, str] | None:
    """'₹1,245' -> (1245.0, 'INR'); '$217' -> (217.0, 'USD'); 'Price unavailable' -> None."""
    if isinstance(text, (int, float)):
        return None  # a bare number has no currency — we never guess one
    if not isinstance(text, str):
        return None
    match = _MONEY.search(text)
    if not match:
        return None
    symbol = (match.group(1) or match.group(4) or "").casefold()
    amount = match.group(2) or match.group(3)
    currency = _SYMBOLS.get(symbol)
    try:
        value = float(amount.replace(",", ""))
    except (TypeError, ValueError):
        return None
    return (value, currency) if currency and value > 0 else None


def _mode_from(text: str) -> str | None:
    t = text.casefold()
    if "bus" in t or "coach" in t:
        return "bus"
    if "train" in t or "rail" in t:
        return "train"
    return None


def _boxes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for key in ("answer_box", "direct_answer_box"):
        raw = payload.get(key)
        for box in raw if isinstance(raw, list) else [raw]:
            if isinstance(box, dict) and box.get("type") == "transport_options":
                out.append(box)
    return out


def parse_transport_options(payload: Any) -> list[ReportedTransportRoute]:
    if not isinstance(payload, dict):
        raise SerpApiMalformedResponse("search payload is not an object", engine=ENGINE)
    if payload.get("_empty"):
        return []
    routes: list[ReportedTransportRoute] = []
    for box in _boxes(payload):
        box_mode = _mode_from(str(box.get("title") or ""))
        for raw in box.get("routes") or []:
            if not isinstance(raw, dict):
                continue
            segments = [s for s in raw.get("itinerary") or [] if isinstance(s, dict)
                        and str(s.get("mode", "")).casefold() != "change"]
            times = _clocks(raw.get("time"))
            depart = times[0] if times else _clock(segments[0].get("departure_time")) if segments else None
            arrive = times[-1] if len(times) > 1 else _clock(segments[-1].get("arrival_time")) if segments else None
            numbers: list[str] = []
            operators: list[str] = []
            seg_mode = None
            for seg in segments:
                numbers += _NUMBER.findall(str(seg.get("transport_number") or ""))
                if isinstance(seg.get("service_by"), str) and seg["service_by"].strip():
                    operators.append(seg["service_by"].strip())
                seg_mode = seg_mode or _mode_from(f"{seg.get('icon') or ''} {seg.get('mode') or ''}")
            tickets = [t for t in raw.get("tickets_details") or [] if isinstance(t, dict)]
            fare = parse_money(raw.get("fare"))
            if fare is None:  # some layouts only price the ticket sellers — take the cheapest
                priced = [m for m in (parse_money(t.get("price")) for t in tickets) if m]
                currencies = {c for _, c in priced}
                fare = min(priced) if priced and len(currencies) == 1 else None
            changes_match = re.search(r"\d+", str(raw.get("changes") or ""))
            routes.append(ReportedTransportRoute(
                mode=box_mode or seg_mode, depart_clock=depart, arrive_clock=arrive,
                duration_minutes=parse_duration_text(raw.get("duration")),
                changes=int(changes_match.group()) if changes_match else None,
                fare=fare[0] if fare else None, currency=fare[1] if fare else None,
                numbers=list(dict.fromkeys(numbers)), operators=list(dict.fromkeys(operators)),
                sellers=list(dict.fromkeys(str(t["company"]).strip() for t in tickets
                                           if isinstance(t.get("company"), str) and t["company"].strip()))))
    return routes
