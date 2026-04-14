from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.config import AppConfig, BusinessConfig, SystemConfig


class HealthResponse(BaseModel):
    ok: bool = True
    env: str
    exchange: str
    database: str


class StatusResponse(BaseModel):
    status: str
    risk_status: str
    env: str
    exchange: str
    strategy_running: bool
    live_enabled: bool
    last_heartbeat: datetime | None
    latest_alerts: list[dict[str, Any]]
    symbol_states: list[dict[str, Any]] = Field(default_factory=list)
    paper_account: dict[str, Any] = Field(default_factory=dict)


class ActionResponse(BaseModel):
    success: bool
    status: str
    message: str


class PaperAccountResetRequest(BaseModel):
    starting_balance: float | None = None


class PaperAccountResetResponse(ActionResponse):
    starting_balance: float
    equity: float
    available_balance: float


class ConfigUpdateRequest(BaseModel):
    config: BusinessConfig
    apply_immediately: bool = True
    changed_by: str = "web-ui"


class SystemConfigUpdateRequest(BaseModel):
    config: SystemConfig
    apply_immediately: bool = True
    changed_by: str = "web-ui"


class CredentialStatus(BaseModel):
    api_key_configured: bool
    api_key_masked: str = ""
    secret_configured: bool
    secret_masked: str = ""
    passphrase_configured: bool


class SystemConfigResponse(BaseModel):
    config: SystemConfig
    live_trading_enabled: bool
    secrets_source: str = "environment"
    database_hot_reload_supported: bool = False
    okx_credentials: CredentialStatus
    binance_credentials: CredentialStatus


class SeriesPoint(BaseModel):
    timestamp: datetime
    value: float


class DailyPnlPoint(BaseModel):
    date: str
    pnl: float


class MarketTickerRead(BaseModel):
    symbol: str
    price: float
    change_percent: float
    bid: float
    ask: float
    spread: float
    volume: float
    sparkline: list[float] = Field(default_factory=list)
    last_updated: datetime
    market_type: str = "spot"
    price_source: str = "live"


class PositionRead(BaseModel):
    id: int
    symbol: str
    side: str
    strategy_name: str
    quantity: float
    avg_price: float
    market_price: float
    market_value: float
    exposure_ratio: float
    realized_pnl: float
    unrealized_pnl: float
    regime: str = "unknown"
    entry_tag: str = ""
    stop_loss: float = 0.0
    take_profit: float = 0.0
    signal_score: float = 0.0
    target_weight: float = 0.0
    expected_cost_bps: float = 0.0
    updated_at: datetime


class OrderRead(BaseModel):
    id: int
    client_order_id: str
    signal_id: str
    strategy_name: str
    symbol: str
    side: str
    order_type: str
    status: str
    quantity: float
    price: float
    average_fill_price: float
    expected_price: float
    risk_checked: bool
    risk_reason: str
    decision_reason: str = ""
    regime: str = "unknown"
    signal_score: float = 0.0
    target_weight: float = 0.0
    expected_cost_bps: float = 0.0
    expected_slippage_bps: float = 0.0
    env: str
    is_live: bool
    requested_by: str
    requested_at: datetime
    updated_at: datetime
    metadata_json: dict[str, Any] | None = None


class TradeRead(BaseModel):
    id: int
    order_id: int | None
    client_order_id: str
    symbol: str
    side: str
    strategy_name: str
    quantity: float
    price: float
    fee: float
    realized_pnl: float
    regime: str = "unknown"
    entry_tag: str = ""
    exit_tag: str = ""
    signal_score: float = 0.0
    expected_cost_bps: float = 0.0
    slippage_bps: float = 0.0
    fee_bps: float = 0.0
    metadata_json: dict[str, Any] | None = None
    timestamp: datetime


class LogRead(BaseModel):
    id: int
    timestamp: datetime
    level: str
    category: str
    message: str
    metadata_json: dict[str, Any] | None = None


class RiskEventRead(BaseModel):
    id: int
    created_at: datetime
    level: str
    symbol: str
    strategy_name: str
    reason: str
    detail: str
    blocked: bool
    status_after: str
    metadata_json: dict[str, Any] | None = None


class SummaryMetricsResponse(BaseModel):
    equity: float
    available_balance: float
    total_pnl: float
    daily_pnl: float
    total_return: float
    daily_return: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    avg_win_loss_ratio: float
    total_trades: int
    trades_today: int
    position_count: int
    realized_pnl: float
    unrealized_pnl: float
    per_symbol_pnl: dict[str, float]
    strategy_status: str
    risk_status: str
    strategy_breakdown: dict[str, float] = Field(default_factory=dict)


class AttributionOverviewRead(BaseModel):
    total_realized_pnl: float
    total_unrealized_pnl: float
    total_fees: float
    open_position_value: float
    avg_expected_cost_bps: float
    avg_slippage_bps: float


class AttributionBucketRead(BaseModel):
    name: str
    pnl: float
    trade_count: int
    win_rate: float | None = None
    fees: float | None = None


class ReasonCountRead(BaseModel):
    reason: str
    count: int


class StrategyDecisionLogRead(BaseModel):
    id: int
    created_at: datetime
    symbol: str
    timeframe: str
    strategy_name: str
    signal: str
    final_action: str
    reason: str
    regime: str
    confidence: float
    signal_score: float
    buy_score: float
    sell_score: float
    target_weight: float
    desired_notional: float
    expected_cost_bps: float
    context_json: dict[str, Any] | None = None


class AttributionResponse(BaseModel):
    overview: AttributionOverviewRead
    by_strategy: list[AttributionBucketRead] = Field(default_factory=list)
    by_regime: list[AttributionBucketRead] = Field(default_factory=list)
    top_reasons: list[ReasonCountRead] = Field(default_factory=list)
    recent_decisions: list[StrategyDecisionLogRead] = Field(default_factory=list)


class BacktestRunRequest(BaseModel):
    name: str = "latest-backtest"
    csv_paths: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)
    use_current_config: bool = True


class OptimizationRunRequest(BaseModel):
    name: str = "latest-optimization"
    symbol: str | None = None
    csv_path: str | None = None
    strategy_name: str = "ma_rsi"


class BacktestResultRead(BaseModel):
    id: int
    created_at: datetime
    name: str
    symbols_csv: str
    total_return: float
    win_rate: float
    max_drawdown: float
    sharpe: float
    summary_json: dict[str, Any] | None
    trades_csv_path: str
    report_json_path: str


class OptimizationResultRead(BaseModel):
    id: int
    created_at: datetime
    name: str
    symbol: str
    strategy_name: str
    score: float
    parameters_json: dict[str, Any] | None
    walk_forward_json: dict[str, Any] | None


class DashboardPayload(BaseModel):
    status: StatusResponse
    metrics: SummaryMetricsResponse
    tickers: list[MarketTickerRead]
    positions: list[PositionRead]
    alerts: list[dict[str, Any]]
    recent_logs: list[LogRead]


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class UserRead(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "viewer"


class ApprovalRead(BaseModel):
    id: int
    order_id: int | None
    signal_id: str
    symbol: str
    side: str
    quantity: float
    expected_price: float
    notional: float
    status: str
    reason: str
    requested_by: str
    reviewed_by: str
    requested_at: datetime
    reviewed_at: datetime | None
    expires_at: datetime | None
    request_payload: dict[str, Any] | None = None


class ApprovalDecisionRequest(BaseModel):
    comment: str = ""
