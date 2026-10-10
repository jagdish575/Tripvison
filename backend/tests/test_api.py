from __future__ import annotations

import time as _time
from datetime import date, timedelta

import pytest

from helpers import MISSION_DAY

BODY = {"origin": "Indore", "destination": "Bangalore", "venue": "Manyata Tech Park", "mission_type": "interview",
        "travel_date": MISSION_DAY.isoformat(), "arrival_deadline": "10:00", "budget": 10000}


def test_health(api):
    data = api.get("/api/v1/health").json()
    assert data["status"] == "ok" and data["serpapi_configured"] is True
    assert "test-serpapi-key" not in str(data)


def test_airport_search(api):
    codes = [a["code"] for a in api.get("/api/v1/airports?q=bang").json()["results"]]
    assert codes[0] == "BLR"


def test_analyze_poll_and_fetch(api):
    created = api.post("/api/v1/missions/analyze", json=BODY)
    assert created.status_code == 202
    mission_id = created.json()["mission_id"]
    deadline = _time.time() + 15
    status = None
    while _time.time() < deadline:
        status = api.get(f"/api/v1/missions/{mission_id}").json()
        if status["status"] in ("complete", "failed"):
            break
        _time.sleep(0.05)
    assert status["status"] == "complete", status
    assert status["progress"]["stage"] == "done" and "flights" in status["progress"]["completed"]
    result = api.get(f"/api/v1/missions/{mission_id}/recommendations").json()
    assert result["mission_id"] == mission_id and result["categories"]["recommended"]
    assert result["itineraries"][0]["timeline"][0]["kind"] == "depart"


def test_analyze_wait_and_persistence(api):
    from app.core.database import session_scope
    from app.models import FlightOption, Itinerary, Recommendation, TravelOption

    mission_id = api.post("/api/v1/missions/analyze?wait=true", json=BODY).json()["mission_id"]
    with session_scope() as s:
        assert s.query(FlightOption).filter_by(mission_id=mission_id).count() > 0
        assert s.query(Itinerary).filter_by(mission_id=mission_id).count() > 0
        assert s.query(Recommendation).filter_by(mission_id=mission_id).count() == 5
        assert s.query(TravelOption).filter_by(mission_id=mission_id).count() > 0


def test_not_found_and_not_ready(api):
    assert api.get("/api/v1/missions/nope").status_code == 404
    assert api.get("/api/v1/missions/nope/recommendations").json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("patch,code", [
    ({"travel_date": (date.today() - timedelta(days=1)).isoformat()}, "validation_error"),
    ({"budget": 0}, "validation_error"),
    ({"travelers": 12}, "validation_error"),
    ({"preferences": ["teleport"]}, "validation_error"),
    ({"destination": "Atlantis"}, "unknown_location"),
    ({"destination": "Indore"}, "validation_error"),
    ({"destination": "Bengaluru", "origin": "BLR"}, "same_origin_destination"),
])
def test_validation_errors(api, patch, code):
    response = api.post("/api/v1/missions/analyze", json={**BODY, **patch})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code


def test_unknown_fields_rejected(api):
    response = api.post("/api/v1/missions/analyze", json={**BODY, "admin": True})
    assert response.status_code == 422


def test_payload_too_large(api):
    response = api.post("/api/v1/missions/analyze", content=b"{" + b" " * 40000 + b"}",
                        headers={"Content-Type": "application/json"})
    assert response.status_code == 413


def test_rate_limit(api, settings, monkeypatch):
    monkeypatch.setattr(settings, "analyze_rate_limit_per_minute", 2)
    for _ in range(2):
        assert api.post("/api/v1/missions/analyze?wait=true", json=BODY).status_code == 202
    limited = api.post("/api/v1/missions/analyze", json=BODY)
    assert limited.status_code == 429 and limited.json()["error"]["details"]["retry_after_seconds"] > 0


def test_setup_required_without_key(api, settings, monkeypatch):
    monkeypatch.setattr(settings, "serpapi_api_key", "")
    response = api.post("/api/v1/missions/analyze", json=BODY)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "setup_required"


def test_demo_mode_rejects_other_routes(api, demo_settings):
    response = api.post("/api/v1/missions/analyze", json={**BODY, "origin": "Delhi"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "demo_route_unsupported"
    ok = api.post("/api/v1/missions/analyze?wait=true", json=BODY)
    assert ok.json()["mode"] == "demo"


def test_search_endpoints_return_normalized_data(api):
    flights = api.get("/api/v1/flights/search", params={"origin": "IDR", "destination": "BLR",
                                                         "date": MISSION_DAY.isoformat()}).json()
    assert flights["results"] and "best_flights" not in flights
    directions = api.get("/api/v1/directions", params={"from": "13.1986,77.7066", "to": "Manyata Tech Park"}).json()
    assert directions["route"]["distance_km"] > 0
    upstream = api.get("/api/v1/flights/search", params={"origin": "IDR", "destination": "XXX", "date": "2026-10-09"})
    assert upstream.status_code == 422
