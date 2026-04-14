from __future__ import annotations

import asyncio
import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.metrics import build_daily_pnl_points, build_drawdown_points, build_equity_curve_points, summarize_performance
from app.models import EquitySnapshot, LogEntry, Order, Position, StrategyDecisionLog, Trade


class MetricsService:
    def __init__(
        self,
        *,
        session_factory: Any,
        adapter: Any,
        config_service: Any,
        state: Any,
        portfolio_service: Any,
        websocket_manager: Any,
    ) -> None:
        self.session_factory = session_factory
        self.adapter = adapter
        self.config_service = config_service
        self.state = state
        self.portfolio_service = portfolio_service
        self.websocket_manager = websocket_manager
        self._summary_cache: dict[str, Any] | None = None
        self._task: asyncio.Task[None] | None = None
        self._running = False

    def _starting_equity(self) -> float:
        if hasattr(self.adapter, "starting_balance"):
            return float(getattr(self.adapter, "starting_balance"))
        simulator = getattr(self.adapter, "simulator", None)
        if simulator is not None and hasattr(simulator, "starting_balance"):
            return float(getattr(simulator, "starting_balance"))
        return 100000.0

    def _calculate_summary(self, session: Session) -> dict[str, Any]:
        available_balance = self.state.account_balance.get("available_balance", getattr(self.adapter, "available_balance", 0.0))
        raw_positions = session.exec(select(Position)).all()
        current_equity = self.state.account_balance.get("equity") or (
            available_balance
            + sum(
                (position.quantity * self.state.latest_prices.get(position.symbol, position.market_price or position.avg_price))
                for position in raw_positions
            )
        )
        positions = self.portfolio_service.revalue_positions(session, self.state.latest_prices, current_equity or 1.0)
        trades = session.exec(select(Trade).order_by(Trade.timestamp.asc())).all()
        snapshots = session.exec(select(EquitySnapshot).order_by(EquitySnapshot.timestamp.asc())).all()
        return summarize_performance(
            starting_equity=self._starting_equity(),
            current_equity=current_equity,
            available_balance=available_balance,
            positions=positions,
            trades=trades,
            snapshots=snapshots,
            strategy_status=self.state.status.value,
            risk_status=self.state.risk_status.value,
        )

    def get_summary(self) -> dict[str, Any]:
        with self.session_factory() as session:
            self._summary_cache = self._calculate_summary(session)
            return self._summary_cache

    def get_equity_curve(self) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            snapshots = session.exec(select(EquitySnapshot).order_by(EquitySnapshot.timestamp.asc())).all()
            return build_equity_curve_points(snapshots)

    def get_drawdown_curve(self) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            snapshots = session.exec(select(EquitySnapshot).order_by(EquitySnapshot.timestamp.asc())).all()
            return build_drawdown_points(snapshots)

    def get_daily_pnl(self) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            trades = session.exec(select(Trade).order_by(Trade.timestamp.asc())).all()
            return build_daily_pnl_points(trades)

    def export_report_csv(self, destination: Path) -> Path:
        summary = self.get_summary()
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["metric", "value"])
            for key, value in summary.items():
                writer.writerow([key, value])
        return destination

    def latest_logs(self, limit: int = 100) -> list[LogEntry]:
        with self.session_factory() as session:
            return session.exec(select(LogEntry).order_by(LogEntry.timestamp.desc()).limit(limit)).all()

    def list_orders(self) -> list[Order]:
        with self.session_factory() as session:
            return session.exec(select(Order).order_by(Order.requested_at.desc())).all()

    def list_positions(self) -> list[Position]:
        with self.session_factory() as session:
            return session.exec(select(Position).order_by(Position.updated_at.desc())).all()

    def list_trades(self) -> list[Trade]:
        with self.session_factory() as session:
            return session.exec(select(Trade).order_by(Trade.timestamp.desc())).all()

    def list_decisions(self, limit: int = 100) -> list[StrategyDecisionLog]:
        with self.session_factory() as session:
            return session.exec(select(StrategyDecisionLog).order_by(StrategyDecisionLog.created_at.desc()).limit(limit)).all()

    def get_attribution_summary(self) -> dict[str, Any]:
        with self.session_factory() as session:
            trades = session.exec(select(Trade).order_by(Trade.timestamp.desc())).all()
            positions = session.exec(select(Position)).all()
            orders = session.exec(select(Order).order_by(Order.requested_at.desc())).all()
            decisions = session.exec(select(StrategyDecisionLog).order_by(StrategyDecisionLog.created_at.desc()).limit(300)).all()

        strategy_map: dict[str, dict[str, Any]] = {}
        regime_map: dict[str, dict[str, Any]] = {}
        reason_counts: dict[str, int] = {}
        total_fee = 0.0
        total_realized = 0.0
        expected_cost_bps_sum = 0.0
        slippage_bps_sum = 0.0

        for trade in trades:
            total_fee += trade.fee
            total_realized += trade.realized_pnl
            expected_cost_bps_sum += trade.expected_cost_bps
            slippage_bps_sum += trade.slippage_bps

            strategy_row = strategy_map.setdefault(
                trade.strategy_name,
                {"name": trade.strategy_name, "pnl": 0.0, "trade_count": 0, "wins": 0, "fees": 0.0},
            )
            strategy_row["pnl"] += trade.realized_pnl
            strategy_row["trade_count"] += 1
            strategy_row["fees"] += trade.fee
            if trade.realized_pnl > 0:
                strategy_row["wins"] += 1

            regime_key = trade.regime or "unknown"
            regime_row = regime_map.setdefault(regime_key, {"name": regime_key, "pnl": 0.0, "trade_count": 0})
            regime_row["pnl"] += trade.realized_pnl
            regime_row["trade_count"] += 1

        for order in orders[:200]:
            reason = order.decision_reason or order.risk_reason or "unknown"
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

        open_position_value = sum(position.market_value for position in positions)
        unrealized_pnl = sum(position.unrealized_pnl for position in positions)
        avg_expected_cost_bps = expected_cost_bps_sum / len(trades) if trades else 0.0
        avg_slippage_bps = slippage_bps_sum / len(trades) if trades else 0.0

        strategy_rows = []
        for item in strategy_map.values():
            trade_count = int(item["trade_count"])
            strategy_rows.append(
                {
                    "name": item["name"],
                    "pnl": round(float(item["pnl"]), 6),
                    "trade_count": trade_count,
                    "win_rate": round(float(item["wins"] / trade_count), 6) if trade_count else 0.0,
                    "fees": round(float(item["fees"]), 6),
                }
            )
        strategy_rows.sort(key=lambda item: item["pnl"], reverse=True)

        regime_rows = [
            {
                "name": item["name"],
                "pnl": round(float(item["pnl"]), 6),
                "trade_count": int(item["trade_count"]),
            }
            for item in regime_map.values()
        ]
        regime_rows.sort(key=lambda item: item["trade_count"], reverse=True)

        recent_decisions = [item.model_dump(mode="json") for item in decisions[:20]]
        top_reasons = [
            {"reason": reason, "count": count}
            for reason, count in sorted(reason_counts.items(), key=lambda entry: entry[1], reverse=True)[:12]
        ]

        return {
            "overview": {
                "total_realized_pnl": round(float(total_realized), 6),
                "total_unrealized_pnl": round(float(unrealized_pnl), 6),
                "total_fees": round(float(total_fee), 6),
                "open_position_value": round(float(open_position_value), 6),
                "avg_expected_cost_bps": round(float(avg_expected_cost_bps), 6),
                "avg_slippage_bps": round(float(avg_slippage_bps), 6),
            },
            "by_strategy": strategy_rows,
            "by_regime": regime_rows,
            "top_reasons": top_reasons,
            "recent_decisions": recent_decisions,
        }

    async def _snapshot_once(self) -> None:
        with self.session_factory() as session:
            summary = self._calculate_summary(session)
            snapshot = EquitySnapshot(
                timestamp=datetime.utcnow(),
                equity=summary["equity"],
                available_balance=summary["available_balance"],
                realized_pnl=summary["realized_pnl"],
                unrealized_pnl=summary["unrealized_pnl"],
                daily_pnl=summary["daily_pnl"],
                total_return=summary["total_return"],
            )
            session.add(snapshot)
            session.commit()
            self._summary_cache = summary
            await self.websocket_manager.broadcast("dashboard", {"type": "metrics", "summary": summary})

    async def run(self) -> None:
        self._running = True
        while self._running:
            await self._snapshot_once()
            await asyncio.sleep(5)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            await asyncio.wait([self._task], timeout=2)
