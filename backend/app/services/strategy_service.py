from __future__ import annotations

import asyncio
from datetime import datetime
from hashlib import md5
from typing import Any

import pandas as pd
from sqlmodel import Session, select

from app.ai_signal_provider import MockAISignalProvider
from app.cost_model import CostModel
from app.decision_engine import DecisionEngine
from app.models import Position, StrategyDecisionLog
from app.portfolio_allocator import PortfolioAllocator
from app.regime_detector import RegimeDetector
from app.signal_engine import SignalEngine
from app.strategy import SignalType, StrategyDecision
from app.strategy_orchestrator import StrategyOrchestrator


class StrategyService:
    def __init__(
        self,
        *,
        session_factory: Any,
        config_service: Any,
        state: Any,
        market_data_service: Any,
        metrics_service: Any,
        executor: Any,
        portfolio_service: Any,
        websocket_manager: Any,
        logger: Any,
    ) -> None:
        self.session_factory = session_factory
        self.config_service = config_service
        self.state = state
        self.market_data_service = market_data_service
        self.metrics_service = metrics_service
        self.executor = executor
        self.portfolio_service = portfolio_service
        self.websocket_manager = websocket_manager
        self.logger = logger
        self.orchestrator = StrategyOrchestrator()
        self.ai_provider = MockAISignalProvider()
        self.regime_detector = RegimeDetector()
        self.signal_engine = SignalEngine()
        self.portfolio_allocator = PortfolioAllocator()
        self.cost_model = CostModel()
        self.decision_engine = DecisionEngine()
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def _broadcast_status(self) -> None:
        await self.websocket_manager.broadcast("dashboard", {"type": "status", "status": self.state.to_dict()})

    def _load_position(self, session: Session, symbol: str) -> Position | None:
        position = session.exec(select(Position).where(Position.symbol == symbol)).first()
        if position and position.quantity > 0:
            return position
        return None

    def _build_exit_decision(self, symbol: str, price: float, reason: str) -> StrategyDecision:
        fingerprint = md5(f"{symbol}:{reason}:{datetime.utcnow().isoformat(timespec='seconds')}".encode("utf-8")).hexdigest()
        return StrategyDecision(
            symbol=symbol,
            signal=SignalType.SELL,
            price=price,
            stop_loss=None,
            take_profit=None,
            reason=reason,
            strategy_name="risk_exit",
            confidence=1.0,
            signal_id=fingerprint,
        )

    def _tracked_exit_reason(self, symbol: str, price: float) -> str | None:
        tracked = self.state.symbol_states.get(symbol, {})
        stop_loss = tracked.get("stop_loss")
        take_profit = tracked.get("take_profit")
        if stop_loss is not None and price <= float(stop_loss):
            return "stop-loss-triggered"
        if take_profit is not None and price >= float(take_profit):
            return "take-profit-triggered"
        return None

    def _update_symbol_watch(self, symbol: str, **payload: Any) -> None:
        self.state.update_symbol_state(symbol, **payload)

    def _record_decision(
        self,
        session: Session,
        *,
        symbol: str,
        config: Any,
        decision: StrategyDecision,
        regime: Any,
        signal_package: Any,
    ) -> None:
        context = decision.reason_context or {}
        session.add(
            StrategyDecisionLog(
                symbol=symbol,
                timeframe=config.timeframe,
                strategy_name=decision.strategy_name,
                signal=decision.signal.value,
                final_action=decision.signal.value,
                reason=decision.reason,
                regime=regime.regime.value,
                confidence=decision.confidence,
                signal_score=float(context.get("signal_score") or signal_package.score or 0.0),
                buy_score=float(context.get("buy_score") or signal_package.buy_score or 0.0),
                sell_score=float(context.get("sell_score") or signal_package.sell_score or 0.0),
                target_weight=float(context.get("target_weight") or 0.0),
                desired_notional=float(context.get("desired_notional") or 0.0),
                expected_cost_bps=float(((context.get("cost") or {}).get("total_cost_bps")) or 0.0),
                context_json={
                    **context,
                    "contributors": decision.contributors,
                    "indicators": decision.indicators,
                },
            )
        )
        session.commit()

    async def _handle_execution_result(
        self,
        *,
        symbol: str,
        decision: StrategyDecision,
        order: Any,
        position: Position | None,
    ) -> None:
        if order is None:
            self._update_symbol_watch(
                symbol,
                phase="watching",
                last_signal=decision.signal.value,
                last_reason=decision.reason,
                last_reason_context=decision.reason_context,
                last_action="no-op",
            )
            return

        metadata = order.metadata_json or {}
        if order.status == "FILLED":
            if order.side == SignalType.BUY.value:
                self._update_symbol_watch(
                    symbol,
                    phase="holding",
                    has_position=True,
                    position_quantity=order.quantity,
                    last_signal=decision.signal.value,
                    last_reason=decision.reason,
                    last_reason_context=decision.reason_context,
                    last_action="buy-filled",
                    last_order_status=order.status,
                    stop_loss=metadata.get("stop_loss"),
                    take_profit=metadata.get("take_profit"),
                    blocked_reason="",
                )
            else:
                self._update_symbol_watch(
                    symbol,
                    phase="flat",
                    has_position=False,
                    position_quantity=0.0,
                    last_signal=decision.signal.value,
                    last_reason=decision.reason,
                    last_reason_context=decision.reason_context,
                    last_action="sell-filled",
                    last_order_status=order.status,
                    stop_loss=None,
                    take_profit=None,
                    blocked_reason="",
                )
        else:
            self._update_symbol_watch(
                symbol,
                phase="blocked" if order.status == "REJECTED" else "pending",
                has_position=bool(position and position.quantity > 0),
                position_quantity=position.quantity if position else 0.0,
                last_signal=decision.signal.value,
                last_reason=decision.reason,
                last_reason_context=decision.reason_context,
                last_action="order-submitted",
                last_order_status=order.status,
                blocked_reason=order.risk_reason,
            )
        await self._broadcast_status()

    async def evaluate_symbol(self, session: Session, symbol: str) -> None:
        config = self.config_service.get_runtime_config()
        candles = self.state.latest_klines.get(symbol) or await self.market_data_service.adapter.fetch_ohlcv(
            symbol, config.timeframe, limit=120
        )
        ai_signal = await self.ai_provider.get_signal(symbol, pd.DataFrame(candles))
        decision = self.orchestrator.generate(symbol=symbol, candles=candles, config=config, ai_signal=ai_signal)
        latest_price = self.state.latest_prices.get(symbol, decision.price)
        summary = self.metrics_service.get_summary()
        open_positions = int(summary.get("position_count", 0))
        regime = self.regime_detector.detect(symbol, candles, config)
        signal_package = self.signal_engine.build(decision=decision, regime=regime, ai_signal=ai_signal, config=config)
        allocation = self.portfolio_allocator.allocate(
            config=config,
            summary=summary,
            regime=regime,
            signal_package=signal_package,
            open_positions=open_positions,
        )
        cost_estimate = self.cost_model.estimate(
            config=config,
            ticker=self.state.latest_tickers.get(symbol),
            price=latest_price,
        )
        decision = self.decision_engine.finalize(
            config=config,
            decision=decision,
            regime=regime,
            signal_package=signal_package,
            allocation=allocation,
            cost_estimate=cost_estimate,
        )
        self._record_decision(
            session,
            symbol=symbol,
            config=config,
            decision=decision,
            regime=regime,
            signal_package=signal_package,
        )
        position = self._load_position(session, symbol)

        exit_reason = self._tracked_exit_reason(symbol, latest_price)
        if position and exit_reason:
            exit_decision = self._build_exit_decision(symbol, latest_price, exit_reason)
            order = await self.executor.execute_signal(
                session=session,
                config=config,
                adapter=self.market_data_service.adapter,
                decision=exit_decision,
                metrics_summary=summary,
            )
            await self._handle_execution_result(symbol=symbol, decision=exit_decision, order=order, position=position)
            self.logger.info(
                "策略保护性离场 %s %s 原因=%s",
                symbol,
                exit_decision.signal.value,
                exit_reason,
                extra={"category": "strategy"},
            )
            return

        if decision.signal == SignalType.HOLD:
            self._update_symbol_watch(
                symbol,
                phase="holding" if position else "watching",
                has_position=bool(position),
                position_quantity=position.quantity if position else 0.0,
                market_regime=regime.regime.value,
                regime_confidence=regime.confidence,
                signal_score=signal_package.score,
                target_weight=decision.reason_context.get("target_weight"),
                expected_cost_bps=(decision.reason_context.get("cost") or {}).get("total_cost_bps"),
                last_signal=decision.signal.value,
                last_reason=decision.reason,
                last_reason_context=decision.reason_context,
                last_action="wait",
                blocked_reason="",
            )
            await self._broadcast_status()
            return

        if decision.signal == SignalType.SELL and not position:
            self._update_symbol_watch(
                symbol,
                phase="watching",
                has_position=False,
                position_quantity=0.0,
                market_regime=regime.regime.value,
                regime_confidence=regime.confidence,
                signal_score=signal_package.score,
                last_signal=decision.signal.value,
                last_reason=decision.reason,
                last_reason_context=decision.reason_context,
                last_action="skip-sell",
                blocked_reason="spot-long-only-waits-for-buy",
            )
            await self._broadcast_status()
            return

        if decision.signal == SignalType.BUY and position:
            self._update_symbol_watch(
                symbol,
                phase="holding",
                has_position=True,
                position_quantity=position.quantity,
                market_regime=regime.regime.value,
                regime_confidence=regime.confidence,
                signal_score=signal_package.score,
                target_weight=decision.reason_context.get("target_weight"),
                expected_cost_bps=(decision.reason_context.get("cost") or {}).get("total_cost_bps"),
                last_signal=decision.signal.value,
                last_reason=decision.reason,
                last_reason_context=decision.reason_context,
                last_action="hold-existing-position",
                blocked_reason="already-in-position",
                stop_loss=self.state.symbol_states.get(symbol, {}).get("stop_loss"),
                take_profit=self.state.symbol_states.get(symbol, {}).get("take_profit"),
            )
            await self._broadcast_status()
            return

        order = await self.executor.execute_signal(
            session=session,
            config=config,
            adapter=self.market_data_service.adapter,
            decision=decision,
            metrics_summary=summary,
        )
        await self._handle_execution_result(symbol=symbol, decision=decision, order=order, position=position)
        self.logger.info(
            "策略决策 %s %s 策略=%s 原因=%s",
            symbol,
            decision.signal.value,
            decision.strategy_name,
            decision.reason,
            extra={"category": "strategy"},
        )

    async def run(self) -> None:
        self._running = True
        while self._running:
            await asyncio.sleep(1)
            if self.state.status.value != "RUNNING":
                continue
            config = self.config_service.get_runtime_config()
            with self.session_factory() as session:
                for symbol in config.symbols:
                    try:
                        await self.evaluate_symbol(session, symbol)
                    except Exception:
                        self.logger.exception("策略轮询执行失败，交易对=%s", symbol, extra={"category": "strategy"})
            self.state.touch()
            await self._broadcast_status()
            await asyncio.sleep(2)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            await asyncio.wait([self._task], timeout=2)
