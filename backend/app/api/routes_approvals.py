from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import require_roles
from app.models import OrderApproval, User
from app.schemas import ApprovalDecisionRequest, ApprovalRead, OrderRead


router = APIRouter(prefix="/api/approvals", tags=["approvals"])


@router.get("", response_model=list[ApprovalRead])
def list_approvals(
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("admin", "approver", "trader")),
) -> list[ApprovalRead]:
    approvals = session.exec(select(OrderApproval).order_by(OrderApproval.requested_at.desc())).all()
    return [ApprovalRead(**approval.model_dump()) for approval in approvals]


@router.post("/{approval_id}/approve", response_model=OrderRead)
async def approve_order(
    approval_id: int,
    payload: ApprovalDecisionRequest,
    request: Request,
    session: Session = Depends(get_session),
    reviewer: User = Depends(require_roles("admin", "approver")),
) -> OrderRead:
    container = request.app.state.container
    order = await container.executor.approve_order(
        session=session,
        approval_id=approval_id,
        reviewer=reviewer.username,
        adapter=container.adapter,
        config=container.config_service.get_runtime_config(),
        metrics_summary=container.metrics_service.get_summary(),
        comment=payload.comment,
    )
    return OrderRead(**order.model_dump())


@router.post("/{approval_id}/reject", response_model=ApprovalRead)
def reject_order(
    approval_id: int,
    payload: ApprovalDecisionRequest,
    request: Request,
    session: Session = Depends(get_session),
    reviewer: User = Depends(require_roles("admin", "approver")),
) -> ApprovalRead:
    approval = request.app.state.container.executor.reject_order(
        session=session,
        approval_id=approval_id,
        reviewer=reviewer.username,
        comment=payload.comment,
    )
    return ApprovalRead(**approval.model_dump())
