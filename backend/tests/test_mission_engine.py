"""End-to-end engine runs: live provider over mocked SerpApi HTTP, and the demo provider."""

from __future__ import annotations

from datetime import time

import httpx
import pytest

from app.core.errors import ValidationAppError
from app.demo.provider import DemoProvider
from app.engines.mission_engine import MissionEngine
from app.integrations.serpapi.client import SerpApiRateLimitError
from app.services.providers import SerpApiProvider
from helpers import request


def _engine(serp_client, settings):
    return MissionEngine(SerpApiProvider(serp_client, settings), settings)


async def test_live_pipeline_with_mocked_serpapi(serp_client, mock_serpapi, settings):
    engine = _engine(serp_client, settings)
    result = await engine.run("m1", request())
    assert result.mode == "live"
    assert result.status in ("complete", "partial")
    assert set(result.categories) == {"recommended", "cheapest", "fastest", "safest", "best_value"}
    assert {m.mode for m in result.modes} >= {"flight", "train"}
    assert next(m for m in result.modes if m.mode == "train").available
    ground = next(m for m in result.modes if m.mode == "ground")
    assert not ground.available and "too long" in ground.reason
    rec = next(i for i in result.itineraries if i.id == result.categories["recommended"])
    assert rec.constraints.feasible and rec.scores.overall > 0 and rec.risk is not None
    assert rec.hotel is not None and rec.hotel.name != "Far Away Suites"
    assert result.mission.venue.resolved and result.mission.venue.name == "Manyata Tech Park"
    # funnel: only shortlisted hotels get directions, reviews for ≤ 2 hotels, ≤ 3 place categories
    assert mock_serpapi.count("google_flights") == 2
    assert mock_serpapi.count("google_hotels") == 2
    assert mock_serpapi.count("google_maps_directions") <= 2 * settings.max_hotels_for_directions + 2  # + transit, road
    assert mock_serpapi.count("google_maps_reviews") <= settings.max_review_hotels
    assert mock_serpapi.count("google_local") == 3
    assert result.review_insights and result.places and result.explanation.source == "rules"
    assert result.data_sources.live_calls == len(mock_serpapi.calls)
    # every displayed journey must arrive on time when any feasible journey exists
    assert all(i.arrival.buffer_minutes >= 0 for i in result.itineraries)


async def test_second_run_is_served_from_cache(serp_client, mock_serpapi, settings):
    await _engine(serp_client, settings).run("m1", request())
    first = len(mock_serpapi.calls)
    result = await _engine(serp_client, settings).run("m2", request())
    assert len(mock_serpapi.calls) == first
    assert result.data_sources.live_calls == 0 and result.data_sources.cache_hits > 0


async def test_no_flights(serp_client, mock_serpapi, settings):
    mock_serpapi.overrides["google_flights"] = httpx.Response(200, json={"error": "Google hasn't returned any results for this query."})
    result = await _engine(serp_client, settings).run("m", request(modes=["flight"]))
    assert result.status == "no_options"
    assert result.itineraries == [] and result.categories == {}
    assert result.suggestions and result.suggestions[0].kind == "no_flights"


async def test_impossible_deadline_suggests_alternatives(serp_client, settings):
    result = await _engine(serp_client, settings).run(
        "m", request(arrival_deadline=time(7, 0), allow_previous_day=False))
    assert result.status == "no_options"
    kinds = {s.kind for s in result.suggestions}
    assert "previous_day" in kinds and "later_deadline" in kinds


async def test_budget_too_low_gives_partial_with_budget_suggestion(serp_client, settings):
    result = await _engine(serp_client, settings).run("m", request(budget=3000))
    assert result.status == "partial"
    suggestion = next(s for s in result.suggestions if s.kind == "increase_budget")
    assert suggestion.patch["budget"] > 3000


async def test_optional_stage_failures_do_not_fail_mission(serp_client, mock_serpapi, settings):
    mock_serpapi.overrides["google_local"] = httpx.Response(500)
    mock_serpapi.overrides["google_maps_reviews"] = httpx.Response(500)
    mock_serpapi.overrides["google_maps_directions"] = httpx.Response(500)
    result = await _engine(serp_client, settings).run("m", request())
    assert result.status in ("complete", "partial")
    assert result.places == []
    assert any("estimated" in w.lower() for w in result.warnings)
    rec = next(i for i in result.itineraries if "recommended" in i.tags)
    assert all(leg.estimated for leg in rec.legs)


async def test_required_stage_failure_propagates(serp_client, mock_serpapi, settings):
    mock_serpapi.overrides["google_flights"] = httpx.Response(429, json={"error": "rate limited"})
    with pytest.raises(SerpApiRateLimitError):
        await _engine(serp_client, settings).run("m", request(modes=["flight"]))


async def test_unknown_location():
    from app.core.config import get_settings
    with pytest.raises(ValidationAppError) as err:
        await MissionEngine(DemoProvider(), get_settings()).run("m", request(destination="Atlantis"))
    assert err.value.code == "unknown_location"


async def test_demo_provider_scenario(settings):
    result = await MissionEngine(DemoProvider(), settings).run("demo", request())
    assert result.mode == "demo" and result.status == "complete"
    rec = next(i for i in result.itineraries if i.id == result.categories["recommended"])
    assert rec.risk.level == "LOW" and rec.constraints.all_ok
    assert {i.strategy for i in result.itineraries} == {"same_day", "night_before"}
    assert all(c.api.startswith("google_") for c in result.data_sources.calls)
