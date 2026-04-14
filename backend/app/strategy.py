from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from hashlib import md5
from typing import Any, Protocol

import pandas as pd

from app.ai_signal_provider import AISignal
from app.config import StrategyConfig
from app.utils.indicators import add_indicators


class SignalType(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class StrategyDecision:
    symbol: str
    signal: SignalType
    price: float
    stop_loss: float | None
    take_profit: float | None
    reason: str
    strategy_name: str = "unknown"
    confidence: float = 0.5
    indicators: dict[str, float] = field(default_factory=dict)
    signal_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    reason_context: dict[str, Any] = field(default_factory=dict)
    contributors: list[dict[str, Any]] = field(default_factory=list)


class StrategyProvider(Protocol):
    name: str

    def generate(
        self,
        symbol: str,
        candles: list[dict[str, Any]],
        strategy_config: StrategyConfig,
        ai_signal: AISignal | None = None,
    ) -> StrategyDecision:
        ...


class MovingAverageRsiStrategy:
    name = "ma_rsi"

    def generate(
        self,
        symbol: str,
        candles: list[dict[str, Any]],
        strategy_config: StrategyConfig,
        ai_signal: AISignal | None = None,
    ) -> StrategyDecision:
        frame = pd.DataFrame(candles)
        if frame.empty or len(frame) < max(strategy_config.ma_slow, strategy_config.atr_period) + 2:
            return StrategyDecision(
                symbol=symbol,
                signal=SignalType.HOLD,
                price=float(frame["close"].iloc[-1]) if not frame.empty else 0.0,
                stop_loss=None,
                take_profit=None,
                reason="insufficient-data",
                strategy_name=self.name,
                confidence=0.0,
            )

        enriched = add_indicators(
            frame,
            fast=strategy_config.ma_fast,
            slow=strategy_config.ma_slow,
            rsi_period=strategy_config.rsi_period,
            atr_period=strategy_config.atr_period,
        ).dropna()
        if len(enriched) < 2:
            return StrategyDecision(
                symbol=symbol,
                signal=SignalType.HOLD,
                price=float(frame["close"].iloc[-1]),
                stop_loss=None,
                take_profit=None,
                reason="indicator-warmup",
                strategy_name=self.name,
                confidence=0.0,
            )

        latest = enriched.iloc[-1]
        previous = enriched.iloc[-2]
        price = float(latest["close"])
        atr_value = float(latest["atr"])
        ai_bias = ai_signal.bias if ai_signal else "NEUTRAL"

        signal = SignalType.HOLD
        reason = "filters-not-met"

        bullish_cross = previous["ma_fast"] <= previous["ma_slow"] and latest["ma_fast"] > latest["ma_slow"]
        bearish_cross = previous["ma_fast"] >= previous["ma_slow"] and latest["ma_fast"] < latest["ma_slow"]
        confidence = 0.45
        confidence += min(abs(float(latest["ma_fast"]) - float(latest["ma_slow"])) / max(price, 1e-9), 0.2)
        confidence += min(abs(float(latest["rsi"]) - 50) / 100, 0.15)

        if bullish_cross and latest["rsi"] >= strategy_config.rsi_buy_threshold and ai_bias != "BEARISH":
            signal = SignalType.BUY
            reason = "ma-cross-up-rsi-confirmed"
        elif bearish_cross and latest["rsi"] <= strategy_config.rsi_sell_threshold and ai_bias != "BULLISH":
            signal = SignalType.SELL
            reason = "ma-cross-down-rsi-confirmed"
        else:
            confidence = min(confidence, 0.49)

        stop_loss = None
        take_profit = None
        if signal == SignalType.BUY:
            stop_loss = price - atr_value * strategy_config.stop_loss_atr_multiple
            take_profit = price + atr_value * strategy_config.take_profit_atr_multiple
        elif signal == SignalType.SELL:
            stop_loss = price + atr_value * strategy_config.stop_loss_atr_multiple
            take_profit = price - atr_value * strategy_config.take_profit_atr_multiple

        signal_id = md5(
            f"{symbol}:{self.name}:{signal.value}:{enriched.index[-1]}:{round(price, 6)}".encode("utf-8")
        ).hexdigest()
        return StrategyDecision(
            symbol=symbol,
            signal=signal,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=reason,
            strategy_name=self.name,
            confidence=min(confidence, 0.95),
            indicators={
                "ma_fast": float(latest["ma_fast"]),
                "ma_slow": float(latest["ma_slow"]),
                "rsi": float(latest["rsi"]),
                "atr": atr_value,
            },
            signal_id=signal_id,
            reason_context={
                "ai_bias": ai_signal.bias.lower() if ai_signal else None,
                "ai_confidence": ai_signal.confidence if ai_signal else None,
                "ai_comment": ai_signal.comment if ai_signal else None,
            },
        )


class TrendBreakoutStrategy:
    name = "trend_breakout"

    def generate(
        self,
        symbol: str,
        candles: list[dict[str, Any]],
        strategy_config: StrategyConfig,
        ai_signal: AISignal | None = None,
    ) -> StrategyDecision:
        frame = pd.DataFrame(candles)
        if frame.empty or len(frame) < max(strategy_config.ma_slow, 30):
            return StrategyDecision(
                symbol=symbol,
                signal=SignalType.HOLD,
                price=float(frame["close"].iloc[-1]) if not frame.empty else 0.0,
                stop_loss=None,
                take_profit=None,
                reason="insufficient-data",
                strategy_name=self.name,
                confidence=0.0,
            )
        enriched = add_indicators(
            frame,
            fast=strategy_config.ma_fast,
            slow=strategy_config.ma_slow,
            rsi_period=strategy_config.rsi_period,
            atr_period=strategy_config.atr_period,
        ).dropna()
        latest = enriched.iloc[-1]
        recent = enriched.tail(20)
        price = float(latest["close"])
        breakout_high = float(recent["high"].max())
        breakout_low = float(recent["low"].min())
        atr_value = float(latest["atr"])
        signal = SignalType.HOLD
        reason = "range-intact"
        confidence = 0.48
        if price >= breakout_high and latest["rsi"] >= 50 and (ai_signal is None or ai_signal.bias != "BEARISH"):
            signal = SignalType.BUY
            reason = "breakout-up"
            confidence = 0.68
        elif price <= breakout_low and latest["rsi"] <= 50 and (ai_signal is None or ai_signal.bias != "BULLISH"):
            signal = SignalType.SELL
            reason = "breakout-down"
            confidence = 0.68

        stop_loss = None
        take_profit = None
        if signal == SignalType.BUY:
            stop_loss = price - atr_value * strategy_config.stop_loss_atr_multiple
            take_profit = price + atr_value * strategy_config.take_profit_atr_multiple
        elif signal == SignalType.SELL:
            stop_loss = price + atr_value * strategy_config.stop_loss_atr_multiple
            take_profit = price - atr_value * strategy_config.take_profit_atr_multiple

        signal_id = md5(
            f"{symbol}:{self.name}:{signal.value}:{enriched.index[-1]}:{round(price, 6)}".encode("utf-8")
        ).hexdigest()
        return StrategyDecision(
            symbol=symbol,
            signal=signal,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=reason,
            strategy_name=self.name,
            confidence=confidence,
            indicators={
                "breakout_high": breakout_high,
                "breakout_low": breakout_low,
                "rsi": float(latest["rsi"]),
                "atr": atr_value,
            },
            signal_id=signal_id,
            reason_context={
                "ai_bias": ai_signal.bias.lower() if ai_signal else None,
                "ai_confidence": ai_signal.confidence if ai_signal else None,
                "ai_comment": ai_signal.comment if ai_signal else None,
            },
        )
