from __future__ import annotations

import asyncio
import logging

from app.adapters.binance_adapter import BinanceAdapter
from app.config import AppConfig, ApprovalConfig, EnvironmentSettings, SimulationConfig
from app.services.approval_service import ApprovalService


class DummyNotifier:
    async def send_approval_request(self, config, approval_payload: dict) -> None:
        return None


def test_small_account_is_auto_approved_below_threshold() -> None:
    config = AppConfig(
        approval=ApprovalConfig(
            enabled=True,
            auto_approve_small_accounts=True,
            auto_approve_below_equity=1000.0,
            require_manual_approval_for_large_orders=True,
            approval_min_notional=100.0,
        )
    )
    config_service = type("Cfg", (), {"get_runtime_config": lambda self: config})()
    service = ApprovalService(config_service=config_service, notifier=DummyNotifier(), logger=logging.getLogger("test-approval"))

    requires_approval, reason = service.should_require_approval(
        config=config,
        notional=500.0,
        is_live=False,
        total_equity=999.0,
    )

    assert requires_approval is False
    assert reason == ""


def test_binance_paper_uses_live_market_data_when_enabled(monkeypatch) -> None:
    config = AppConfig(
        exchange="binance",
        env="paper",
        simulation=SimulationConfig(use_live_market_data=True),
    )
    adapter = BinanceAdapter(config=config, env_settings=EnvironmentSettings(_env_file=None), starting_balance=1000.0)

    async def fake_request(method: str, path: str, *, params=None, auth: bool = False):
        if path == "/api/v3/ticker/24hr":
            return {"lastPrice": "65000.1", "priceChangePercent": "2.5", "quoteVolume": "1234567.8"}
        if path == "/api/v3/ticker/bookTicker":
            return {"bidPrice": "64999.9", "askPrice": "65000.3"}
        raise AssertionError(f"unexpected request: {method} {path}")

    monkeypatch.setattr(adapter, "_request", fake_request)

    ticker = asyncio.run(adapter.fetch_ticker("BTC/USDT"))

    assert ticker.price == 65000.1
    assert ticker.price_source == "live"
    assert ticker.market_type == "spot"
    assert adapter.simulator.market_state["BTC/USDT"]["quote"]["price"] == 65000.1

    asyncio.run(adapter.close())