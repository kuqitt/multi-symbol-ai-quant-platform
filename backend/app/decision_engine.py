from __future__ import annotations

from dataclasses import replace

from app.config import AppConfig
from app.cost_model import ExecutionCostEstimate
from app.portfolio_allocator import AllocationPlan
from app.regime_detector import RegimeAssessment, RegimeType
from app.signal_engine import SignalPackage
from app.strategy import SignalType, StrategyDecision


class DecisionEngine:
    def finalize(
        self,
        *,
        config: AppConfig,
        decision: StrategyDecision,
        regime: RegimeAssessment,
        signal_package: SignalPackage,
        allocation: AllocationPlan,
        cost_estimate: ExecutionCostEstimate,
    ) -> StrategyDecision:
        reason_context = {
            **(decision.reason_context or {}),
            "regime": regime.regime.value,
            "regime_confidence": regime.confidence,
            "regime_detail": regime.detail,
            "signal_score": signal_package.score,
            "buy_score": signal_package.buy_score,
            "sell_score": signal_package.sell_score,
            "signal_detail": signal_package.detail,
            "allocation": allocation.detail,
            "target_weight": allocation.target_weight,
            "desired_notional": allocation.target_notional,
            "size_multiplier": allocation.size_multiplier,
            "available_slots": allocation.available_slots,
            "cost": {
                "total_cost_bps": cost_estimate.total_cost_bps,
                "spread_bps": cost_estimate.spread_bps,
                "slippage_bps": cost_estimate.slippage_bps,
                "fee_bps": cost_estimate.fee_bps,
                "market_impact_bps": cost_estimate.market_impact_bps,
            },
        }

        if decision.signal == SignalType.HOLD:
            return replace(decision, reason_context=reason_context)

        if signal_package.score < config.signal.min_signal_score:
            return replace(
                decision,
                signal=SignalType.HOLD,
                reason="signal-score-too-low",
                confidence=signal_package.score,
                reason_context=reason_context,
            )

        if config.cost_model.enabled and not cost_estimate.allowed:
            return replace(
                decision,
                signal=SignalType.HOLD,
                reason="cost-too-high",
                confidence=min(decision.confidence, 0.49),
                reason_context=reason_context,
            )

        if allocation.target_notional <= 0 and decision.signal == SignalType.BUY:
            return replace(
                decision,
                signal=SignalType.HOLD,
                reason="allocation-blocked",
                confidence=min(decision.confidence, 0.49),
                reason_context=reason_context,
            )

        if decision.signal == SignalType.BUY and regime.regime == RegimeType.TRENDING_DOWN and signal_package.score < 0.72:
            return replace(
                decision,
                signal=SignalType.HOLD,
                reason="regime-conflict",
                confidence=min(decision.confidence, 0.49),
                reason_context=reason_context,
            )

        if decision.signal == SignalType.SELL and regime.regime == RegimeType.TRENDING_UP and signal_package.score < 0.72:
            return replace(
                decision,
                signal=SignalType.HOLD,
                reason="regime-conflict",
                confidence=min(decision.confidence, 0.49),
                reason_context=reason_context,
            )

        return replace(decision, reason_context=reason_context, confidence=max(decision.confidence, signal_package.score))