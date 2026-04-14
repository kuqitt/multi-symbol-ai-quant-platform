from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import AppConfig
from app.strategy import MovingAverageRsiStrategy, SignalType


@dataclass
class BacktestRunOutput:
    summary: dict[str, Any]
    trades: pd.DataFrame
    equity_curve: pd.DataFrame
    report_json_path: Path
    trades_csv_path: Path


class BacktestEngine:
    def __init__(self, results_dir: Path) -> None:
        self.results_dir = results_dir
        self.strategy = MovingAverageRsiStrategy()

    def _load_csv(self, path: Path) -> pd.DataFrame:
        frame = pd.read_csv(path)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        frame = frame.sort_values("timestamp").reset_index(drop=True)
        return frame

    def _resolve_paths(self, csv_paths: list[str], config: AppConfig) -> list[Path]:
        if csv_paths:
            return [Path(path) for path in csv_paths]
        sample_dir = Path(__file__).resolve().parents[1] / "data"
        return [
            sample_dir / f"{symbol.replace('/', '').lower()}.csv"
            for symbol in config.symbols
            if (sample_dir / f"{symbol.replace('/', '').lower()}.csv").exists()
        ]

    def run(self, *, name: str, csv_paths: list[str], config: AppConfig) -> BacktestRunOutput:
        self.results_dir.mkdir(parents=True, exist_ok=True)
        cash = float(config.simulation.starting_balance)
        fee_rate = float(config.simulation.fee_rate)
        positions: dict[str, dict[str, float]] = {}
        trades: list[dict[str, Any]] = []
        equity_points: list[dict[str, Any]] = []
        total_fees = 0.0

        for path in self._resolve_paths(csv_paths, config):
            symbol = path.stem.upper().replace("USDT", "/USDT")
            frame = self._load_csv(path)
            for idx in range(len(frame)):
                subset = frame.iloc[: idx + 1]
                candles = subset[["timestamp", "open", "high", "low", "close", "volume"]].to_dict(orient="records")
                decision = self.strategy.generate(symbol, candles, config.strategy)
                price = float(subset.iloc[-1]["close"])
                intrabar_range = max(float(subset.iloc[-1]["high"]) - float(subset.iloc[-1]["low"]), 0.0)
                slippage_ratio = min((intrabar_range / price) * 0.1 if price else 0.0, config.risk.max_slippage)
                position = positions.get(symbol, {"qty": 0.0, "avg_price": 0.0})
                allocation = min(cash * config.risk.max_symbol_exposure, cash * 0.2)
                qty = allocation / price if price else 0.0

                if decision.signal == SignalType.BUY and position["qty"] == 0 and qty > 0:
                    fill_price = price * (1 + slippage_ratio)
                    fee = qty * fill_price * fee_rate
                    cash -= qty * fill_price + fee
                    total_fees += fee
                    positions[symbol] = {"qty": qty, "avg_price": fill_price}
                    trades.append(
                        {
                            "timestamp": subset.iloc[-1]["timestamp"],
                            "symbol": symbol,
                            "side": "BUY",
                            "quantity": qty,
                            "price": fill_price,
                            "fee": fee,
                            "slippage": slippage_ratio,
                            "realized_pnl": 0.0,
                        }
                    )
                elif decision.signal == SignalType.SELL and position["qty"] > 0:
                    fill_price = price * (1 - slippage_ratio)
                    fee = position["qty"] * fill_price * fee_rate
                    realized = (fill_price - position["avg_price"]) * position["qty"] - fee
                    cash += position["qty"] * fill_price - fee
                    total_fees += fee
                    trades.append(
                        {
                            "timestamp": subset.iloc[-1]["timestamp"],
                            "symbol": symbol,
                            "side": "SELL",
                            "quantity": position["qty"],
                            "price": fill_price,
                            "fee": fee,
                            "slippage": slippage_ratio,
                            "realized_pnl": realized,
                        }
                    )
                    positions[symbol] = {"qty": 0.0, "avg_price": 0.0}

                equity = cash + sum((pos["qty"] * price) for pos in positions.values())
                equity_points.append({"timestamp": subset.iloc[-1]["timestamp"], "equity": equity, "symbol": symbol})

        trades_frame = pd.DataFrame(trades)
        equity_frame = pd.DataFrame(equity_points)
        if equity_frame.empty:
            equity_frame = pd.DataFrame([{"timestamp": pd.Timestamp.utcnow(), "equity": cash, "symbol": "N/A"}])
        equity_series = equity_frame.groupby("timestamp", as_index=False)["equity"].sum()
        equity_series["returns"] = equity_series["equity"].pct_change().fillna(0.0)
        drawdown = (equity_series["equity"] / equity_series["equity"].cummax()) - 1
        wins = trades_frame[trades_frame["realized_pnl"] > 0] if not trades_frame.empty else pd.DataFrame()
        starting_balance = float(config.simulation.starting_balance)
        total_return = (equity_series["equity"].iloc[-1] - starting_balance) / starting_balance if starting_balance else 0.0
        sharpe = 0.0
        if equity_series["returns"].std() not in (0, None):
            sharpe = (equity_series["returns"].mean() / equity_series["returns"].std()) * (252 ** 0.5)
        summary = {
            "name": name,
            "total_return": round(float(total_return), 6),
            "win_rate": round(float(len(wins) / len(trades_frame)) if len(trades_frame) else 0.0, 6),
            "max_drawdown": round(float(drawdown.min()), 6),
            "sharpe": round(float(sharpe), 6),
            "trade_count": int(len(trades_frame)),
            "total_fees": round(float(total_fees), 6),
            "avg_trade_pnl": round(float(trades_frame["realized_pnl"].mean()), 6) if not trades_frame.empty else 0.0,
            "symbols": sorted({item["symbol"] for item in trades}),
        }

        report_json_path = self.results_dir / f"{name}_report.json"
        trades_csv_path = self.results_dir / f"{name}_trades.csv"
        report_json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        trades_frame.to_csv(trades_csv_path, index=False)
        return BacktestRunOutput(
            summary=summary,
            trades=trades_frame,
            equity_curve=equity_series,
            report_json_path=report_json_path,
            trades_csv_path=trades_csv_path,
        )
