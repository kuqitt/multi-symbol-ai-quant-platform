from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from app.config import AppConfig
from app.models import Position, RiskEvent, Trade
from app.state import RiskStatus, RuntimeState, StrategyRuntimeStatus


@dataclass
class TradeIntent:
    symbol: str
    side: str
    quantity: float
    expected_price: float
    order_type: str
    signal_id: str
    strategy_name: str
    stop_loss: float | None = None
    take_profit: float | None = None


@dataclass
class RiskCheckResult:
    allowed: bool
    reason: str
    adjusted_quantity: float
    details: dict[str, Any]


class RiskManager:
    def __init__(self, state: RuntimeState, logger: Any) -> None:
        self.state = state
        self.logger = logger

    def _record_event(
        self,
        session: Session,
        *,
        level: str,
        symbol: str,
        reason: str,
        detail: str,
        blocked: bool,
        protect_mode: bool = False,
        strategy_name: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        event = RiskEvent(
            level=level,
            symbol=symbol,
            strategy_name=strategy_name,
            reason=reason,
            detail=detail,
            blocked=blocked,
            status_after=self.state.status.value,
            metadata_json=metadata,
        )
        session.add(event)
        session.commit()
        self.state.push_alert(level, "risk", f"{symbol}: {reason}", symbol=symbol)
        self.logger.warning(
            "风控事件 %s | %s",
            reason,
            detail,
            extra={"category": "risk", "metadata_json": {"symbol": symbol, "reason": reason}},
        )
        if protect_mode:
            self.state.set_status(StrategyRuntimeStatus.PROTECT_MODE)
            self.state.set_risk_status(RiskStatus.PROTECT_MODE, reason)

    def _consecutive_losses(self, session: Session) -> int:
        trades = session.exec(select(Trade).order_by(Trade.timestamp.desc()).limit(20)).all()
        streak = 0
        for trade in trades:
            if trade.realized_pnl < 0:
                streak += 1
            elif trade.realized_pnl > 0:
                break
        return streak

    async def evaluate(
        self,
        session: Session,
        config: AppConfig,
        intent: TradeIntent,
        adapter: Any,
        metrics_summary: dict[str, Any],
    ) -> RiskCheckResult:
        if config.env == "live" and not self.state.live_enabled:
            self._record_event(
                session,
                level="CRITICAL",
                symbol=intent.symbol,
                strategy_name=intent.strategy_name,
                reason="live-trading-disabled",
                detail="当前未开启实盘总开关，所有实盘订单都会被拦截",
                blocked=True,
                protect_mode=True,
            )
            return RiskCheckResult(False, "live-trading-disabled", 0.0, {})

        if self.state.status in {StrategyRuntimeStatus.PROTECT_MODE, StrategyRuntimeStatus.STOPPED}:
            return RiskCheckResult(False, f"strategy-status-{self.state.status.value.lower()}", 0.0, {})
        if self.state.risk_status != RiskStatus.NORMAL:
            return RiskCheckResult(False, f"risk-status-{self.state.risk_status.value.lower()}", 0.0, {})
        if not self.state.network_healthy or not self.state.exchange_available:
            self._record_event(
                session,
                level="ERROR",
                symbol=intent.symbol,
                strategy_name=intent.strategy_name,
                reason="exchange-unavailable",
                detail="网络状态或交易所健康检查异常，暂停下单并进入保护流程",
                blocked=True,
                protect_mode=True,
            )
            return RiskCheckResult(False, "exchange-unavailable", 0.0, {})
        if not self.state.state_consistent:
            self._record_event(
                session,
                level="CRITICAL",
                symbol=intent.symbol,
                strategy_name=intent.strategy_name,
                reason="state-mismatch",
                detail="检测到账户持仓状态不一致，已阻止继续交易",
                blocked=True,
                protect_mode=True,
            )
            return RiskCheckResult(False, "state-mismatch", 0.0, {})

        orderbook = await adapter.fetch_orderbook(intent.symbol)
        spread_limit = config.risk.max_spread
        slippage_limit = config.risk.max_slippage
        if config.env == "paper":
            spread_limit *= config.simulation.max_spread_multiplier
            slippage_limit *= config.simulation.max_slippage_multiplier
        spread = (orderbook.asks[0][0] - orderbook.bids[0][0]) / intent.expected_price if intent.expected_price else 0.0
        if spread > spread_limit:
            self._record_event(
                session,
                level="WARNING",
                symbol=intent.symbol,
                strategy_name=intent.strategy_name,
                reason="spread-too-wide",
                detail=f"当前点差 {spread:.6f}，超过阈值 {spread_limit:.6f}",
                blocked=True,
                metadata={"spread": spread},
            )
            return RiskCheckResult(False, "spread-too-wide", 0.0, {"spread": spread})

        reference_price = orderbook.asks[0][0] if intent.side == "BUY" else orderbook.bids[0][0]
        slippage = abs(reference_price - intent.expected_price) / intent.expected_price if intent.expected_price else 0.0
        if slippage > slippage_limit:
            self._record_event(
                session,
                level="WARNING",
                symbol=intent.symbol,
                strategy_name=intent.strategy_name,
                reason="slippage-too-high",
                detail=f"当前滑点 {slippage:.6f}，超过阈值 {slippage_limit:.6f}",
                blocked=True,
                metadata={"slippage": slippage},
            )
            return RiskCheckResult(False, "slippage-too-high", 0.0, {"slippage": slippage})

        equity = metrics_summary["equity"]
        daily_pnl = metrics_summary["daily_pnl"]
        if daily_pnl <= -(equity * config.risk.max_daily_loss):
            self._record_event(
                session,
                level="ERROR",
                symbol=intent.symbol,
                strategy_name=intent.strategy_name,
                reason="daily-loss-limit-hit",
                detail=f"当日盈亏 {daily_pnl:.2f}，已触发最大日亏损限制 {config.risk.max_daily_loss:.4f}",
                blocked=True,
                protect_mode=True,
            )
            return RiskCheckResult(False, "daily-loss-limit-hit", 0.0, {})

        if self._consecutive_losses(session) >= config.risk.max_consecutive_losses:
            self._record_event(
                session,
                level="ERROR",
                symbol=intent.symbol,
                strategy_name=intent.strategy_name,
                reason="consecutive-loss-limit-hit",
                detail=f"连续亏损次数已达到上限 {config.risk.max_consecutive_losses}",
                blocked=True,
                protect_mode=True,
            )
            return RiskCheckResult(False, "consecutive-loss-limit-hit", 0.0, {})

        position = session.exec(select(Position).where(Position.symbol == intent.symbol)).first()
        current_symbol_exposure = position.market_value if position else 0.0
        total_exposure = sum(item.market_value for item in session.exec(select(Position)).all())
        current_strategy_exposure = sum(
            item.market_value for item in session.exec(select(Position)).all() if item.strategy_name == intent.strategy_name
        )
        desired_notional = intent.quantity * intent.expected_price

        if intent.side == "BUY":
            next_symbol_exposure = current_symbol_exposure + desired_notional
            next_total_exposure = total_exposure + desired_notional
            next_strategy_exposure = current_strategy_exposure + desired_notional
        else:
            next_symbol_exposure = max(current_symbol_exposure - desired_notional, 0.0)
            next_total_exposure = max(total_exposure - desired_notional, 0.0)
            next_strategy_exposure = max(current_strategy_exposure - desired_notional, 0.0)

        if position and position.quantity > 0 and position.unrealized_pnl < 0 and intent.side == "BUY":
            self._record_event(
                session,
                level="WARNING",
                symbol=intent.symbol,
                strategy_name=intent.strategy_name,
                reason="martingale-blocked",
                detail="当前持仓处于亏损状态，禁止继续加仓",
                blocked=True,
            )
            return RiskCheckResult(False, "martingale-blocked", 0.0, {})

        if intent.side == "SELL" and (position is None or position.quantity <= 0):
            self._record_event(
                session,
                level="WARNING",
                symbol=intent.symbol,
                strategy_name=intent.strategy_name,
                reason="no-position-to-sell",
                detail="现货模式下只能卖出已有持仓",
                blocked=True,
            )
            return RiskCheckResult(False, "no-position-to-sell", 0.0, {})

        if next_symbol_exposure > equity * config.risk.max_symbol_exposure:
            self._record_event(
                session,
                level="WARNING",
                symbol=intent.symbol,
                strategy_name=intent.strategy_name,
                reason="symbol-exposure-limit-hit",
                detail=f"该交易对下一步风险敞口 {next_symbol_exposure:.2f} 已超过限制",
                blocked=True,
            )
            return RiskCheckResult(False, "symbol-exposure-limit-hit", 0.0, {})

        if next_total_exposure > equity * config.risk.max_total_exposure:
            self._record_event(
                session,
                level="WARNING",
                symbol=intent.symbol,
                strategy_name=intent.strategy_name,
                reason="total-exposure-limit-hit",
                detail=f"组合总风险敞口 {next_total_exposure:.2f} 已超过限制",
                blocked=True,
            )
            return RiskCheckResult(False, "total-exposure-limit-hit", 0.0, {})

        if next_strategy_exposure > equity * config.risk.max_strategy_exposure:
            self._record_event(
                session,
                level="WARNING",
                symbol=intent.symbol,
                strategy_name=intent.strategy_name,
                reason="strategy-exposure-limit-hit",
                detail=f"当前策略风险敞口 {next_strategy_exposure:.2f} 已超过限制",
                blocked=True,
            )
            return RiskCheckResult(False, "strategy-exposure-limit-hit", 0.0, {})

        max_risk_amount = equity * config.risk.risk_per_trade
        adjusted_quantity = intent.quantity
        portfolio_heat = 0.0
        if intent.stop_loss is not None and intent.side == "BUY":
            per_unit_risk = max(intent.expected_price - intent.stop_loss, 0.0)
            if per_unit_risk > 0:
                max_qty = max_risk_amount / per_unit_risk
                adjusted_quantity = min(intent.quantity, max_qty)
                open_risk = sum(
                    max(item.avg_price - item.market_price, 0.0) * item.quantity
                    for item in session.exec(select(Position)).all()
                )
                portfolio_heat = (open_risk + adjusted_quantity * per_unit_risk) / equity if equity else 0.0
        if adjusted_quantity <= 0:
            return RiskCheckResult(False, "zero-quantity-after-risk-sizing", 0.0, {})

        if portfolio_heat > config.risk.max_portfolio_heat:
            self._record_event(
                session,
                level="WARNING",
                symbol=intent.symbol,
                strategy_name=intent.strategy_name,
                reason="portfolio-heat-limit-hit",
                detail=f"组合热度 {portfolio_heat:.6f} 已超过阈值 {config.risk.max_portfolio_heat:.6f}",
                blocked=True,
                metadata={"portfolio_heat": portfolio_heat},
            )
            return RiskCheckResult(False, "portfolio-heat-limit-hit", 0.0, {})

        return RiskCheckResult(
            allowed=True,
            reason="approved",
            adjusted_quantity=adjusted_quantity,
            details={
                "spread": spread,
                "slippage": slippage,
                "portfolio_heat": portfolio_heat,
                "approved_at": datetime.utcnow().isoformat(),
            },
        )
