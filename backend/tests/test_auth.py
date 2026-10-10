"""Authentication, protected mission creation, demo sessions, user isolation, trips, saved missions,
email preferences (incl. email failure) and user-safe API responses."""

from __future__ import annotations

import jwt
import pytest

from app.core.config import get_settings
from app.services import auth as auth_service
from app.services.email import service as email_service_module
from conftest import sign_in_google
from helpers import MISSION_DAY

BODY = {"origin": "Indore", "destination": "Bangalore", "venue": "Manyata Tech Park", "mission_type": "interview",
        "travel_date": MISSION_DAY.isoformat(), "arrival_deadline": "10:00", "budget": 10000}
UJJAIN = {**BODY, "destination": "Ujjain", "venue": "Mahakal Mandir", "mission_type": "other"}


def _new_client(serp_client):
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


# ------------------------------------------------------------------ authentication
def test_mission_creation_requires_sign_in(anon_api):
    response = anon_api.post("/api/v1/missions/analyze", json=BODY)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth_required"


def test_google_sign_in_session_and_sign_out(anon_api, monkeypatch):
    assert anon_api.get("/api/v1/auth/me").json() == {"user": None}
    user = sign_in_google(anon_api, monkeypatch)
    assert user["email"] == "traveller@example.com" and user["is_demo"] is False
    cookie = anon_api.cookies.get(get_settings().session_cookie_name)
    assert cookie and "traveller@example.com" not in cookie  # opaque signed token, no PII in clear
    assert anon_api.get("/api/v1/auth/me").json()["user"]["name"] == "Asha Traveller"
    assert anon_api.post("/api/v1/auth/logout").status_code == 200
    anon_api.cookies.clear()
    assert anon_api.get("/api/v1/auth/me").json() == {"user": None}


def test_invalid_google_token_is_rejected(anon_api, monkeypatch):
    def reject(credential, client_id):
        raise jwt.InvalidAudienceError("wrong audience")

    monkeypatch.setattr(auth_service, "_verify_google_sync", reject)
    response = anon_api.post("/api/v1/auth/google", json={"credential": "x" * 40})
    assert response.status_code == 401
    assert "verify" in response.json()["error"]["message"]


def test_unverified_google_email_is_rejected(anon_api, monkeypatch):
    monkeypatch.setattr(auth_service, "_verify_google_sync",
                        lambda c, cid: {"sub": "s", "email": "a@b.co", "email_verified": False})
    assert anon_api.post("/api/v1/auth/google", json={"credential": "x" * 40}).status_code == 401


def test_google_not_configured(anon_api, monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_id", "")
    response = anon_api.post("/api/v1/auth/google", json={"credential": "x" * 40})
    assert response.status_code == 503 and response.json()["error"]["code"] == "google_auth_unavailable"
    assert anon_api.get("/api/v1/auth/config").json()["google_enabled"] is False


def test_auth_config_never_exposes_secrets(anon_api, monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_secret", "super-secret-value-123")
    data = anon_api.get("/api/v1/auth/config").json()
    assert data["google_client_id"].endswith(".apps.googleusercontent.com")
    assert "super-secret" not in str(data) and "session" not in str(data).lower()


def test_tampered_session_cookie_is_ignored(anon_api):
    forged = jwt.encode({"sub": "someone", "exp": 9999999999, "iss": "tripmission"}, "wrong-key-0123456789-abcdefghijklmn",
                        algorithm="HS256")
    anon_api.cookies.set(get_settings().session_cookie_name, forged)
    assert anon_api.get("/api/v1/auth/me").json() == {"user": None}
    assert anon_api.post("/api/v1/missions/analyze", json=BODY).status_code == 401


def test_cross_site_post_is_blocked(api):
    response = api.post("/api/v1/missions/analyze", json=BODY, headers={"Origin": "https://evil.example"})
    assert response.status_code == 403 and response.json()["error"]["code"] == "forbidden_origin"


# ------------------------------------------------------------------ protected missions & isolation
def test_users_only_see_their_own_missions(api, serp_client, monkeypatch):
    mission_id = api.post("/api/v1/missions/analyze?wait=true", json=BODY).json()["mission_id"]
    assert api.get(f"/api/v1/missions/{mission_id}/recommendations").status_code == 200

    with _new_client(serp_client) as other:
        sign_in_google(other, monkeypatch, {**_claims("google-sub-2", "other@example.com")})
        assert other.get(f"/api/v1/missions/{mission_id}").status_code == 404
        assert other.get(f"/api/v1/missions/{mission_id}/recommendations").status_code == 404
        assert other.get(f"/api/v1/missions/{mission_id}/notifications").status_code == 404
        assert other.post(f"/api/v1/missions/{mission_id}/save").status_code == 404
        assert mission_id not in str(other.get("/api/v1/me/trips").json())

    with _new_client(serp_client) as anonymous:
        assert anonymous.get(f"/api/v1/missions/{mission_id}/recommendations").status_code == 401


def _claims(sub: str, email: str) -> dict:
    return {"sub": sub, "email": email, "email_verified": True, "name": email.split("@")[0]}


# ------------------------------------------------------------------ demo mode
def test_demo_session_uses_labelled_demo_data(anon_api):
    user = anon_api.post("/api/v1/auth/demo").json()["user"]
    assert user["is_demo"] is True and user["email"] is None
    created = anon_api.post("/api/v1/missions/analyze?wait=true", json=UJJAIN).json()
    assert created["mode"] == "demo"
    result = anon_api.get(f"/api/v1/missions/{created['mission_id']}/recommendations").json()
    assert result["mode"] == "demo" and result["route"]["flight"] == "skipped"
    assert result["methodology"][0]["kind"] == "demo"
    assert all(i["main"]["data_source"] == "Demo dataset" for i in result["itineraries"])


def test_demo_session_never_calls_live_apis(anon_api, mock_serpapi):
    anon_api.post("/api/v1/auth/demo")
    anon_api.post("/api/v1/missions/analyze?wait=true", json=BODY)
    assert mock_serpapi.calls == []


def test_demo_mode_explains_supported_routes(anon_api):
    anon_api.post("/api/v1/auth/demo")
    response = anon_api.post("/api/v1/missions/analyze", json={**BODY, "origin": "Delhi", "destination": "Mumbai"})
    assert response.status_code == 422 and response.json()["error"]["code"] == "demo_route_unsupported"
    assert "Ujjain" in response.json()["error"]["message"]


def test_demo_login_can_be_disabled(anon_api, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_login_enabled", False)
    assert anon_api.post("/api/v1/auth/demo").status_code == 403


# ------------------------------------------------------------------ trips, saving, preferences, email
def test_trips_save_and_trip_summary_email(api):
    api.put("/api/v1/me/preferences", json={"notifications": {"enabled": True}, "email": {
        "trip_summary": True, "departure_reminder": True, "journey_changes": True, "price_changes": False}})
    mission_id = api.post("/api/v1/missions/analyze?wait=true", json=BODY).json()["mission_id"]
    trip = next(t for t in api.get("/api/v1/me/trips").json()["trips"] if t["mission_id"] == mission_id)
    assert trip["upcoming"] and not trip["saved"] and trip["destination"] == "Bengaluru"
    assert trip["recommended"]["mode"] and trip["recommended"]["total_cost"] > 0 and trip["recommended"]["score"] > 0

    saved = api.post(f"/api/v1/missions/{mission_id}/save").json()
    assert saved["saved"] is True and saved["email"]["status"] == "preview"  # EMAIL_PROVIDER=preview in tests
    status = api.get(f"/api/v1/missions/{mission_id}/notifications").json()
    assert status["subscriptions"][0]["email"] == "traveller@example.com"
    assert any(m["kind"] == "summary" for m in status["messages"])
    assert next(t for t in api.get("/api/v1/me/trips").json()["trips"] if t["mission_id"] == mission_id)["saved"]

    assert api.delete(f"/api/v1/missions/{mission_id}/save").json() == {"saved": False}


def test_email_preferences_persist_and_control_subscriptions(api):
    prefs = api.get("/api/v1/me/preferences").json()["preferences"]
    assert prefs["email"] == {"trip_summary": True, "departure_reminder": True, "journey_changes": True,
                              "price_changes": False}
    update = {"email": {"trip_summary": False, "departure_reminder": False, "journey_changes": False,
                        "price_changes": True},
              "travel": {"home_city": "Indore", "priority": "save_money", "modes": ["train", "bus"],
                         "buffer_minutes": 45}}
    assert api.put("/api/v1/me/preferences", json=update).status_code == 200
    stored = api.get("/api/v1/me/preferences").json()["preferences"]
    assert stored["email"]["price_changes"] is True and stored["email"]["trip_summary"] is False
    assert stored["travel"] == {"home_city": "Indore", "priority": "save_money", "modes": ["train", "bus"],
                                "buffer_minutes": 45}

    api.put("/api/v1/me/preferences", json={"notifications": {"enabled": False}})
    mission_id = api.post("/api/v1/missions/analyze?wait=true", json=BODY).json()["mission_id"]
    assert api.post(f"/api/v1/missions/{mission_id}/save").json()["email"] is None  # notifications off
    assert api.put("/api/v1/me/preferences", json={"email": {"trip_summary": "yes-please"}}).status_code == 422


def test_preferences_require_sign_in(anon_api):
    assert anon_api.get("/api/v1/me/preferences").status_code == 401
    assert anon_api.get("/api/v1/me/trips").status_code == 401


def test_email_failure_does_not_fail_saving(api, monkeypatch):
    class Failing:
        name = "smtp"

        async def send(self, email):
            from app.services.email.providers import EmailDeliveryError
            raise EmailDeliveryError("SMTP authentication failed")

    monkeypatch.setattr(email_service_module, "get_email_provider", lambda settings: Failing())
    api.put("/api/v1/me/preferences", json={"notifications": {"enabled": True}, "email": {
        "trip_summary": True, "departure_reminder": True, "journey_changes": True, "price_changes": False}})
    mission_id = api.post("/api/v1/missions/analyze?wait=true", json=BODY).json()["mission_id"]
    response = api.post(f"/api/v1/missions/{mission_id}/save")
    assert response.status_code == 200 and response.json()["saved"] is True
    assert response.json()["email"]["status"] == "failed"
    assert "SMTP" not in response.text


# ------------------------------------------------------------------ no developer details for normal users
def test_results_hide_request_counts_and_diagnostics(api, monkeypatch):
    mission_id = api.post("/api/v1/missions/analyze?wait=true", json=BODY).json()["mission_id"]
    result = api.get(f"/api/v1/missions/{mission_id}/recommendations").json()
    ds = result["data_sources"]
    assert ds["calls"] is None and ds["live_calls"] is None and ds["cache_hits"] is None
    assert result["diagnostics"] is None and result["methodology"]
    monkeypatch.setattr(get_settings(), "debug_mode", True)
    debug = api.get(f"/api/v1/missions/{mission_id}/recommendations").json()
    assert debug["data_sources"]["calls"] and debug["diagnostics"] is not None


@pytest.mark.parametrize("status", [401, 429, 500])
def test_upstream_errors_are_user_safe(api, mock_serpapi, status):
    import httpx

    mock_serpapi.overrides["google_flights"] = httpx.Response(status, json={"error": "Invalid API key. Your key: abc"})
    response = api.get("/api/v1/flights/search", params={"origin": "IDR", "destination": "BLR",
                                                          "date": MISSION_DAY.isoformat()})
    body = response.json()["error"]
    assert "request_id" not in body
    assert not any(term in body["message"] for term in ("SERPAPI", "API key", "SerpApi", "HTTP", "abc"))
