from __future__ import annotations

import random
from collections import deque
from datetime import datetime, timedelta
from typing import Any

from app.adapters.base_adapter import (
    AdapterBalance,
    AdapterOrder,
    AdapterOrderResult,
    AdapterPosition,
    InstrumentRule,
    LatestTradeSnapshot,
    OrderbookSnapshot,
    TickerSnapshot,
)


class PaperTradingSimulator:
    def __init__(self, exchange_name: str, starting_balance: float = 1000.0, fee_rate: float = 0.0004) -> None:
        self.exchange_name = exchange_name
        self.random = random.Random(hash(exchange_name) & 0xFFFF)
        self.starting_balance = starting_balance
        self.fee_rate = fee_rate
        self.available_balance = starting_balance
        self.rules: dict[str, InstrumentRule] = {}
        self.market_state: dict[str, dict[str, Any]] = {}
        self.orders: dict[str, AdapterOrder] = {}
        self.positions: dict[str, AdapterPosition] = {}

    def reset(self, starting_balance: float | None = None, fee_rate: float | None = None) -> None:
        if starting_balance is not None:
            self.starting_balance = starting_balance
        if fee_rate is not None:
            self.fee_rate = fee_rate
        self.available_balance = self.starting_balance
        self.orders = {}
        self.positions = {}

    def sync_quote(
        self,
        symbol: str,
        *,
        price: float,
        bid: float,
        ask: float,
        volume: float = 0.0,
        timestamp: datetime | None = None,
    ) -> None:
        self.ensure_symbol(symbol)
        state = self.market_state[symbol]
        ts = timestamp or datetime.utcnow()
        candles = state["candles"]
        if candles:
            candles[-1] = {
                **candles[-1],
                "timestamp": ts,
                "high": max(float(candles[-1]["high"]), price),
                "low": min(float(candles[-1]["low"]), price),
                "close": round(price, 6),
                "volume": round(volume or float(candles[-1]["volume"]), 6),
            }
        state["quote"] = {
            "price": price,
            "bid": bid,
            "ask": ask,
            "volume": volume,
            "timestamp": ts,
        }
        for position in self.positions.values():
            if position.symbol == symbol:
                position.market_price = price
                position.unrealized_pnl = (price - position.avg_price) * position.quantity

    def _base_price(self, symbol: str) -> float:
        base_asset = symbol.split("/")[0].upper()
        fingerprint = sum(ord(char) for char in base_asset)
        bucket = fingerprint % 5
        scale = [0.1, 1.0, 10.0, 100.0, 1000.0][bucket]
        offset = (fingerprint % 900) + 25
        return round(scale * offset, 6)

    def ensure_symbol(self, symbol: str) -> None:
        if symbol not in self.rules:
            if symbol.startswith("DOGE"):
                price_precision = 5
                qty_precision = 0
                min_qty = 10.0
                tick = 0.00001
            elif symbol.startswith("BTC"):
                price_precision = 2
                qty_precision = 4
                min_qty = 0.0001
                tick = 0.01
            elif symbol.startswith("ETH"):
                price_precision = 2
                qty_precision = 3
                min_qty = 0.001
                tick = 0.01
            else:
                price_precision = 3
                qty_precision = 2
                min_qty = 0.01
                tick = 0.001
            self.rules[symbol] = InstrumentRule(
                symbol=symbol,
                price_precision=price_precision,
                quantity_precision=qty_precision,
                min_quantity=min_qty,
                tick_size=tick,
            )

        if symbol not in self.market_state:
            base = self._base_price(symbol)
            now = datetime.utcnow()
            candles: deque[dict[str, Any]] = deque(maxlen=500)
            price = base
            for idx in range(220):
                ts = now - timedelta(minutes=220 - idx)
                drift = self.random.uniform(-0.003, 0.003)
                open_price = price
                close_price = max(base * 0.05, open_price * (1 + drift))
                high = max(open_price, close_price) * (1 + self.random.uniform(0.0, 0.002))
                low = min(open_price, close_price) * (1 - self.random.uniform(0.0, 0.002))
                volume = abs(self.random.gauss(500, 120))
                candles.append(
                    {
                        "timestamp": ts,
                        "open": round(open_price, 6),
                        "high": round(high, 6),
                        "low": round(low, 6),
                        "close": round(close_price, 6),
                        "volume": round(volume, 6),
                    }
                )
                price = close_price
            self.market_state[symbol] = {
                "candles": candles,
                "last_trade_qty": 0.0,
                "last_trade_side": "buy",
                "quote": None,
            }

    def advance_market(self, symbol: str) -> None:
        self.ensure_symbol(symbol)
        state = self.market_state[symbol]
        last = state["candles"][-1]
        now = datetime.utcnow()
        if now - last["timestamp"] < timedelta(seconds=1):
            return
        price = float(last["close"])
        drift = self.random.uniform(-0.004, 0.004)
        open_price = price
        close_price = max(price * 0.9, open_price * (1 + drift))
        high = max(open_price, close_price) * (1 + self.random.uniform(0.0, 0.0015))
        low = min(open_price, close_price) * (1 - self.random.uniform(0.0, 0.0015))
        volume = abs(self.random.gauss(550, 140))
        state["candles"].append(
            {
                "timestamp": now,
                "open": round(open_price, 6),
                "high": round(high, 6),
                "low": round(low, 6),
                "close": round(close_price, 6),
                "volume": round(volume, 6),
            }
        )
        state["last_trade_qty"] = round(abs(self.random.gauss(0.8, 0.25)), 6)
        state["last_trade_side"] = "buy" if close_price >= open_price else "sell"
        for position in self.positions.values():
            if position.symbol == symbol:
                position.market_price = close_price
                position.unrealized_pnl = (close_price - position.avg_price) * position.quantity

    async def fetch_ohlcv(self, symbol: str, limit: int = 200) -> list[dict[str, Any]]:
        self.advance_market(symbol)
        return list(self.market_state[symbol]["candles"])[-limit:]

    async def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        self.advance_market(symbol)
        candles = list(self.market_state[symbol]["candles"])
        last = candles[-1]
        previous = candles[-2]
        quote = self.market_state[symbol].get("quote")
        price = float(quote["price"]) if quote else float(last["close"])
        bid = float(quote["bid"]) if quote else price * 0.9993
        ask = float(quote["ask"]) if quote else price * 1.0007
        volume = float(quote["volume"]) if quote and quote.get("volume") else float(last["volume"])
        last_updated = quote["timestamp"] if quote else last["timestamp"]
        return TickerSnapshot(
            symbol=symbol,
            price=round(price, 6),
            change_percent=round(((price - previous["close"]) / previous["close"]) * 100, 4),
            bid=round(bid, 6),
            ask=round(ask, 6),
            spread=round((ask - bid) / price, 6),
            volume=volume,
            last_updated=last_updated,
            sparkline=[float(item["close"]) for item in candles[-30:]],
            market_type="spot",
            price_source="simulated",
        )

    async def fetch_orderbook(self, symbol: str) -> OrderbookSnapshot:
        ticker = await self.fetch_ticker(symbol)
        base_qty = 1.0 if ticker.price > 1 else 100.0
        bids = [[round(ticker.bid * (1 - idx * 0.0005), 6), round(base_qty * (idx + 1), 6)] for idx in range(5)]
        asks = [[round(ticker.ask * (1 + idx * 0.0005), 6), round(base_qty * (idx + 1), 6)] for idx in range(5)]
        return OrderbookSnapshot(symbol=symbol, bids=bids, asks=asks, timestamp=datetime.utcnow())

    async def fetch_latest_trade(self, symbol: str) -> LatestTradeSnapshot:
        self.advance_market(symbol)
        state = self.market_state[symbol]
        quote = state.get("quote")
        price = float(quote["price"]) if quote else float(state["candles"][-1]["close"])
        return LatestTradeSnapshot(
            symbol=symbol,
            price=price,
            quantity=max(state["last_trade_qty"], 0.01),
            side=state["last_trade_side"],
            timestamp=quote["timestamp"] if quote else datetime.utcnow(),
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
        ticker = await self.fetch_ticker(symbol)
        rule = self.rules[symbol]
        quantity = round(quantity, rule.quantity_precision)
        if quantity < rule.min_quantity:
            return AdapterOrderResult(
                client_order_id=client_order_id,
                status="REJECTED",
                fill_price=0.0,
                requested_price=price or ticker.price,
                filled_quantity=0.0,
                message=f"quantity below minimum {rule.min_quantity}",
            )

        marketable_price = ticker.ask if side == "BUY" else ticker.bid
        requested_price = price or marketable_price
        status = "FILLED"
        fill_price = marketable_price
        message = f"{self.exchange_name} paper order accepted"

        if order_type == "limit":
            if side == "BUY" and requested_price < ticker.bid:
                status = "OPEN"
                fill_price = 0.0
            elif side == "SELL" and requested_price > ticker.ask:
                status = "OPEN"
                fill_price = 0.0
            else:
                fill_price = requested_price

        position = self.positions.get(
            symbol,
            AdapterPosition(symbol=symbol, quantity=0.0, avg_price=0.0, market_price=ticker.price, unrealized_pnl=0.0),
        )

        if status == "FILLED" and side == "BUY":
            estimated_fee = fill_price * quantity * self.fee_rate
            total_cost = fill_price * quantity + estimated_fee
            if total_cost > self.available_balance:
                return AdapterOrderResult(
                    client_order_id=client_order_id,
                    status="REJECTED",
                    fill_price=0.0,
                    requested_price=round(requested_price, rule.price_precision),
                    filled_quantity=0.0,
                    message="insufficient paper balance",
                    raw={"mode": "paper"},
                )

        if status == "FILLED" and side == "SELL" and position.quantity <= 0:
            return AdapterOrderResult(
                client_order_id=client_order_id,
                status="REJECTED",
                fill_price=0.0,
                requested_price=round(requested_price, rule.price_precision),
                filled_quantity=0.0,
                message="no position available to sell in spot paper mode",
                raw={"mode": "paper"},
            )

        order = AdapterOrder(
            client_order_id=client_order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=requested_price,
            status=status,
            average_fill_price=fill_price,
            created_at=datetime.utcnow(),
        )
        self.orders[client_order_id] = order

        if status == "FILLED":
            notional = fill_price * quantity
            fee = notional * self.fee_rate
            filled_quantity = quantity
            if side == "BUY":
                total_cost = position.avg_price * position.quantity + notional
                position.quantity += quantity
                position.avg_price = total_cost / position.quantity if position.quantity else fill_price
                self.available_balance -= notional + fee
            else:
                sell_qty = min(quantity, position.quantity)
                realized_notional = fill_price * sell_qty
                self.available_balance += realized_notional - (realized_notional * self.fee_rate)
                position.quantity = max(position.quantity - sell_qty, 0.0)
                filled_quantity = sell_qty
                if position.quantity == 0:
                    position.avg_price = 0.0
                    message = f"{self.exchange_name} paper position closed"
            position.market_price = fill_price
            position.unrealized_pnl = (fill_price - position.avg_price) * position.quantity
            self.positions[symbol] = position
        else:
            filled_quantity = 0.0

        return AdapterOrderResult(
            client_order_id=client_order_id,
            status=status,
            fill_price=round(fill_price, rule.price_precision) if fill_price else 0.0,
            requested_price=round(requested_price, rule.price_precision),
            filled_quantity=filled_quantity,
            message=message,
            raw={"mode": "paper", "fee_rate": self.fee_rate},
        )

    async def cancel_order(self, client_order_id: str) -> bool:
        order = self.orders.get(client_order_id)
        if order and order.status == "OPEN":
            order.status = "CANCELED"
            return True
        return False

    async def get_balance(self) -> AdapterBalance:
        equity = self.available_balance + sum(
            position.quantity * position.market_price for position in self.positions.values()
        )
        return AdapterBalance(equity=equity, available_balance=self.available_balance, currency="USDT")

    async def get_positions(self) -> list[AdapterPosition]:
        for symbol in list(self.positions):
            self.advance_market(symbol)
        return list(self.positions.values())

    async def get_orders(self) -> list[AdapterOrder]:
        return list(self.orders.values())

    async def get_instrument_rule(self, symbol: str) -> InstrumentRule:
        self.ensure_symbol(symbol)
        return self.rules[symbol]
