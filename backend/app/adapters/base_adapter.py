from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable


@dataclass
class InstrumentRule:
    symbol: str
    price_precision: int
    quantity_precision: int
    min_quantity: float
    tick_size: float


@dataclass
class TickerSnapshot:
    symbol: str
    price: float
    change_percent: float
    bid: float
    ask: float
    spread: float
    volume: float
    last_updated: datetime
    sparkline: list[float] = field(default_factory=list)
    market_type: str = "spot"
    price_source: str = "live"


@dataclass
class OrderbookSnapshot:
    symbol: str
    bids: list[list[float]]
    asks: list[list[float]]
    timestamp: datetime


@dataclass
class LatestTradeSnapshot:
    symbol: str
    price: float
    quantity: float
    side: str
    timestamp: datetime


@dataclass
class AdapterBalance:
    equity: float
    available_balance: float
    currency: str = "USDT"


@dataclass
class AdapterPosition:
    symbol: str
    quantity: float
    avg_price: float
    market_price: float
    unrealized_pnl: float


@dataclass
class AdapterOrder:
    client_order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: float
    status: str
    average_fill_price: float
    created_at: datetime


@dataclass
class AdapterOrderResult:
    client_order_id: str
    status: str
    fill_price: float
    requested_price: float
    filled_quantity: float
    message: str
    raw: dict[str, Any] = field(default_factory=dict)


MarketStreamHandler = Callable[[str, str, dict[str, Any]], Awaitable[None]]


class BaseExchangeAdapter(ABC):
    def __init__(self, exchange_name: str, env: str) -> None:
        self.exchange_name = exchange_name
        self.env = env

    @abstractmethod
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        raise NotImplementedError

    @abstractmethod
    async def fetch_orderbook(self, symbol: str) -> OrderbookSnapshot:
        raise NotImplementedError

    @abstractmethod
    async def fetch_latest_trade(self, symbol: str) -> LatestTradeSnapshot:
        raise NotImplementedError

    @abstractmethod
    async def place_order(
        self,
        *,
        client_order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        price: float | None = None,
    ) -> AdapterOrderResult:
        raise NotImplementedError

    @abstractmethod
    async def cancel_order(self, client_order_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def get_balance(self) -> AdapterBalance:
        raise NotImplementedError

    @abstractmethod
    async def get_positions(self) -> list[AdapterPosition]:
        raise NotImplementedError

    @abstractmethod
    async def get_orders(self) -> list[AdapterOrder]:
        raise NotImplementedError

    @abstractmethod
    async def get_instrument_rule(self, symbol: str) -> InstrumentRule:
        raise NotImplementedError

    @property
    def supports_streaming(self) -> bool:
        return False

    async def stream_market_data(
        self,
        *,
        symbols: list[str],
        timeframe: str,
        handler: MarketStreamHandler,
    ) -> None:
        raise NotImplementedError(f"{self.exchange_name} adapter does not implement streaming")

    async def close(self) -> None:
        return None
