from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.dependencies import require_roles
from app.models import User
from app.schemas import StatusResponse


router = APIRouter(prefix="/api", tags=["status"])


@router.get("/status", response_model=StatusResponse)
def get_status(
    request: Request,
    _: User = Depends(require_roles("admin", "trader", "viewer", "approver")),
) -> StatusResponse:
    container = request.app.state.container
    return StatusResponse(**container.state.to_dict())
