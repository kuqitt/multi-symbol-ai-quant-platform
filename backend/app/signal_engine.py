from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ai_signal_provider import AISignal
from app.config import AppConfig
from app.regime_detector import RegimeAssessment, RegimeType
from app.strategy import SignalType, StrategyDecision


@dataclass
class SignalPackage:
    decision: StrategyDecision
    score: float
    buy_score: float
    sell_score: float
    regime_bias: str
    detail: dict[str, Any] = field(default_factory=dict)


class SignalEngine:
    def build(
        self,
        *,
        decision: StrategyDecision,
        regime: RegimeAssessment,
        ai_signal: AISignal | None,
        config: AppConfig,
    ) -> SignalPackage:
        indicators = decision.indicators or {}
        buy_score = 0.0
        sell_score = 0.0

        if decision.signal == SignalType.BUY:
            buy_score += 0.35 + decision.confidence * 0.35
        elif decision.signal == SignalType.SELL:
            sell_score += 0.35 + decision.confidence * 0.35

        rsi_value = float(indicators.get("rsi", 50.0))
        if rsi_value >= 55:
            buy_score += config.signal.momentum_weight * min((rsi_value - 50) / 20, 1.0)
        elif rsi_value <= 45:
            sell_score += config.signal.momentum_weight * min((50 - rsi_value) / 20, 1.0)
        else:
            mean_reversion_boost = config.signal.mean_reversion_weight * (1 - abs(rsi_value - 50) / 5)
            buy_score += max(mean_reversion_boost, 0.0) * 0.5
            sell_score += max(mean_reversion_boost, 0.0) * 0.5

        regime_bias = "neutral"
        if regime.regime == RegimeType.TRENDING_UP:
            buy_score += config.signal.regime_weight * regime.confidence
            regime_bias = "bullish"
        elif regime.regime == RegimeType.TRENDING_DOWN:
            sell_score += config.signal.regime_weight * regime.confidence
            regime_bias = "bearish"
        elif regime.regime == RegimeType.VOLATILE:
            buy_score *= 0.85
            sell_score *= 0.85
            regime_bias = "volatile"

        if decision.strategy_name == "trend_breakout":
            if decision.signal == SignalType.BUY:
                buy_score += config.signal.breakout_weight * 0.5
            elif decision.signal == SignalType.SELL:
                sell_score += config.signal.breakout_weight * 0.5

        if ai_signal is not None:
            ai_boost = config.signal.ai_weight * max(min(ai_signal.confidence, 1.0), 0.0)
            if ai_signal.bias == "BULLISH":
                buy_score += ai_boost
            elif ai_signal.bias == "BEARISH":
                sell_score += ai_boost

        buy_score = min(max(buy_score, 0.0), 1.0)
        sell_score = min(max(sell_score, 0.0), 1.0)
        score = max(buy_score, sell_score)
        return SignalPackage(
            decision=decision,
            score=score,
            buy_score=buy_score,
            sell_score=sell_score,
            regime_bias=regime_bias,
            detail={
                "decision_confidence": decision.confidence,
                "rsi": rsi_value,
                "ai_bias": ai_signal.bias.lower() if ai_signal else None,
                "ai_confidence": ai_signal.confidence if ai_signal else None,
            },
        )