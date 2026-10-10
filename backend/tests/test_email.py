"""Email system: payload accuracy, provider failure, change detection, reminders, opt-in flow."""

from __future__ import annotations

import time as _time
from datetime import datetime, timedelta, timezone

import pytest

from app.core.database import session_scope
from app.models import EmailMessage, EmailSubscription
from app.services.email import service as email_service_module
from app.services.email.changes import detect_changes, snapshot
from app.services.email.providers import EmailDeliveryError, OutgoingEmail, PreviewProvider, get_email_provider
from app.services.email.service import FAILURE_MESSAGE, EmailService
from app.services.notifications import NotificationService
from helpers import MISSION_DAY

BODY = {"origin": "Indore", "destination": "Bangalore", "venue": "Manyata Tech Park", "mission_type": "interview",
        "travel_date": MISSION_DAY.isoformat(), "arrival_deadline": "10:00", "budget": 10000}


class RecordingProvider:
    name = "smtp"

    def __init__(self):
        self.sent: list[OutgoingEmail] = []

    async def send(self, email):
        self.sent.append(email)


class FailingProvider:
    name = "smtp"

    async def send(self, email):
        raise EmailDeliveryError("SMTP authentication failed")


def _mission(api, **extra) -> tuple[str, dict]:
    mission_id = api.post("/api/v1/missions/analyze?wait=true", json={**BODY, **extra}).json()["mission_id"]
    return mission_id, api.get(f"/api/v1/missions/{mission_id}/recommendations").json()


# ------------------------------------------------------------------ payload accuracy
async def test_trip_summary_uses_only_stored_values(api):
    mission_id, result = _mission(api)
    snap = snapshot(result)
    provider = RecordingProvider()
    delivery = await EmailService(provider=provider).send_trip_summary(mission_id, "a@example.com", result, snap)
    assert delivery.status == "sent"
    email = provider.sent[0]
    rec = next(i for i in result["itineraries"] if i["id"] == result["categories"]["recommended"])
    total = f"₹{int(rec['cost']['total']):,}".replace(",", ",")
    assert snap["score"] == rec["scores"]["overall"]
    for expected in (f"{rec['scores']['overall']}/100", f"{rec['arrival']['buffer_minutes']} minutes",
                     rec["risk"]["level"], "View my journey", "Indore → Bengaluru"):
        assert expected in email.html
    assert "TOTAL TRIP COST" in email.html and "ESTIMATED" in email.html
    assert f"/results/{mission_id}" in email.html and "Recommended:" in email.text
    assert total.replace("₹", "") in email.html.replace(",", ",")


async def test_provider_failure_never_fails_the_mission(api, monkeypatch):
    monkeypatch.setattr(email_service_module, "get_email_provider", lambda settings: FailingProvider())
    response = api.post("/api/v1/missions/analyze?wait=true",
                        json={**BODY, "notifications": {"email": "fail@example.com"}})
    mission_id = response.json()["mission_id"]
    assert api.get(f"/api/v1/missions/{mission_id}").json()["status"] == "complete"
    status = api.get(f"/api/v1/missions/{mission_id}/notifications").json()
    assert status["subscriptions"][0]["email"] == "fail@example.com"
    assert status["messages"][0]["status"] == "failed"
    out = await NotificationService(email=EmailService(provider=FailingProvider())).subscribe(
        mission_id, __import__("app.schemas.mission", fromlist=["NotificationPrefs"]).NotificationPrefs(email="fail@example.com"))
    assert out["summary"]["status"] == "failed" and out["summary"]["message"] == FAILURE_MESSAGE
    with session_scope() as s:
        logged = s.query(EmailMessage).filter_by(mission_id=mission_id, status="failed").first()
        assert "password" not in (logged.error or "").lower()


def test_preview_provider_is_default_and_preview_endpoint(api):
    from app.core.config import get_settings
    assert isinstance(get_email_provider(get_settings()), PreviewProvider)
    mission_id, _ = _mission(api)
    out = api.post(f"/api/v1/missions/{mission_id}/notifications", json={"email": "me@example.com"}).json()
    assert out["summary"]["status"] == "preview"
    html = api.get(out["summary"]["preview_url"])
    assert html.status_code == 200 and "Your journey is ready." in html.text
    assert html.headers["content-type"].startswith("text/html")
    bad = api.post(f"/api/v1/missions/{mission_id}/notifications", json={"email": "not-an-email"})
    assert bad.status_code == 422


# ------------------------------------------------------------------ change detection
def _snap(**over):
    base = {"itinerary_id": "a", "title": "X", "venue_arrival": "2026-10-09T08:30:00", "arrival_main": "2026-10-09T07:30:00",
            "buffer": 90, "required_buffer": 60, "risk": "LOW", "total_cost": 8000}
    return {**base, **over}


def test_meaningful_change_detection():
    assert not detect_changes(_snap(), _snap()).meaningful
    small = detect_changes(_snap(), _snap(venue_arrival="2026-10-09T08:35:00", buffer=85, total_cost=8200))
    assert not small.meaningful and len(small.changes) == 3
    big = detect_changes(_snap(), _snap(venue_arrival="2026-10-09T09:20:00", buffer=40, risk="MEDIUM"))
    assert big.meaningful and {c.field for c in big.changes if c.meaningful} == {"venue_arrival", "buffer", "risk"}
    assert detect_changes(_snap(), _snap(total_cost=9000)).meaningful  # +12.5% and ≥ ₹500
    assert detect_changes(_snap(), None).journey_unavailable
    absorbed = detect_changes(_snap(), _snap(arrival_main="2026-10-08T22:00:00"))
    assert not absorbed.meaningful


# ------------------------------------------------------------------ reminders
async def test_reminder_due_logic(api):
    mission_id, result = _mission(api)
    provider = RecordingProvider()
    notifier = NotificationService(email=EmailService(provider=provider))
    from app.schemas.mission import NotificationPrefs
    await notifier.subscribe(mission_id, NotificationPrefs(email="r@example.com", changes=False), send_summary=False)
    local_now = (datetime.now(timezone.utc) + timedelta(minutes=330)).replace(tzinfo=None)
    with session_scope() as s:
        sub = s.query(EmailSubscription).filter_by(mission_id=mission_id).one()
        sub.departure_at = local_now + timedelta(hours=40)  # too early for a 24 h reminder
    assert await notifier.process_due_reminders() == 0
    with session_scope() as s:
        s.query(EmailSubscription).filter_by(mission_id=mission_id).one().departure_at = local_now + timedelta(hours=10)
    assert await notifier.process_due_reminders() == 1
    assert "Reminder" in provider.sent[0].subject and "Required arrival" in provider.sent[0].html
    assert await notifier.process_due_reminders() == 0  # sent only once


# ------------------------------------------------------------------ demo re-check & change alert
async def test_demo_recheck_sends_alert_only_for_meaningful_changes(api, demo_settings):
    same_day = {**BODY, "preferences": ["same_day_only"], "hotel_required": False, "modes": ["flight"]}
    mission_id, result = _mission(api, **{k: v for k, v in same_day.items() if k not in BODY or BODY[k] != v})
    api.post(f"/api/v1/missions/{mission_id}/notifications", json={"email": "c@example.com", "trip_summary": False})
    quiet = api.post(f"/api/v1/missions/{mission_id}/recheck", json={}).json()
    assert quiet["report"]["meaningful"] is False and quiet["alerts"][0]["alert"] is None
    delayed = api.post(f"/api/v1/missions/{mission_id}/recheck", json={"simulate_delay_minutes": 45}).json()
    assert delayed["simulated"] and delayed["report"]["meaningful"]
    assert delayed["alerts"][0]["alert"]["status"] == "preview"
    status = api.get(f"/api/v1/missions/{mission_id}/notifications").json()
    assert status["messages"][0]["kind"] == "change"
    html = api.get(status["messages"][0]["preview_url"]).text
    assert "Your journey needs attention." in html and "Review alternatives" in html


def test_simulated_delay_is_demo_only(api):
    mission_id, _ = _mission(api)
    response = api.post(f"/api/v1/missions/{mission_id}/recheck", json={"simulate_delay_minutes": 30})
    assert response.status_code == 422 and response.json()["error"]["code"] == "demo_only"
