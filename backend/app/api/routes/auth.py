"""Sign-in: Google (ID token verified server-side), demo sessions, current user, sign-out."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.rate_limit import client_key, limiter
from app.services.auth import (CurrentUser, clear_session_cookie, create_demo_user, issue_session, optional_user,
                               set_session_cookie, upsert_google_user, verify_google_id_token)

router = APIRouter(prefix="/auth", tags=["auth"])


class GoogleSignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential: str = Field(min_length=20, max_length=4096, description="Google Identity Services ID token")


@router.get("/config")
def auth_config() -> dict[str, Any]:
    """Public configuration for the sign-in UI. The Google *client ID* is public by design; the secret never is."""
    s = get_settings()
    return {"google_client_id": s.google_client_id or None, "google_enabled": s.google_auth_configured,
            "demo_enabled": s.demo_login_enabled, "auth_required": s.auth_required}


@router.get("/me")
def me(user: CurrentUser | None = Depends(optional_user)) -> dict[str, Any]:
    return {"user": user.public() if user else None}


@router.post("/google")
async def google_sign_in(body: GoogleSignIn, request: Request, response: Response) -> dict[str, Any]:
    limiter.check("auth", client_key(request), 20)
    claims = await verify_google_id_token(body.credential)
    user = upsert_google_user(claims)
    set_session_cookie(response, issue_session(user))
    return {"user": CurrentUser(id=user.id, email=user.email, name=user.name, picture=user.picture,
                                is_demo=False).public()}


@router.post("/demo")
def demo_sign_in(request: Request, response: Response) -> dict[str, Any]:
    if not get_settings().demo_login_enabled:
        raise AppError("Demo mode isn't available on this server.", code="demo_disabled", status_code=403)
    limiter.check("auth", client_key(request), 20)
    user = create_demo_user()
    set_session_cookie(response, issue_session(user))
    return {"user": CurrentUser(id=user.id, email=None, name=user.name, picture=None, is_demo=True).public()}


@router.post("/logout")
def logout(response: Response) -> dict[str, Any]:
    clear_session_cookie(response)
    return {"ok": True}
