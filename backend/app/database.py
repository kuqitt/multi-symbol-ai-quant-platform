from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_env_settings


env_settings = get_env_settings()
engine = create_engine(
    env_settings.database_url,
    echo=False,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if env_settings.database_url.startswith("sqlite") else {},
)



def _ensure_schema() -> None:
    SQLModel.metadata.create_all(engine)
    inspector = inspect(engine)
    column_specs: dict[str, dict[str, str]] = {
        "positions": {
            "regime": "VARCHAR NOT NULL DEFAULT 'unknown'",
            "entry_tag": "VARCHAR NOT NULL DEFAULT ''",
            "stop_loss": "FLOAT NOT NULL DEFAULT 0",
            "take_profit": "FLOAT NOT NULL DEFAULT 0",
            "signal_score": "FLOAT NOT NULL DEFAULT 0",
            "target_weight": "FLOAT NOT NULL DEFAULT 0",
            "expected_cost_bps": "FLOAT NOT NULL DEFAULT 0",
        },
        "orders": {
            "decision_reason": "VARCHAR NOT NULL DEFAULT ''",
            "regime": "VARCHAR NOT NULL DEFAULT 'unknown'",
            "signal_score": "FLOAT NOT NULL DEFAULT 0",
            "target_weight": "FLOAT NOT NULL DEFAULT 0",
            "expected_cost_bps": "FLOAT NOT NULL DEFAULT 0",
            "expected_slippage_bps": "FLOAT NOT NULL DEFAULT 0",
        },
        "trades": {
            "regime": "VARCHAR NOT NULL DEFAULT 'unknown'",
            "entry_tag": "VARCHAR NOT NULL DEFAULT ''",
            "exit_tag": "VARCHAR NOT NULL DEFAULT ''",
            "signal_score": "FLOAT NOT NULL DEFAULT 0",
            "expected_cost_bps": "FLOAT NOT NULL DEFAULT 0",
            "slippage_bps": "FLOAT NOT NULL DEFAULT 0",
            "fee_bps": "FLOAT NOT NULL DEFAULT 0",
            "metadata_json": "JSON NULL",
        },
    }

    with engine.begin() as connection:
        for table_name, columns in column_specs.items():
            if not inspector.has_table(table_name):
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, ddl in columns.items():
                if column_name not in existing_columns:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))


def init_db() -> None:
    alembic_ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    if alembic_ini.exists():
        try:
            alembic_config = Config(str(alembic_ini))
            alembic_config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
            command.upgrade(alembic_config, "head")
        except Exception:
            _ensure_schema()
        else:
            _ensure_schema()
        return
    _ensure_schema()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
