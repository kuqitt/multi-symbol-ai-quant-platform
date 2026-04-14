"""decision pipeline upgrade"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260414_0002"
down_revision = "20260413_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("positions", sa.Column("regime", sa.String(), nullable=False, server_default="unknown"))
    op.add_column("positions", sa.Column("entry_tag", sa.String(), nullable=False, server_default=""))
    op.add_column("positions", sa.Column("stop_loss", sa.Float(), nullable=False, server_default="0"))
    op.add_column("positions", sa.Column("take_profit", sa.Float(), nullable=False, server_default="0"))
    op.add_column("positions", sa.Column("signal_score", sa.Float(), nullable=False, server_default="0"))
    op.add_column("positions", sa.Column("target_weight", sa.Float(), nullable=False, server_default="0"))
    op.add_column("positions", sa.Column("expected_cost_bps", sa.Float(), nullable=False, server_default="0"))
    op.create_index("ix_positions_regime", "positions", ["regime"])

    op.add_column("orders", sa.Column("decision_reason", sa.String(), nullable=False, server_default=""))
    op.add_column("orders", sa.Column("regime", sa.String(), nullable=False, server_default="unknown"))
    op.add_column("orders", sa.Column("signal_score", sa.Float(), nullable=False, server_default="0"))
    op.add_column("orders", sa.Column("target_weight", sa.Float(), nullable=False, server_default="0"))
    op.add_column("orders", sa.Column("expected_cost_bps", sa.Float(), nullable=False, server_default="0"))
    op.add_column("orders", sa.Column("expected_slippage_bps", sa.Float(), nullable=False, server_default="0"))
    op.create_index("ix_orders_decision_reason", "orders", ["decision_reason"])
    op.create_index("ix_orders_regime", "orders", ["regime"])

    op.add_column("trades", sa.Column("regime", sa.String(), nullable=False, server_default="unknown"))
    op.add_column("trades", sa.Column("entry_tag", sa.String(), nullable=False, server_default=""))
    op.add_column("trades", sa.Column("exit_tag", sa.String(), nullable=False, server_default=""))
    op.add_column("trades", sa.Column("signal_score", sa.Float(), nullable=False, server_default="0"))
    op.add_column("trades", sa.Column("expected_cost_bps", sa.Float(), nullable=False, server_default="0"))
    op.add_column("trades", sa.Column("slippage_bps", sa.Float(), nullable=False, server_default="0"))
    op.add_column("trades", sa.Column("fee_bps", sa.Float(), nullable=False, server_default="0"))
    op.add_column("trades", sa.Column("metadata_json", sa.JSON(), nullable=True))
    op.create_index("ix_trades_regime", "trades", ["regime"])

    op.create_table(
        "strategy_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("timeframe", sa.String(), nullable=False),
        sa.Column("strategy_name", sa.String(), nullable=False),
        sa.Column("signal", sa.String(), nullable=False),
        sa.Column("final_action", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("regime", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("signal_score", sa.Float(), nullable=False),
        sa.Column("buy_score", sa.Float(), nullable=False),
        sa.Column("sell_score", sa.Float(), nullable=False),
        sa.Column("target_weight", sa.Float(), nullable=False),
        sa.Column("desired_notional", sa.Float(), nullable=False),
        sa.Column("expected_cost_bps", sa.Float(), nullable=False),
        sa.Column("context_json", sa.JSON(), nullable=True),
    )
    op.create_index("ix_strategy_decisions_created_at", "strategy_decisions", ["created_at"])
    op.create_index("ix_strategy_decisions_symbol", "strategy_decisions", ["symbol"])
    op.create_index("ix_strategy_decisions_strategy_name", "strategy_decisions", ["strategy_name"])
    op.create_index("ix_strategy_decisions_signal", "strategy_decisions", ["signal"])
    op.create_index("ix_strategy_decisions_final_action", "strategy_decisions", ["final_action"])
    op.create_index("ix_strategy_decisions_reason", "strategy_decisions", ["reason"])
    op.create_index("ix_strategy_decisions_regime", "strategy_decisions", ["regime"])


def downgrade() -> None:
    op.drop_index("ix_strategy_decisions_regime", table_name="strategy_decisions")
    op.drop_index("ix_strategy_decisions_reason", table_name="strategy_decisions")
    op.drop_index("ix_strategy_decisions_final_action", table_name="strategy_decisions")
    op.drop_index("ix_strategy_decisions_signal", table_name="strategy_decisions")
    op.drop_index("ix_strategy_decisions_strategy_name", table_name="strategy_decisions")
    op.drop_index("ix_strategy_decisions_symbol", table_name="strategy_decisions")
    op.drop_index("ix_strategy_decisions_created_at", table_name="strategy_decisions")
    op.drop_table("strategy_decisions")

    op.drop_index("ix_trades_regime", table_name="trades")
    op.drop_column("trades", "metadata_json")
    op.drop_column("trades", "fee_bps")
    op.drop_column("trades", "slippage_bps")
    op.drop_column("trades", "expected_cost_bps")
    op.drop_column("trades", "signal_score")
    op.drop_column("trades", "exit_tag")
    op.drop_column("trades", "entry_tag")
    op.drop_column("trades", "regime")

    op.drop_index("ix_orders_regime", table_name="orders")
    op.drop_index("ix_orders_decision_reason", table_name="orders")
    op.drop_column("orders", "expected_slippage_bps")
    op.drop_column("orders", "expected_cost_bps")
    op.drop_column("orders", "target_weight")
    op.drop_column("orders", "signal_score")
    op.drop_column("orders", "regime")
    op.drop_column("orders", "decision_reason")

    op.drop_index("ix_positions_regime", table_name="positions")
    op.drop_column("positions", "expected_cost_bps")
    op.drop_column("positions", "target_weight")
    op.drop_column("positions", "signal_score")
    op.drop_column("positions", "take_profit")
    op.drop_column("positions", "stop_loss")
    op.drop_column("positions", "entry_tag")
    op.drop_column("positions", "regime")
