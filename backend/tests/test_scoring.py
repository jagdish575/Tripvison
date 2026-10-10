"""Scoring engine — including the seven required behaviours from the brief."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.engines.scoring_engine import (ScoringConfig, ScoringEngine, arrival_curve, budget_curve, ground_curve,
                                        location_curve)
from helpers import MISSION_DAY, build, context, evaluate, flight, hotel, route


# ------------------------------------------------------------------ required behaviours
def test_cheap_but_late_itinerary_scores_poorly():
    ctx = context()
    late_cheap = build(ctx, flight("07:30", "09:20", price=2500), hotel())  # lands 09:20 → misses 10:00
    on_time = build(ctx, flight("05:30", "07:30", price=5500), hotel())
    evaluate(ctx, [late_cheap, on_time])
    assert late_cheap.arrival.buffer_minutes < 0
    assert late_cheap.scores.overall <= 25
    assert on_time.scores.overall > late_cheap.scores.overall + 30


def test_expensive_but_reliable_scores_well_but_does_not_automatically_win():
    ctx = context(budget=10000)
    reliable_expensive = build(ctx, flight("18:00", "20:10", day=MISSION_DAY - timedelta(days=1), price=8200),
                               hotel(price=3500))  # night before, ₹11.7k+ → over budget
    balanced = build(ctx, flight("18:30", "20:40", day=MISSION_DAY - timedelta(days=1), price=4200),
                     hotel(price=3000))
    evaluate(ctx, [reliable_expensive, balanced])
    assert reliable_expensive.scores.arrival >= 85
    assert reliable_expensive.scores.overall >= 60  # still a decent journey
    assert balanced.scores.overall > reliable_expensive.scores.overall


def test_over_budget_itinerary_is_penalised():
    ctx = context(budget=9000)
    within = build(ctx, flight("05:30", "07:30", price=4000), hotel(price=3000))
    over = build(ctx, flight("05:30", "07:30", price=7000, number="6E 200"), hotel(price=3000))
    evaluate(ctx, [within, over])
    assert over.cost.total > 9000 >= within.cost.total
    assert over.scores.budget < within.scores.budget - 40
    assert over.scores.overall < within.scores.overall


def test_very_small_buffer_creates_high_risk():
    ctx = context(hotel_required=False)
    tight = build(ctx, flight("06:30", "08:45"), a2v=route(45, 26))  # 08:45 + 25 + 45 → 09:55
    evaluate(ctx, [tight])
    assert tight.arrival.buffer_minutes == 5
    assert tight.risk.level == "HIGH"
    assert tight.risk.factors[0].key == "buffer"


def test_direct_flight_has_lower_connection_risk():
    ctx = context(hotel_required=False)
    direct = build(ctx, flight("05:00", "07:00"))
    connecting = build(ctx, flight("04:00", "07:00", stops=1, layover=50, number="6E 9"))
    evaluate(ctx, [direct, connecting])
    direct_conn = sum(f.points for f in direct.risk.factors if f.key in ("connection", "layover"))
    conn_conn = sum(f.points for f in connecting.risk.factors if f.key in ("connection", "layover"))
    assert direct_conn == 0 < conn_conn
    assert "Direct flight" in direct.risk.strengths
    assert direct.risk.score < connecting.risk.score


def test_far_hotel_reduces_location_score():
    ctx = context()
    near = build(ctx, flight("05:30", "07:30"), hotel("Near", distance=1.0))
    far = build(ctx, flight("05:30", "07:30"), hotel("Far", distance=14.0))
    evaluate(ctx, [near, far])
    assert near.scores.location > far.scores.location + 30  # distance (60%) + rating (40%)
    assert far.scores.location < 60
    assert any(f.key == "hotel_distance" and f.severity == "high" for f in far.risk.factors)


def test_missing_information_does_not_crash():
    ctx = context()
    sparse_hotel = hotel("Sparse", distance=None, rating=None, price=None, reviews=None, breakdown=[])
    sparse_hotel.review_breakdown = []
    itin = build(ctx, flight("05:30", "07:30", price=None), sparse_hotel, a2h=route(40, 25, estimated=True))
    evaluate(ctx, [itin])
    assert itin.cost.total is None
    assert 0 <= itin.scores.overall <= 100
    assert itin.scores.review == 35
    assert any(f.key == "missing_data" for f in itin.risk.factors)


# ------------------------------------------------------------------ curves
@pytest.mark.parametrize("cost,expected", [(5000, 100), (7000, 100), (10000, 80), (11000, 50), (14000, 0)])
def test_budget_curve(cost, expected):
    assert budget_curve(cost, 10000) == pytest.approx(expected, abs=0.01)


def test_arrival_curve_is_monotonic_then_gently_decays():
    values = [arrival_curve(b, 60) for b in (-10, 0, 30, 60, 150, 240)]
    assert values == sorted(values)
    assert arrival_curve(150, 60) == 100
    assert 85 <= arrival_curve(600, 60) < 100  # enormous buffers are not rewarded blindly


def test_ground_and_location_curves():
    assert ground_curve(30, 90) == 100
    assert ground_curve(90, 90) == pytest.approx(70)
    assert ground_curve(180, 90) == 0
    assert location_curve(1.0) == 100
    assert location_curve(None) is None
    assert location_curve(30) == 10


def test_weights_renormalise_without_hotel():
    ctx = context(hotel_required=False)
    itin = build(ctx, flight("05:00", "07:00"))
    evaluate(ctx, [itin])
    assert itin.scores.location is None and itin.scores.review is None
    assert sum(itin.scores.weights.values()) == pytest.approx(1.0, abs=0.01)
    assert set(itin.scores.weights) == {"arrival", "budget", "ground", "duration", "convenience"}


def test_priority_profiles_and_overrides():
    config = ScoringConfig.from_overrides({"arrival": 0.5})
    balanced = ScoringConfig().weights_for("balanced")
    assert balanced == {"arrival": 0.30, "budget": 0.20, "ground": 0.15, "location": 0.10, "duration": 0.10,
                        "review": 0.05, "convenience": 0.10}
    assert sum(balanced.values()) == pytest.approx(1.0)
    for profile in ("save_money", "save_time", "avoid_risk"):
        assert sum(ScoringConfig().weights_for(profile).values()) == pytest.approx(1.0)
    assert ScoringConfig().weights_for("save_money")["budget"] == 0.45
    assert ScoringConfig().weights_for("save_time")["duration"] == 0.40
    assert config.weights_for("balanced")["arrival"] == 0.5
    assert config.weights_for("unknown")["arrival"] == 0.5


def test_preferences_adjust_scores():
    plain = context()
    prefer = context(preferences=["avoid_early_departure", "free_cancellation"])
    h = hotel()
    h.free_cancellation = True
    a = build(plain, flight("05:00", "07:00"), h)
    b = build(prefer, flight("05:00", "07:00"), h)
    sa = ScoringEngine(plain).score(a)
    sb = ScoringEngine(prefer).score(b)
    assert sb.overall == sa.overall - 4 + 3
    assert any(f.key == "preference" for f in sb.factors)
