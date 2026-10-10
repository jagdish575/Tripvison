"""Google Search transport-options answer box (SerpApi engine=google): parsing, conservative matching to
Google Maps transit options, and labelling. A reported fare replaces an estimate only on a clear match."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import httpx

from app.demo import ujjain
from app.demo.provider import DemoProvider
from app.engines.mission_engine import MissionEngine, attach_reported_fares, match_reported_route
from app.integrations.serpapi.client import CallTracker
from app.integrations.serpapi.maps import parse_transit
from app.integrations.serpapi.transport import build_params, parse_money, parse_transport_options
from app.schemas.travel import ReportedTransportRoute
from app.services.providers import SerpApiProvider
from helpers import MISSION_DAY, request

# Same shape as SerpApi's documented example (serpapi.com/direct-answer-box-api — "Transport Options Answer Box")
BOSTON_NEWARK = {"answer_box": {
    "type": "transport_options", "title": "Trains from Boston to Newark", "from": "South Station",
    "to": "Newark - Penn Station", "climate_friendly": True,
    "routes": [
        {"time": "5:05 AM – 9:13 AM", "duration": "4h 8m", "fare": "$217", "changes": "0 changes",
         "itinerary": [{"service_by": "Amtrak", "transport_number": "Acela 2151", "departure_location": "South Station",
                        "arrival_location": "Newark - Penn Station", "departure_time": "5:05 AM",
                        "arrival_time": "9:13 AM", "duration": "4h 8m"}],
         "tickets_details": [{"url": "https://www.amtrak.com/", "company": "Amtrak.com", "price": "$217"}]},
        {"time": "6:00 AM – 10:19 AM", "duration": "4h 19m", "fare": "Price unavailable", "changes": "1 change",
         "itinerary": [{"service_by": "Amtrak", "transport_number": "Northeast Regional 171",
                        "departure_time": "6:00 AM", "arrival_time": "9:52 AM"},
                       {"mode": "Change", "duration": "12m"},
                       {"service_by": "NJ Transit Rail", "transport_number": "3829",
                        "departure_time": "10:04 AM", "arrival_time": "10:19 AM"}],
         "tickets_details": [{"url": "https://www.amtrak.com/", "company": "Amtrak.com"},
                             {"url": "https://www.njtransit.com/", "company": "NJ Transit Rail"}]},
    ]}}

IDR_BLR = json.loads((Path(__file__).parent / "fixtures" / "serpapi_transit_idr_blr.json").read_text(encoding="utf-8"))


def test_parses_documented_transport_options_answer_box():
    first, second = parse_transport_options(BOSTON_NEWARK)
    assert first.mode == "train" and first.depart_clock == (5, 5) and first.arrive_clock == (9, 13)
    assert first.duration_minutes == 248 and first.changes == 0
    assert (first.fare, first.currency) == (217.0, "USD") and first.numbers == ["2151"]
    assert first.operators == ["Amtrak"] and first.sellers == ["Amtrak.com"]
    # "Price unavailable" and unpriced sellers → no fare; the transfer entry isn't a service
    assert second.fare is None and second.changes == 1 and second.numbers == ["3829"]
    assert second.operators == ["Amtrak", "NJ Transit Rail"]


def test_pages_without_the_box_and_alternative_layouts():
    assert parse_transport_options({"organic_results": []}) == []
    assert parse_transport_options({"_empty": True}) == []
    alt = {"direct_answer_box": [{"type": "transport_options", "title": "Buses from Indore to Ujjain", "routes": [
        {"time": "7:10 AM - 9:00 AM", "duration": "1 hr 50 min",
         "tickets_details": [{"company": "Operator A", "price": "₹220"}, {"company": "Operator B", "price": "₹180"}]}]}]}
    [route] = parse_transport_options(alt)
    assert route.mode == "bus" and route.depart_clock == (7, 10) and route.duration_minutes == 110
    assert (route.fare, route.currency) == (180.0, "INR")  # cheapest seller price when the route has no fare


def test_money_parsing_never_guesses_a_currency():
    assert parse_money("₹1,245") == (1245.0, "INR")
    assert parse_money("From Rs. 185") == (185.0, "INR")
    assert parse_money("$217") == (217.0, "USD")
    assert parse_money("Price unavailable") is None
    assert parse_money(185) is None


def test_query_names_the_mode_route_and_date():
    params = build_params("bus", "Indore", "Ujjain", datetime(2026, 10, 12).date())
    assert params["q"] == "buses from Indore to Ujjain on 12 October 2026" and params["gl"] == "in"


def test_matching_by_service_numbers_requires_the_same_trains():
    options = parse_transit(IDR_BLR, datetime(2026, 10, 10, 8, 45))
    first = options[0]  # 12919 → 12622 → 20607 (+ city bus, which isn't matched)
    same = ReportedTransportRoute(mode="train", fare=2450, currency="INR", numbers=["12919", "12622", "20607"])
    other = ReportedTransportRoute(mode="train", fare=1900, currency="INR", numbers=["12919"],
                                   depart_clock=(first.segments[1].depart_at.hour, first.segments[1].depart_at.minute))
    assert match_reported_route(first, [other]) is None  # numbers present but different → never a time match
    assert match_reported_route(first, [other, same]) is same


def test_fares_attach_only_in_the_mission_currency():
    options = parse_transit(IDR_BLR, datetime(2026, 10, 10, 8, 45))
    route = ReportedTransportRoute(mode="train", fare=2450, currency="USD", numbers=["12919", "12622", "20607"])
    assert attach_reported_fares(options, [route], "INR") == 0 and options[0].fare is None
    route.currency = "INR"
    # options 0 and 1 ride the same three trains (only the last city bus differs); option 2 uses other trains
    assert attach_reported_fares(options, [route], "INR") == 2
    assert options[0].fare == 2450 and options[0].fare_source == "google_search_transport_options"
    assert options[1].fare == 2450 and options[2].fare is None


def _ujjain_train_departure() -> tuple[int, int]:
    arrive_by = datetime.combine(MISSION_DAY, datetime.min.time()).replace(hour=9)  # 10:00 deadline − 60 min buffer
    trip = ujjain.transit_payload(arrive_by, "train")["directions"][0]["trips"][1]
    hh, mm = trip["start_stop"]["time"].split()[0].split(":")
    hour = int(hh) % 12 + (12 if trip["start_stop"]["time"].endswith("PM") else 0)
    return hour, int(mm)


async def test_indore_ujjain_train_gets_the_reported_fare_and_bus_stays_estimated(serp_client, mock_serpapi, settings):
    hour, minute = _ujjain_train_departure()
    clock = f"{(hour - 1) % 12 + 1}:{minute:02d} {'AM' if hour < 12 else 'PM'}"
    mock_serpapi.transport_options = {"answer_box": {"type": "transport_options", "title": "Trains from Indore to Ujjain",
        "routes": [{"time": f"{clock} – later", "duration": "1h 10m", "fare": "₹185", "changes": "0 changes",
                    "itinerary": [{"service_by": "Indian Railways", "departure_time": clock}],
                    "tickets_details": [{"company": "IRCTC", "price": "₹185"}]}]}}
    result = await MissionEngine(SerpApiProvider(serp_client, settings), settings).run(
        "fares", request(origin="Indore", destination="Ujjain", venue="Mahakal Mandir", mission_type="other",
                         hotel_required=False))
    searches = [c["q"] for c in mock_serpapi.calls if c.get("engine") == "google"]
    assert any(q.startswith("trains from Indore to Ujjain") for q in searches)
    assert any(q.startswith("buses from Indore to Ujjain") for q in searches)
    train = next(i for i in result.itineraries if i.mode == "train")
    assert train.cost.ticket_source == "live" and train.main.fare_label == "Fare"
    assert train.cost.ticket >= 185 and "Google Search" in train.main.data_source
    ticket = next(i for i in train.cost.items if i.key == "ticket")
    assert "IRCTC" in ticket.detail and "before booking" in ticket.detail
    # the answer box was about trains — the bus keeps its clearly-labelled estimate
    bus = next(i for i in result.itineraries if i.mode == "bus")
    assert bus.cost.ticket_source == "estimated" and bus.main.fare_label == "Estimated fare"
    assert result.funnel.fares_matched == 1
    assert any("fares where Google Search shows them" in m.detail for m in result.methodology)


async def test_fare_lookup_failure_is_silent_and_keeps_estimates(serp_client, mock_serpapi, settings):
    mock_serpapi.overrides["google"] = httpx.Response(500)
    result = await MissionEngine(SerpApiProvider(serp_client, settings), settings).run(
        "nofares", request(origin="Indore", destination="Ujjain", venue="Mahakal Mandir", mission_type="other",
                           hotel_required=False))
    assert result.categories.get("recommended")
    train = next(i for i in result.itineraries if i.mode == "train")
    assert train.cost.ticket_source == "estimated"
    assert not any("fare" in w.lower() for w in result.warnings)  # optional enrichment: no user-facing alarm


async def test_demo_provider_never_supplies_search_fares():
    assert await DemoProvider().transport_options("train", "Indore", "Ujjain", MISSION_DAY, tracker=CallTracker()) == []
