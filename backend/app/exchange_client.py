from __future__ import annotations

from app.adapters.base_adapter import BaseExchangeAdapter
from app.adapters.binance_adapter import BinanceAdapter
from app.adapters.okx_adapter import OKXAdapter
from app.config import AppConfig, EnvironmentSettings


def create_exchange_adapter(config: AppConfig, env_settings: EnvironmentSettings) -> BaseExchangeAdapter:
    starting_balance = config.simulation.starting_balance or env_settings.paper_balance
    if config.exchange == "okx":
        return OKXAdapter(config=config, env_settings=env_settings, starting_balance=starting_balance)
    if config.exchange == "binance":
        return BinanceAdapter(config=config, env_settings=env_settings, starting_balance=starting_balance)
    raise ValueError(f"Unsupported exchange adapter: {config.exchange}")
