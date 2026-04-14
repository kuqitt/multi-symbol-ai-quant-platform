from __future__ import annotations

from datetime import datetime, timedelta

from app.metrics import compute_max_drawdown, summarize_performance
from app.models import EquitySnapshot, Position, Trade


def test_metrics_summary_and_drawdown() -> None:
    positions = [
        Position(symbol="BTC/USDT", quantity=1, avg_price=100, market_price=110, realized_pnl=5, unrealized_pnl=10),
        Position(symbol="ETH/USDT", quantity=0, avg_price=0, market_price=0, realized_pnl=-2, unrealized_pnl=0),
    ]
    trades = [
        Trade(symbol="BTC/USDT", client_order_id="1", side="SELL", quantity=1, price=110, realized_pnl=5),
        Trade(symbol="ETH/USDT", client_order_id="2", side="SELL", quantity=1, price=90, realized_pnl=-2),
    ]
    snapshots = [
        EquitySnapshot(timestamp=datetime.utcnow() - timedelta(days=2), equity=100000),
        EquitySnapshot(timestamp=datetime.utcnow() - timedelta(days=1), equity=98000),
        EquitySnapshot(timestamp=datetime.utcnow(), equity=101000),
    ]
    summary = summarize_performance(
        starting_equity=100000,
        current_equity=101000,
        available_balance=90000,
        positions=positions,
        trades=trades,
        snapshots=snapshots,
        strategy_status="RUNNING",
        risk_status="NORMAL",
    )
    assert summary["total_pnl"] == 1000
    assert summary["realized_pnl"] == 3
    assert compute_max_drawdown([100000, 98000, 101000]) < 0

