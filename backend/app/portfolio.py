from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, delete, select

from app.adapters.base_adapter import AdapterPosition
from app.config import EnvironmentSettings
from app.models import EquitySnapshot, Order, OrderApproval, Position, RiskEvent, Trade


class PortfolioService:
    def __init__(self, adapter: object, config_service: object, env_settings: EnvironmentSettings, state: object) -> None:
        self.adapter = adapter
        self.config_service = config_service
        self.env_settings = env_settings
        self.state = state

    def _paper_state_target(self) -> object:
        return getattr(self.adapter, "simulator", self.adapter)

    def get_starting_balance(self) -> float:
        config = self.config_service.get_runtime_config()
        return float(getattr(config.simulation, "starting_balance", self.env_settings.paper_balance))

    def bootstrap_adapter(self, session: Session, starting_balance: float | None = None) -> None:
        positions = session.exec(select(Position)).all()
        base_balance = starting_balance if starting_balance is not None else self.get_starting_balance()
        cash = base_balance
        adapter_positions: dict[str, AdapterPosition] = {}
        for row in positions:
            cash += row.realized_pnl
            if row.quantity <= 0:
                continue
            cash -= row.avg_price * row.quantity
            adapter_positions[row.symbol] = AdapterPosition(
                symbol=row.symbol,
                quantity=row.quantity,
                avg_price=row.avg_price,
                market_price=row.market_price or row.avg_price,
                unrealized_pnl=row.unrealized_pnl,
            )
        target = self._paper_state_target()
        if hasattr(self.adapter, "starting_balance"):
            self.adapter.starting_balance = base_balance
        if hasattr(target, "positions"):
            target.positions = adapter_positions
        if hasattr(target, "available_balance"):
            target.available_balance = max(cash, 0.0)
        if hasattr(target, "starting_balance"):
            target.starting_balance = base_balance
        self.state.set_paper_account(starting_balance=base_balance)

    def reset_paper_account(self, session: Session, starting_balance: float | None = None) -> float:
        base_balance = starting_balance if starting_balance is not None else self.get_starting_balance()
        for model in (OrderApproval, Trade, Order, Position, EquitySnapshot, RiskEvent):
            session.exec(delete(model))
        session.commit()

        target = self._paper_state_target()
        if hasattr(target, "reset"):
            target.reset(
                starting_balance=base_balance,
                fee_rate=getattr(self.config_service.get_runtime_config().simulation, "fee_rate", None),
            )
        self.bootstrap_adapter(session, starting_balance=base_balance)
        self.state.reset_symbol_states()
        self.state.account_balance = {"equity": base_balance, "available_balance": base_balance}
        self.state.set_paper_account(starting_balance=base_balance, last_reset_at=datetime.utcnow())
        self.state.push_alert("INFO", "paper", f"paper account reset to {base_balance:.2f} USDT")
        return base_balance

    def get_position(self, session: Session, symbol: str) -> Position | None:
        return session.exec(select(Position).where(Position.symbol == symbol)).first()

    def list_positions(self, session: Session) -> list[Position]:
        return session.exec(select(Position).order_by(Position.updated_at.desc())).all()

    def apply_fill(
        self,
        session: Session,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        equity: float,
        strategy_name: str,
        metadata: dict | None = None,
    ) -> float:
        position = self.get_position(session, symbol)
        if position is None:
            position = Position(symbol=symbol, quantity=0.0, avg_price=0.0, strategy_name=strategy_name)
        elif strategy_name:
            position.strategy_name = strategy_name

        metadata = metadata or {}

        realized_pnl = 0.0
        if side == "BUY":
            total_cost = position.avg_price * position.quantity + price * quantity
            position.quantity += quantity
            position.avg_price = total_cost / position.quantity if position.quantity else 0.0
            position.entry_tag = str(metadata.get("entry_tag") or metadata.get("reason") or position.entry_tag or "")
            position.regime = str(metadata.get("regime") or position.regime or "unknown")
            position.stop_loss = float(metadata.get("stop_loss") or 0.0)
            position.take_profit = float(metadata.get("take_profit") or 0.0)
            position.signal_score = float(metadata.get("signal_score") or 0.0)
            position.target_weight = float(metadata.get("target_weight") or 0.0)
            position.expected_cost_bps = float(metadata.get("expected_cost_bps") or 0.0)
        else:
            sell_qty = min(quantity, position.quantity)
            realized_pnl = (price - position.avg_price) * sell_qty
            position.realized_pnl += realized_pnl
            position.quantity = max(position.quantity - sell_qty, 0.0)
            if position.quantity == 0:
                position.avg_price = 0.0
                position.entry_tag = ""
                position.stop_loss = 0.0
                position.take_profit = 0.0
                position.signal_score = 0.0
                position.target_weight = 0.0
                position.expected_cost_bps = 0.0

        position.market_price = price
        position.market_value = position.quantity * position.market_price
        position.unrealized_pnl = (position.market_price - position.avg_price) * position.quantity
        position.exposure_ratio = position.market_value / equity if equity else 0.0
        position.updated_at = datetime.utcnow()
        session.add(position)
        session.commit()
        session.refresh(position)
        return realized_pnl

    def revalue_positions(self, session: Session, prices: dict[str, float], equity: float) -> list[Position]:
        positions = session.exec(select(Position)).all()
        for position in positions:
            price = prices.get(position.symbol, position.market_price or position.avg_price)
            position.market_price = price
            position.market_value = position.quantity * price
            position.unrealized_pnl = (price - position.avg_price) * position.quantity
            position.exposure_ratio = position.market_value / equity if equity else 0.0
            position.updated_at = datetime.utcnow()
            session.add(position)
        session.commit()
        return positions
