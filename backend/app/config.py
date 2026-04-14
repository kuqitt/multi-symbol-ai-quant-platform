from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = BASE_DIR / "config.yaml"

EnvironmentName = Literal["paper", "testnet", "demo", "live"]
ExchangeName = Literal["okx", "binance"]
MarketType = Literal["spot", "futures"]
OrderType = Literal["market", "limit"]


class StrategyConfig(BaseModel):
    ma_fast: int = 5
    ma_slow: int = 20
    rsi_period: int = 14
    rsi_buy_threshold: float = 55.0
    rsi_sell_threshold: float = 45.0
    atr_period: int = 14
    stop_loss_atr_multiple: float = 1.5
    take_profit_atr_multiple: float = 2.5

    @model_validator(mode="after")
    def validate_windows(self) -> "StrategyConfig":
        if self.ma_fast >= self.ma_slow:
            raise ValueError("ma_fast must be smaller than ma_slow")
        return self


class RiskConfig(BaseModel):
    risk_per_trade: float = 0.005
    max_daily_loss: float = 0.02
    max_symbol_exposure: float = 0.2
    max_total_exposure: float = 0.6
    max_strategy_exposure: float = 0.35
    max_portfolio_heat: float = 0.03
    max_consecutive_losses: int = 3
    max_slippage: float = 0.002
    max_spread: float = 0.003


class ExecutionConfig(BaseModel):
    order_type: OrderType = "market"
    retry_count: int = 2


class StrategyEngineConfig(BaseModel):
    enabled_strategies: list[str] = Field(default_factory=lambda: ["ma_rsi", "trend_breakout"])
    selection_mode: Literal["vote", "weighted"] = "weighted"
    strategy_weights: dict[str, float] = Field(default_factory=lambda: {"ma_rsi": 1.0, "trend_breakout": 0.8})
    minimum_confidence: float = 0.55

    @field_validator("enabled_strategies")
    @classmethod
    def validate_enabled_strategies(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if not cleaned:
            raise ValueError("At least one strategy must be enabled")
        return list(dict.fromkeys(cleaned))


class RegimeConfig(BaseModel):
    enabled: bool = True
    trend_lookback: int = 30
    trend_strength_threshold: float = 0.015
    high_volatility_threshold: float = 0.035
    low_volatility_threshold: float = 0.008
    confidence_floor: float = 0.55


class SignalPolicyConfig(BaseModel):
    min_signal_score: float = 0.58
    ai_weight: float = 0.15
    regime_weight: float = 0.2
    momentum_weight: float = 0.35
    mean_reversion_weight: float = 0.2
    breakout_weight: float = 0.25
    sell_score_buffer: float = 0.02


class AllocationConfig(BaseModel):
    enabled: bool = True
    base_risk_budget: float = 1.0
    min_notional_ratio: float = 0.05
    max_notional_ratio: float = 0.2
    max_concurrent_positions: int = 5
    regime_multipliers: dict[str, float] = Field(
        default_factory=lambda: {
            "trending_up": 1.15,
            "trending_down": 0.85,
            "range": 0.75,
            "volatile": 0.6,
            "unknown": 0.5,
        }
    )


class CostModelConfig(BaseModel):
    enabled: bool = True
    taker_fee_bps: float = 4.0
    slippage_spread_weight: float = 0.6
    impact_weight: float = 0.25
    max_cost_bps: float = 35.0


class OptimizationConfig(BaseModel):
    enable_grid_search: bool = True
    walk_forward_train_bars: int = 180
    walk_forward_test_bars: int = 60
    parameter_grid: dict[str, list[int | float]] = Field(
        default_factory=lambda: {
            "ma_fast": [5, 8, 10],
            "ma_slow": [20, 30, 40],
            "rsi_buy_threshold": [52, 55, 58],
            "rsi_sell_threshold": [42, 45, 48],
        }
    )


class ApprovalConfig(BaseModel):
    enabled: bool = False
    require_manual_approval_for_live: bool = True
    require_manual_approval_for_large_orders: bool = True
    auto_approve_small_accounts: bool = True
    auto_approve_below_equity: float = 1000.0
    approval_min_notional: float = 5000.0
    approval_timeout_seconds: int = 900

    @field_validator("auto_approve_below_equity", "approval_min_notional")
    @classmethod
    def validate_non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("approval thresholds must be non-negative")
        return value


class AuthConfig(BaseModel):
    access_token_ttl_minutes: int = 720


class NotifierConfig(BaseModel):
    telegram_enabled: bool = False
    feishu_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    feishu_app_id: str = ""
    feishu_webhook_url: str = ""
    feishu_app_secret: str = ""
    feishu_receive_id: str = ""
    feishu_receive_id_type: Literal["open_id", "user_id", "union_id", "chat_id", "email"] = "chat_id"


class SimulationConfig(BaseModel):
    starting_balance: float = 1000.0
    fee_rate: float = 0.0004
    use_live_market_data: bool = True
    max_slippage_multiplier: float = 2.0
    max_spread_multiplier: float = 1.5
    reset_account_on_start: bool = False

    @field_validator("starting_balance", "fee_rate", "max_slippage_multiplier", "max_spread_multiplier")
    @classmethod
    def validate_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("simulation values must be greater than zero")
        return value


class UIConfig(BaseModel):
    refresh_interval_ms: int = 1000
    chart_points_limit: int = 500


class LoggingConfig(BaseModel):
    level: str = "INFO"


class OKXConnectorConfig(BaseModel):
    base_url: str = "https://www.okx.com"
    public_ws_url: str = "wss://ws.okx.com:8443/ws/v5/public"
    demo_public_ws_url: str = "wss://wspap.okx.com:8443/ws/v5/public"
    demo_broker_id: str = "9999"


class BinanceConnectorConfig(BaseModel):
    base_url: str = "https://api.binance.com"
    testnet_base_url: str = "https://testnet.binance.vision"
    public_ws_url: str = "wss://stream.binance.com:9443/stream"
    testnet_public_ws_url: str = "wss://testnet.binance.vision/stream"


class ConnectorsConfig(BaseModel):
    okx: OKXConnectorConfig = Field(default_factory=OKXConnectorConfig)
    binance: BinanceConnectorConfig = Field(default_factory=BinanceConnectorConfig)


class BusinessConfig(BaseModel):
    symbols: list[str] = Field(default_factory=lambda: ["BTC/USDT", "ETH/USDT", "SOL/USDT"])
    timeframe: str = "1m"
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    strategy_engine: StrategyEngineConfig = Field(default_factory=StrategyEngineConfig)
    regime: RegimeConfig = Field(default_factory=RegimeConfig)
    signal: SignalPolicyConfig = Field(default_factory=SignalPolicyConfig)
    allocation: AllocationConfig = Field(default_factory=AllocationConfig)
    cost_model: CostModelConfig = Field(default_factory=CostModelConfig)
    optimization: OptimizationConfig = Field(default_factory=OptimizationConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip().upper() for value in values if value.strip()]
        if not cleaned:
            raise ValueError("At least one symbol is required")
        return list(dict.fromkeys(cleaned))


class SystemConfig(BaseModel):
    exchange: ExchangeName = "okx"
    env: EnvironmentName = "paper"
    market_type: MarketType = "spot"
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    approval: ApprovalConfig = Field(default_factory=ApprovalConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    notifier: NotifierConfig = Field(default_factory=NotifierConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    connectors: ConnectorsConfig = Field(default_factory=ConnectorsConfig)


class AppConfig(BaseModel):
    exchange: ExchangeName = "okx"
    env: EnvironmentName = "paper"
    market_type: MarketType = "spot"
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    symbols: list[str] = Field(default_factory=lambda: ["BTC/USDT", "ETH/USDT", "SOL/USDT"])
    timeframe: str = "1m"
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    strategy_engine: StrategyEngineConfig = Field(default_factory=StrategyEngineConfig)
    regime: RegimeConfig = Field(default_factory=RegimeConfig)
    signal: SignalPolicyConfig = Field(default_factory=SignalPolicyConfig)
    allocation: AllocationConfig = Field(default_factory=AllocationConfig)
    cost_model: CostModelConfig = Field(default_factory=CostModelConfig)
    optimization: OptimizationConfig = Field(default_factory=OptimizationConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    approval: ApprovalConfig = Field(default_factory=ApprovalConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    notifier: NotifierConfig = Field(default_factory=NotifierConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    connectors: ConnectorsConfig = Field(default_factory=ConnectorsConfig)

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip().upper() for value in values if value.strip()]
        if not cleaned:
            raise ValueError("At least one symbol is required")
        return list(dict.fromkeys(cleaned))

    def to_business_config(self) -> BusinessConfig:
        return BusinessConfig(
            symbols=self.symbols,
            timeframe=self.timeframe,
            strategy=self.strategy.model_copy(deep=True),
            strategy_engine=self.strategy_engine.model_copy(deep=True),
            regime=self.regime.model_copy(deep=True),
            signal=self.signal.model_copy(deep=True),
            allocation=self.allocation.model_copy(deep=True),
            cost_model=self.cost_model.model_copy(deep=True),
            optimization=self.optimization.model_copy(deep=True),
            risk=self.risk.model_copy(deep=True),
            execution=self.execution.model_copy(deep=True),
        )

    def to_system_config(self) -> SystemConfig:
        return SystemConfig(
            exchange=self.exchange,
            env=self.env,
            market_type=self.market_type,
            simulation=self.simulation.model_copy(deep=True),
            approval=self.approval.model_copy(deep=True),
            auth=self.auth.model_copy(deep=True),
            notifier=self.notifier.model_copy(deep=True),
            ui=self.ui.model_copy(deep=True),
            logging=self.logging.model_copy(deep=True),
            connectors=self.connectors.model_copy(deep=True),
        )

    def apply_business_config(self, business: BusinessConfig) -> "AppConfig":
        payload = self.model_dump(mode="python")
        payload.update(
            {
                "symbols": business.symbols,
                "timeframe": business.timeframe,
                "strategy": business.strategy.model_dump(mode="python"),
                "strategy_engine": business.strategy_engine.model_dump(mode="python"),
                "regime": business.regime.model_dump(mode="python"),
                "signal": business.signal.model_dump(mode="python"),
                "allocation": business.allocation.model_dump(mode="python"),
                "cost_model": business.cost_model.model_dump(mode="python"),
                "optimization": business.optimization.model_dump(mode="python"),
                "risk": business.risk.model_dump(mode="python"),
                "execution": business.execution.model_dump(mode="python"),
            }
        )
        return AppConfig.model_validate(payload)

    def apply_system_config(self, system: SystemConfig) -> "AppConfig":
        payload = self.model_dump(mode="python")
        payload.update(
            {
                "exchange": system.exchange,
                "env": system.env,
                "market_type": system.market_type,
                "simulation": system.simulation.model_dump(mode="python"),
                "approval": system.approval.model_dump(mode="python"),
                "auth": system.auth.model_dump(mode="python"),
                "notifier": system.notifier.model_dump(mode="python"),
                "ui": system.ui.model_dump(mode="python"),
                "logging": system.logging.model_dump(mode="python"),
                "connectors": system.connectors.model_dump(mode="python"),
            }
        )
        return AppConfig.model_validate(payload)


class EnvironmentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    api_key: str = ""
    api_secret: str = ""
    api_passphrase: str = ""
    okx_api_key: str = ""
    okx_api_secret: str = ""
    okx_api_passphrase: str = ""
    binance_api_key: str = ""
    binance_api_secret: str = ""
    enable_live_trading: bool = False
    database_url: str = f"sqlite:///{(BASE_DIR / 'trading.db').as_posix()}"
    secret_key: str = "quant-platform-default-secret-key-change-in-production-2026"
    paper_balance: float = 100000.0
    admin_username: str = "admin"
    admin_password: str = "ChangeMe123!"
    access_token_ttl_minutes: int = 720
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    feishu_app_id: str = ""
    feishu_webhook_url: str = ""
    feishu_app_secret: str = ""
    feishu_receive_id: str = ""
    feishu_receive_id_type: str = "chat_id"


def read_config_file(path: Path | None = None) -> AppConfig:
    config_path = path or DEFAULT_CONFIG_PATH
    data: dict[str, Any] = {}
    if config_path.exists():
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(data)


def write_config_file(config: AppConfig, path: Path | None = None) -> None:
    config_path = path or DEFAULT_CONFIG_PATH
    config_path.write_text(
        yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def validate_runtime(config: AppConfig, env_settings: EnvironmentSettings) -> None:
    if config.env == "live" and not env_settings.enable_live_trading:
        raise ValueError("env=live detected but ENABLE_LIVE_TRADING is false. Live trading is blocked by default.")


@lru_cache(maxsize=1)
def get_env_settings() -> EnvironmentSettings:
    return EnvironmentSettings()
