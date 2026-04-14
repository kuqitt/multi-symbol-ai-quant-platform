from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx
import websockets

from app.adapters.base_adapter import (
    AdapterBalance,
    AdapterOrder,
    AdapterOrderResult,
    AdapterPosition,
    BaseExchangeAdapter,
    InstrumentRule,
    LatestTradeSnapshot,
    MarketStreamHandler,
    OrderbookSnapshot,
    TickerSnapshot,
)
from app.adapters.simulator import PaperTradingSimulator
from app.config import AppConfig, EnvironmentSettings


def _precision_from_step(step_size: str) -> int:
    if "." not in step_size:
        return 0
    return len(step_size.rstrip("0").split(".")[1])


class BinanceAdapter(BaseExchangeAdapter):
    def __init__(self, config: AppConfig, env_settings: EnvironmentSettings, starting_balance: float = 1000.0) -> None:
        super().__init__(exchange_name="binance", env=config.env)
        self.env_settings = env_settings
        self.config = config
        self.starting_balance = starting_balance
        self.simulator = PaperTradingSimulator(
            "binance",
            starting_balance=starting_balance,
            fee_rate=config.simulation.fee_rate,
        )
        use_testnet = config.env in {"testnet", "demo"}
        binance_config = config.connectors.binance
        self.base_url = binance_config.testnet_base_url if use_testnet else binance_config.base_url
        self.ws_url = binance_config.testnet_public_ws_url if use_testnet else binance_config.public_ws_url
        self._http = httpx.AsyncClient(base_url=self.base_url, timeout=15.0)
        self._rules_cache: dict[str, InstrumentRule] = {}
        self._paper_ticker_cache: dict[str, TickerSnapshot] = {}

    @property
    def supports_streaming(self) -> bool:
        return self.env != "paper" or self.use_live_market_data_in_paper

    @property
    def use_live_market_data_in_paper(self) -> bool:
        return bool(self.config.simulation.use_live_market_data)

    @property
    def has_private_access(self) -> bool:
        api_key = self.env_settings.binance_api_key or self.env_settings.api_key
        api_secret = self.env_settings.binance_api_secret or self.env_settings.api_secret
        return bool(api_key and api_secret)

    def _symbol_to_exchange(self, symbol: str) -> str:
        return symbol.replace("/", "").upper()

    def _symbol_from_exchange(self, symbol: str) -> str:
        return symbol[:-4] + "/USDT" if symbol.endswith("USDT") else symbol

    def _sign_params(self, params: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        params = {**params, "timestamp": int(time.time() * 1000)}
        query = urlencode(params)
        api_secret = self.env_settings.binance_api_secret or self.env_settings.api_secret
        signature = hmac.new(api_secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()
        params["signature"] = signature
        headers = {"X-MBX-APIKEY": self.env_settings.binance_api_key or self.env_settings.api_key}
        return params, headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        auth: bool = False,
    ) -> Any:
        headers: dict[str, str] = {}
        final_params = params or {}
        if auth:
            final_params, headers = self._sign_params(final_params)
        response = await self._http.request(method, path, params=final_params, headers=headers)
        response.raise_for_status()
        return response.json()

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> list[dict[str, Any]]:
        if self.env == "paper" and not self.use_live_market_data_in_paper:
            return await self.simulator.fetch_ohlcv(symbol, limit=limit)
        payload = await self._request(
            "GET",
            "/api/v3/klines",
            params={"symbol": self._symbol_to_exchange(symbol), "interval": timeframe, "limit": limit},
        )
        return [
            {
                "timestamp": datetime.fromtimestamp(row[0] / 1000, tz=UTC).replace(tzinfo=None),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            }
            for row in payload
        ]

    async def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        if self.env == "paper" and not self.use_live_market_data_in_paper:
            return await self.simulator.fetch_ticker(symbol)
        symbol_value = self._symbol_to_exchange(symbol)
        ticker = await self._request("GET", "/api/v3/ticker/24hr", params={"symbol": symbol_value})
        best = await self._request("GET", "/api/v3/ticker/bookTicker", params={"symbol": symbol_value})
        last = float(ticker["lastPrice"])
        bid = float(best["bidPrice"])
        ask = float(best["askPrice"])
        snapshot = TickerSnapshot(
            symbol=symbol,
            price=last,
            change_percent=float(ticker["priceChangePercent"]),
            bid=bid,
            ask=ask,
            spread=((ask - bid) / last) if last else 0.0,
            volume=float(ticker["quoteVolume"]),
            last_updated=datetime.utcnow(),
            sparkline=[],
            market_type=self.config.market_type,
            price_source="live",
        )
        if self.env == "paper":
            self._paper_ticker_cache[symbol] = snapshot
            self.simulator.sync_quote(
                symbol,
                price=snapshot.price,
                bid=snapshot.bid,
                ask=snapshot.ask,
                volume=snapshot.volume,
                timestamp=snapshot.last_updated,
            )
        return snapshot

    async def fetch_orderbook(self, symbol: str) -> OrderbookSnapshot:
        if self.env == "paper" and not self.use_live_market_data_in_paper:
            return await self.simulator.fetch_orderbook(symbol)
        payload = await self._request(
            "GET",
            "/api/v3/depth",
            params={"symbol": self._symbol_to_exchange(symbol), "limit": 5},
        )
        return OrderbookSnapshot(
            symbol=symbol,
            bids=[[float(price), float(size)] for price, size in payload.get("bids", [])[:5]],
            asks=[[float(price), float(size)] for price, size in payload.get("asks", [])[:5]],
            timestamp=datetime.utcnow(),
        )

    async def fetch_latest_trade(self, symbol: str) -> LatestTradeSnapshot:
        if self.env == "paper" and not self.use_live_market_data_in_paper:
            return await self.simulator.fetch_latest_trade(symbol)
        payload = await self._request(
            "GET",
            "/api/v3/trades",
            params={"symbol": self._symbol_to_exchange(symbol), "limit": 1},
        )
        item = payload[0]
        return LatestTradeSnapshot(
            symbol=symbol,
            price=float(item["price"]),
            quantity=float(item["qty"]),
            side="sell" if item.get("isBuyerMaker") else "buy",
            timestamp=datetime.utcnow(),
        )

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
        if self.env == "paper" or not self.has_private_access:
            if self.env == "paper" and self.use_live_market_data_in_paper:
                ticker = self._paper_ticker_cache.get(symbol) or await self.fetch_ticker(symbol)
                self.simulator.sync_quote(
                    symbol,
                    price=ticker.price,
                    bid=ticker.bid,
                    ask=ticker.ask,
                    volume=ticker.volume,
                    timestamp=ticker.last_updated,
                )
            return await self.simulator.place_order(
                client_order_id=client_order_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                price=price,
            )
        rule = await self.get_instrument_rule(symbol)
        params: dict[str, Any] = {
            "symbol": self._symbol_to_exchange(symbol),
            "side": side,
            "type": "MARKET" if order_type == "market" else "LIMIT",
            "quantity": round(quantity, rule.quantity_precision),
            "newClientOrderId": client_order_id,
            "recvWindow": 5000,
        }
        if order_type == "limit":
            params["timeInForce"] = "GTC"
            params["price"] = round(price or 0.0, rule.price_precision)
        payload = await self._request("POST", "/api/v3/order", params=params, auth=True)
        executed_qty = float(payload.get("executedQty") or 0.0)
        fills = payload.get("fills") or []
        fill_price = float(fills[0]["price"]) if fills else float(payload.get("price") or price or 0.0)
        status = str(payload.get("status") or "NEW").upper()
        mapped_status = "FILLED" if status == "FILLED" else "OPEN" if status in {"NEW", "PARTIALLY_FILLED"} else status
        return AdapterOrderResult(
            client_order_id=client_order_id,
            status=mapped_status,
            fill_price=fill_price,
            requested_price=float(price or fill_price or 0.0),
            filled_quantity=executed_qty,
            message="binance order submitted",
            raw=payload,
        )

    async def cancel_order(self, client_order_id: str) -> bool:
        if self.env == "paper" or not self.has_private_access:
            return await self.simulator.cancel_order(client_order_id)
        open_orders = await self._request("GET", "/api/v3/openOrders", auth=True)
        target = next((item for item in open_orders if item.get("clientOrderId") == client_order_id), None)
        if target is None:
            return False
        await self._request(
            "DELETE",
            "/api/v3/order",
            params={"symbol": target["symbol"], "origClientOrderId": client_order_id},
            auth=True,
        )
        return True

    async def get_balance(self) -> AdapterBalance:
        if self.env == "paper" or not self.has_private_access:
            if self.env == "paper" and self.use_live_market_data_in_paper:
                for symbol in list(self.simulator.positions):
                    try:
                        await self.fetch_ticker(symbol)
                    except Exception:
                        continue
            return await self.simulator.get_balance()
        payload = await self._request("GET", "/api/v3/account", auth=True)
        usdt_balance = next((item for item in payload.get("balances", []) if item["asset"] == "USDT"), {"free": "0", "locked": "0"})
        available = float(usdt_balance["free"])
        equity = available + float(usdt_balance["locked"])
        return AdapterBalance(equity=equity, available_balance=available, currency="USDT")

    async def get_positions(self) -> list[AdapterPosition]:
        if self.env == "paper" or not self.has_private_access:
            if self.env == "paper" and self.use_live_market_data_in_paper:
                for symbol in list(self.simulator.positions):
                    try:
                        await self.fetch_ticker(symbol)
                    except Exception:
                        continue
            return await self.simulator.get_positions()
        payload = await self._request("GET", "/api/v3/account", auth=True)
        positions: list[AdapterPosition] = []
        for item in payload.get("balances", []):
            free_qty = float(item["free"])
            locked_qty = float(item["locked"])
            quantity = free_qty + locked_qty
            if quantity <= 0 or item["asset"] == "USDT":
                continue
            symbol = f"{item['asset']}/USDT"
            ticker = await self.fetch_ticker(symbol)
            positions.append(
                AdapterPosition(
                    symbol=symbol,
                    quantity=quantity,
                    avg_price=ticker.price,
                    market_price=ticker.price,
                    unrealized_pnl=0.0,
                )
            )
        return positions

    async def get_orders(self) -> list[AdapterOrder]:
        if self.env == "paper" or not self.has_private_access:
            return await self.simulator.get_orders()
        payload = await self._request("GET", "/api/v3/openOrders", auth=True)
        return [
            AdapterOrder(
                client_order_id=item.get("clientOrderId", ""),
                symbol=self._symbol_from_exchange(item["symbol"]),
                side=item["side"],
                order_type=item["type"].lower(),
                quantity=float(item["origQty"]),
                price=float(item.get("price") or 0.0),
                status=str(item.get("status") or "OPEN").upper(),
                average_fill_price=float(item.get("price") or 0.0),
                created_at=datetime.utcnow(),
            )
            for item in payload
        ]

    async def get_instrument_rule(self, symbol: str) -> InstrumentRule:
        if self.env == "paper" and not self.use_live_market_data_in_paper:
            return await self.simulator.get_instrument_rule(symbol)
        if symbol in self._rules_cache:
            return self._rules_cache[symbol]
        payload = await self._request("GET", "/api/v3/exchangeInfo", params={"symbol": self._symbol_to_exchange(symbol)})
        symbol_info = payload["symbols"][0]
        price_filter = next(item for item in symbol_info["filters"] if item["filterType"] == "PRICE_FILTER")
        lot_filter = next(item for item in symbol_info["filters"] if item["filterType"] == "LOT_SIZE")
        rule = InstrumentRule(
            symbol=symbol,
            price_precision=_precision_from_step(price_filter["tickSize"]),
            quantity_precision=_precision_from_step(lot_filter["stepSize"]),
            min_quantity=float(lot_filter["minQty"]),
            tick_size=float(price_filter["tickSize"]),
        )
        self._rules_cache[symbol] = rule
        return rule

    async def stream_market_data(
        self,
        *,
        symbols: list[str],
        timeframe: str,
        handler: MarketStreamHandler,
    ) -> None:
        if self.env == "paper" and not self.use_live_market_data_in_paper:
            return
        streams: list[str] = []
        for symbol in symbols:
            stream_symbol = self._symbol_to_exchange(symbol).lower()
            streams.extend(
                [
                    f"{stream_symbol}@ticker",
                    f"{stream_symbol}@trade",
                    f"{stream_symbol}@depth5@100ms",
                    f"{stream_symbol}@kline_{timeframe}",
                ]
            )
        stream_url = f"{self.ws_url}?streams={'/'.join(streams)}"
        async with websockets.connect(stream_url, ping_interval=15, ping_timeout=15) as websocket:
            async for raw in websocket:
                payload = json.loads(raw)
                data = payload.get("data")
                if not data:
                    continue
                event = data.get("e")
                if event == "24hrTicker":
                    symbol = self._symbol_from_exchange(data["s"])
                    await handler(
                        "ticker",
                        symbol,
                        {
                            "symbol": symbol,
                            "price": float(data["c"]),
                            "change_percent": float(data["P"]),
                            "bid": float(data["b"]),
                            "ask": float(data["a"]),
                            "spread": ((float(data["a"]) - float(data["b"])) / float(data["c"])) if float(data["c"]) else 0.0,
                            "volume": float(data["q"]),
                            "sparkline": [],
                            "last_updated": datetime.utcnow().isoformat(),
                            "market_type": self.config.market_type,
                            "price_source": "live",
                        },
                    )
                elif event == "trade":
                    symbol = self._symbol_from_exchange(data["s"])
                    await handler(
                        "trade",
                        symbol,
                        {
                            "symbol": symbol,
                            "price": float(data["p"]),
                            "quantity": float(data["q"]),
                            "side": "sell" if data.get("m") else "buy",
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )
                elif event == "depthUpdate":
                    symbol = self._symbol_from_exchange(data["s"])
                    await handler(
                        "orderbook",
                        symbol,
                        {
                            "symbol": symbol,
                            "bids": [[float(price), float(size)] for price, size in data.get("b", [])[:5]],
                            "asks": [[float(price), float(size)] for price, size in data.get("a", [])[:5]],
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )
                elif event == "kline":
                    symbol = self._symbol_from_exchange(data["s"])
                    kline = data["k"]
                    await handler(
                        "candle",
                        symbol,
                        {
                            "timestamp": datetime.fromtimestamp(kline["t"] / 1000, tz=UTC).replace(tzinfo=None).isoformat(),
                            "open": float(kline["o"]),
                            "high": float(kline["h"]),
                            "low": float(kline["l"]),
                            "close": float(kline["c"]),
                            "volume": float(kline["v"]),
                        },
                    )

    async def close(self) -> None:
        await self._http.aclose()
