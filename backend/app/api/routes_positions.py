from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.dependencies import require_roles
from app.models import User
from app.schemas import PositionRead


router = APIRouter(prefix="/api", tags=["positions"])


@router.get("/positions", response_model=list[PositionRead])
def get_positions(
    request: Request,
    _: User = Depends(require_roles("admin", "trader", "viewer", "approver")),
) -> list[PositionRead]:
    positions = request.app.state.container.metrics_service.list_positions()
    return [PositionRead(**item.model_dump()) for item in positions]
