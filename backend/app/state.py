from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class StrategyRuntimeStatus(StrEnum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    PROTECT_MODE = "PROTECT_MODE"


class RiskStatus(StrEnum):
    NORMAL = "NORMAL"
    PROTECT_MODE = "PROTECT_MODE"
    HALTED = "HALTED"


@dataclass
class AlertRecord:
    level: str
    category: str
    message: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    symbol: str = ""


class RuntimeState:
    def __init__(self) -> None:
        self.status: StrategyRuntimeStatus = StrategyRuntimeStatus.STOPPED
        self.risk_status: RiskStatus = RiskStatus.NORMAL
        self.env: str = "paper"
        self.exchange: str = "okx"
        self.live_enabled: bool = False
        self.last_heartbeat: datetime | None = None
        self.network_healthy: bool = True
        self.exchange_available: bool = True
        self.state_consistent: bool = True
        self.protection_reason: str = ""
        self.latest_prices: dict[str, float] = {}
        self.latest_tickers: dict[str, dict[str, Any]] = {}
        self.latest_klines: dict[str, list[dict[str, Any]]] = {}
        self.latest_orderbooks: dict[str, dict[str, Any]] = {}
        self.latest_trades: dict[str, list[dict[str, Any]]] = {}
        self.account_balance: dict[str, float] = {"equity": 0.0, "available_balance": 0.0}
        self.alerts: list[AlertRecord] = []
        self.run_id: int | None = None
        self.started_at: datetime | None = None
        self.symbol_states: dict[str, dict[str, Any]] = {}
        self.paper_account: dict[str, Any] = {"starting_balance": 0.0, "last_reset_at": None}

    def touch(self) -> None:
        self.last_heartbeat = datetime.utcnow()

    def set_status(self, status: StrategyRuntimeStatus) -> None:
        self.status = status
        self.touch()

    def set_risk_status(self, status: RiskStatus, reason: str = "") -> None:
        self.risk_status = status
        self.protection_reason = reason
        self.touch()

    def push_alert(self, level: str, category: str, message: str, symbol: str = "") -> None:
        self.alerts.insert(0, AlertRecord(level=level, category=category, message=message, symbol=symbol))
        del self.alerts[20:]
        self.touch()

    def update_symbol_state(self, symbol: str, **payload: Any) -> None:
        current = self.symbol_states.get(symbol, {"symbol": symbol})
        current.update(payload)
        current["updated_at"] = datetime.utcnow().isoformat()
        self.symbol_states[symbol] = current
        self.touch()

    def clear_symbol_state(self, symbol: str) -> None:
        self.symbol_states.pop(symbol, None)
        self.touch()

    def reset_symbol_states(self) -> None:
        self.symbol_states = {}
        self.touch()

    def set_paper_account(self, *, starting_balance: float, last_reset_at: datetime | None = None) -> None:
        self.paper_account = {
            "starting_balance": starting_balance,
            "last_reset_at": last_reset_at.isoformat() if last_reset_at else None,
        }
        self.touch()

    def mark_exchange_error(self, reason: str) -> None:
        self.exchange_available = False
        self.network_healthy = False
        self.set_risk_status(RiskStatus.PROTECT_MODE, reason)
        self.push_alert("ERROR", "exchange", reason)

    def clear_exchange_error(self) -> None:
        self.exchange_available = True
        self.network_healthy = True
        if self.risk_status == RiskStatus.PROTECT_MODE and self.protection_reason:
            self.set_risk_status(RiskStatus.NORMAL, "")

    def mark_state_mismatch(self, reason: str) -> None:
        self.state_consistent = False
        self.set_status(StrategyRuntimeStatus.PROTECT_MODE)
        self.set_risk_status(RiskStatus.PROTECT_MODE, reason)
        self.push_alert("CRITICAL", "risk", reason)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "risk_status": self.risk_status.value,
            "env": self.env,
            "exchange": self.exchange,
            "strategy_running": self.status == StrategyRuntimeStatus.RUNNING,
            "live_enabled": self.live_enabled,
            "last_heartbeat": self.last_heartbeat,
            "latest_alerts": [asdict(alert) for alert in self.alerts[:10]],
            "symbol_states": list(self.symbol_states.values()),
            "paper_account": self.paper_account,
        }
