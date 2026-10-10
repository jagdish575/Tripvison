"""Authentication: Google ID-token verification, signed session cookies, demo sessions.

Flow
  1. The browser gets a Google ID token from Google Identity Services ("Sign in with Google").
  2. POST /auth/google sends it here; we verify its RS256 signature against Google's published keys,
     its audience (GOOGLE_CLIENT_ID), issuer and expiry — the browser is never trusted.
  3. We issue our own short HS256 session token in an HttpOnly, SameSite=Lax cookie.
Demo sessions ("Continue in Demo Mode") are anonymous users flagged `is_demo`; their missions always
use the labelled demo dataset, never live searches.
"""

from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Request, Response

from app.core.config import Settings, get_settings
from app.core.database import session_scope
from app.core.errors import AppError
from app.core.logging import get_logger
from app.models import User, UserPreference

log = get_logger(__name__)

GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
_SESSION_ALG = "HS256"
_ephemeral_secret = secrets.token_urlsafe(48)
_jwks_client: jwt.PyJWKClient | None = None


class AuthRequiredError(AppError):
    status_code = 401
    code = "auth_required"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None
    name: str
    picture: str | None
    is_demo: bool

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "email": self.email, "name": self.name, "picture": self.picture,
                "is_demo": self.is_demo}


def _secret(settings: Settings) -> str:
    if settings.session_secret.strip():
        return settings.session_secret
    return _ephemeral_secret  # dev only: sessions end when the server restarts


# ---------------------------------------------------------------------------- session tokens
def issue_session(user: User, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    claims = {"sub": user.id, "demo": user.is_demo, "iat": int(now.timestamp()),
              "exp": int((now + timedelta(hours=settings.session_ttl_hours)).timestamp()), "iss": "tripmission"}
    return jwt.encode(claims, _secret(settings), algorithm=_SESSION_ALG)


def read_session(token: str, settings: Settings | None = None) -> dict[str, Any] | None:
    settings = settings or get_settings()
    try:
        return jwt.decode(token, _secret(settings), algorithms=[_SESSION_ALG], issuer="tripmission",
                          options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        return None


def set_session_cookie(response: Response, token: str, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    response.set_cookie(settings.session_cookie_name, token, max_age=settings.session_ttl_hours * 3600,
                        httponly=True, secure=settings.cookie_secure, samesite="lax", path="/")


def clear_session_cookie(response: Response, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/", httponly=True, secure=settings.cookie_secure,
                           samesite="lax")


# ---------------------------------------------------------------------------- Google
def _google_keys() -> jwt.PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(GOOGLE_CERTS_URL, cache_keys=True, lifespan=3600)
    return _jwks_client


def _verify_google_sync(credential: str, client_id: str) -> dict[str, Any]:
    key = _google_keys().get_signing_key_from_jwt(credential)
    claims = jwt.decode(credential, key.key, algorithms=["RS256"], audience=client_id,
                        options={"require": ["exp", "iat", "sub", "aud", "iss"]})
    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise jwt.InvalidIssuerError("unexpected issuer")
    return claims


async def verify_google_id_token(credential: str, settings: Settings | None = None) -> dict[str, Any]:
    """Returns verified Google claims (sub, email, email_verified, name, picture). Raises AuthRequiredError."""
    settings = settings or get_settings()
    if not settings.google_auth_configured:
        raise AppError("Google sign-in isn't available right now. You can continue in Demo Mode.",
                       code="google_auth_unavailable", status_code=503)
    try:
        claims = await asyncio.to_thread(_verify_google_sync, credential, settings.google_client_id)
    except (jwt.PyJWTError, OSError) as exc:
        log.warning("google token rejected", extra={"context": {"reason": type(exc).__name__}})
        raise AuthRequiredError("We couldn't verify your Google sign-in. Please try again.") from None
    if not claims.get("email") or not claims.get("email_verified", False):
        raise AuthRequiredError("Your Google account needs a verified email address to sign in.")
    return claims


# ---------------------------------------------------------------------------- users
def upsert_google_user(claims: dict[str, Any]) -> User:
    now = datetime.now(timezone.utc)
    with session_scope() as session:
        user = session.query(User).filter_by(google_sub=str(claims["sub"])).one_or_none()
        if user is None:
            user = User(google_sub=str(claims["sub"]), is_demo=False)
            session.add(user)
        user.email = str(claims["email"])[:254]
        user.name = str(claims.get("name") or claims["email"].split("@")[0])[:120]
        picture = claims.get("picture")
        user.picture = str(picture)[:500] if picture else None
        user.last_login_at = now
        session.flush()
        if session.get(UserPreference, user.id) is None:
            session.add(UserPreference(user_id=user.id))
        session.flush()
        session.expunge(user)
        return user


def create_demo_user() -> User:
    with session_scope() as session:
        user = User(is_demo=True, name="Demo traveller", email=None)
        session.add(user)
        session.flush()
        session.add(UserPreference(user_id=user.id, notifications_enabled=False))
        session.flush()
        session.expunge(user)
        return user


def _load(user_id: str) -> CurrentUser | None:
    with session_scope() as session:
        user = session.get(User, user_id)
        if user is None:
            return None
        return CurrentUser(id=user.id, email=user.email, name=user.name, picture=user.picture, is_demo=user.is_demo)


# ---------------------------------------------------------------------------- dependencies
def optional_user(request: Request) -> CurrentUser | None:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    claims = read_session(token, settings)
    if claims is None:
        return None
    return _load(str(claims["sub"]))


def require_user(request: Request) -> CurrentUser:
    user = optional_user(request)
    if user is None:
        raise AuthRequiredError("Please sign in to continue.")
    return user


def mission_user(request: Request) -> CurrentUser | None:
    """For mission creation: a session is required unless AUTH_REQUIRED=false."""
    if get_settings().auth_required:
        return require_user(request)
    return optional_user(request)
