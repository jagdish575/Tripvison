"""EmailService — composes and delivers trip emails. Never raises: a failed email must not fail a mission."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings
from app.core.database import session_scope
from app.core.logging import get_logger
from app.models import EmailMessage
from app.services.email.changes import recommended
from app.services.email.providers import EmailDeliveryError, EmailProvider, OutgoingEmail, get_email_provider
from app.services.email.templates import render_change_alert, render_reminder, render_trip_summary

log = get_logger(__name__)

FAILURE_MESSAGE = "Your journey was created, but we couldn't send the email."


@dataclass
class DeliveryResult:
    status: str  # sent | preview | failed
    message: str
    message_id: str | None = None
    preview_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class EmailService:
    def __init__(self, settings: Settings | None = None, provider: EmailProvider | None = None) -> None:
        self.settings = settings or get_settings()
        self.provider = provider or get_email_provider(self.settings)

    def view_url(self, mission_id: str) -> str:
        return f"{self.settings.public_base_url}/results/{mission_id}"

    # ------------------------------------------------------------------ public API
    async def send_trip_summary(self, mission_id: str, to: str, result: dict[str, Any],
                                snap: dict[str, Any]) -> DeliveryResult:
        itin = recommended(result, snap["itinerary_id"]) or {}
        explanation = result.get("explanation") or {}
        why = explanation.get("text") if itin.get("id") == (result.get("categories") or {}).get("recommended") else None
        subject, html, text = render_trip_summary(snap, why=why, cost_items=(itin.get("cost") or {}).get("items", []),
                                                  view_url=self.view_url(mission_id))
        return await self._deliver(mission_id, "summary", to, subject, html, text)

    async def send_trip_reminder(self, mission_id: str, to: str, result: dict[str, Any],
                                 snap: dict[str, Any]) -> DeliveryResult:
        itin = recommended(result, snap["itinerary_id"]) or {}
        notes = list((itin.get("risk") or {}).get("recommendations", []))[:4]
        if itin.get("cost", {}).get("ticket_source") == "estimated":
            notes.append("Ticket price is an estimate — check the fare when you book.")
        subject, html, text = render_reminder(snap, notes=notes, view_url=self.view_url(mission_id))
        return await self._deliver(mission_id, "reminder", to, subject, html, text)

    async def send_trip_change_alert(self, mission_id: str, to: str, before: dict[str, Any],
                                     after: dict[str, Any] | None, report: dict[str, Any]) -> DeliveryResult:
        subject, html, text = render_change_alert(before, after, report, view_url=self.view_url(mission_id))
        return await self._deliver(mission_id, "change", to, subject, html, text)

    # ------------------------------------------------------------------ delivery
    async def _deliver(self, mission_id: str, kind: str, to: str, subject: str, html: str, text: str) -> DeliveryResult:
        status, error = "preview", None
        if self.provider.name != "preview":
            try:
                await self.provider.send(OutgoingEmail(to=to, subject=subject, html=html, text=text))
                status = "sent"
            except EmailDeliveryError as exc:
                status, error = "failed", str(exc)[:300]
            except Exception as exc:  # never propagate
                status, error = "failed", f"Unexpected email error: {type(exc).__name__}"
        message_id = None
        try:
            with session_scope() as session:
                row = EmailMessage(mission_id=mission_id, kind=kind, to_email=to, subject=subject[:300], html=html,
                                   text=text, provider=self.provider.name, status=status, error=error)
                session.add(row)
                session.flush()
                message_id = row.id
        except Exception as exc:
            log.warning("email log write failed", extra={"context": {"error": type(exc).__name__}})
        log.info("email processed", extra={"context": {"mission_id": mission_id, "kind": kind, "status": status,
                                                         "provider": self.provider.name, "error": error}})
        preview_url = f"/api/v1/emails/{message_id}" if message_id else None
        if status == "sent":
            return DeliveryResult("sent", f"Email sent to {to}.", message_id, preview_url)
        if status == "preview":
            return DeliveryResult("preview", "Email delivery isn't configured on this server — here's a preview of "
                                             "what would be sent.", message_id, preview_url)
        return DeliveryResult("failed", FAILURE_MESSAGE, message_id, preview_url)
