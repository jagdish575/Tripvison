from __future__ import annotations

from datetime import date

import pytest

from app.integrations.serpapi import flights, hotels, local, maps, reviews
from app.integrations.serpapi.client import SerpApiMalformedResponse
from app.utils.time import parse_duration_range_max, parse_duration_text
from fixtures.serpapi_payloads import (directions_payload, flights_payload, hotels_payload, local_payload,
                                       maps_search_payload, reviews_payload)

DAY = date(2026, 10, 9)


def test_flight_normalization():
    result = flights.parse_flights(flights_payload(DAY))
    assert len(result) == 4  # malformed item skipped
    direct = next(f for f in result if f.flight_numbers == ["6E 6312"])
    assert direct.stops == 0 and direct.price == 5480 and direct.duration_minutes == 130
    assert direct.departure_time.isoformat() == "2026-10-09T05:35:00"
    conn = next(f for f in result if f.stops == 1)
    assert conn.flight_numbers == ["6E 517", "6E 902"] and conn.min_layover_minutes == 55
    assert conn.layovers[0].airport == "HYD" and conn.arrival_airport == "BLR"
    assert next(f for f in result if f.flight_numbers == ["QP 1381"]).often_delayed is True


def test_flight_params_map_stops():
    p = flights.build_params("IDR", "BLR", DAY, adults=2, max_stops=0)
    assert p["stops"] == 1 and p["type"] == 2 and p["adults"] == 2 and p["outbound_date"] == "2026-10-09"


def test_flight_empty_and_malformed():
    assert flights.parse_flights({"_empty": True}) == []
    assert flights.parse_flights({"best_flights": "nope"}) == []
    with pytest.raises(SerpApiMalformedResponse):
        flights.parse_flights(["not", "a", "dict"])


def test_hotel_normalization():
    result = hotels.parse_hotels(hotels_payload())
    names = [h.name for h in result]
    assert "Lakeview Residency Hebbal" in names and len(result) == 5  # nameless skipped
    lake = result[0]
    assert lake.price_per_night == 3400 and lake.rating == 4.3 and lake.reviews == 2180
    assert lake.location.lat == pytest.approx(13.041) and lake.free_cancellation is True
    assert lake.image.endswith("tok-lake.jpg") and lake.hotel_class == 4
    assert {a.name for a in lake.review_breakdown} == {"Location", "Cleanliness", "Service"}
    flat = next(h for h in result if h.name == "No Price Flat")
    assert flat.price_per_night is None and flat.rating is None


def test_hotel_rating_param():
    assert hotels.build_params("q", DAY, DAY, min_rating=4.2)["rating"] == 8
    assert hotels.build_params("q", DAY, DAY, min_rating=3.0)["rating"] is None


def test_geocode_and_directions():
    places = maps.parse_search(maps_search_payload("Manyata Tech Park, Bengaluru"))
    assert places[0].name == "Manyata Tech Park" and places[0].location.lat == pytest.approx(13.0475)
    assert maps.parse_search({"_empty": True}) == []
    route = maps.parse_directions(directions_payload("13.1986,77.7066", "13.0475,77.6205"), "A", "B")
    assert route.mode == "Driving" and route.distance_km > 15 and route.duration_minutes > 30
    assert route.typical_max_minutes and route.typical_max_minutes >= route.duration_minutes
    assert maps.parse_directions({"directions": []}, "A", "B") is None
    params = maps.build_directions_params(maps.GeoPoint(lat=1, lng=2), "Somewhere")
    assert params["travel_mode"] == 0 and params["start_coords"].startswith("1.0") and params["end_addr"] == "Somewhere"


def test_local_and_reviews():
    places = local.parse_places(local_payload("cafe near Manyata"), "cafe")
    assert len(places) == 2 and places[1].reviews == 1200 and places[1].location is None
    rv, topics, info = reviews.parse_reviews(reviews_payload())
    assert len(rv) == 5 and rv[3].text.startswith("Noisy corridor")
    assert topics[0].keyword == "location" and info["title"] == "Lakeview Residency Hebbal"


@pytest.mark.parametrize("text,expected", [("45 min", 45), ("1 hr 5 min", 65), ("2 h", 120), ("", None),
                                           ("1 day 2 hr", 1560)])
def test_duration_text(text, expected):
    assert parse_duration_text(text) == expected


@pytest.mark.parametrize("text,expected", [("35 min to 1 hr 5 min", 65), ("40–55 min", 55), ("1–2 hr", 120)])
def test_duration_range(text, expected):
    assert parse_duration_range_max(text) == expected
