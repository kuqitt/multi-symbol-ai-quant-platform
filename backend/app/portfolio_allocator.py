from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import AppConfig
from app.regime_detector import RegimeAssessment
from app.signal_engine import SignalPackage
from app.strategy import SignalType


@dataclass
class AllocationPlan:
    target_weight: float
    target_notional: float
    size_multiplier: float
    available_slots: int
    detail: dict[str, Any] = field(default_factory=dict)


class PortfolioAllocator:
    def allocate(
        self,
        *,
        config: AppConfig,
        summary: dict[str, float],
        regime: RegimeAssessment,
        signal_package: SignalPackage,
        open_positions: int,
    ) -> AllocationPlan:
        equity = max(float(summary.get("equity", 0.0)), 0.0)
        available_balance = max(float(summary.get("available_balance", 0.0)), 0.0)
        available_slots = max(config.allocation.max_concurrent_positions - open_positions, 0)
        base_weight = min(config.risk.max_symbol_exposure, config.allocation.max_notional_ratio)
        regime_multiplier = config.allocation.regime_multipliers.get(regime.regime.value, 1.0)
        score_multiplier = 0.5 + signal_package.score * 0.5
        target_weight = base_weight * config.allocation.base_risk_budget * regime_multiplier * score_multiplier
        target_weight = min(max(target_weight, config.allocation.min_notional_ratio), config.allocation.max_notional_ratio)

        if signal_package.decision.signal == SignalType.BUY:
            target_notional = min(equity * target_weight, available_balance)
        elif signal_package.decision.signal == SignalType.SELL:
            target_notional = 0.0
        else:
            target_notional = 0.0

        size_multiplier = target_weight / max(base_weight, 1e-9)
        if available_slots <= 0 and signal_package.decision.signal == SignalType.BUY:
            target_notional = 0.0
            size_multiplier = 0.0

        return AllocationPlan(
            target_weight=target_weight,
            target_notional=target_notional,
            size_multiplier=size_multiplier,
            available_slots=available_slots,
            detail={
                "equity": equity,
                "available_balance": available_balance,
                "base_weight": base_weight,
                "regime_multiplier": regime_multiplier,
                "score_multiplier": score_multiplier,
                "open_positions": open_positions,
            },
        )