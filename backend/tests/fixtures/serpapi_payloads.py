"""Payloads shaped like real SerpApi responses (field names follow serpapi.com docs), plus a mock router
that serves them through httpx.MockTransport. Automated tests never call the real SerpApi."""

from __future__ import annotations

import json
import math
from datetime import date

import httpx

VENUE = (13.0475, 77.6205)
MAHAKAL = (23.1828, 75.7682)
CITY_COORDS = {"indore": (22.7196, 75.8577), "bangalore": (12.9716, 77.5946), "bengaluru": (12.9716, 77.5946)}
BLR = (13.1986, 77.7066)


def _seg(number, airline, frm, to, dep, arr, minutes, delayed=False):
    seg = {
        "departure_airport": {"name": f"{frm} Airport", "id": frm, "time": dep},
        "arrival_airport": {"name": f"{to} Airport", "id": to, "time": arr},
        "duration": minutes, "airplane": "Airbus A320neo", "airline": airline,
        "airline_logo": "https://www.gstatic.com/flights/airline_logos/70px/6E.png",
        "travel_class": "Economy", "flight_number": number, "legroom": "28 in",
        "extensions": ["Average legroom (28 in)", "Carbon emissions estimate: 92 kg"],
    }
    if delayed:
        seg["often_delayed_by_over_30_min"] = True
    return seg


def flights_payload(day: date, dep: str = "IDR", arr: str = "BLR") -> dict:
    d = day.isoformat()
    return {
        "search_metadata": {"status": "Success"},
        "best_flights": [
            {"flights": [_seg("6E 6312", "IndiGo", dep, arr, f"{d} 05:35", f"{d} 07:45", 130)],
             "total_duration": 130, "carbon_emissions": {"this_flight": 92000}, "price": 5480, "type": "One way",
             "airline_logo": "https://www.gstatic.com/flights/airline_logos/70px/6E.png", "booking_token": "tok-a"},
            {"flights": [_seg("6E 517", "IndiGo", dep, "HYD", f"{d} 05:10", f"{d} 06:30", 80),
                         _seg("6E 902", "IndiGo", "HYD", arr, f"{d} 07:25", f"{d} 08:35", 70)],
             "layovers": [{"duration": 55, "name": "Rajiv Gandhi International Airport", "id": "HYD"}],
             "total_duration": 205, "price": 3890, "type": "One way"},
        ],
        "other_flights": [
            {"flights": [_seg("QP 1381", "Akasa Air", dep, arr, f"{d} 06:05", f"{d} 08:10", 125, delayed=True)],
             "total_duration": 125, "price": 6250, "type": "One way"},
            {"flights": [_seg("6E 6311", "IndiGo", dep, arr, f"{d} 18:40", f"{d} 20:50", 130)],
             "total_duration": 130, "price": 4350, "type": "One way"},
            {"flights": [{"departure_airport": {"id": "IDR"}}], "price": 1},  # malformed — must be skipped
        ],
    }


def hotels_payload() -> dict:
    def prop(name, lat, lng, price, rating, reviews, token, breakdown=None, **extra):
        item = {
            "type": "hotel", "name": name, "description": "Business hotel",
            "gps_coordinates": {"latitude": lat, "longitude": lng},
            "check_in_time": "2:00 PM", "check_out_time": "12:00 PM",
            "rate_per_night": {"lowest": f"₹{price:,}", "extracted_lowest": price},
            "total_rate": {"lowest": f"₹{price:,}", "extracted_lowest": price},
            "hotel_class": "4-star hotel", "extracted_hotel_class": 4,
            "images": [{"thumbnail": f"https://example.test/{token}-t.jpg", "original_image": f"https://example.test/{token}.jpg"}],
            "overall_rating": rating, "reviews": reviews,
            "amenities": ["Free Wi-Fi", "Breakfast ($)", "Air conditioning"],
            "property_token": token, "link": f"https://example.test/{token}",
        }
        if breakdown:
            item["reviews_breakdown"] = [
                {"name": n, "description": n, "total_mentioned": p + q, "positive": p, "negative": q, "neutral": 0}
                for n, p, q in breakdown]
        item.update(extra)
        return item

    return {
        "properties": [
            prop("Lakeview Residency Hebbal", 13.0410, 77.6115, 3400, 4.3, 2180, "tok-lake",
                 [("Location", 412, 18), ("Cleanliness", 280, 41), ("Service", 305, 22)], free_cancellation=True),
            prop("Manyata Business Hotel", 13.0502, 77.6230, 4600, 4.0, 860, "tok-many",
                 [("Location", 210, 6), ("Noise", 10, 25)]),
            prop("Far Away Suites", 12.9000, 77.5000, 2500, 4.5, 3000, "tok-far"),
            prop("Budget Lodge", 13.0300, 77.6300, 1800, 3.2, 150, "tok-budget"),
            {"type": "vacation rental", "name": "No Price Flat",
             "gps_coordinates": {"latitude": 13.04, "longitude": 77.62}},
            {"type": "hotel", "description": "missing name — must be skipped"},
        ]
    }


def maps_search_payload(query: str) -> dict:
    q = query.lower()
    if "lakeview" in q:
        return {"place_results": {"title": "Lakeview Residency Hebbal", "data_id": "0x1:0xlake", "place_id": "P-lake",
                                  "gps_coordinates": {"latitude": 13.0411, "longitude": 77.6116},
                                  "address": "Outer Ring Road", "rating": 4.3, "reviews": 2180}}
    if "manyata business" in q:
        return {"local_results": [{"title": "Manyata Business Hotel", "data_id": "0x1:0xmany",
                                   "gps_coordinates": {"latitude": 13.0503, "longitude": 77.6231}}]}
    if "mahakal" in q:
        return {"place_results": {"title": "Shri Mahakaleshwar Jyotirlinga", "address": "Jaisinghpura, Ujjain 456006",
                                  "gps_coordinates": {"latitude": MAHAKAL[0], "longitude": MAHAKAL[1]},
                                  "data_id": "0x1:0xmahakal", "type": "Hindu temple"}}
    if "manyata" in q or "city centre" in q:
        return {"place_results": {"title": "Manyata Tech Park", "address": "Nagavara, Bengaluru 560045",
                                  "gps_coordinates": {"latitude": VENUE[0], "longitude": VENUE[1]},
                                  "data_id": "0x1:0xvenue", "place_id": "P-venue", "type": "Business park"}}
    return {"error": "Google hasn't returned any results for this query."}


def _haversine(a, b):
    r = 6371.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def directions_payload(start: str, end: str) -> dict:
    a = tuple(float(x) for x in start.split(","))
    b = tuple(float(x) for x in end.split(","))
    km = max(0.6, _haversine(a, b) * 1.3)
    minutes = max(6, round(km / (30 if km > 10 else 16) * 60))
    lo, hi = int(minutes * 0.85), int(minutes * 1.4)
    return {"directions": [
        {"travel_mode": "Driving", "via": "Outer Ring Road", "distance": int(km * 1000), "duration": minutes * 60,
         "formatted_distance": f"{km:.1f} km", "formatted_duration": f"{minutes} min",
         "typical_duration_range": f"{lo} min to {hi // 60} hr {hi % 60} min" if hi >= 60 else f"{lo}–{hi} min"},
        {"travel_mode": "Transit", "distance": int(km * 1100), "duration": minutes * 120},
    ]}


def local_payload(query: str) -> dict:
    return {"local_results": [
        {"position": 1, "title": f"{query.split(' near ')[0].title()} One", "rating": 4.5, "reviews": 1840,
         "type": "Coffee shop", "address": "Nagavara", "hours": "Open ⋅ Closes 10 PM", "place_id": "L1",
         "gps_coordinates": {"latitude": 13.0490, "longitude": 77.6190}},
        {"position": 2, "title": f"{query.split(' near ')[0].title()} Two", "rating": 4.1,
         "reviews_original": "(1.2K)", "type": "Cafe", "address": "Hebbal", "place_id": "L2"},
    ]}


def reviews_payload() -> dict:
    return {
        "place_info": {"title": "Lakeview Residency Hebbal", "rating": 4.3, "reviews": 2180},
        "topics": [{"keyword": "location", "mentions": 120, "id": "/m/1"}, {"keyword": "breakfast", "mentions": 44}],
        "reviews": [
            {"rating": 5, "date": "2 weeks ago", "snippet": "Perfect location for Manyata. The room was clean and quiet.",
             "user": {"name": "Asha"}},
            {"rating": 4, "date": "a month ago", "snippet": "Helpful staff and a good breakfast. Check-in was quick.",
             "user": {"name": "Ravi"}},
            {"rating": 2, "date": "2 months ago",
             "snippet": "The room facing the road was noisy at night with constant honking.", "user": {"name": "Neel"}},
            {"rating": 3, "date": "3 months ago", "extracted_snippet": {"original": "Noisy corridor late at night, otherwise fine."}},
            {"rating": 5, "date": "4 months ago", "snippet": "Great location and friendly staff, very convenient."},
        ],
    }


def transit_payload(params: dict | None = None) -> dict:
    """A real Google Maps transit response (via SerpApi) for Indore → Manyata Tech Park, trimmed. Requests that
    end near Ujjain get a short-trip payload in the same Google Maps transit shape."""
    from datetime import datetime, timedelta, timezone
    from pathlib import Path

    params = params or {}
    end = params.get("end_coords", "")
    if end and abs(float(end.split(",")[0]) - MAHAKAL[0]) < 0.3 and abs(float(end.split(",")[1]) - MAHAKAL[1]) < 0.3:
        from app.demo.ujjain import transit_payload as short_trip

        epoch = int(str(params.get("time", "")).removeprefix("arrive_by:"))
        arrive_by = datetime.fromtimestamp(epoch, timezone(timedelta(minutes=330))).replace(tzinfo=None)
        return short_trip(arrive_by, params.get("prefer"))
    return json.loads((Path(__file__).parent / "serpapi_transit_idr_blr.json").read_text(encoding="utf-8"))


class MockSerpApi:
    """Routes requests by `engine` and records every call. Optional per-engine overrides for failures."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.overrides: dict[str, httpx.Response | Exception] = {}
        # engine=google (transport-options answer box): None = an ordinary results page without the box
        self.transport_options: dict | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        self.calls.append(params)
        engine = params.get("engine")
        override = self.overrides.get(engine)
        if isinstance(override, Exception):
            raise override
        if isinstance(override, httpx.Response):
            return override
        if engine == "google_flights":
            body = flights_payload(date.fromisoformat(params["outbound_date"]), params.get("departure_id", "IDR"),
                                   params.get("arrival_id", "BLR"))
        elif engine == "google_hotels":
            body = hotels_payload()
        elif engine == "google_maps":
            body = maps_search_payload(params.get("q", ""))
        elif engine == "google_maps_directions" and params.get("travel_mode") == "3":
            body = transit_payload(params)
        elif (engine == "google_maps_directions" and "start_addr" in params
              and params["start_addr"].casefold() in CITY_COORDS and "end_coords" in params):
            start = CITY_COORDS[params["start_addr"].casefold()]
            body = directions_payload(f"{start[0]},{start[1]}", params["end_coords"])
        elif engine == "google_maps_directions" and "start_addr" in params:
            body = {"directions": [{"travel_mode": "Driving", "via": "NH 44", "distance": 1_410_000,
                                    "duration": 86_400, "formatted_distance": "1,410 km",
                                    "formatted_duration": "1 day", "typical_duration_range": "23 hr to 1 day 2 hr"}]}
        elif engine == "google_maps_directions":
            body = directions_payload(params["start_coords"], params["end_coords"])
        elif engine == "google_local":
            body = local_payload(params.get("q", ""))
        elif engine == "google_maps_reviews":
            body = reviews_payload()
        elif engine == "google":
            body = self.transport_options or {"search_metadata": {"status": "Success"},
                                              "organic_results": [{"position": 1, "title": "Timetable"}]}
        else:
            return httpx.Response(400, json={"error": f"Unsupported engine {engine}"})
        return httpx.Response(200, content=json.dumps(body), headers={"Content-Type": "application/json"})

    def count(self, engine: str) -> int:
        return sum(1 for c in self.calls if c.get("engine") == engine)
