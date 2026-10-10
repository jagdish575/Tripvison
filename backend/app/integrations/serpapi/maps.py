"""Google Maps search (geocoding) and Google Maps Directions: request builders + normalizers."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta
from typing import Any

from app.integrations.serpapi.client import SerpApiMalformedResponse
from app.schemas.travel import GeoPoint, NormalizedPlace, NormalizedRoute, NormalizedTransit, TransitSegment
from app.utils.time import parse_duration_range_max, parse_duration_text

SEARCH_ENGINE = "google_maps"
DIRECTIONS_ENGINE = "google_maps_directions"
GEOCODE_TTL_SECONDS = 7 * 24 * 3600
DIRECTIONS_TTL_SECONDS = 24 * 3600


# ---------------------------------------------------------------- geocoding
def build_search_params(query: str, *, near: GeoPoint | None = None, hl: str = "en", gl: str = "in") -> dict[str, Any]:
    params: dict[str, Any] = {"q": query, "type": "search", "hl": hl, "gl": gl}
    if near is not None:
        params["ll"] = f"@{near.lat:.5f},{near.lng:.5f},14z"
    return params


def _place(raw: dict[str, Any], category: str | None = None) -> NormalizedPlace | None:
    name = raw.get("title")
    gps = raw.get("gps_coordinates") or {}
    if not name:
        return None
    location = None
    if isinstance(gps.get("latitude"), (int, float)) and isinstance(gps.get("longitude"), (int, float)):
        location = GeoPoint(lat=float(gps["latitude"]), lng=float(gps["longitude"]))
    ident = raw.get("place_id") or raw.get("data_id") or hashlib.sha1(str(name).encode()).hexdigest()[:12]
    reviews = raw.get("reviews")
    rating = raw.get("rating")
    return NormalizedPlace(
        id=f"p-{ident}"[:120],
        name=str(name),
        category=category or (raw.get("type") if isinstance(raw.get("type"), str) else None),
        rating=float(rating) if isinstance(rating, (int, float)) else None,
        reviews=int(reviews) if isinstance(reviews, (int, float)) else None,
        address=raw.get("address") if isinstance(raw.get("address"), str) else None,
        location=location,
        hours=raw.get("hours") if isinstance(raw.get("hours"), str) else raw.get("open_state"),
        thumbnail=raw.get("thumbnail"),
        price=raw.get("price") if isinstance(raw.get("price"), str) else None,
        data_id=raw.get("data_id"),
        place_id=raw.get("place_id"),
        source="google_maps",
    )


def parse_search(payload: Any) -> list[NormalizedPlace]:
    """Returns place_results (exact match) first, then local_results."""
    if not isinstance(payload, dict):
        raise SerpApiMalformedResponse("maps payload is not an object", engine=SEARCH_ENGINE)
    if payload.get("_empty"):
        return []
    places: list[NormalizedPlace] = []
    exact = payload.get("place_results")
    if isinstance(exact, dict):
        place = _place(exact)
        if place:
            places.append(place)
    local = payload.get("local_results")
    if isinstance(local, list):
        for raw in local:
            if isinstance(raw, dict):
                place = _place(raw)
                if place:
                    places.append(place)
    return places


# ---------------------------------------------------------------- directions
# SerpApi travel_mode (per serpapi.com/google-maps-directions-api):
# 6 best (default), 0 driving, 9 two-wheeler, 3 transit, 2 walking, 1 cycling, 4 flight
_TRAVEL_MODE = {"best": 6, "driving": 0, "two_wheeler": 9, "transit": 3, "walking": 2, "cycling": 1}
_KM = re.compile(r"([\d.,]+)\s*km", re.IGNORECASE)
_M = re.compile(r"([\d.,]+)\s*m\b", re.IGNORECASE)
_MI = re.compile(r"([\d.,]+)\s*mi", re.IGNORECASE)


def build_directions_params(start: GeoPoint | str, end: GeoPoint | str, *, mode: str = "driving",
                            hl: str = "en", gl: str = "in") -> dict[str, Any]:
    params: dict[str, Any] = {"travel_mode": _TRAVEL_MODE.get(mode, 6), "distance_unit": 0, "hl": hl, "gl": gl}
    if isinstance(start, GeoPoint):
        params["start_coords"] = start.as_param()
    else:
        params["start_addr"] = start
    if isinstance(end, GeoPoint):
        params["end_coords"] = end.as_param()
    else:
        params["end_addr"] = end
    return params


def _distance_km(raw: dict[str, Any]) -> float | None:
    meters = raw.get("distance")
    if isinstance(meters, (int, float)) and meters > 0:
        return round(meters / 1000.0, 1)
    text = raw.get("formatted_distance")
    if isinstance(text, str):
        for pattern, factor in ((_KM, 1.0), (_MI, 1.609), (_M, 0.001)):
            match = pattern.search(text)
            if match:
                return round(float(match.group(1).replace(",", "")) * factor, 1)
    return None


def _duration_minutes(raw: dict[str, Any]) -> int | None:
    seconds = raw.get("duration")
    if isinstance(seconds, (int, float)) and seconds > 0:
        return max(1, int(round(seconds / 60)))
    return parse_duration_text(raw.get("formatted_duration"))


def parse_directions(payload: Any, origin_label: str, destination_label: str) -> NormalizedRoute | None:
    if not isinstance(payload, dict):
        raise SerpApiMalformedResponse("directions payload is not an object", engine=DIRECTIONS_ENGINE)
    if payload.get("_empty"):
        return None
    options = payload.get("directions")
    if not isinstance(options, list):
        return None
    candidates = []
    for raw in options:
        if not isinstance(raw, dict):
            continue
        km, minutes = _distance_km(raw), _duration_minutes(raw)
        if km is None or minutes is None:
            continue
        candidates.append((raw, km, minutes))
    if not candidates:
        return None
    # Prefer a driving option (taxi), else the fastest option returned
    driving = [c for c in candidates if str(c[0].get("travel_mode", "")).lower() in ("driving", "car", "drive")]
    raw, km, minutes = (driving or sorted(candidates, key=lambda c: c[2]))[0]
    typical = parse_duration_range_max(raw.get("typical_duration_range"))
    return NormalizedRoute(
        origin_label=origin_label,
        destination_label=destination_label,
        distance_km=km,
        duration_minutes=minutes,
        typical_max_minutes=typical if typical and typical >= minutes else None,
        mode=str(raw.get("travel_mode") or "Driving"),
        via=raw.get("via") if isinstance(raw.get("via"), str) else None,
        estimated=False,
    )


# ---------------------------------------------------------------- transit (train / bus / metro)
TRANSIT_TTL_SECONDS = 6 * 3600
LONG_DISTANCE_MINUTES = 90
SHORT_INTERCITY_MINUTES = 35
_CLOCK = re.compile(r"(\d{1,2}):(\d{2})\s*([AaPp][Mm])?")
_SERVICE = re.compile(r"^\s*(\d{4,5})\s*-\s*(.+?)(?:\s+\d{4,5}\b.*)?$")


TRANSIT_PREFER = {"bus", "train", "subway", "tram_light_rail"}  # SerpApi `prefer` (transit only)


def build_transit_params(start: GeoPoint | str, end: GeoPoint | str, *, arrive_by_epoch: int | None,
                         wheelchair: bool = False, prefer: str | None = None, hl: str = "en",
                         gl: str = "in") -> dict[str, Any]:
    params = build_directions_params(start, end, mode="transit", hl=hl, gl=gl)
    if arrive_by_epoch is not None:
        params["time"] = f"arrive_by:{arrive_by_epoch}"
    if wheelchair:
        params["route"] = 4  # SerpApi: wheelchair-accessible routing (transit only)
    if prefer in TRANSIT_PREFER:
        params["prefer"] = prefer  # SerpApi: preferred transit vehicle — used for dedicated bus / train searches
    return params


def _clock(text: Any) -> tuple[int, int] | None:
    if not isinstance(text, str):
        return None
    match = _CLOCK.search(text.replace(" ", " "))
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    meridiem = (match.group(3) or "").lower()
    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    return hour, minute


def _at_or_after(cursor: datetime, clock: tuple[int, int]) -> datetime:
    candidate = cursor.replace(hour=clock[0], minute=clock[1], second=0, microsecond=0)
    if candidate < cursor - timedelta(minutes=1):
        candidate += timedelta(days=1)
    return candidate


def _segment_mode(trip: dict[str, Any]) -> str:
    if str(trip.get("travel_mode", "")).lower() == "walking":
        return "walk"
    icon = str(trip.get("icon", "")).lower()
    operator = str((trip.get("service_run_by") or {}).get("name", "")).lower()
    if "rail" in icon or "train" in icon or "railway" in operator:
        return "train"
    if "bus" in icon:
        return "bus"
    if "subway" in icon or "metro" in icon or "tram" in icon:
        return "metro"
    if "ferry" in icon:
        return "ferry"
    return "other"


def _service_name(title: str) -> tuple[str | None, str]:
    match = _SERVICE.match(title or "")
    if match:
        return match.group(1), match.group(2).strip()
    return None, (title or "Service").strip()


def parse_transit(payload: Any, arrive_by: datetime, currency: str = "INR") -> list[NormalizedTransit]:
    """`arrive_by` is the naive local datetime that was requested; Google returns clock times only, so
    absolute datetimes are reconstructed from it and the reported durations."""
    if not isinstance(payload, dict):
        raise SerpApiMalformedResponse("transit payload is not an object", engine=DIRECTIONS_ENGINE)
    if payload.get("_empty"):
        return []
    options: list[NormalizedTransit] = []
    for raw in payload.get("directions") or []:
        if not isinstance(raw, dict) or str(raw.get("travel_mode", "")).lower() != "transit":
            continue
        end_clock = _clock(raw.get("end_time"))
        seconds = raw.get("duration")
        trips = [t for t in raw.get("trips") or [] if isinstance(t, dict)]
        if not end_clock or not isinstance(seconds, (int, float)) or not trips:
            continue
        end = arrive_by.replace(hour=end_clock[0], minute=end_clock[1], second=0, microsecond=0)
        if end > arrive_by + timedelta(minutes=1):
            end -= timedelta(days=1)
        start = end - timedelta(minutes=int(round(seconds / 60)))

        segments: list[TransitSegment] = []
        cursor = start
        for trip in trips:
            mode = _segment_mode(trip)
            minutes = max(1, int(round((trip.get("duration") or 0) / 60)))
            if mode == "walk":
                distance = trip.get("distance")
                segments.append(TransitSegment(
                    mode="walk", name="Walk", duration_minutes=minutes, depart_at=cursor,
                    arrive_at=cursor + timedelta(minutes=minutes),
                    distance_km=round(distance / 1000, 1) if isinstance(distance, (int, float)) else None))
                cursor += timedelta(minutes=minutes)
                continue
            start_stop = trip.get("start_stop") or {}
            end_stop = trip.get("end_stop") or {}
            dep_clock, arr_clock = _clock(start_stop.get("time")), _clock(end_stop.get("time"))
            depart = _at_or_after(cursor, dep_clock) if dep_clock else cursor
            arrive = _at_or_after(depart, arr_clock) if arr_clock else depart + timedelta(minutes=minutes)
            number, name = _service_name(str(trip.get("title") or ""))
            operator = (trip.get("service_run_by") or {}).get("name")
            segments.append(TransitSegment(
                mode=mode, name=f"{number} {name}" if number else name, operator=operator,
                from_stop=start_stop.get("name"), to_stop=end_stop.get("name"), depart_at=depart, arrive_at=arrive,
                duration_minutes=max(minutes, int((arrive - depart).total_seconds() // 60)),
                stops_count=len(trip.get("stops") or [])))
            cursor = arrive

        services = [s for s in segments if s.mode != "walk"]
        if not services:
            continue
        long_haul = [s for s in services if s.duration_minutes >= LONG_DISTANCE_MINUTES]
        if not long_haul:
            # Short intercity trips (e.g. a 70-minute train between neighbouring cities): the longest
            # train/bus segment defines the journey if it is clearly more than a city hop.
            longest = max(services, key=lambda s: s.duration_minutes)
            if longest.mode in ("train", "bus") and longest.duration_minutes >= SHORT_INTERCITY_MINUTES:
                long_haul = [longest]
        if any(s.mode == "train" for s in long_haul):
            mode = "train"
        elif any(s.mode == "bus" for s in long_haul):
            mode = "bus"
        else:
            mode = "transit"
        main = long_haul or services
        title = " → ".join(_service_name(s.name.replace(" ", " - ", 1))[1] if s.name[:1].isdigit() else s.name
                           for s in main)
        operators = list(dict.fromkeys(s.operator for s in main if s.operator))
        fare = raw.get("cost") if isinstance(raw.get("cost"), (int, float)) else None
        distance = raw.get("distance")
        ident = hashlib.sha1(f"{'|'.join(s.name for s in services)}|{start.isoformat()}".encode()).hexdigest()[:12]
        options.append(NormalizedTransit(
            id=f"t-{ident}", mode=mode, title=title, provider=", ".join(operators) or None,
            departure_time=start, arrival_time=end, duration_minutes=int(round(seconds / 60)),
            distance_km=round(distance / 1000, 1) if isinstance(distance, (int, float)) else None,
            transfers=max(0, len(services) - 1),
            walking_minutes=sum(s.duration_minutes for s in segments if s.mode == "walk"),
            long_distance_minutes=sum(s.duration_minutes for s in long_haul),
            segments=segments, fare=float(fare) if fare is not None else None,
            currency=raw.get("currency") if fare is not None else None,
            fare_source="google_maps" if fare is not None else None))
    return options
