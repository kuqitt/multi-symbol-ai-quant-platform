from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any


class MarketDataService:
    def __init__(self, adapter: Any, config_service: Any, state: Any, websocket_manager: Any, logger: Any) -> None:
        self.adapter = adapter
        self.config_service = config_service
        self.state = state
        self.websocket_manager = websocket_manager
        self.logger = logger
        self._poll_task: asyncio.Task[None] | None = None
        self._stream_task: asyncio.Task[None] | None = None
        self._running = False

    def _serialize_ticker(self, ticker: Any) -> dict[str, Any]:
        return {
            "symbol": ticker.symbol,
            "price": ticker.price,
            "change_percent": ticker.change_percent,
            "bid": ticker.bid,
            "ask": ticker.ask,
            "spread": ticker.spread,
            "volume": ticker.volume,
            "sparkline": ticker.sparkline,
            "last_updated": ticker.last_updated,
            "market_type": getattr(ticker, "market_type", "spot"),
            "price_source": getattr(ticker, "price_source", "live"),
        }

    async def _handle_stream_event(self, event_type: str, symbol: str, payload: dict[str, Any]) -> None:
        if event_type == "ticker":
            self.state.latest_prices[symbol] = payload["price"]
            previous = self.state.latest_tickers.get(symbol, {})
            payload.setdefault("market_type", previous.get("market_type", self.config_service.get_runtime_config().market_type))
            payload.setdefault("price_source", previous.get("price_source", "live"))
            self.state.latest_tickers[symbol] = payload
            await self.websocket_manager.broadcast("dashboard", {"type": "market", "tickers": [payload]})
        elif event_type == "trade":
            trades = self.state.latest_trades.setdefault(symbol, [])
            trades.insert(0, payload)
            del trades[50:]
            await self.websocket_manager.broadcast("dashboard", {"type": "trade", "symbol": symbol, "trade": payload})
        elif event_type == "orderbook":
            self.state.latest_orderbooks[symbol] = payload
            await self.websocket_manager.broadcast("dashboard", {"type": "orderbook", "symbol": symbol, "orderbook": payload})
        elif event_type == "candle":
            klines = self.state.latest_klines.setdefault(symbol, [])
            normalized = {
                "timestamp": datetime.fromisoformat(payload["timestamp"])
                if isinstance(payload["timestamp"], str)
                else payload["timestamp"],
                "open": payload["open"],
                "high": payload["high"],
                "low": payload["low"],
                "close": payload["close"],
                "volume": payload["volume"],
            }
            if klines and klines[-1]["timestamp"] == normalized["timestamp"]:
                klines[-1] = normalized
            else:
                klines.append(normalized)
            del klines[:-500]
            await self.websocket_manager.broadcast("dashboard", {"type": "candle", "symbol": symbol, "candle": payload})
        self.state.touch()

    async def refresh_once(self) -> None:
        config = self.config_service.get_runtime_config()
        tickers: list[dict[str, Any]] = []
        for symbol in config.symbols:
            ticker = await self.adapter.fetch_ticker(symbol)
            candles = await self.adapter.fetch_ohlcv(symbol, config.timeframe, limit=120)
            orderbook = await self.adapter.fetch_orderbook(symbol)
            latest_trade = await self.adapter.fetch_latest_trade(symbol)
            self.state.latest_prices[symbol] = ticker.price
            self.state.latest_tickers[symbol] = self._serialize_ticker(ticker)
            self.state.latest_klines[symbol] = candles
            self.state.latest_orderbooks[symbol] = {
                "symbol": symbol,
                "bids": orderbook.bids,
                "asks": orderbook.asks,
                "timestamp": orderbook.timestamp,
            }
            self.state.latest_trades[symbol] = [
                {
                    "symbol": symbol,
                    "price": latest_trade.price,
                    "quantity": latest_trade.quantity,
                    "side": latest_trade.side,
                    "timestamp": latest_trade.timestamp,
                }
            ]
            tickers.append(self.state.latest_tickers[symbol])
        try:
            balance = await self.adapter.get_balance()
            self.state.account_balance = {
                "equity": balance.equity,
                "available_balance": balance.available_balance,
            }
        except Exception:
            self.logger.exception("账户余额刷新失败", extra={"category": "market"})
        self.state.touch()
        await self.websocket_manager.broadcast("dashboard", {"type": "market", "tickers": tickers})

    async def run_polling(self) -> None:
        while self._running:
            try:
                await self.refresh_once()
                self.state.clear_exchange_error()
            except Exception as exc:
                self.state.mark_exchange_error(f"market-data-error: {exc}")
                self.logger.exception("行情数据刷新失败", extra={"category": "market"})
            await asyncio.sleep(max(self.config_service.get_runtime_config().ui.refresh_interval_ms / 1000, 1.0))

    async def run_streaming(self) -> None:
        while self._running and getattr(self.adapter, "supports_streaming", False):
            config = self.config_service.get_runtime_config()
            try:
                await self.adapter.stream_market_data(
                    symbols=config.symbols,
                    timeframe=config.timeframe,
                    handler=self._handle_stream_event,
                )
            except Exception as exc:
                self.logger.exception("行情流连接断开：%s", exc, extra={"category": "market"})
                await asyncio.sleep(3)

    def start(self) -> None:
        self._running = True
        if self._poll_task is None or self._poll_task.done():
            self._poll_task = asyncio.create_task(self.run_polling())
        if getattr(self.adapter, "supports_streaming", False) and (self._stream_task is None or self._stream_task.done()):
            self._stream_task = asyncio.create_task(self.run_streaming())

    async def stop(self) -> None:
        self._running = False
        if self._poll_task:
            await asyncio.wait([self._poll_task], timeout=2)
        if self._stream_task:
            await asyncio.wait([self._stream_task], timeout=2)
        await self.adapter.close()
