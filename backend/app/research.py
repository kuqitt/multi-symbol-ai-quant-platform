from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import AppConfig, StrategyConfig
from app.strategy import MovingAverageRsiStrategy, SignalType, TrendBreakoutStrategy


@dataclass
class OptimizationOutput:
    score: float
    parameters: dict[str, Any]
    walk_forward: dict[str, Any]


class ParameterResearchService:
    def __init__(self) -> None:
        self.providers = {
            "ma_rsi": MovingAverageRsiStrategy(),
            "trend_breakout": TrendBreakoutStrategy(),
        }

    def _load_frame(self, path: Path) -> pd.DataFrame:
        frame = pd.read_csv(path)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        return frame.sort_values("timestamp").reset_index(drop=True)

    def _simulate(self, frame: pd.DataFrame, strategy_name: str, strategy_config: StrategyConfig) -> dict[str, float]:
        provider = self.providers[strategy_name]
        cash = 100000.0
        quantity = 0.0
        avg_price = 0.0
        trade_pnls: list[float] = []
        equity_points: list[float] = []
        for idx in range(len(frame)):
            subset = frame.iloc[: idx + 1]
            candles = subset[["timestamp", "open", "high", "low", "close", "volume"]].to_dict(orient="records")
            decision = provider.generate("TEST/USDT", candles, strategy_config)
            price = float(subset.iloc[-1]["close"])
            if decision.signal == SignalType.BUY and quantity == 0:
                quantity = (cash * 0.2) / price if price else 0.0
                cash -= quantity * price
                avg_price = price
            elif decision.signal == SignalType.SELL and quantity > 0:
                pnl = (price - avg_price) * quantity
                cash += quantity * price
                trade_pnls.append(pnl)
                quantity = 0.0
                avg_price = 0.0
            equity_points.append(cash + quantity * price)
        equity = pd.Series(equity_points) if equity_points else pd.Series([100000.0])
        returns = equity.pct_change().fillna(0.0)
        sharpe = float((returns.mean() / returns.std()) * (252**0.5)) if returns.std() else 0.0
        max_drawdown = float(((equity / equity.cummax()) - 1).min())
        total_return = float((equity.iloc[-1] - 100000.0) / 100000.0)
        win_rate = float(len([value for value in trade_pnls if value > 0]) / len(trade_pnls)) if trade_pnls else 0.0
        score = total_return + sharpe * 0.1 + win_rate * 0.2 + max_drawdown
        return {
            "total_return": total_return,
            "sharpe": sharpe,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "score": score,
        }

    def optimize(
        self,
        *,
        csv_path: Path,
        config: AppConfig,
        strategy_name: str,
    ) -> OptimizationOutput:
        frame = self._load_frame(csv_path)
        grid = config.optimization.parameter_grid
        combinations = itertools.product(
            grid.get("ma_fast", [config.strategy.ma_fast]),
            grid.get("ma_slow", [config.strategy.ma_slow]),
            grid.get("rsi_buy_threshold", [config.strategy.rsi_buy_threshold]),
            grid.get("rsi_sell_threshold", [config.strategy.rsi_sell_threshold]),
        )
        best_score = float("-inf")
        best_parameters: dict[str, Any] = {}
        for ma_fast, ma_slow, rsi_buy, rsi_sell in combinations:
            if ma_fast >= ma_slow:
                continue
            strategy_config = config.strategy.model_copy(
                update={
                    "ma_fast": int(ma_fast),
                    "ma_slow": int(ma_slow),
                    "rsi_buy_threshold": float(rsi_buy),
                    "rsi_sell_threshold": float(rsi_sell),
                }
            )
            metrics = self._simulate(frame, strategy_name, strategy_config)
            if metrics["score"] > best_score:
                best_score = metrics["score"]
                best_parameters = {
                    "ma_fast": int(ma_fast),
                    "ma_slow": int(ma_slow),
                    "rsi_buy_threshold": float(rsi_buy),
                    "rsi_sell_threshold": float(rsi_sell),
                    **metrics,
                }
        walk_forward = self.walk_forward(
            frame=frame,
            config=config,
            strategy_name=strategy_name,
            parameters=best_parameters,
        )
        return OptimizationOutput(
            score=float(best_parameters.get("score", 0.0)),
            parameters=best_parameters,
            walk_forward=walk_forward,
        )

    def walk_forward(
        self,
        *,
        frame: pd.DataFrame,
        config: AppConfig,
        strategy_name: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        train_size = config.optimization.walk_forward_train_bars
        test_size = config.optimization.walk_forward_test_bars
        segments: list[dict[str, Any]] = []
        for start in range(0, max(len(frame) - train_size - test_size + 1, 1), test_size):
            train = frame.iloc[start : start + train_size]
            test = frame.iloc[start + train_size : start + train_size + test_size]
            if train.empty or test.empty:
                continue
            strategy_config = config.strategy.model_copy(
                update={
                    "ma_fast": int(parameters.get("ma_fast", config.strategy.ma_fast)),
                    "ma_slow": int(parameters.get("ma_slow", config.strategy.ma_slow)),
                    "rsi_buy_threshold": float(parameters.get("rsi_buy_threshold", config.strategy.rsi_buy_threshold)),
                    "rsi_sell_threshold": float(parameters.get("rsi_sell_threshold", config.strategy.rsi_sell_threshold)),
                }
            )
            metrics = self._simulate(test.reset_index(drop=True), strategy_name, strategy_config)
            segments.append(
                {
                    "train_range": [str(train["timestamp"].iloc[0]), str(train["timestamp"].iloc[-1])],
                    "test_range": [str(test["timestamp"].iloc[0]), str(test["timestamp"].iloc[-1])],
                    **metrics,
                }
            )
        return {
            "train_bars": train_size,
            "test_bars": test_size,
            "segments": segments,
            "average_score": float(sum(item["score"] for item in segments) / len(segments)) if segments else 0.0,
        }
