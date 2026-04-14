from __future__ import annotations

import asyncio
import logging

from sqlmodel import select

from app.executor import ExecutionService
from app.portfolio import PortfolioService
from app.risk_manager import RiskManager
from app.services.approval_service import ApprovalService
from app.strategy import SignalType, StrategyDecision


class DummyNotifier:
    async def send_alert(self, config, message: str) -> None:
        return None

    async def send_approval_request(self, config, approval_payload: dict) -> None:
        return None


def test_executor_places_and_records_order(session, config, env_settings, state, adapter) -> None:
    ticker = asyncio.run(adapter.fetch_ticker("ETH/USDT"))
    config_service = type("Cfg", (), {"get_runtime_config": lambda self: config})()
    portfolio = PortfolioService(adapter, config_service, env_settings, state)
    risk_manager = RiskManager(state, logging.getLogger("test-executor"))
    approval_service = ApprovalService(
        config_service=type("Cfg", (), {"get_config": lambda self: config})(),
        notifier=DummyNotifier(),
        logger=logging.getLogger("test-executor"),
    )
    executor = ExecutionService(risk_manager, portfolio, approval_service, DummyNotifier(), logging.getLogger("test-executor"))

    decision = StrategyDecision(
        symbol="ETH/USDT",
        signal=SignalType.BUY,
        price=ticker.price,
        stop_loss=ticker.price * 0.99,
        take_profit=ticker.price * 1.02,
        reason="unit-test",
        strategy_name="ma_rsi",
        signal_id="executor-signal-1",
    )
    order = asyncio.run(
        executor.execute_signal(
            session=session,
            config=config,
            adapter=adapter,
            decision=decision,
            metrics_summary={"equity": 100000.0, "daily_pnl": 0.0},
        )
    )
    assert order is not None
    assert order.status in {"FILLED", "OPEN"}
    assert session.exec(select(type(order))).first() is not None
