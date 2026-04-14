from __future__ import annotations

from typing import Iterable

from app.ai_signal_provider import AISignal
from app.config import AppConfig
from app.strategy import MovingAverageRsiStrategy, SignalType, StrategyDecision, StrategyProvider, TrendBreakoutStrategy


class StrategyOrchestrator:
    def __init__(self) -> None:
        providers: Iterable[StrategyProvider] = (
            MovingAverageRsiStrategy(),
            TrendBreakoutStrategy(),
        )
        self.providers = {provider.name: provider for provider in providers}

    def generate(
        self,
        *,
        symbol: str,
        candles: list[dict],
        config: AppConfig,
        ai_signal: AISignal | None = None,
    ) -> StrategyDecision:
        enabled = [name for name in config.strategy_engine.enabled_strategies if name in self.providers]
        if not enabled:
            return StrategyDecision(
                symbol=symbol,
                signal=SignalType.HOLD,
                price=float(candles[-1]["close"]) if candles else 0.0,
                stop_loss=None,
                take_profit=None,
                reason="no-enabled-strategy",
                strategy_name="orchestrator",
                confidence=0.0,
            )
        decisions = [
            self.providers[name].generate(symbol, candles, config.strategy, ai_signal)
            for name in enabled
        ]
        buy_score = 0.0
        sell_score = 0.0
        weights = config.strategy_engine.strategy_weights
        for decision in decisions:
            weight = weights.get(decision.strategy_name, 1.0)
            if decision.signal == SignalType.BUY:
                buy_score += decision.confidence * weight
            elif decision.signal == SignalType.SELL:
                sell_score += decision.confidence * weight
        threshold = config.strategy_engine.minimum_confidence
        final_signal = SignalType.HOLD
        confidence = 0.0
        selected = decisions[0]
        if config.strategy_engine.selection_mode == "vote":
            buy_votes = sum(1 for item in decisions if item.signal == SignalType.BUY)
            sell_votes = sum(1 for item in decisions if item.signal == SignalType.SELL)
            if buy_votes > sell_votes and buy_votes / len(decisions) >= threshold:
                final_signal = SignalType.BUY
            elif sell_votes > buy_votes and sell_votes / len(decisions) >= threshold:
                final_signal = SignalType.SELL
            confidence = max(buy_votes, sell_votes) / len(decisions)
        else:
            if buy_score >= threshold and buy_score > sell_score:
                final_signal = SignalType.BUY
                confidence = buy_score
            elif sell_score >= threshold and sell_score > buy_score:
                final_signal = SignalType.SELL
                confidence = sell_score

        if final_signal == SignalType.BUY:
            selected = max(
                [item for item in decisions if item.signal == SignalType.BUY] or decisions,
                key=lambda item: item.confidence,
            )
        elif final_signal == SignalType.SELL:
            selected = max(
                [item for item in decisions if item.signal == SignalType.SELL] or decisions,
                key=lambda item: item.confidence,
            )

        return StrategyDecision(
            symbol=symbol,
            signal=final_signal,
            price=selected.price,
            stop_loss=selected.stop_loss,
            take_profit=selected.take_profit,
            reason=selected.reason,
            strategy_name=selected.strategy_name,
            confidence=confidence or selected.confidence,
            indicators=selected.indicators,
            signal_id=selected.signal_id,
            reason_context={
                **selected.reason_context,
                "selection_mode": config.strategy_engine.selection_mode,
                "selected_strategy": selected.strategy_name,
                "buy_score": buy_score,
                "sell_score": sell_score,
            },
            contributors=[
                {
                    "strategy_name": item.strategy_name,
                    "signal": item.signal.value,
                    "confidence": item.confidence,
                    "reason": item.reason,
                    "reason_context": item.reason_context,
                }
                for item in decisions
            ],
        )
