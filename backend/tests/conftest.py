from __future__ import annotations

import logging

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.adapters.okx_adapter import OKXAdapter
from app.config import AppConfig, ApprovalConfig, EnvironmentSettings
from app.state import RiskStatus, RuntimeState, StrategyRuntimeStatus


@pytest.fixture
def engine():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    yield test_engine
    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture
def session(engine):
    with Session(engine) as db:
        yield db


@pytest.fixture
def config() -> AppConfig:
    return AppConfig(approval=ApprovalConfig(require_manual_approval_for_large_orders=False))


@pytest.fixture
def env_settings() -> EnvironmentSettings:
    return EnvironmentSettings(_env_file=None)


@pytest.fixture
def state() -> RuntimeState:
    runtime_state = RuntimeState()
    runtime_state.set_status(StrategyRuntimeStatus.RUNNING)
    runtime_state.set_risk_status(RiskStatus.NORMAL)
    return runtime_state


@pytest.fixture
def adapter(config: AppConfig, env_settings: EnvironmentSettings) -> OKXAdapter:
    return OKXAdapter(config=config, env_settings=env_settings, starting_balance=100000.0)


@pytest.fixture
def logger():
    return logging.getLogger("test-suite")
