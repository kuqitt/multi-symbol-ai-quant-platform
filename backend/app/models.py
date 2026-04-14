from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, String
from sqlmodel import Field, SQLModel


class StrategyRun(SQLModel, table=True):
    __tablename__ = "strategy_runs"

    id: int | None = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    ended_at: datetime | None = Field(default=None, index=True)
    status: str = Field(default="STOPPED", index=True)
    mode: str = Field(default="paper")
    env: str = Field(default="paper")
    note: str = Field(default="")
    total_symbols: int = Field(default=0)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(sa_column=Column(String, unique=True, nullable=False, index=True))
    hashed_password: str = Field(default="")
    role: str = Field(default="viewer", index=True)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class Position(SQLModel, table=True):
    __tablename__ = "positions"

    id: int | None = Field(default=None, primary_key=True)
    symbol: str = Field(index=True)
    side: str = Field(default="LONG")
    strategy_name: str = Field(default="manual", index=True)
    quantity: float = Field(default=0.0)
    avg_price: float = Field(default=0.0)
    market_price: float = Field(default=0.0)
    market_value: float = Field(default=0.0)
    exposure_ratio: float = Field(default=0.0)
    realized_pnl: float = Field(default=0.0)
    unrealized_pnl: float = Field(default=0.0)
    regime: str = Field(default="unknown", index=True)
    entry_tag: str = Field(default="")
    stop_loss: float = Field(default=0.0)
    take_profit: float = Field(default=0.0)
    signal_score: float = Field(default=0.0)
    target_weight: float = Field(default=0.0)
    expected_cost_bps: float = Field(default=0.0)
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class Order(SQLModel, table=True):
    __tablename__ = "orders"

    id: int | None = Field(default=None, primary_key=True)
    client_order_id: str = Field(sa_column=Column(String, unique=True, nullable=False, index=True))
    signal_id: str = Field(default="", index=True)
    strategy_name: str = Field(default="manual", index=True)
    symbol: str = Field(index=True)
    side: str = Field(index=True)
    order_type: str = Field(default="market")
    status: str = Field(default="NEW", index=True)
    quantity: float = Field(default=0.0)
    price: float = Field(default=0.0)
    average_fill_price: float = Field(default=0.0)
    expected_price: float = Field(default=0.0)
    risk_checked: bool = Field(default=False)
    risk_reason: str = Field(default="")
    decision_reason: str = Field(default="", index=True)
    regime: str = Field(default="unknown", index=True)
    signal_score: float = Field(default=0.0)
    target_weight: float = Field(default=0.0)
    expected_cost_bps: float = Field(default=0.0)
    expected_slippage_bps: float = Field(default=0.0)
    env: str = Field(default="paper")
    is_live: bool = Field(default=False)
    requested_by: str = Field(default="system", index=True)
    requested_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    metadata_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))


class OrderApproval(SQLModel, table=True):
    __tablename__ = "order_approvals"

    id: int | None = Field(default=None, primary_key=True)
    order_id: int | None = Field(default=None, foreign_key="orders.id", index=True)
    signal_id: str = Field(default="", index=True)
    symbol: str = Field(default="", index=True)
    side: str = Field(default="")
    quantity: float = Field(default=0.0)
    expected_price: float = Field(default=0.0)
    notional: float = Field(default=0.0)
    status: str = Field(default="PENDING", index=True)
    reason: str = Field(default="")
    requested_by: str = Field(default="system")
    reviewed_by: str = Field(default="")
    requested_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    reviewed_at: datetime | None = Field(default=None, index=True)
    expires_at: datetime | None = Field(default=None, index=True)
    request_payload: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))


class Trade(SQLModel, table=True):
    __tablename__ = "trades"

    id: int | None = Field(default=None, primary_key=True)
    order_id: int | None = Field(default=None, foreign_key="orders.id", index=True)
    client_order_id: str = Field(index=True)
    symbol: str = Field(index=True)
    side: str = Field(index=True)
    strategy_name: str = Field(default="manual", index=True)
    quantity: float = Field(default=0.0)
    price: float = Field(default=0.0)
    fee: float = Field(default=0.0)
    realized_pnl: float = Field(default=0.0)
    regime: str = Field(default="unknown", index=True)
    entry_tag: str = Field(default="")
    exit_tag: str = Field(default="")
    signal_score: float = Field(default=0.0)
    expected_cost_bps: float = Field(default=0.0)
    slippage_bps: float = Field(default=0.0)
    fee_bps: float = Field(default=0.0)
    metadata_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)


class StrategyDecisionLog(SQLModel, table=True):
    __tablename__ = "strategy_decisions"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    symbol: str = Field(index=True)
    timeframe: str = Field(default="1m")
    strategy_name: str = Field(default="unknown", index=True)
    signal: str = Field(default="HOLD", index=True)
    final_action: str = Field(default="HOLD", index=True)
    reason: str = Field(default="", index=True)
    regime: str = Field(default="unknown", index=True)
    confidence: float = Field(default=0.0)
    signal_score: float = Field(default=0.0)
    buy_score: float = Field(default=0.0)
    sell_score: float = Field(default=0.0)
    target_weight: float = Field(default=0.0)
    desired_notional: float = Field(default=0.0)
    expected_cost_bps: float = Field(default=0.0)
    context_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))


class EquitySnapshot(SQLModel, table=True):
    __tablename__ = "equity_snapshots"

    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    equity: float = Field(default=0.0)
    available_balance: float = Field(default=0.0)
    realized_pnl: float = Field(default=0.0)
    unrealized_pnl: float = Field(default=0.0)
    daily_pnl: float = Field(default=0.0)
    total_return: float = Field(default=0.0)


class RiskEvent(SQLModel, table=True):
    __tablename__ = "risk_events"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    level: str = Field(default="WARNING")
    symbol: str = Field(default="", index=True)
    strategy_name: str = Field(default="", index=True)
    reason: str = Field(default="", index=True)
    detail: str = Field(default="")
    blocked: bool = Field(default=True)
    status_after: str = Field(default="RUNNING")
    metadata_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))


class LogEntry(SQLModel, table=True):
    __tablename__ = "logs"

    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    level: str = Field(default="INFO", index=True)
    category: str = Field(default="system", index=True)
    message: str = Field(default="")
    metadata_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))


class BacktestResult(SQLModel, table=True):
    __tablename__ = "backtest_results"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    name: str = Field(default="default-backtest", index=True)
    symbols_csv: str = Field(default="")
    total_return: float = Field(default=0.0)
    win_rate: float = Field(default=0.0)
    max_drawdown: float = Field(default=0.0)
    sharpe: float = Field(default=0.0)
    summary_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    trades_csv_path: str = Field(default="")
    report_json_path: str = Field(default="")


class OptimizationResult(SQLModel, table=True):
    __tablename__ = "optimization_results"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    name: str = Field(default="latest-optimization", index=True)
    symbol: str = Field(default="", index=True)
    strategy_name: str = Field(default="", index=True)
    score: float = Field(default=0.0)
    parameters_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    walk_forward_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))


class ConfigHistory(SQLModel, table=True):
    __tablename__ = "config_history"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    apply_immediately: bool = Field(default=False)
    changed_by: str = Field(default="system")
    config_yaml: str = Field(default="")
