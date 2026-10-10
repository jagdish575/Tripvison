"""Trip-update notifications: opt-in, trip summary, reminders and change alerts.

Kept separate from the mission engine: the engine produces results; this service reads stored results and
decides what to email. A failed email never fails a mission.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.database import session_scope
from app.core.errors import NotFoundError, NotReadyError
from app.core.logging import get_logger
from app.models import EmailMessage, EmailSubscription, Mission
from app.schemas.mission import NotificationPrefs
from app.services.email.changes import detect_changes, snapshot
from app.services.email.service import EmailService

log = get_logger(__name__)


def _local_now(offset_minutes: int) -> datetime:
    return (datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)).replace(tzinfo=None)


def _sub_dict(sub: EmailSubscription) -> dict[str, Any]:
    return {"email": sub.email, "trip_summary": sub.trip_summary, "reminder": sub.reminder, "changes": sub.changes,
            "departure_at": sub.departure_at.isoformat() if sub.departure_at else None,
            "reminder_sent_at": sub.reminder_sent_at.isoformat() if sub.reminder_sent_at else None,
            "active": sub.active}


class NotificationService:
    def __init__(self, settings: Settings | None = None, email: EmailService | None = None) -> None:
        self.settings = settings or get_settings()
        self.email = email or EmailService(self.settings)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _load(mission_id: str) -> tuple[str, dict[str, Any] | None, dict[str, Any]]:
        with session_scope() as session:
            mission = session.get(Mission, mission_id)
            if mission is None:
                raise NotFoundError("We couldn't find that mission.")
            return mission.status, mission.result, mission.request or {}

    @staticmethod
    def _offset(result: dict[str, Any]) -> int:
        return 330 if result["mission"]["destination"].get("country") == "IN" else 0

    # ------------------------------------------------------------------ opt-in
    async def subscribe(self, mission_id: str, prefs: NotificationPrefs, *, send_summary: bool = True) -> dict[str, Any]:
        status, result, _ = self._load(mission_id)
        email = prefs.email.strip().lower()
        snap = snapshot(result) if result else None
        with session_scope() as session:
            sub = session.scalar(select(EmailSubscription).where(EmailSubscription.mission_id == mission_id,
                                                                 EmailSubscription.email == email))
            if sub is None:
                sub = EmailSubscription(mission_id=mission_id, email=email)
                session.add(sub)
            sub.trip_summary, sub.reminder, sub.changes, sub.active = prefs.trip_summary, prefs.reminder, prefs.changes, True
            if snap:
                sub.snapshot = snap
                sub.departure_at = datetime.fromisoformat(snap["departure"])
                sub.utc_offset_minutes = self._offset(result)  # type: ignore[arg-type]
            session.flush()
            sub_data = _sub_dict(sub)

        summary = None
        if send_summary and prefs.trip_summary:
            if status == "complete" and result and snap:
                summary = (await self.email.send_trip_summary(mission_id, email, result, snap)).to_dict()
            elif status != "complete":
                summary = {"status": "pending", "message": "We'll email your trip summary when the analysis finishes."}
            else:
                summary = {"status": "skipped", "message": "No journey to summarise for this mission."}
        return {"subscription": sub_data, "summary": summary}

    async def on_mission_complete(self, mission_id: str) -> None:
        """Called after an analysis finishes: honour any opt-in submitted with the mission form."""
        try:
            _, result, request = self._load(mission_id)
            prefs = request.get("notifications")
            if prefs and result:
                await self.subscribe(mission_id, NotificationPrefs(**prefs))
        except Exception as exc:  # notifications must never break a mission
            log.warning("notification on completion failed", extra={"context": {"mission_id": mission_id,
                                                                                  "error": type(exc).__name__}})

    def status(self, mission_id: str) -> dict[str, Any]:
        self._load(mission_id)
        with session_scope() as session:
            subs = session.scalars(select(EmailSubscription).where(EmailSubscription.mission_id == mission_id)).all()
            messages = session.scalars(select(EmailMessage).where(EmailMessage.mission_id == mission_id)
                                       .order_by(EmailMessage.created_at.desc()).limit(20)).all()
            return {
                "subscriptions": [_sub_dict(s) for s in subs],
                "messages": [{"id": m.id, "kind": m.kind, "to": m.to_email, "subject": m.subject, "status": m.status,
                              "provider": m.provider, "created_at": m.created_at.isoformat(),
                              "preview_url": f"/api/v1/emails/{m.id}"} for m in messages],
                "delivery": self.email.provider.name,
            }

    # ------------------------------------------------------------------ change detection
    async def recheck(self, mission_id: str, *, simulate_delay_minutes: int | None = None) -> dict[str, Any]:
        """Re-run the analysis with fresh data, compare against what subscribers were told, alert if meaningful."""
        from app.services.mission_service import MissionService

        status, old_result, _ = self._load(mission_id)
        if status != "complete" or not old_result:
            raise NotReadyError("This mission isn't ready to re-check yet.")
        with session_scope() as session:
            subs = [(_sub_dict(s), s.id, s.snapshot) for s in session.scalars(
                select(EmailSubscription).where(EmailSubscription.mission_id == mission_id,
                                                EmailSubscription.active.is_(True))).all()]
        baseline = snapshot(old_result)
        new_result = await MissionService(self.settings).recheck(
            mission_id, simulate_delay_minutes=simulate_delay_minutes, focus=baseline)
        new_for_baseline = snapshot(new_result, baseline["itinerary_id"]) if baseline else None
        report = detect_changes(baseline, new_for_baseline) if baseline else None

        alerts = []
        for sub, sub_id, sub_snapshot in subs:
            before = sub_snapshot or baseline
            if before is None:
                continue
            after = snapshot(new_result, before["itinerary_id"])
            sub_report = detect_changes(before, after)
            alert = None
            if sub_report.meaningful and sub["changes"]:
                alert = (await self.email.send_trip_change_alert(mission_id, sub["email"], before, after,
                                                                 sub_report.to_dict())).to_dict()
            alerts.append({"email": sub["email"], "meaningful": sub_report.meaningful, "alert": alert})
            with session_scope() as session:
                row = session.get(EmailSubscription, sub_id)
                if row is not None:
                    fresh = after or snapshot(new_result)
                    row.snapshot = fresh
                    if fresh:
                        row.departure_at = datetime.fromisoformat(fresh["departure"])
        return {"report": report.to_dict() if report else None, "alerts": alerts,
                "simulated": simulate_delay_minutes is not None}

    # ------------------------------------------------------------------ reminders
    async def send_reminder(self, mission_id: str, *, email: str | None = None) -> list[dict[str, Any]]:
        _, result, _ = self._load(mission_id)
        if not result:
            raise NotReadyError("This mission isn't ready yet.")
        out = []
        with session_scope() as session:
            query = select(EmailSubscription).where(EmailSubscription.mission_id == mission_id,
                                                    EmailSubscription.active.is_(True))
            if email:
                query = query.where(EmailSubscription.email == email.strip().lower())
            subs = [(s.id, s.email, s.snapshot) for s in session.scalars(query).all()]
        for sub_id, address, snap in subs:
            snap = snap or snapshot(result)
            if not snap:
                continue
            delivery = await self.email.send_trip_reminder(mission_id, address, result, snap)
            out.append({"email": address, **delivery.to_dict()})
            if delivery.status != "failed":
                with session_scope() as session:
                    row = session.get(EmailSubscription, sub_id)
                    if row is not None:
                        row.reminder_sent_at = datetime.now(timezone.utc)
        return out

    async def process_due_reminders(self) -> int:
        """Send reminders whose departure is within REMINDER_HOURS_BEFORE. Re-checks first when the
        subscriber wants change alerts. Returns the number of missions processed."""
        hours = self.settings.reminder_hours_before
        with session_scope() as session:
            due = [(s.mission_id, s.email, s.departure_at, s.utc_offset_minutes, s.changes) for s in session.scalars(
                select(EmailSubscription).where(EmailSubscription.active.is_(True),
                                                EmailSubscription.reminder.is_(True),
                                                EmailSubscription.reminder_sent_at.is_(None),
                                                EmailSubscription.departure_at.is_not(None))).all()]
        processed = 0
        for mission_id, address, departure, offset, wants_changes in due:
            now = _local_now(offset)
            if not (now < departure <= now + timedelta(hours=hours)):
                continue
            try:
                if wants_changes:
                    await self.recheck(mission_id)
                await self.send_reminder(mission_id, email=address)
                processed += 1
            except Exception as exc:
                log.warning("reminder failed", extra={"context": {"mission_id": mission_id, "error": type(exc).__name__}})
        return processed


async def reminder_loop(interval_seconds: int) -> None:
    """Simple in-process scheduler (hackathon MVP). Swap for a task queue when running several workers."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            count = await NotificationService().process_due_reminders()
            if count:
                log.info("reminders sent", extra={"context": {"missions": count}})
        except Exception as exc:
            log.warning("reminder loop error", extra={"context": {"error": type(exc).__name__}})
