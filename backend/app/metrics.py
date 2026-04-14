from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from app.models import EquitySnapshot, Position, Trade


def build_equity_curve_points(snapshots: list[EquitySnapshot]) -> list[dict[str, Any]]:
    return [{"timestamp": item.timestamp, "value": item.equity} for item in snapshots]


def build_drawdown_points(snapshots: list[EquitySnapshot]) -> list[dict[str, Any]]:
    if not snapshots:
        return []
    equity = pd.Series([snapshot.equity for snapshot in snapshots])
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max.replace(0, pd.NA)
    return [{"timestamp": snapshots[idx].timestamp, "value": float(drawdown.iloc[idx])} for idx in range(len(snapshots))]


def build_daily_pnl_points(trades: list[Trade]) -> list[dict[str, Any]]:
    if not trades:
        return []
    frame = pd.DataFrame(
        [{"date": trade.timestamp.date().isoformat(), "pnl": trade.realized_pnl} for trade in trades]
    )
    grouped = frame.groupby("date", as_index=False).sum(numeric_only=True)
    return grouped.to_dict(orient="records")


def compute_max_drawdown(values: list[float]) -> float:
    if not values:
        return 0.0
    series = pd.Series(values)
    running_max = series.cummax()
    drawdown = (series - running_max) / running_max.replace(0, pd.NA)
    return float(drawdown.min())


def summarize_performance(
    *,
    starting_equity: float,
    current_equity: float,
    available_balance: float,
    positions: list[Position],
    trades: list[Trade],
    snapshots: list[EquitySnapshot],
    strategy_status: str,
    risk_status: str,
) -> dict[str, Any]:
    realized_pnl = sum(item.realized_pnl for item in positions)
    unrealized_pnl = sum(item.unrealized_pnl for item in positions)
    total_pnl = current_equity - starting_equity
    today = datetime.utcnow().date()
    trades_today = [trade for trade in trades if trade.timestamp.date() == today]
    daily_pnl = sum(trade.realized_pnl for trade in trades_today) + unrealized_pnl
    total_return = total_pnl / starting_equity if starting_equity else 0.0
    daily_return = daily_pnl / starting_equity if starting_equity else 0.0

    wins = [trade.realized_pnl for trade in trades if trade.realized_pnl > 0]
    losses = [abs(trade.realized_pnl) for trade in trades if trade.realized_pnl < 0]
    total_trades = len(trades)
    win_rate = len(wins) / total_trades if total_trades else 0.0
    profit_factor = sum(wins) / sum(losses) if losses else float(sum(wins)) if wins else 0.0
    avg_win_loss_ratio = (sum(wins) / len(wins)) / (sum(losses) / len(losses)) if wins and losses else 0.0
    max_drawdown = compute_max_drawdown([snapshot.equity for snapshot in snapshots] or [current_equity])
    per_symbol_pnl = {
        position.symbol: round(position.realized_pnl + position.unrealized_pnl, 6) for position in positions if position.symbol
    }
    strategy_breakdown: dict[str, float] = {}
    for position in positions:
        if not position.strategy_name:
            continue
        strategy_breakdown[position.strategy_name] = round(
            strategy_breakdown.get(position.strategy_name, 0.0) + position.market_value,
            6,
        )
    return {
        "equity": round(current_equity, 6),
        "available_balance": round(available_balance, 6),
        "total_pnl": round(total_pnl, 6),
        "daily_pnl": round(daily_pnl, 6),
        "total_return": round(total_return, 6),
        "daily_return": round(daily_return, 6),
        "max_drawdown": round(max_drawdown, 6),
        "win_rate": round(win_rate, 6),
        "profit_factor": round(profit_factor, 6),
        "avg_win_loss_ratio": round(avg_win_loss_ratio, 6),
        "total_trades": total_trades,
        "trades_today": len(trades_today),
        "position_count": len([position for position in positions if position.quantity > 0]),
        "realized_pnl": round(realized_pnl, 6),
        "unrealized_pnl": round(unrealized_pnl, 6),
        "per_symbol_pnl": per_symbol_pnl,
        "strategy_status": strategy_status,
        "risk_status": risk_status,
        "strategy_breakdown": strategy_breakdown,
    }
