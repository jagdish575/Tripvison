"""Airport-less destinations, nearby-airport fallback, door-to-door journeys, venue-first routing,
bus/train discovery, optional-API degradation and user-safe messages."""

from __future__ import annotations

import asyncio
from datetime import time

import httpx
import pytest

from app.core.config import get_settings
from app.engines.mission_engine import MissionEngine
from app.schemas.travel import GeoPoint
from app.services.location_resolution import LocationResolutionService
from app.services.providers import SerpApiProvider
from app.services.route_intelligence import RouteIntelligenceService
from helpers import request

MAHAKAL = GeoPoint(lat=23.1828, lng=75.7682)
RAW_TERMS = ("serpapi", "http", "upstream", "took too long", "api key", "request id", "traceback", "exception")


def _engine(serp_client, settings):
    return MissionEngine(SerpApiProvider(serp_client, settings), settings)


def _ujjain(**overrides):
    base = dict(origin="Indore", destination="Ujjain", venue="Mahakal Mandir", mission_type="other",
                hotel_required=False, budget=10000)
    base.update(overrides)
    return request(**base)


# ------------------------------------------------------------------ location resolution
def test_city_without_airport_is_a_valid_location(settings):
    loc = LocationResolutionService(settings).resolve_offline("Ujjain")
    assert loc is not None and loc.city == "Ujjain"
    assert loc.has_airport is False and loc.code is None and loc.airports == []
    nearest = loc.nearby_airports[0]
    assert nearest.code == "IDR" and nearest.practical and 30 < nearest.distance_km < 70


@pytest.mark.parametrize("query,city,own", [
    ("Jaipur", "Jaipur", "JAI"), ("Delhi", "Delhi", "DEL"), ("Bangalore", "Bengaluru", "BLR"),
    ("Indore", "Indore", "IDR"), ("Mumbai", "Mumbai", "BOM"), ("BLR", "Bengaluru", "BLR"),
    ("Mathura", "Mathura", None), ("Ujjain, Madhya Pradesh", "Ujjain", None), ("Dewas", "Dewas", None),
])
def test_resolution_for_cities_and_towns(settings, query, city, own):
    loc = LocationResolutionService(settings).resolve_offline(query)
    assert loc is not None and loc.city == city and loc.code == own
    assert loc.has_airport is (own is not None)


async def test_unknown_small_town_is_geocoded_live(serp_client, settings):
    """Places outside the reference list are resolved with live geocoding, not rejected."""
    loc = await LocationResolutionService(settings, SerpApiProvider(serp_client, settings)).resolve(
        "Mahakal Mandir", field="destination")
    assert loc.source == "geocoded" and abs(loc.location.lat - MAHAKAL.lat) < 0.01
    assert loc.nearby_airports and loc.nearby_airports[0].code == "IDR"


# ------------------------------------------------------------------ route intelligence (pure)
def _plan(origin, destination, modes=("flight", "train", "bus", "ground"), settings=None, venue=None):
    s = settings or get_settings()
    svc = LocationResolutionService(s)
    o, d = svc.resolve_offline(origin), svc.resolve_offline(destination)
    return RouteIntelligenceService(s).plan(o, d, venue or d.location, list(modes))


def test_short_trip_skips_flights_and_explains_why():
    plan = _plan("Indore", "Ujjain", venue=MAHAKAL)
    assert plan.flight == "skipped" and "only about" in plan.flight_reason
    assert plan.modes_evaluated == ["train", "bus", "ground"]
    kinds = [n.kind for n in plan.notices]
    assert kinds[:2] == ["airport_fallback", "short_distance"]
    assert "Ujjain doesn't have a commercial airport" in plan.notices[0].message
    assert "Indore Airport (IDR)" in plan.notices[0].message
    assert plan.destination_airport.code == "IDR" and plan.destination_has_airport is False


def test_flight_only_request_still_gets_a_complete_answer():
    plan = _plan("Indore", "Ujjain", modes=["flight"], venue=MAHAKAL)
    assert plan.flight == "skipped" and {"train", "bus", "ground"} <= set(plan.modes_evaluated)
    assert any(n.kind == "modes_added" for n in plan.notices)


def test_long_trip_to_airportless_city_uses_nearby_airport(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "low_practicality_airport_transfer_minutes", 60)
    plan = _plan("Bangalore", "Ujjain", settings=s, venue=MAHAKAL)
    assert plan.flight == "searched" and plan.origin_airport.code == "BLR" and plan.destination_airport.code == "IDR"
    assert ("We found Indore Airport (IDR) as the nearest practical airport and added the road transfer"
            in plan.notices[0].message)
    assert 60 < plan.destination_airport.transfer_minutes <= 120
    assert plan.flight_practicality == "low"  # transfer above the (configured) LOW threshold
    assert any(n.kind == "low_practicality" for n in plan.notices)


def test_airport_transfer_threshold_is_configurable(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "max_practical_airport_transfer_minutes", 45)
    plan = _plan("Bangalore", "Ujjain", settings=s, venue=MAHAKAL)
    assert plan.flight == "skipped" and plan.destination_airport is None
    assert any(n.kind == "no_airport" for n in plan.notices)
    monkeypatch.setattr(s, "max_practical_airport_transfer_minutes", 180)
    monkeypatch.setattr(s, "low_practicality_airport_transfer_minutes", 150)
    assert _plan("Bangalore", "Ujjain", settings=s, venue=MAHAKAL).flight_practicality == "high"


def test_impractical_road_is_not_searched():
    plan = _plan("Indore", "Bangalore")
    assert plan.ground_search is False and "too long" in plan.ground_reason
    assert plan.flight == "searched" and plan.flight_practicality == "high"


# ------------------------------------------------------------------ the Indore → Ujjain → Mahakal Mandir mission
async def test_indore_to_ujjain_mahakal_mandir_end_to_end(serp_client, mock_serpapi, settings):
    result = await _engine(serp_client, settings).run("ujjain", _ujjain())
    # resolved destination, no airport validation error
    assert result.mission.destination.city == "Ujjain" and not result.mission.destination.has_airport
    assert result.mission.venue.resolved and result.mission.venue.name == "Mahakal Mandir"
    # flight evaluated as impractical — and no flight search wasted on it
    assert result.route.flight == "skipped" and mock_serpapi.count("google_flights") == 0
    assert result.route.destination_airport.code == "IDR"
    # train, bus and road all compared
    modes = {m.mode: m for m in result.modes}
    assert modes["train"].available and modes["bus"].available and modes["ground"].available
    assert not modes["flight"].available and "only about" in modes["flight"].reason
    # dedicated bus- and train-preferred transit searches
    prefers = {c.get("prefer") for c in mock_serpapi.calls if c.get("travel_mode") == "3"}
    assert prefers == {"bus", "train"}
    # hubs discovered from live transit data
    assert "Ujjain Junction" in result.route.railway_stations
    # comparison + recommendation
    assert result.status == "complete" and result.categories["recommended"]
    rec = next(i for i in result.itineraries if i.id == result.categories["recommended"])
    assert rec.mode in ("train", "bus", "ground") and rec.scores.overall > 0 and rec.risk is not None
    # venue-first: every journey ends at Mahakal Mandir, with door-to-door cost and budget
    for itin in result.itineraries:
        arrive = next(e for e in itin.timeline if e.kind == "arrive")
        assert arrive.title == "Arrive at Mahakal Mandir"
        assert itin.cost.total is not None and itin.cost.budget_remaining == 10000 - itin.cost.total
        assert itin.arrival.buffer_minutes >= 0
    bus = next(i for i in result.itineraries if i.mode == "bus")
    assert bus.main.fare_label == "Estimated fare" and bus.cost.ticket_source == "estimated"
    assert "Estimated bus/transit route" in bus.main.note and "confirmed ticket" in bus.main.note.lower()
    train = next(i for i in result.itineraries if i.mode == "train")
    assert "Not a booking" in train.main.note
    ground = next(i for i in result.itineraries if i.mode == "ground")
    assert ground.main.distance_km < 120  # live route Indore → Mahakal Mandir, not a city-centre guess


async def test_flight_plus_ground_transfer_to_airportless_city(serp_client, mock_serpapi, settings, monkeypatch):
    monkeypatch.setattr(settings, "low_practicality_airport_transfer_minutes", 60)
    result = await _engine(serp_client, settings).run(
        "fg", request(origin="Bangalore", destination="Ujjain", venue="Mahakal Mandir", mission_type="other",
                      arrival_deadline=time(15, 0), budget=40000, modes=["flight"], hotel_required=False,
                      allow_previous_day=False))
    assert mock_serpapi.count("google_flights") >= 1
    flights = [c for c in mock_serpapi.calls if c.get("engine") == "google_flights"]
    assert {(c["departure_id"], c["arrival_id"]) for c in flights} == {("BLR", "IDR")}
    assert result.mission.destination_airport.code == "IDR"
    itin = next(i for i in result.itineraries if i.mode == "flight")
    assert itin.main.note.startswith("Flight + ground transfer")
    assert itin.practicality == "low"
    transfer = next(l for l in itin.legs if l.from_kind == "airport")
    assert transfer.distance_km > 40  # Indore Airport → Mahakal Mandir / hotel in Ujjain
    # door to door: home → airport → check-in → flight → transfer → venue
    assert itin.legs[0].from_kind == "origin" and itin.timeline[0].title.startswith("Leave Bengaluru")
    assert itin.total_travel_minutes > itin.flight.duration_minutes + settings.airport_checkin_minutes
    assert itin.door_to_venue_minutes >= itin.total_travel_minutes - 1


async def test_flight_total_cost_includes_every_leg(serp_client, settings):
    result = await _engine(serp_client, settings).run("cost", request())
    itin = next(i for i in result.itineraries if i.mode == "flight")
    keys = {i.key for i in itin.cost.items}
    assert {"ticket", "ground", "hotel", "food"} <= keys
    assert itin.cost.ground == round(sum(l.cost for l in itin.legs))
    assert itin.cost.total == sum(i.amount for i in itin.cost.items)


# ------------------------------------------------------------------ degradation & messages
async def test_optional_api_timeout_does_not_block_the_mission(serp_client, settings, monkeypatch):
    monkeypatch.setattr(settings, "optional_timeout_seconds", 0.05)
    provider = SerpApiProvider(serp_client, settings)

    async def slow_places(*args, **kwargs):
        await asyncio.sleep(5)

    monkeypatch.setattr(provider, "search_places", slow_places)
    result = await MissionEngine(provider, settings).run("slow", request())
    assert result.status in ("complete", "partial") and result.places == []
    assert "Some local recommendations are temporarily unavailable." in result.warnings


async def test_partial_failure_keeps_the_journey_and_hides_raw_errors(serp_client, mock_serpapi, settings):
    mock_serpapi.overrides["google_local"] = httpx.Response(500)
    mock_serpapi.overrides["google_maps_reviews"] = httpx.Response(504)
    result = await _engine(serp_client, settings).run("partial", request())
    assert result.categories.get("recommended")
    assert result.warnings, "the user should be told something is missing"
    for warning in result.warnings:
        assert not any(term in warning.lower() for term in RAW_TERMS), warning
    assert result.diagnostics["degraded"]  # developers can still see what happened


async def test_failed_flight_search_message_is_user_safe(serp_client, mock_serpapi, settings):
    mock_serpapi.overrides["google_flights"] = httpx.Response(401, json={"error": "Invalid API key."})
    result = await _engine(serp_client, settings).run("auth", request())
    flight = next(m for m in result.modes if m.mode == "flight")
    assert not any(term in (flight.reason or "").lower() for term in RAW_TERMS)
    assert all("SERPAPI_API_KEY" not in w for w in result.warnings)
