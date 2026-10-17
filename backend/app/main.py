"""TripMission API — FastAPI application factory."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import asyncio
from pathlib import Path

from app.api.routes import auth, me, meta, missions, notifications, search
from app.core.cache import init_cache
from app.core.config import get_settings
from app.core.database import init_db, session_scope
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger, request_id_var
from app.integrations.serpapi.client import (SerpApiAuthError, SerpApiError, SerpApiQuotaError,
                                             SerpApiRateLimitError, SerpApiTimeoutError, public_message)
from app.repositories.mission_repository import MissionRepository

log = get_logger("app")


def _error(status: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    body = {"code": code, "message": message, "details": details or {}}
    if get_settings().debug_mode:  # request IDs are support/debug information only
        body["request_id"] = request_id_var.get()
    return JSONResponse(status_code=status, content={"error": body})


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level, settings.secret_values())
    init_db()
    await init_cache(settings.redis_url)
    with session_scope() as session:
        interrupted = MissionRepository(session).fail_interrupted()
    log.info("startup", extra={"context": {
        "demo_mode": settings.demo_mode, "serpapi_configured": settings.serpapi_configured,
        "ai_configured": settings.ai_configured, "database": settings.database_kind, "interrupted": interrupted}})
    if not settings.demo_mode and not settings.serpapi_configured:
        log.warning("SERPAPI_API_KEY is not set and DEMO_MODE=false — analyses will return setup_required")
    from app.services.notifications import reminder_loop

    reminders = asyncio.create_task(reminder_loop(settings.reminder_check_interval_seconds))
    yield
    reminders.cancel()
    from app.services.providers import _serp_client
    if _serp_client is not None:
        await _serp_client.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="TripMission API", version=settings.version, lifespan=lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,  # the session is an HttpOnly cookie; origins are an explicit allow-list
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        token = request_id_var.set(rid[:64])
        try:
            length = request.headers.get("content-length")
            if length and length.isdigit() and int(length) > settings.max_request_bytes:
                return _error(413, "payload_too_large", "Request body is too large.")
            # CSRF defence in depth (the cookie is SameSite=Lax): state-changing requests from a browser
            # must come from an allowed origin.
            origin = request.headers.get("origin")
            if (request.method in ("POST", "PUT", "DELETE") and origin
                    and origin.rstrip("/") not in settings.cors_origins
                    and origin.rstrip("/") != str(request.base_url).rstrip("/")):
                return _error(403, "forbidden_origin", "This request isn't allowed from that site.")
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid[:64]
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response
        finally:
            request_id_var.reset(token)

    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError):
        return _error(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(SerpApiError)
    async def serpapi_error(_: Request, exc: SerpApiError):
        status = 504 if isinstance(exc, SerpApiTimeoutError) else 503 if isinstance(
            exc, (SerpApiAuthError, SerpApiQuotaError, SerpApiRateLimitError)) else 502
        return _error(status, exc.code, public_message(exc, get_settings().debug_mode))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        fields = []
        for err in exc.errors():
            loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query")]
            message = str(err.get("msg", "Invalid value")).removeprefix("Value error, ")
            fields.append({"field": ".".join(loc) or None, "message": message})
        first = fields[0]["message"] if fields else "Invalid request."
        return _error(422, "validation_error", first, {"fields": fields})

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        log.exception("unhandled error")
        return _error(500, "internal_error", "Something went wrong on our side. Please try again.")

    for router in (meta.router, auth.router, me.router, missions.router, search.router, notifications.router):
        app.include_router(router, prefix="/api/v1")
    _serve_frontend(app, Path(settings.static_dir))
    return app


def _serve_frontend(app: FastAPI, static: Path) -> None:
    """Single-process deployments: serve the built React app (frontend/dist copied to STATIC_DIR) from the API's
    origin, so the session cookie and /api calls need no CORS. Registered after the API routes, which always win."""
    index = static / "index.html"
    if not index.is_file():
        return
    root = static.resolve()
    if (static / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path == "api" or path.startswith("api/"):
            return _error(404, "not_found", "Not found.")
        candidate = (static / path).resolve()
        if path and candidate.is_file() and root in candidate.parents:
            return FileResponse(candidate)
        # client-side routes (/plan, /results/…) all load the app shell; never cache it so deploys show up at once
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


app = create_app()
