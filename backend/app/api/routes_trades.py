from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.dependencies import require_roles
from app.models import User
from app.schemas import TradeRead


router = APIRouter(prefix="/api", tags=["trades"])


@router.get("/trades", response_model=list[TradeRead])
def get_trades(
    request: Request,
    _: User = Depends(require_roles("admin", "trader", "viewer", "approver")),
) -> list[TradeRead]:
    trades = request.app.state.container.metrics_service.list_trades()
    return [TradeRead(**item.model_dump()) for item in trades]
