from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models import Order, OrderApproval, Position, Trade
from app.risk_manager import RiskManager, TradeIntent
from app.strategy import SignalType, StrategyDecision


class ExecutionService:
    def __init__(
        self,
        risk_manager: RiskManager,
        portfolio_service: object,
        approval_service: object,
        notifier: object,
        logger: object,
    ) -> None:
        self.risk_manager = risk_manager
        self.portfolio_service = portfolio_service
        self.approval_service = approval_service
        self.notifier = notifier
        self.logger = logger

    def _build_quantity(self, config: object, equity: float, price: float, stop_loss: float | None) -> float:
        risk_budget = equity * config.risk.risk_per_trade
        max_notional = equity * min(config.risk.max_symbol_exposure, config.risk.max_total_exposure)
        if stop_loss is not None and stop_loss < price:
            unit_risk = max(price - stop_loss, price * 0.002)
            quantity = max(risk_budget / unit_risk, 0.0)
        else:
            quantity = max((equity * min(config.risk.max_symbol_exposure, 0.1)) / price, 0.0)
        exposure_capped_quantity = max_notional / price if price else 0.0
        return min(quantity, exposure_capped_quantity)

    def _apply_decision_sizing(self, quantity: float, decision: StrategyDecision, price: float, equity: float, config: object) -> float:
        reason_context = decision.reason_context or {}
        desired_notional = reason_context.get("desired_notional")
        size_multiplier = reason_context.get("size_multiplier")
        exposure_cap = equity * min(config.risk.max_symbol_exposure, config.risk.max_total_exposure)

        if isinstance(desired_notional, (int, float)) and desired_notional > 0 and price > 0:
            quantity = min(float(desired_notional) / price, exposure_cap / price)
        elif isinstance(size_multiplier, (int, float)) and size_multiplier > 0:
            quantity *= float(size_multiplier)
            quantity = min(quantity, exposure_cap / price if price else quantity)
        return max(quantity, 0.0)

    def _decision_snapshot(self, decision: StrategyDecision) -> dict:
        context = decision.reason_context or {}
        cost = context.get("cost") or {}
        return {
            "reason": decision.reason,
            "reason_context": context,
            "confidence": decision.confidence,
            "contributors": decision.contributors,
            "stop_loss": decision.stop_loss,
            "take_profit": decision.take_profit,
            "regime": context.get("regime", "unknown"),
            "signal_score": context.get("signal_score", 0.0),
            "target_weight": context.get("target_weight", 0.0),
            "desired_notional": context.get("desired_notional", 0.0),
            "expected_cost_bps": cost.get("total_cost_bps", 0.0),
            "expected_slippage_bps": cost.get("slippage_bps", 0.0),
            "fee_bps": cost.get("fee_bps", 0.0),
            "entry_tag": decision.reason,
            "exit_tag": decision.reason if decision.signal == SignalType.SELL else "",
        }

    async def _submit_to_adapter(
        self,
        *,
        session: Session,
        config: object,
        adapter: object,
        order: Order,
        decision: StrategyDecision,
        metrics_summary: dict[str, float],
    ) -> Order:
        adapter_result = None
        last_error: Exception | None = None
        for _ in range(config.execution.retry_count + 1):
            try:
                adapter_result = await adapter.place_order(
                    client_order_id=order.client_order_id,
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    order_type=order.order_type,
                    price=order.price if order.order_type == "limit" else None,
                )
                break
            except Exception as exc:
                last_error = exc
        if adapter_result is None:
            order.status = "ERROR"
            order.risk_reason = f"adapter-error:{last_error}"
            order.updated_at = datetime.utcnow()
            session.add(order)
            session.commit()
            return order

        order.status = adapter_result.status
        order.average_fill_price = adapter_result.fill_price
        order.metadata_json = {**(order.metadata_json or {}), "adapter_result": adapter_result.raw}
        order.updated_at = datetime.utcnow()
        session.add(order)
        session.commit()
        session.refresh(order)

        if adapter_result.status == "FILLED":
            decision_snapshot = self._decision_snapshot(decision)
            realized_pnl = self.portfolio_service.apply_fill(
                session=session,
                symbol=decision.symbol,
                side=order.side,
                quantity=adapter_result.filled_quantity,
                price=adapter_result.fill_price,
                equity=metrics_summary["equity"],
                strategy_name=order.strategy_name,
                metadata=decision_snapshot,
            )
            trade = Trade(
                order_id=order.id,
                client_order_id=order.client_order_id,
                symbol=decision.symbol,
                side=order.side,
                strategy_name=order.strategy_name,
                quantity=adapter_result.filled_quantity,
                price=adapter_result.fill_price,
                fee=adapter_result.fill_price * adapter_result.filled_quantity * 0.0004,
                realized_pnl=realized_pnl if order.side == "SELL" else 0.0,
                regime=order.regime,
                entry_tag=decision_snapshot["entry_tag"] if order.side == "BUY" else "",
                exit_tag=decision_snapshot["exit_tag"] if order.side == "SELL" else "",
                signal_score=float(order.signal_score or 0.0),
                expected_cost_bps=float(order.expected_cost_bps or 0.0),
                slippage_bps=float(order.expected_slippage_bps or 0.0),
                fee_bps=float(decision_snapshot["fee_bps"] or 0.0),
                metadata_json=decision_snapshot,
            )
            session.add(trade)
            session.commit()
            self.logger.info(
                "订单已成交 %s %s 数量=%.6f 成交价=%.6f 策略=%s",
                decision.symbol,
                order.side,
                adapter_result.filled_quantity,
                adapter_result.fill_price,
                order.strategy_name,
                extra={"category": "execution"},
            )
        return order

    async def execute_signal(
        self,
        session: Session,
        config: object,
        adapter: object,
        decision: StrategyDecision,
        metrics_summary: dict[str, float],
        requested_by: str = "system",
    ) -> Order | None:
        if decision.signal == SignalType.HOLD:
            return None

        existing = session.exec(select(Order).where(Order.signal_id == decision.signal_id)).first()
        if existing:
            return existing

        side = decision.signal.value
        quantity = self._build_quantity(config, metrics_summary["equity"], decision.price, decision.stop_loss)
        quantity = self._apply_decision_sizing(quantity, decision, decision.price, metrics_summary["equity"], config)
        if side == SignalType.SELL.value:
            current_position = session.exec(select(Position).where(Position.symbol == decision.symbol)).first()
            quantity = max(current_position.quantity if current_position else 0.0, 0.0)
        intent = TradeIntent(
            symbol=decision.symbol,
            side=side,
            quantity=quantity,
            expected_price=decision.price,
            order_type=config.execution.order_type,
            signal_id=decision.signal_id,
            strategy_name=decision.strategy_name,
            stop_loss=decision.stop_loss,
            take_profit=decision.take_profit,
        )
        risk_result = await self.risk_manager.evaluate(session, config, intent, adapter, metrics_summary)
        client_order_id = f"{decision.symbol.replace('/', '')}-{uuid4().hex[:14]}"
        decision_snapshot = self._decision_snapshot(decision)
        order = Order(
            client_order_id=client_order_id,
            signal_id=decision.signal_id,
            strategy_name=decision.strategy_name,
            symbol=decision.symbol,
            side=side,
            order_type=config.execution.order_type,
            status="REJECTED" if not risk_result.allowed else "NEW",
            quantity=risk_result.adjusted_quantity,
            price=decision.price,
            expected_price=decision.price,
            risk_checked=True,
            risk_reason=risk_result.reason,
            decision_reason=decision.reason,
            regime=str(decision_snapshot["regime"]),
            signal_score=float(decision_snapshot["signal_score"] or 0.0),
            target_weight=float(decision_snapshot["target_weight"] or 0.0),
            expected_cost_bps=float(decision_snapshot["expected_cost_bps"] or 0.0),
            expected_slippage_bps=float(decision_snapshot["expected_slippage_bps"] or 0.0),
            env=config.env,
            is_live=config.env == "live",
            requested_by=requested_by,
            requested_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata_json={
                **decision_snapshot,
                "risk_details": risk_result.details,
            },
        )
        session.add(order)
        session.commit()
        session.refresh(order)

        if not risk_result.allowed:
            return order

        requires_approval, approval_reason = self.approval_service.should_require_approval(
            config=config,
            notional=order.quantity * order.expected_price,
            is_live=order.is_live,
            total_equity=metrics_summary["equity"],
        )
        if requires_approval:
            order.status = "PENDING_APPROVAL"
            order.risk_reason = approval_reason
            order.updated_at = datetime.utcnow()
            session.add(order)
            session.commit()
            await self.approval_service.create_approval_request(
                session,
                order=order,
                requested_by=requested_by,
                reason=approval_reason,
                payload={
                    "client_order_id": order.client_order_id,
                    "symbol": order.symbol,
                    "side": order.side,
                    "quantity": order.quantity,
                    "order_type": order.order_type,
                    "price": order.price,
                    "strategy_name": order.strategy_name,
                },
            )
            return order

        return await self._submit_to_adapter(
            session=session,
            config=config,
            adapter=adapter,
            order=order,
            decision=decision,
            metrics_summary=metrics_summary,
        )

    async def approve_order(
        self,
        *,
        session: Session,
        approval_id: int,
        reviewer: str,
        adapter: object,
        config: object,
        metrics_summary: dict[str, float],
        comment: str,
    ) -> Order:
        approval = session.get(OrderApproval, approval_id)
        if approval is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到对应的审批请求")
        self.approval_service.validate_pending(approval)
        order = session.get(Order, approval.order_id)
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="审批关联的订单不存在")
        approval.status = "APPROVED"
        approval.reviewed_by = reviewer
        approval.reviewed_at = datetime.utcnow()
        session.add(approval)
        session.commit()
        decision = StrategyDecision(
            symbol=order.symbol,
            signal=SignalType(order.side),
            price=order.expected_price,
            stop_loss=(order.metadata_json or {}).get("stop_loss"),
            take_profit=(order.metadata_json or {}).get("take_profit"),
            reason=(order.metadata_json or {}).get("reason", "approved"),
            strategy_name=order.strategy_name,
            confidence=float((order.metadata_json or {}).get("confidence", 0.0)),
            signal_id=order.signal_id,
            reason_context=(order.metadata_json or {}).get("reason_context", {}),
            contributors=(order.metadata_json or {}).get("contributors", []),
        )
        if comment:
            order.metadata_json = {**(order.metadata_json or {}), "approval_comment": comment}
        return await self._submit_to_adapter(
            session=session,
            config=config,
            adapter=adapter,
            order=order,
            decision=decision,
            metrics_summary=metrics_summary,
        )

    def reject_order(self, *, session: Session, approval_id: int, reviewer: str, comment: str) -> OrderApproval:
        approval = session.get(OrderApproval, approval_id)
        if approval is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到对应的审批请求")
        self.approval_service.validate_pending(approval)
        return self.approval_service.mark_rejected(session, approval, reviewer, comment)
