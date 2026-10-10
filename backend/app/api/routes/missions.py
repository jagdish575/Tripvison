from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status

from app.core.config import get_settings
from app.core.rate_limit import client_key, limiter
from app.schemas.mission import MissionCreated, MissionRequest, MissionStatus
from app.services.auth import CurrentUser, mission_user, optional_user
from app.services.mission_service import MissionService

router = APIRouter(prefix="/missions", tags=["missions"])


@router.post("/analyze", response_model=MissionCreated, status_code=status.HTTP_202_ACCEPTED)
async def analyze_mission(payload: MissionRequest, request: Request,
                          wait: bool = Query(False, description="Block until the analysis finishes"),
                          user: CurrentUser | None = Depends(mission_user)) -> MissionCreated:
    limiter.check("analyze", client_key(request), get_settings().analyze_rate_limit_per_minute)
    return await MissionService().start(payload, wait=wait, user=user)


@router.get("/{mission_id}", response_model=MissionStatus)
def get_mission(mission_id: str, user: CurrentUser | None = Depends(optional_user)) -> MissionStatus:
    return MissionService().status(mission_id, user)


@router.get("/{mission_id}/recommendations")
def get_recommendations(mission_id: str, user: CurrentUser | None = Depends(optional_user)) -> dict[str, Any]:
    return MissionService().result(mission_id, user)
