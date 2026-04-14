from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import AppConfig


@dataclass
class ExecutionCostEstimate:
    total_cost_bps: float
    spread_bps: float
    slippage_bps: float
    fee_bps: float
    market_impact_bps: float
    allowed: bool
    detail: dict[str, Any] = field(default_factory=dict)


class CostModel:
    def estimate(self, *, config: AppConfig, ticker: dict[str, Any] | None, price: float) -> ExecutionCostEstimate:
        bid = float((ticker or {}).get("bid") or price)
        ask = float((ticker or {}).get("ask") or price)
        last_price = max(price, 1e-9)
        spread_bps = max((ask - bid) / last_price * 10000, 0.0)
        slippage_bps = spread_bps * config.cost_model.slippage_spread_weight
        fee_bps = config.cost_model.taker_fee_bps
        market_impact_bps = spread_bps * config.cost_model.impact_weight
        total_cost_bps = fee_bps + slippage_bps + market_impact_bps
        return ExecutionCostEstimate(
            total_cost_bps=total_cost_bps,
            spread_bps=spread_bps,
            slippage_bps=slippage_bps,
            fee_bps=fee_bps,
            market_impact_bps=market_impact_bps,
            allowed=total_cost_bps <= config.cost_model.max_cost_bps,
            detail={
                "bid": bid,
                "ask": ask,
                "reference_price": price,
            },
        )