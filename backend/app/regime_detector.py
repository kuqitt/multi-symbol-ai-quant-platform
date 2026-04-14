from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import pandas as pd

from app.config import AppConfig
from app.utils.indicators import add_indicators


class RegimeType(StrEnum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGE = "range"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


@dataclass
class RegimeAssessment:
    symbol: str
    regime: RegimeType
    confidence: float
    trend_score: float
    volatility_score: float
    detail: dict[str, Any] = field(default_factory=dict)


class RegimeDetector:
    def detect(self, symbol: str, candles: list[dict[str, Any]], config: AppConfig) -> RegimeAssessment:
        frame = pd.DataFrame(candles)
        lookback = max(config.regime.trend_lookback, config.strategy.ma_slow, config.strategy.atr_period) + 2
        if frame.empty or len(frame) < lookback:
            return RegimeAssessment(
                symbol=symbol,
                regime=RegimeType.UNKNOWN,
                confidence=0.0,
                trend_score=0.0,
                volatility_score=0.0,
                detail={"reason": "insufficient-data", "required_bars": lookback, "actual_bars": len(frame)},
            )

        enriched = add_indicators(
            frame,
            fast=config.strategy.ma_fast,
            slow=config.strategy.ma_slow,
            rsi_period=config.strategy.rsi_period,
            atr_period=config.strategy.atr_period,
        ).dropna()
        if enriched.empty:
            return RegimeAssessment(
                symbol=symbol,
                regime=RegimeType.UNKNOWN,
                confidence=0.0,
                trend_score=0.0,
                volatility_score=0.0,
                detail={"reason": "indicator-warmup"},
            )

        recent = enriched.tail(config.regime.trend_lookback)
        latest = recent.iloc[-1]
        first = recent.iloc[0]
        price = float(latest["close"])
        ma_gap = (float(latest["ma_fast"]) - float(latest["ma_slow"])) / max(price, 1e-9)
        directional_return = (float(latest["close"]) - float(first["close"])) / max(float(first["close"]), 1e-9)
        realized_vol = float(recent["close"].pct_change().dropna().std(ddof=0) or 0.0)
        atr_ratio = float(latest["atr"]) / max(price, 1e-9)

        trend_score = min(abs(ma_gap) * 18 + abs(directional_return) * 4, 1.0)
        volatility_score = min(max(realized_vol * 5, atr_ratio * 8), 1.0)
        regime = RegimeType.RANGE

        if volatility_score >= config.regime.high_volatility_threshold * 10:
            regime = RegimeType.VOLATILE
        elif ma_gap >= config.regime.trend_strength_threshold:
            regime = RegimeType.TRENDING_UP
        elif ma_gap <= -config.regime.trend_strength_threshold:
            regime = RegimeType.TRENDING_DOWN
        elif volatility_score <= config.regime.low_volatility_threshold * 10:
            regime = RegimeType.RANGE

        confidence = max(config.regime.confidence_floor, min(0.45 + trend_score * 0.35 + volatility_score * 0.2, 0.95))
        return RegimeAssessment(
            symbol=symbol,
            regime=regime,
            confidence=confidence,
            trend_score=trend_score,
            volatility_score=volatility_score,
            detail={
                "price": price,
                "ma_gap": ma_gap,
                "directional_return": directional_return,
                "realized_vol": realized_vol,
                "atr_ratio": atr_ratio,
                "rsi": float(latest["rsi"]),
            },
        )