from __future__ import annotations

from datetime import timedelta

from app.schemas.travel import NormalizedReview, ReviewAspect, ReviewBundle
from app.services.explanation import RuleExplainer, build_fact_sheet, explain_recommendation, fact_check
from app.services.review_insights import build_insights
from helpers import MISSION_DAY, build, context, evaluate, flight, hotel


def _scenario():
    ctx = context()
    best = build(ctx, flight("18:40", "20:50", day=MISSION_DAY - timedelta(days=1), price=4350), hotel())
    cheap = build(ctx, flight("05:30", "08:40", price=2000, stops=1, layover=45, number="6E 9"), hotel("Cheap", distance=4))
    evaluate(ctx, [best, cheap])
    from app.engines.mission_engine import MissionEngine
    from app.schemas.result import MissionSummary
    for i in (best, cheap):
        i.constraints = MissionEngine._constraints(ctx, i)
    summary = MissionSummary(origin=ctx.origin, destination=ctx.destination, venue=ctx.venue, mission_type="interview",
                             travel_date=MISSION_DAY, arrival_deadline="10:00", travelers=1, budget=10000,
                             currency="INR", min_buffer_minutes=60, max_ground_minutes=90, hotel_required=True,
                             min_hotel_rating=3.5, max_stops=1, preferences=[])
    return summary, best, {"recommended": best, "cheapest": cheap}


def test_rule_explanation_uses_only_engine_facts():
    summary, best, alts = _scenario()
    text = RuleExplainer().explain(summary, best, alts).text
    assert text.startswith("You spend ₹2,850 more than the cheapest option")
    assert "evening before" in text and "6E 100" in text and "of your budget" in text
    assert "1 hours" not in text


def test_fact_check_accepts_copied_numbers_and_rejects_invented_ones():
    summary, best, alts = _scenario()
    facts = build_fact_sheet(summary, best, alts)
    ok = f"Fly in the night before; you arrive by {facts['recommended']['arrive_at_venue']} with a 75 minutes buffer."
    assert fact_check(ok, facts) == []
    bad = "It costs ₹7,999 and lands at 19:05."
    assert set(fact_check(bad, facts)) == {"7999", "19:05"}


class _FakeAI:
    model = "fake-model"

    def __init__(self, text):
        self.text = text

    async def explain(self, facts):
        return self.text


async def test_ai_text_is_used_only_when_it_passes_the_fact_check(settings):
    summary, best, alts = _scenario()
    good = await explain_recommendation(settings, summary, best, alts,
                                        ai=_FakeAI("This journey keeps a 75 minutes buffer and stays within budget."))
    assert good.source == "ai" and good.model == "fake-model"
    invented = await explain_recommendation(settings, summary, best, alts, ai=_FakeAI("Only ₹1,234 and 12 km away!"))
    assert invented.source == "rules" and "fact check" in invented.note
    failed = await explain_recommendation(settings, summary, best, alts, ai=_FakeAI(None))
    assert failed.source == "rules" and "unavailable" in failed.note


def test_review_insights_extracts_signals_and_verbatim_quotes():
    h = hotel()
    h.review_breakdown = [ReviewAspect(name="Location", positive=400, negative=10, total=410)]
    bundle = ReviewBundle(reviews=[
        NormalizedReview(rating=5, text="Perfect location and very clean rooms. Staff were friendly."),
        NormalizedReview(rating=2, text="The room was noisy at night with constant honking."),
        NormalizedReview(rating=2, text="Noisy corridor and loud guests."),
        NormalizedReview(rating=4, text="Great location for the tech park."),
    ])
    insights = build_insights(h, bundle)
    assert insights.strengths[0].aspect == "Location"
    assert any(c.aspect == "Noise" for c in insights.concerns)
    texts = " ".join(r.text for r in bundle.reviews)
    for quote in insights.quotes:
        assert quote.text.rstrip("…") in texts  # verbatim, never generated
    assert set(insights.sources) == {"google_maps_reviews", "google_hotels"}


def test_review_insights_absent_without_data():
    h = hotel()
    h.review_breakdown = []
    assert build_insights(h, None) is None
