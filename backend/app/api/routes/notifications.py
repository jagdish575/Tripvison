from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.core.database import session_scope
from app.core.errors import NotFoundError
from app.core.rate_limit import client_key, limiter
from app.models import EmailMessage
from app.schemas.mission import NotificationPrefs
from app.services.auth import CurrentUser, optional_user
from app.services.mission_service import assert_owner
from app.services.notifications import NotificationService

router = APIRouter(tags=["notifications"])


class RecheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    simulate_delay_minutes: int | None = Field(default=None, ge=1, le=720,
                                               description="Demo missions only: delay the recommended journey")


@router.post("/missions/{mission_id}/notifications")
async def subscribe(mission_id: str, prefs: NotificationPrefs, request: Request,
                    user: CurrentUser | None = Depends(optional_user)) -> dict[str, Any]:
    assert_owner(mission_id, user)
    limiter.check("notify", client_key(request), get_settings().search_rate_limit_per_minute)
    return await NotificationService().subscribe(mission_id, prefs)


@router.get("/missions/{mission_id}/notifications")
def notification_status(mission_id: str, user: CurrentUser | None = Depends(optional_user)) -> dict[str, Any]:
    assert_owner(mission_id, user)
    return NotificationService().status(mission_id)


@router.post("/missions/{mission_id}/notifications/reminder")
async def send_reminder_now(mission_id: str, request: Request,
                            user: CurrentUser | None = Depends(optional_user)) -> dict[str, Any]:
    assert_owner(mission_id, user)
    limiter.check("notify", client_key(request), get_settings().search_rate_limit_per_minute)
    return {"results": await NotificationService().send_reminder(mission_id)}


@router.post("/missions/{mission_id}/recheck")
async def recheck(mission_id: str, request: Request, body: RecheckRequest | None = None,
                  user: CurrentUser | None = Depends(optional_user)) -> dict[str, Any]:
    assert_owner(mission_id, user)
    limiter.check("analyze", client_key(request), get_settings().analyze_rate_limit_per_minute)
    body = body or RecheckRequest()
    return await NotificationService().recheck(mission_id, simulate_delay_minutes=body.simulate_delay_minutes)


@router.get("/emails/{message_id}", response_class=HTMLResponse)
def email_preview(message_id: str, user: CurrentUser | None = Depends(optional_user)) -> HTMLResponse:
    with session_scope() as session:
        message = session.get(EmailMessage, message_id)
        if message is None:
            raise NotFoundError("Email not found.")
        html, mission_id = message.html, message.mission_id
    assert_owner(mission_id, user)
    return HTMLResponse(html, headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src https: data:",
                                       "X-Frame-Options": "SAMEORIGIN"})
