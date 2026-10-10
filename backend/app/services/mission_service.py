"""Mission lifecycle: validate → resolve places → persist → analyse in the background → persist results.

Every mission belongs to the user who created it; reads are owner-only. Demo sessions always use the
labelled demo dataset."""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import Settings, get_settings
from app.core.database import session_scope
from app.core.errors import AppError, NotFoundError, NotReadyError, ValidationAppError
from app.core.logging import get_logger
from app.demo.provider import SCENARIOS, DemoProvider, DemoRouteUnsupported
from app.engines.mission_engine import STAGES, MissionEngine, resolve_locations
from app.integrations.serpapi.client import SerpApiError, public_message
from app.models import Mission
from app.repositories.mission_repository import MissionRepository
from app.schemas.mission import MissionCreated, MissionRequest, MissionStatus
from app.schemas.travel import ResolvedLocation
from app.services.auth import AuthRequiredError, CurrentUser
from app.services.providers import TravelDataProvider, get_provider

log = get_logger(__name__)

_running: set[asyncio.Task[Any]] = set()


def check_access(mission: Mission | None, user: CurrentUser | None, settings: Settings) -> Mission:
    """Owner-only access. Unknown, other people's and pre-sign-in (owner-less) missions all look 'not found'."""
    if mission is None:
        raise NotFoundError("We couldn't find that mission.")
    if mission.user_id is None and not settings.auth_required:
        return mission
    if user is None:
        raise AuthRequiredError("Please sign in to view this mission.")
    if mission.user_id != user.id:
        raise NotFoundError("We couldn't find that mission.")
    return mission


def public_result(result: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Strip developer diagnostics (request counts, provider calls, raw errors) unless DEBUG_MODE=true."""
    if settings.debug_mode:
        return result
    out = dict(result)
    sources = dict(out.get("data_sources") or {})
    for key in ("calls", "live_calls", "cache_hits"):
        sources[key] = None
    out["data_sources"] = sources
    out["diagnostics"] = None
    return out


class MissionService:
    def __init__(self, settings: Settings | None = None, provider: TravelDataProvider | None = None) -> None:
        self.settings = settings or get_settings()
        self._provider = provider

    def provider(self, user: CurrentUser | None = None) -> TravelDataProvider:
        if self._provider is not None:
            return self._provider
        if user is not None and user.is_demo:
            return DemoProvider()
        return get_provider(self.settings)

    # ------------------------------------------------------------------ create
    async def start(self, request: MissionRequest, *, wait: bool = False,
                    user: CurrentUser | None = None) -> MissionCreated:
        provider = self.provider(user)  # raises setup_required before anything is stored
        origin, destination = await resolve_locations(request, provider, self.settings)
        if not provider.supports_route(origin, destination):
            raise DemoRouteUnsupported(
                f"Demo mode includes these journeys: {'; '.join(SCENARIOS.values())}. "
                f"{origin.city} → {destination.city} isn't one of them — sign in with Google to plan it with live data.",
                details={"supported": list(SCENARIOS.values())})
        with session_scope() as session:
            mission = MissionRepository(session).create(
                request, mode=provider.mode, origin_code=origin.code, destination_code=destination.code,
                user_id=user.id if user else None)
            mission_id = mission.id
        log.info("mission created", extra={"context": {"mission_id": mission_id, "mode": provider.mode,
                                                        "route": f"{origin.city}-{destination.city}"}})
        task = asyncio.create_task(self.run(mission_id, request, provider, (origin, destination)))
        _running.add(task)
        task.add_done_callback(_running.discard)
        if wait:
            await task
        return MissionCreated(mission_id=mission_id, status="complete" if wait else "queued", mode=provider.mode)

    # ------------------------------------------------------------------ run
    async def run(self, mission_id: str, request: MissionRequest, provider: TravelDataProvider,
                  resolved: tuple[ResolvedLocation, ResolvedLocation] | None = None) -> None:
        progress: dict[str, Any] = {"stage": "resolve", "completed": [], "counts": {}, "message": "Starting"}

        async def on_progress(stage: str, message: str, counts: dict[str, Any]) -> None:
            # Stages run in order; every stage before the current one is complete (skipped ones included).
            progress["completed"] = list(STAGES[: STAGES.index(stage)])
            progress["stage"] = stage
            progress["message"] = message
            progress["counts"].update(counts)
            with session_scope() as session:
                MissionRepository(session).set_progress(mission_id, dict(progress))

        engine = MissionEngine(provider, self.settings, progress=on_progress)
        try:
            result = await engine.run(mission_id, request, resolved)
        except SerpApiError as exc:
            log.warning("mission failed (upstream)", extra={"context": {"mission_id": mission_id, "code": exc.code}})
            self._fail(mission_id, exc.code, public_message(exc, self.settings.debug_mode))
            return
        except AppError as exc:
            self._fail(mission_id, exc.code, exc.message)
            return
        except Exception:
            log.exception("mission failed (internal)", extra={"context": {"mission_id": mission_id}})
            self._fail(mission_id, "internal_error", "Something went wrong while planning this journey. Please try again.")
            return

        progress["completed"] = list(STAGES)
        progress["stage"] = "done"
        progress["message"] = "Analysis complete"
        with session_scope() as session:
            MissionRepository(session).complete(mission_id, result, engine.artifacts, dict(progress))
        if request.notifications is not None:
            from app.services.notifications import NotificationService

            await NotificationService(self.settings).on_mission_complete(mission_id)
        log.info("mission complete", extra={"context": {
            "mission_id": mission_id, "status": result.status, "live_calls": result.data_sources.live_calls,
            "cache_hits": result.data_sources.cache_hits, "itineraries": result.funnel.itineraries_scored}})

    async def recheck(self, mission_id: str, *, simulate_delay_minutes: int | None = None,
                      focus: dict[str, Any] | None = None) -> dict[str, Any]:
        """Re-run a completed mission with fresh data and store the new result. For demo missions a delay can
        be simulated on the journey in `focus` to demonstrate change alerts."""
        with session_scope() as session:
            mission = MissionRepository(session).get(mission_id)
            if mission is None:
                raise NotFoundError("We couldn't find that mission.")
            payload, old_result, mode = dict(mission.request or {}), mission.result or {}, mission.mode
        payload.pop("notifications", None)
        request = MissionRequest(**payload)
        provider = DemoProvider() if mode == "demo" else self.provider()
        if simulate_delay_minutes:
            if provider.mode != "demo":
                raise ValidationAppError("Simulated delays are only available in demo mode.", code="demo_only")
            from app.services.email.changes import recommended

            itin = recommended(old_result, focus["itinerary_id"] if focus else None) or {}
            keys = list((itin.get("flight") or {}).get("flight_numbers", [])[:1])
            if itin.get("transit"):
                keys.append(itin["transit"]["id"])
            provider = DemoProvider(delays={k: simulate_delay_minutes for k in keys})
        engine = MissionEngine(provider, self.settings)
        result = await engine.run(mission_id, request)
        progress = {"stage": "done", "completed": list(STAGES), "counts": {}, "message": "Re-checked"}
        with session_scope() as session:
            repo = MissionRepository(session)
            repo.reset_derived(mission_id)
            repo.complete(mission_id, result, engine.artifacts, progress)
        log.info("mission rechecked", extra={"context": {"mission_id": mission_id,
                                                          "simulated_delay": simulate_delay_minutes}})
        return result.model_dump(mode="json")

    @staticmethod
    def _fail(mission_id: str, code: str, message: str) -> None:
        with session_scope() as session:
            MissionRepository(session).fail(mission_id, code, message)

    # ------------------------------------------------------------------ read
    def status(self, mission_id: str, user: CurrentUser | None = None) -> MissionStatus:
        with session_scope() as session:
            mission = check_access(MissionRepository(session).get(mission_id), user, self.settings)
            return MissionStatus(mission_id=mission.id, status=mission.status, mode=mission.mode,
                                 progress=mission.progress or {}, input=mission.request or {}, error=mission.error,
                                 created_at=mission.created_at.isoformat())

    def result(self, mission_id: str, user: CurrentUser | None = None) -> dict[str, Any]:
        with session_scope() as session:
            mission = check_access(MissionRepository(session).get(mission_id), user, self.settings)
            if mission.status == "failed":
                error = mission.error or {}
                raise AppError(error.get("message", "This mission failed."), code=error.get("code", "mission_failed"),
                               status_code=409)
            if mission.status != "complete" or mission.result is None:
                raise NotReadyError("This mission is still being analysed.")
            return public_result(mission.result, self.settings)


def assert_owner(mission_id: str, user: CurrentUser | None, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    with session_scope() as session:
        check_access(MissionRepository(session).get(mission_id), user, settings)
