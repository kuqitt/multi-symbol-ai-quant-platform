from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any

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


def _precision_from_step(value: str) -> int:
    if "." not in value:
        return 0
    return len(value.rstrip("0").split(".")[1])


class OKXAdapter(BaseExchangeAdapter):
    def __init__(self, config: AppConfig, env_settings: EnvironmentSettings, starting_balance: float = 1000.0) -> None:
        super().__init__(exchange_name="okx", env=config.env)
        self.env_settings = env_settings
        self.config = config
        self.starting_balance = starting_balance
        self.simulator = PaperTradingSimulator(
            "okx",
            starting_balance=starting_balance,
            fee_rate=config.simulation.fee_rate,
        )
        okx_config = config.connectors.okx
        self.base_url = okx_config.base_url
        if config.env in {"testnet", "demo"}:
            separator = "&" if "?" in okx_config.demo_public_ws_url else "?"
            self.ws_public_url = f"{okx_config.demo_public_ws_url}{separator}brokerId={okx_config.demo_broker_id}"
        else:
            self.ws_public_url = okx_config.public_ws_url
        self._http = httpx.AsyncClient(base_url=self.base_url, timeout=15.0)
        self._rules_cache: dict[str, InstrumentRule] = {}
        self._paper_ticker_cache: dict[str, TickerSnapshot] = {}

    @property
    def supports_streaming(self) -> bool:
        return True

    @property
    def use_live_market_data_in_paper(self) -> bool:
        return bool(self.config.simulation.use_live_market_data)

    @property
    def has_private_access(self) -> bool:
        api_key = self.env_settings.okx_api_key or self.env_settings.api_key
        api_secret = self.env_settings.okx_api_secret or self.env_settings.api_secret
        api_passphrase = self.env_settings.okx_api_passphrase or self.env_settings.api_passphrase
        return bool(api_key and api_secret and api_passphrase)

    def _symbol_to_inst_id(self, symbol: str) -> str:
        return symbol.replace("/", "-").upper()

    def _inst_id_to_symbol(self, inst_id: str) -> str:
        return inst_id.replace("-", "/").upper()

    def _timeframe_to_bar(self, timeframe: str) -> str:
        mapping = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1H", "4h": "4H", "1d": "1D"}
        return mapping.get(timeframe, "1m")

    def _build_headers(self, method: str, path: str, body: str = "") -> dict[str, str]:
        timestamp = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        api_key = self.env_settings.okx_api_key or self.env_settings.api_key
        api_secret = self.env_settings.okx_api_secret or self.env_settings.api_secret
        api_passphrase = self.env_settings.okx_api_passphrase or self.env_settings.api_passphrase
        sign_payload = f"{timestamp}{method.upper()}{path}{body}"
        signature = base64.b64encode(
            hmac.new(api_secret.encode("utf-8"), sign_payload.encode("utf-8"), hashlib.sha256).digest()
        ).decode("utf-8")
        headers = {
            "OK-ACCESS-KEY": api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": api_passphrase,
        }
        if self.env in {"testnet", "demo"}:
            headers["x-simulated-trading"] = "1"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        auth: bool = False,
    ) -> dict[str, Any]:
        body = json.dumps(json_body, separators=(",", ":")) if json_body else ""
        headers: dict[str, str] = {}
        query_path = path
        if params:
            query = httpx.QueryParams(params)
            query_path = f"{path}?{query}"
        if auth:
            headers = self._build_headers(method, query_path, body)
        response = await self._http.request(method, path, params=params, content=body or None, headers=headers)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") not in {None, "0"}:
            raise RuntimeError(f"OKX error: {payload.get('msg', 'unknown')}")
        return payload

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> list[dict[str, Any]]:
        if self.env == "paper" and not self.use_live_market_data_in_paper:
            return await self.simulator.fetch_ohlcv(symbol, limit=limit)
        payload = await self._request(
            "GET",
            "/api/v5/market/candles",
            params={"instId": self._symbol_to_inst_id(symbol), "bar": self._timeframe_to_bar(timeframe), "limit": limit},
        )
        candles = sorted(payload.get("data", []), key=lambda item: int(item[0]))
        return [
            {
                "timestamp": datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC).replace(tzinfo=None),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            }
            for row in candles
        ]

    async def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        if self.env == "paper" and not self.use_live_market_data_in_paper:
            return await self.simulator.fetch_ticker(symbol)
        payload = await self._request(
            "GET",
            "/api/v5/market/ticker",
            params={"instId": self._symbol_to_inst_id(symbol)},
        )
        item = payload["data"][0]
        last = float(item["last"])
        open24h = float(item.get("open24h") or last)
        bid = float(item["bidPx"])
        ask = float(item["askPx"])
        ticker = TickerSnapshot(
            symbol=symbol,
            price=last,
            change_percent=((last - open24h) / open24h * 100) if open24h else 0.0,
            bid=bid,
            ask=ask,
            spread=((ask - bid) / last) if last else 0.0,
            volume=float(item.get("volCcy24h") or item.get("vol24h") or 0.0),
            last_updated=datetime.utcnow(),
            sparkline=[],
            market_type=self.config.market_type,
            price_source="live",
        )
        if self.env == "paper":
            self._paper_ticker_cache[symbol] = ticker
            self.simulator.sync_quote(
                symbol,
                price=ticker.price,
                bid=ticker.bid,
                ask=ticker.ask,
                volume=ticker.volume,
                timestamp=ticker.last_updated,
            )
        return ticker

    async def fetch_orderbook(self, symbol: str) -> OrderbookSnapshot:
        if self.env == "paper" and not self.use_live_market_data_in_paper:
            return await self.simulator.fetch_orderbook(symbol)
        payload = await self._request(
            "GET",
            "/api/v5/market/books",
            params={"instId": self._symbol_to_inst_id(symbol), "sz": 5},
        )
        item = payload["data"][0]
        return OrderbookSnapshot(
            symbol=symbol,
            bids=[[float(price), float(size)] for price, size, *_ in item.get("bids", [])[:5]],
            asks=[[float(price), float(size)] for price, size, *_ in item.get("asks", [])[:5]],
            timestamp=datetime.utcnow(),
        )

    async def fetch_latest_trade(self, symbol: str) -> LatestTradeSnapshot:
        if self.env == "paper" and not self.use_live_market_data_in_paper:
            return await self.simulator.fetch_latest_trade(symbol)
        payload = await self._request(
            "GET",
            "/api/v5/market/trades",
            params={"instId": self._symbol_to_inst_id(symbol), "limit": 1},
        )
        item = payload["data"][0]
        return LatestTradeSnapshot(
            symbol=symbol,
            price=float(item["px"]),
            quantity=float(item["sz"]),
            side=item["side"],
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
        body: dict[str, Any] = {
            "instId": self._symbol_to_inst_id(symbol),
            "tdMode": "cash",
            "clOrdId": client_order_id,
            "side": side.lower(),
            "ordType": order_type,
            "sz": f"{round(quantity, rule.quantity_precision):f}",
        }
        if order_type == "limit" and price is not None:
            body["px"] = f"{round(price, rule.price_precision):f}"
        payload = await self._request("POST", "/api/v5/trade/order", json_body=body, auth=True)
        data = payload.get("data", [{}])[0]
        status = "OPEN" if data.get("sCode") == "0" else "REJECTED"
        fill_price = price or 0.0
        return AdapterOrderResult(
            client_order_id=client_order_id,
            status=status,
            fill_price=fill_price,
            requested_price=price or 0.0,
            filled_quantity=0.0 if status == "OPEN" else quantity,
            message=data.get("sMsg") or "okx order submitted",
            raw=data,
        )

    async def cancel_order(self, client_order_id: str) -> bool:
        if self.env == "paper" or not self.has_private_access:
            return await self.simulator.cancel_order(client_order_id)
        payload = await self._request(
            "POST",
            "/api/v5/trade/cancel-order",
            json_body={"clOrdId": client_order_id},
            auth=True,
        )
        data = payload.get("data", [{}])[0]
        return data.get("sCode") == "0"

    async def get_balance(self) -> AdapterBalance:
        if self.env == "paper" or not self.has_private_access:
            if self.env == "paper" and self.use_live_market_data_in_paper:
                for symbol in list(self.simulator.positions):
                    try:
                        await self.fetch_ticker(symbol)
                    except Exception:
                        continue
            return await self.simulator.get_balance()
        payload = await self._request("GET", "/api/v5/account/balance", params={"ccy": "USDT"}, auth=True)
        details = payload.get("data", [{}])[0].get("details", [{}])
        detail = details[0] if details else {}
        equity = float(detail.get("eq") or payload.get("data", [{}])[0].get("totalEq") or 0.0)
        available = float(detail.get("availEq") or detail.get("cashBal") or 0.0)
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
        payload = await self._request("GET", "/api/v5/account/positions", params={"instType": "SPOT"}, auth=True)
        positions: list[AdapterPosition] = []
        for item in payload.get("data", []):
            qty = float(item.get("pos") or 0.0)
            if qty <= 0:
                continue
            positions.append(
                AdapterPosition(
                    symbol=self._inst_id_to_symbol(item["instId"]),
                    quantity=qty,
                    avg_price=float(item.get("avgPx") or 0.0),
                    market_price=float(item.get("markPx") or item.get("last") or 0.0),
                    unrealized_pnl=float(item.get("upl") or 0.0),
                )
            )
        return positions

    async def get_orders(self) -> list[AdapterOrder]:
        if self.env == "paper" or not self.has_private_access:
            return await self.simulator.get_orders()
        payload = await self._request("GET", "/api/v5/trade/orders-pending", params={"instType": "SPOT"}, auth=True)
        return [
            AdapterOrder(
                client_order_id=item.get("clOrdId", ""),
                symbol=self._inst_id_to_symbol(item["instId"]),
                side=item["side"].upper(),
                order_type=item["ordType"],
                quantity=float(item.get("sz") or 0.0),
                price=float(item.get("px") or 0.0),
                status=item.get("state", "OPEN").upper(),
                average_fill_price=float(item.get("avgPx") or 0.0),
                created_at=datetime.utcnow(),
            )
            for item in payload.get("data", [])
        ]

    async def get_instrument_rule(self, symbol: str) -> InstrumentRule:
        if self.env == "paper" and not self.use_live_market_data_in_paper:
            return await self.simulator.get_instrument_rule(symbol)
        if symbol in self._rules_cache:
            return self._rules_cache[symbol]
        payload = await self._request(
            "GET",
            "/api/v5/public/instruments",
            params={"instType": "SPOT", "instId": self._symbol_to_inst_id(symbol)},
        )
        item = payload["data"][0]
        rule = InstrumentRule(
            symbol=symbol,
            price_precision=_precision_from_step(item["tickSz"]),
            quantity_precision=_precision_from_step(item["lotSz"]),
            min_quantity=float(item.get("minSz") or item["lotSz"]),
            tick_size=float(item["tickSz"]),
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
        subscribe_args: list[dict[str, str]] = []
        channel = f"candle{self._timeframe_to_bar(timeframe)}"
        for symbol in symbols:
            inst_id = self._symbol_to_inst_id(symbol)
            subscribe_args.extend(
                [
                    {"channel": "tickers", "instId": inst_id},
                    {"channel": "trades", "instId": inst_id},
                    {"channel": "books5", "instId": inst_id},
                    {"channel": channel, "instId": inst_id},
                ]
            )
        async with websockets.connect(self.ws_public_url, ping_interval=15, ping_timeout=15) as websocket:
            await websocket.send(json.dumps({"op": "subscribe", "args": subscribe_args}))
            async for raw in websocket:
                payload = json.loads(raw)
                arg = payload.get("arg")
                if not arg or "data" not in payload:
                    continue
                symbol = self._inst_id_to_symbol(arg["instId"])
                channel_name = arg["channel"]
                data = payload["data"][0]
                if channel_name == "tickers":
                    await handler(
                        "ticker",
                        symbol,
                        {
                            "symbol": symbol,
                            "price": float(data["last"]),
                            "change_percent": (
                                (float(data["last"]) - float(data.get("open24h") or data["last"]))
                                / float(data.get("open24h") or data["last"])
                                * 100
                            )
                            if float(data.get("open24h") or data["last"])
                            else 0.0,
                            "bid": float(data["bidPx"]),
                            "ask": float(data["askPx"]),
                            "spread": (
                                (float(data["askPx"]) - float(data["bidPx"])) / float(data["last"])
                                if float(data["last"])
                                else 0.0
                            ),
                            "volume": float(data.get("vol24h") or 0.0),
                            "sparkline": [],
                            "last_updated": datetime.utcnow().isoformat(),
                            "market_type": self.config.market_type,
                            "price_source": "live",
                        },
                    )
                elif channel_name == "trades":
                    await handler(
                        "trade",
                        symbol,
                        {
                            "symbol": symbol,
                            "price": float(data["px"]),
                            "quantity": float(data["sz"]),
                            "side": data["side"],
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )
                elif channel_name == "books5":
                    await handler(
                        "orderbook",
                        symbol,
                        {
                            "symbol": symbol,
                            "bids": [[float(price), float(size)] for price, size, *_ in data.get("bids", [])[:5]],
                            "asks": [[float(price), float(size)] for price, size, *_ in data.get("asks", [])[:5]],
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )
                elif channel_name.startswith("candle"):
                    await handler(
                        "candle",
                        symbol,
                        {
                            "timestamp": datetime.fromtimestamp(int(data[0]) / 1000, tz=UTC).replace(tzinfo=None).isoformat(),
                            "open": float(data[1]),
                            "high": float(data[2]),
                            "low": float(data[3]),
                            "close": float(data[4]),
                            "volume": float(data[5]),
                        },
                    )

    async def close(self) -> None:
        await self._http.aclose()
