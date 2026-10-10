"""Multi-modal engine: normalization, total trip cost, categories, priorities and the required cases."""

from __future__ import annotations

import json
from datetime import datetime, time, timedelta
from pathlib import Path

import pytest

from app.engines.itinerary_engine import ItineraryEngine
from app.engines.mission_engine import MissionEngine
from app.engines.scoring_engine import ScoringEngine
from app.engines.risk_engine import RiskEngine
from app.integrations.serpapi.maps import parse_transit
from app.schemas.travel import NormalizedRoute, NormalizedTransit, TransitSegment
from helpers import MISSION_DAY, build, context, flight, hotel, route

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "serpapi_transit_idr_blr.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ normalization
def test_train_normalization_from_real_google_maps_transit_response():
    options = parse_transit(FIXTURE, datetime(2026, 10, 10, 8, 45))
    assert len(options) == 3 and all(o.mode == "train" for o in options)
    first = options[0]
    assert first.title == "Malwa SF Express → Tamil Nadu Express → Mysuru Vande Bharat Express"
    assert first.provider == "Indian Railways"
    # clock-only times are anchored to the requested arrival: 9:38 PM the day before, 1 day 9 h earlier
    assert first.arrival_time == datetime(2026, 10, 9, 21, 38)
    assert first.departure_time == datetime(2026, 10, 8, 12, 15)
    trains = [s for s in first.segments if s.mode == "train"]
    assert [s.name for s in trains][0] == "12919 Malwa SF Express"
    assert trains[1].depart_at == datetime(2026, 10, 8, 18, 20) and trains[1].arrive_at == datetime(2026, 10, 9, 16, 45)
    city_bus = [s for s in first.segments if s.mode == "bus"]
    assert city_bus and city_bus[0].operator == "Bengaluru Metropolitan Transport Corporation"
    assert first.transfers == 3 and first.fare is None  # Google Maps returns no fare for these services


def test_bus_normalization_and_empty_results():
    payload = {"directions": [{"travel_mode": "Transit", "start_time": "2:00 PM", "end_time": "6:42 PM",
                               "duration": 103320, "distance": 1468000, "trips": [
        {"travel_mode": "Transit", "title": "Indore → Bengaluru AC sleeper", "duration": 99600,
         "start_stop": {"name": "Indore", "time": "2:00 PM"}, "end_stop": {"name": "Hebbal", "time": "5:40 PM"},
         "icon": "https://maps.gstatic.com/mapfiles/transit/iw2/svg/bus2.svg",
         "service_run_by": {"name": "Sleeper Co"}},
        {"travel_mode": "Walking", "title": "Walk", "duration": 600}]}]}
    [bus] = parse_transit(payload, datetime(2026, 10, 10, 8, 45))
    assert bus.mode == "bus" and bus.provider == "Sleeper Co" and bus.transfers == 0
    assert bus.arrival_time == datetime(2026, 10, 9, 18, 42)
    assert parse_transit({"_empty": True}, datetime(2026, 10, 10, 8, 45)) == []
    assert parse_transit({"directions": [{"travel_mode": "Driving"}]}, datetime(2026, 10, 10, 8, 45)) == []


# ------------------------------------------------------------------ helpers
def _transit(ctx, *, hours: float, arrive: datetime, fare: float | None = None, mode: str = "train") -> NormalizedTransit:
    minutes = int(hours * 60)
    depart = arrive - timedelta(minutes=minutes)
    seg = TransitSegment(mode=mode, name="12345 Test Express", operator="Indian Railways", from_stop="Indore Jn",
                         to_stop="Bengaluru", depart_at=depart, arrive_at=arrive, duration_minutes=minutes)
    return NormalizedTransit(id=f"t-{mode}{hours}", mode=mode, title="Test Express", provider="Indian Railways",
                             departure_time=depart, arrival_time=arrive, duration_minutes=minutes, distance_km=1700,
                             segments=[seg], long_distance_minutes=minutes, fare=fare)


def _score(ctx, itins):
    fastest = min(i.total_travel_minutes for i in itins)
    cheapest = min(i.cost.total for i in itins if i.cost.total is not None)
    for i in itins:
        i.scores = ScoringEngine(ctx).score(i, fastest, cheapest)
        i.risk = RiskEngine(ctx).assess(i)
        i.constraints = MissionEngine._constraints(ctx, i)
    return itins


# ------------------------------------------------------------------ total cost
def test_total_trip_cost_items_sources_and_budget_remaining():
    ctx = context(budget=10000, food_per_day=600)
    train = ItineraryEngine(ctx).build_transit(
        _transit(ctx, hours=16, arrive=datetime.combine(MISSION_DAY - timedelta(days=1), time(18, 0))),
        hotel=hotel(price=1500), hotel_to_venue=route(10, 2))
    sources = {i.key: i.source for i in train.cost.items}
    assert sources == {"ticket": "estimated", "ground": "estimated", "hotel": "live", "food": "user_provided"}
    assert train.cost.ticket == round(1.25 * 1700)
    assert train.cost.total == sum(i.amount for i in train.cost.items)
    assert train.cost.budget_remaining == 10000 - train.cost.total
    assert train.confidence == "medium" and train.main.schedule_source == "live"


def test_hotel_nights_multiply_and_no_hotel_when_not_required():
    ctx = context(stay_nights=2)
    itin = build(ctx, flight("18:00", "20:00", day=MISSION_DAY - timedelta(days=1)), hotel(price=1500))
    itin_hotel = next(i for i in itin.cost.items if i.key == "hotel")
    assert itin.cost.hotel_nights == 2 and itin_hotel.detail == "₹1,500/night × 2"
    no_hotel = context(hotel_required=False)
    same_day = build(no_hotel, flight("05:00", "07:00"))
    assert same_day.hotel is None and same_day.cost.hotel is None
    assert all(i.key != "hotel" for i in same_day.cost.items)


def test_over_budget_is_negative_remaining():
    ctx = context(budget=5000)
    itin = build(ctx, flight("05:00", "07:00", price=6000), hotel(price=1000))
    assert itin.cost.budget_remaining < 0


# ------------------------------------------------------------------ required cases
def test_case1_train_cheaper_flight_faster():
    ctx = context(budget=20000, hotel_required=False, allow_previous_day=True)
    eng = ItineraryEngine(ctx)
    fl = build(ctx, flight("00:30", "08:30", price=8000), a2v=route(30, 20))  # 8 h flight
    tr = eng.build_transit(_transit(ctx, hours=16, arrive=datetime.combine(MISSION_DAY, time(8, 30)), fare=4000),
                           hotel=None)
    itins = _score(ctx, [fl, tr])
    cats = MissionEngine._categorise(itins)
    assert cats["cheapest"] == tr.id
    assert cats["fastest"] == fl.id
    assert tr.cost.ticket_source == "live" and fl.cost.total > tr.cost.total


def test_case2_late_arrival_is_rejected():
    ctx = context(hotel_required=False)
    late = build(ctx, flight("08:00", "09:40", price=2000), a2v=route(40, 25))
    ok = build(ctx, flight("05:00", "07:00", price=6000, number="6E 2"), a2v=route(40, 25))
    itins = _score(ctx, [late, ok])
    assert not late.constraints.feasible and late.scores.overall <= 25
    feasible = [i for i in itins if i.constraints.feasible]
    assert MissionEngine._categorise(feasible)["recommended"] == ok.id
    assert MissionEngine._categorise(feasible)["cheapest"] == ok.id  # the cheaper late option is not "cheapest"


def test_case3_over_budget_strongly_penalised():
    ctx = context(budget=8000, hotel_required=False)
    within = build(ctx, flight("05:00", "07:00", price=5000), a2v=route(40, 25))
    over = build(ctx, flight("05:00", "07:00", price=9500, number="6E 9"), a2v=route(40, 25))
    _score(ctx, [within, over])
    assert over.scores.budget < 50 <= within.scores.budget
    assert over.scores.overall < within.scores.overall - 8


async def test_case4_no_option_offers_relaxations_with_unlocks(serp_client, settings):
    from helpers import request
    engine = MissionEngine(__import__("app.services.providers", fromlist=["SerpApiProvider"]).SerpApiProvider(serp_client, settings), settings)
    result = await engine.run("m", request(budget=3000))
    assert result.status == "partial"
    budget = next(s for s in result.suggestions if s.kind == "increase_budget")
    assert budget.title.startswith("Increase budget by ₹") and budget.unlocks.endswith("becomes available")
    assert budget.patch["budget"] > 3000


def test_best_value_and_priority_change_the_recommendation():
    def scenario(priority: str):
        ctx = context(budget=20000, hotel_required=False, priority=priority)
        eng = ItineraryEngine(ctx)
        fl = build(ctx, flight("05:00", "07:00", price=9000), a2v=route(40, 25))
        tr = eng.build_transit(_transit(ctx, hours=14, arrive=datetime.combine(MISSION_DAY, time(7, 30)), fare=2000),
                               hotel=None)
        itins = _score(ctx, [fl, tr])
        return MissionEngine._categorise(itins), fl, tr

    cats, fl, tr = scenario("save_money")
    assert cats["recommended"] == tr.id
    cats, fl, tr = scenario("save_time")
    assert cats["recommended"] == fl.id
    assert "best_value" in cats and fl.scores.value > 0 and tr.scores.value > 0


def test_ground_option_and_tradeoff_sentence():
    ctx = context(hotel_required=False)
    drive = ItineraryEngine(ctx).build_ground(
        NormalizedRoute(origin_label="Indore", destination_label="Venue", distance_km=600, duration_minutes=600,
                        typical_max_minutes=660), hotel=None)
    assert drive.mode == "ground" and drive.cost.ticket_source == "estimated"
    assert drive.arrival.buffer_minutes == 75 and drive.main.departure_time == drive.arrival.venue_arrival - timedelta(minutes=660)
    fl = build(ctx, flight("05:00", "07:00", price=9000), a2v=route(40, 25))
    _score(ctx, [fl, drive])
    by_id = {fl.id: fl, drive.id: drive}
    trade = MissionEngine._tradeoff(by_id, {"cheapest": drive.id, "fastest": fl.id}, ctx)
    assert trade and trade.sentence.startswith("Spend ₹") and "flight instead of road trip" in trade.sentence
    assert trade.extra_cost == fl.cost.total - drive.cost.total


def test_mission_templates_endpoint(api):
    templates = {t["mission_type"]: t for t in api.get("/api/v1/templates").json()["templates"]}
    assert templates["interview"]["min_buffer_minutes"] == 60 and templates["interview"]["priority"] == "avoid_risk"
    assert templates["exam"]["min_buffer_minutes"] == 120 and templates["exam"]["risk_tolerance"] == "very low"
    assert templates["vacation"]["priority"] == "balanced"


def test_accessibility_never_guesses():
    ctx = context(accessibility=["wheelchair", "elevator"])
    itin = build(ctx, flight("18:00", "20:00", day=MISSION_DAY - timedelta(days=1)), hotel())
    statuses = {n.need: n.status for n in itin.accessibility}
    assert statuses["Accessible hotel"] == "unavailable" and statuses["Elevator"] == "unavailable"
    assert all(any(w in n.detail.lower() for w in ("unavailable", "confirm")) for n in itin.accessibility)
    h = hotel()
    h.amenities = ["Wheelchair accessible", "Elevator"]
    itin2 = build(ctx, flight("18:00", "20:00", day=MISSION_DAY - timedelta(days=1)), h)
    assert {n.need: n.status for n in itin2.accessibility}["Accessible hotel"] == "available"


@pytest.mark.parametrize("modes", [["flight"], ["train", "bus"]])
async def test_mode_filter(serp_client, settings, mock_serpapi, modes):
    from app.services.providers import SerpApiProvider
    from helpers import request
    result = await MissionEngine(SerpApiProvider(serp_client, settings), settings).run("m", request(modes=modes))
    assert {i.mode for i in result.itineraries} <= set(modes) | {"transit"}
    assert (mock_serpapi.count("google_flights") > 0) == ("flight" in modes)
