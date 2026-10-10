from __future__ import annotations

from datetime import datetime, time, timedelta

from app.engines.risk_engine import RiskEngine
from helpers import MISSION_DAY, build, context, evaluate, flight, hotel, route


# ------------------------------------------------------------------ itinerary
def test_same_day_with_hotel_timeline_and_buffer():
    ctx = context()
    itin = build(ctx, flight("05:35", "07:45"), hotel(), a2h=route(45, 26), h2v=route(8, 1.5))
    # 07:45 land → +25 exit → 08:10 → +45 → 08:55 hotel → +15 → 09:10 → +8 → 09:18
    assert itin.arrival.venue_arrival == datetime.combine(MISSION_DAY, time(9, 18))
    assert itin.arrival.buffer_minutes == 42
    kinds = [e.kind for e in itin.timeline]
    assert kinds == ["depart", "transfer", "board", "land", "exit", "hotel", "leave", "arrive", "deadline"]
    assert itin.hotel_check_in == MISSION_DAY and itin.hotel_check_out == MISSION_DAY + timedelta(days=1)


def test_night_before_plans_departure_from_hotel():
    ctx = context(min_buffer_minutes=60)
    itin = build(ctx, flight("18:40", "20:50", day=MISSION_DAY - timedelta(days=1)), hotel(), h2v=route(10, 1.6))
    assert itin.strategy == "night_before"
    assert itin.arrival.buffer_minutes == 75  # required 60 + 15 planned margin
    assert itin.arrival.leave_hotel_at == datetime.combine(MISSION_DAY, time(8, 35))
    assert itin.ground_minutes_mission_day == 10
    assert itin.door_to_venue_minutes > 12 * 60


def test_cost_aggregation_counts_cabs_for_groups():
    ctx = context(travelers=5)
    itin = build(ctx, flight("05:35", "07:45", price=20000), hotel(price=6000), a2h=route(45, 20), h2v=route(8, 2))
    # taxi = (100 + 18 * km) * 2 cabs — home → airport (door to door) + airport → hotel + hotel → venue
    access = itin.legs[0]
    assert (access.from_kind, access.to_kind) == ("origin", "airport") and access.estimated
    assert access.cost == round((100 + 18 * access.distance_km) * 2)
    assert itin.cost.ground == access.cost + (100 + 18 * 20) * 2 + (100 + 18 * 2) * 2
    assert itin.cost.food == 500 * 1 * 5  # ₹500/day × 1 day × 5 travellers
    assert itin.cost.total == 20000 + 6000 + itin.cost.ground + itin.cost.food
    assert itin.cost.budget_remaining == itin.cost.budget - itin.cost.total
    assert {i.key: i.source for i in itin.cost.items} == {"ticket": "live", "ground": "estimated", "hotel": "live",
                                                         "food": "estimated"}


def test_flight_landing_after_mission_day_is_rejected():
    from app.engines.itinerary_engine import ItineraryEngine
    ctx = context()
    f = flight("10:00", "12:00", day=MISSION_DAY + timedelta(days=1))
    assert ItineraryEngine(ctx).build(f, hotel=None, airport_to_venue=route(40, 25)) is None


# ------------------------------------------------------------------ risk
def test_buffer_thresholds():
    ctx = context(hotel_required=False, min_buffer_minutes=60)
    ok = build(ctx, flight("05:00", "07:00", number="A1"), a2v=route(45, 26))      # buffer 110
    medium = build(ctx, flight("06:30", "08:00", number="A2"), a2v=route(45, 26))  # buffer 50
    late = build(ctx, flight("08:00", "09:30", number="A3"), a2v=route(45, 26))    # buffer -40
    evaluate(ctx, [ok, medium, late])
    assert ok.risk.level == "LOW"
    assert medium.risk.level == "MEDIUM"
    assert late.risk.level == "HIGH" and late.risk.factors[0].points == 60


def test_delay_flag_is_cushioned_by_night_before():
    ctx = context()
    same = build(ctx, flight("05:00", "07:00", delayed=True), hotel())
    before = build(ctx, flight("18:00", "20:00", day=MISSION_DAY - timedelta(days=1), delayed=True), hotel())
    evaluate(ctx, [same, before])
    sev = {i.strategy: next(f.severity for f in i.risk.factors if f.key == "delays") for i in (same, before)}
    assert sev == {"same_day": "medium", "night_before": "low"}


def test_ground_and_budget_risks():
    ctx = context(max_ground_minutes=60, budget=6000)
    itin = build(ctx, flight("04:00", "06:00", price=6000), hotel(distance=12), a2h=route(70, 40), h2v=route(40, 15))
    evaluate(ctx, [itin])
    keys = {f.key: f.severity for f in itin.risk.factors}
    assert keys["ground"] == "high"
    assert keys["hotel_distance"] == "high"
    assert keys["budget"] == "high"
    assert itin.risk.level == "HIGH"


def test_risk_with_review_signal():
    from app.schemas.result import ReviewInsights, ReviewSignal
    ctx = context()
    itin = build(ctx, flight("18:00", "20:00", day=MISSION_DAY - timedelta(days=1)), hotel())
    insights = ReviewInsights(hotel_id="x", hotel_name="x", strengths=[], quotes=[], review_count=5, sources=[],
                              concerns=[ReviewSignal(aspect="Noise", mentions=4, positive=1, negative=3, source="t")])
    risk = RiskEngine(ctx).assess(itin, insights)
    assert any(f.key == "review_signal" for f in risk.factors)
