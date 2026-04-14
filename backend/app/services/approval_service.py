from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session

from app.models import Order, OrderApproval


class ApprovalService:
    def __init__(self, config_service: Any, notifier: Any, logger: Any) -> None:
        self.config_service = config_service
        self.notifier = notifier
        self.logger = logger

    def should_require_approval(
        self,
        *,
        config: Any,
        notional: float,
        is_live: bool,
        total_equity: float,
    ) -> tuple[bool, str]:
        if not config.approval.enabled:
            return False, ""
        if (
            config.approval.auto_approve_small_accounts
            and config.approval.auto_approve_below_equity > 0
            and total_equity < config.approval.auto_approve_below_equity
        ):
            return False, ""
        if is_live and config.approval.require_manual_approval_for_live:
            return True, "live-order-requires-approval"
        if (
            config.approval.require_manual_approval_for_large_orders
            and notional >= config.approval.approval_min_notional
        ):
            return True, "large-order-requires-approval"
        return False, ""

    async def create_approval_request(
        self,
        session: Session,
        *,
        order: Order,
        payload: dict[str, Any],
        requested_by: str,
        reason: str,
    ) -> OrderApproval:
        config = self.config_service.get_runtime_config()
        approval = OrderApproval(
            order_id=order.id,
            signal_id=order.signal_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            expected_price=order.expected_price,
            notional=order.quantity * order.expected_price,
            status="PENDING",
            reason=reason,
            requested_by=requested_by,
            requested_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(seconds=config.approval.approval_timeout_seconds),
            request_payload=payload,
        )
        session.add(approval)
        session.commit()
        session.refresh(approval)
        await self.notifier.send_approval_request(
            config,
            {
                "id": approval.id,
                "symbol": approval.symbol,
                "side": approval.side,
                "notional": approval.notional,
            },
        )
        return approval

    def mark_rejected(self, session: Session, approval: OrderApproval, reviewer: str, comment: str) -> OrderApproval:
        approval.status = "REJECTED"
        approval.reviewed_by = reviewer
        approval.reviewed_at = datetime.utcnow()
        session.add(approval)
        if approval.order_id:
            order = session.get(Order, approval.order_id)
            if order:
                order.status = "REJECTED"
                order.risk_reason = f"manual-rejection:{comment}".strip(":")
                order.updated_at = datetime.utcnow()
                session.add(order)
        session.commit()
        return approval

    def validate_pending(self, approval: OrderApproval) -> None:
        if approval.status != "PENDING":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该审批单当前不是待处理状态")
        if approval.expires_at and approval.expires_at < datetime.utcnow():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该审批单已过期")
