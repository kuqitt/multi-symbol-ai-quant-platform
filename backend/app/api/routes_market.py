from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.dependencies import require_roles
from app.models import User
from app.schemas import MarketTickerRead


router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/tickers", response_model=list[MarketTickerRead])
def get_tickers(
    request: Request,
    _: User = Depends(require_roles("admin", "trader", "viewer", "approver")),
) -> list[MarketTickerRead]:
    data = request.app.state.container.state.latest_tickers.values()
    return [MarketTickerRead(**item) for item in data]


@router.get("/candles/{symbol_path:path}")
def get_candles(
    symbol_path: str,
    request: Request,
    _: User = Depends(require_roles("admin", "trader", "viewer", "approver")),
) -> dict:
    symbol = symbol_path.upper()
    candles = request.app.state.container.state.latest_klines.get(symbol)
    if candles is None:
        raise HTTPException(status_code=404, detail="symbol not found")
    return {"symbol": symbol, "candles": candles[-200:]}


@router.get("/orderbook/{symbol_path:path}")
def get_orderbook(
    symbol_path: str,
    request: Request,
    _: User = Depends(require_roles("admin", "trader", "viewer", "approver")),
) -> dict:
    symbol = symbol_path.upper()
    orderbook = request.app.state.container.state.latest_orderbooks.get(symbol)
    if orderbook is None:
        raise HTTPException(status_code=404, detail="symbol not found")
    return orderbook


@router.get("/trades/{symbol_path:path}")
def get_recent_trades(
    symbol_path: str,
    request: Request,
    _: User = Depends(require_roles("admin", "trader", "viewer", "approver")),
) -> dict:
    symbol = symbol_path.upper()
    trades = request.app.state.container.state.latest_trades.get(symbol)
    if trades is None:
        raise HTTPException(status_code=404, detail="symbol not found")
    return {"symbol": symbol, "trades": trades}


@router.get("/replay/{symbol_path:path}")
def get_replay(
    symbol_path: str,
    request: Request,
    _: User = Depends(require_roles("admin", "trader", "viewer", "approver")),
) -> dict:
    symbol = symbol_path.upper()
    candles = request.app.state.container.state.latest_klines.get(symbol)
    trades = request.app.state.container.state.latest_trades.get(symbol, [])
    if candles is None:
        raise HTTPException(status_code=404, detail="symbol not found")
    frames = [
        {
            "timestamp": candle["timestamp"],
            "open": candle["open"],
            "high": candle["high"],
            "low": candle["low"],
            "close": candle["close"],
            "volume": candle["volume"],
            "latest_trade": trades[0] if trades else None,
        }
        for candle in candles[-150:]
    ]
    return {"symbol": symbol, "frames": frames}
