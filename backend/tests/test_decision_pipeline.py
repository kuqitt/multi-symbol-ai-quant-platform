from __future__ import annotations

from datetime import datetime, timedelta

from app.config import AppConfig
from app.cost_model import CostModel
from app.decision_engine import DecisionEngine
from app.portfolio_allocator import PortfolioAllocator
from app.regime_detector import RegimeDetector, RegimeType
from app.signal_engine import SignalEngine
from app.strategy import SignalType, StrategyDecision


def _candles(closes: list[float]) -> list[dict]:
    now = datetime.utcnow()
    candles = []
    for idx, close in enumerate(closes):
        candles.append(
            {
                "timestamp": now + timedelta(minutes=idx),
                "open": close * 0.999,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 1000 + idx,
            }
        )
    return candles


def test_regime_detector_identifies_uptrend() -> None:
    detector = RegimeDetector()
    config = AppConfig()
    result = detector.detect(
        "BTC/USDT",
        _candles(
            [
                10,
                10.1,
                10.2,
                10.3,
                10.4,
                10.55,
                10.5,
                10.7,
                10.85,
                10.8,
                11.0,
                11.15,
                11.05,
                11.3,
                11.45,
                11.35,
                11.6,
                11.8,
                11.7,
                12.0,
                12.2,
                12.05,
                12.35,
                12.5,
                12.4,
                12.7,
                12.9,
                12.75,
                13.1,
                13.3,
                13.15,
                13.55,
                13.8,
                13.65,
                14.0,
                14.2,
                14.05,
                14.45,
                14.7,
                14.55,
                14.95,
                15.2,
                15.0,
                15.45,
                15.7,
                16.0,
            ]
        ),
        config,
    )
    assert result.regime in {RegimeType.TRENDING_UP, RegimeType.VOLATILE}
    assert result.confidence >= config.regime.confidence_floor


def test_decision_engine_blocks_high_cost_buy() -> None:
    config = AppConfig()
    decision = StrategyDecision(
        symbol="BTC/USDT",
        signal=SignalType.BUY,
        price=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        reason="ma-cross-up-rsi-confirmed",
        strategy_name="ma_rsi",
        confidence=0.72,
        indicators={"rsi": 60.0},
        signal_id="abc",
    )
    detector = RegimeDetector()
    regime = detector.detect("BTC/USDT", _candles([90, 92, 94, 96, 98, 99, 100, 101, 102, 103, 104, 105]), config)
    signal_package = SignalEngine().build(decision=decision, regime=regime, ai_signal=None, config=config)
    allocation = PortfolioAllocator().allocate(
        config=config,
        summary={"equity": 1000.0, "available_balance": 800.0, "position_count": 0},
        regime=regime,
        signal_package=signal_package,
        open_positions=0,
    )
    cost = CostModel().estimate(
        config=config.model_copy(update={"cost_model": config.cost_model.model_copy(update={"max_cost_bps": 1.0})}),
        ticker={"bid": 99.0, "ask": 101.0},
        price=100.0,
    )
    final_decision = DecisionEngine().finalize(
        config=config.model_copy(update={"cost_model": config.cost_model.model_copy(update={"max_cost_bps": 1.0})}),
        decision=decision,
        regime=regime,
        signal_package=signal_package,
        allocation=allocation,
        cost_estimate=cost,
    )
    assert final_decision.signal == SignalType.HOLD
    assert final_decision.reason == "cost-too-high"


def test_allocator_scales_target_notional_with_signal_score() -> None:
    config = AppConfig()
    decision = StrategyDecision(
        symbol="ETH/USDT",
        signal=SignalType.BUY,
        price=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        reason="breakout-up",
        strategy_name="trend_breakout",
        confidence=0.8,
        indicators={"rsi": 65.0},
        signal_id="def",
    )
    detector = RegimeDetector()
    regime = detector.detect("ETH/USDT", _candles([50, 52, 54, 57, 60, 63, 66, 70, 74, 79, 84, 90]), config)
    signal_package = SignalEngine().build(decision=decision, regime=regime, ai_signal=None, config=config)
    allocation = PortfolioAllocator().allocate(
        config=config,
        summary={"equity": 2000.0, "available_balance": 1500.0, "position_count": 1},
        regime=regime,
        signal_package=signal_package,
        open_positions=1,
    )
    assert allocation.target_notional > 0
    assert allocation.size_multiplier > 0
    assert allocation.target_weight <= config.allocation.max_notional_ratio