from __future__ import annotations

from datetime import datetime, timedelta

from app.config import StrategyConfig
from app.strategy import MovingAverageRsiStrategy, SignalType


def _candles(closes: list[float]) -> list[dict]:
    now = datetime.utcnow()
    candles = []
    for idx, close in enumerate(closes):
        candles.append(
            {
                "timestamp": now + timedelta(minutes=idx),
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 1000 + idx,
            }
        )
    return candles


def test_strategy_generates_buy_signal() -> None:
    strategy = MovingAverageRsiStrategy()
    config = StrategyConfig(
        ma_fast=2,
        ma_slow=3,
        rsi_period=2,
        rsi_buy_threshold=50,
        rsi_sell_threshold=50,
        atr_period=2,
    )
    decision = strategy.generate("BTC/USDT", _candles([10, 10, 10, 9, 10, 12]), config)
    assert decision.signal == SignalType.BUY
    assert decision.stop_loss is not None


def test_strategy_generates_sell_signal() -> None:
    strategy = MovingAverageRsiStrategy()
    config = StrategyConfig(
        ma_fast=2,
        ma_slow=3,
        rsi_period=2,
        rsi_buy_threshold=50,
        rsi_sell_threshold=50,
        atr_period=2,
    )
    decision = strategy.generate("ETH/USDT", _candles([10, 10, 10, 11, 10, 8]), config)
    assert decision.signal == SignalType.SELL
    assert decision.take_profit is not None

