from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class AISignal:
    bias: str
    confidence: float
    comment: str


class MockAISignalProvider:
    async def get_signal(self, symbol: str, candles: pd.DataFrame) -> AISignal:
        if candles.empty:
            return AISignal(bias="NEUTRAL", confidence=0.0, comment="no-data")
        recent_return = (candles["close"].iloc[-1] - candles["close"].iloc[-5]) / candles["close"].iloc[-5]
        if recent_return > 0.01:
            return AISignal(bias="BULLISH", confidence=min(abs(recent_return) * 20, 0.8), comment=f"{symbol} trend up")
        if recent_return < -0.01:
            return AISignal(bias="BEARISH", confidence=min(abs(recent_return) * 20, 0.8), comment=f"{symbol} trend down")
        return AISignal(bias="NEUTRAL", confidence=0.2, comment=f"{symbol} mixed")

