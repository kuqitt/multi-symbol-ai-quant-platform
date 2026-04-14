from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.dependencies import require_roles
from app.models import User
from app.schemas import OrderRead


router = APIRouter(prefix="/api", tags=["orders"])


@router.get("/orders", response_model=list[OrderRead])
def get_orders(
    request: Request,
    _: User = Depends(require_roles("admin", "trader", "viewer", "approver")),
) -> list[OrderRead]:
    orders = request.app.state.container.metrics_service.list_orders()
    return [OrderRead(**item.model_dump()) for item in orders]
