from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app.api import (
    routes_approvals,
    routes_auth,
    routes_backtest,
    routes_bot,
    routes_config,
    routes_health,
    routes_logs,
    routes_market,
    routes_metrics,
    routes_orders,
    routes_positions,
    routes_status,
    routes_strategy,
    routes_trades,
)
from app.auth import decode_access_token
from app.backtest import BacktestEngine
from app.config import DEFAULT_CONFIG_PATH, get_env_settings
from app.database import engine, init_db
from app.exchange_client import create_exchange_adapter
from app.executor import ExecutionService
from app.models import LogEntry
from app.notifier import NotificationManager
from app.portfolio import PortfolioService
from app.research import ParameterResearchService
from app.risk_manager import RiskManager
from app.services.approval_service import ApprovalService
from app.services.auth_service import AuthService
from app.services.bot_service import BotService
from app.services.config_service import ConfigService
from app.services.market_data_service import MarketDataService
from app.services.metrics_service import MetricsService
from app.services.strategy_service import StrategyService
from app.state import RuntimeState
from app.utils.logger import configure_logging
from app.websocket_manager import WebSocketManager


def _build_dashboard_payload(container: Any) -> dict[str, Any]:
    return {
        "type": "snapshot",
        "status": container.state.to_dict(),
        "metrics": container.metrics_service.get_summary(),
        "tickers": list(container.state.latest_tickers.values()),
        "positions": [item.model_dump(mode="json") for item in container.metrics_service.list_positions()],
        "recent_logs": [item.model_dump(mode="json") for item in container.metrics_service.latest_logs(limit=20)],
        "alerts": container.state.to_dict()["latest_alerts"],
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    env_settings = get_env_settings()
    config_service = ConfigService(DEFAULT_CONFIG_PATH, env_settings)
    config = config_service.get_runtime_config()
    adapter = create_exchange_adapter(config, env_settings)
    state = RuntimeState()
    state.env = config.env
    state.exchange = config.exchange
    state.live_enabled = env_settings.enable_live_trading
    websocket_manager = WebSocketManager()

    def persist_log(level: str, category: str, message: str, metadata: dict[str, Any] | None) -> None:
        with Session(engine) as session:
            entry = LogEntry(level=level, category=category, message=message, metadata_json=metadata)
            session.add(entry)
            session.commit()
            session.refresh(entry)
        if level in {"WARNING", "ERROR", "CRITICAL"}:
            state.push_alert(level, category, message)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                websocket_manager.broadcast(
                    "dashboard",
                    {"type": "log", "log": entry.model_dump(mode="json"), "alerts": state.to_dict()["latest_alerts"]},
                )
            )
        except RuntimeError:
            pass

    logger = configure_logging(config.logging.level, persist_log)
    notifier = NotificationManager(env_settings, logger)
    auth_service = AuthService(env_settings, logger)
    approval_service = ApprovalService(config_service, notifier, logger)
    portfolio_service = PortfolioService(adapter, config_service, env_settings, state)
    research_service = ParameterResearchService()

    with Session(engine) as session:
        auth_service.seed_admin(session)
        portfolio_service.bootstrap_adapter(session)
        state.set_paper_account(starting_balance=config.simulation.starting_balance)

    metrics_service = MetricsService(
        session_factory=lambda: Session(engine),
        adapter=adapter,
        config_service=config_service,
        state=state,
        portfolio_service=portfolio_service,
        websocket_manager=websocket_manager,
    )
    risk_manager = RiskManager(state, logger)
    executor = ExecutionService(risk_manager, portfolio_service, approval_service, notifier, logger)
    market_data_service = MarketDataService(adapter, config_service, state, websocket_manager, logger)
    strategy_service = StrategyService(
        session_factory=lambda: Session(engine),
        config_service=config_service,
        state=state,
        market_data_service=market_data_service,
        metrics_service=metrics_service,
        executor=executor,
        portfolio_service=portfolio_service,
        websocket_manager=websocket_manager,
        logger=logger,
    )
    bot_service = BotService(
        session_factory=lambda: Session(engine),
        config_service=config_service,
        env_settings=env_settings,
        state=state,
        metrics_service=metrics_service,
        portfolio_service=portfolio_service,
        market_data_service=market_data_service,
        approval_service=approval_service,
        websocket_manager=websocket_manager,
        logger=logger,
    )
    backtest_engine = BacktestEngine(Path(__file__).resolve().parents[1] / "results")

    app.state.container = SimpleNamespace(
        env_settings=env_settings,
        config_service=config_service,
        adapter=adapter,
        state=state,
        websocket_manager=websocket_manager,
        logger=logger,
        notifier=notifier,
        auth_service=auth_service,
        approval_service=approval_service,
        portfolio_service=portfolio_service,
        metrics_service=metrics_service,
        risk_manager=risk_manager,
        executor=executor,
        market_data_service=market_data_service,
        strategy_service=strategy_service,
        bot_service=bot_service,
        backtest_engine=backtest_engine,
        research_service=research_service,
    )

    logger.info("应用启动完成", extra={"category": "system"})
    market_data_service.start()
    metrics_service.start()
    strategy_service.start()
    await bot_service.start()

    try:
        yield
    finally:
        await bot_service.stop()
        await strategy_service.stop()
        await market_data_service.stop()
        await metrics_service.stop()
        logger.info("应用关闭完成", extra={"category": "system"})


app = FastAPI(
    title="Multi-Symbol AI Quant Trading Platform",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_health.router)
app.include_router(routes_auth.router)
app.include_router(routes_status.router)
app.include_router(routes_config.router)
app.include_router(routes_strategy.router)
app.include_router(routes_metrics.router)
app.include_router(routes_positions.router)
app.include_router(routes_orders.router)
app.include_router(routes_trades.router)
app.include_router(routes_logs.router)
app.include_router(routes_backtest.router)
app.include_router(routes_market.router)
app.include_router(routes_approvals.router)
app.include_router(routes_bot.router)


@app.get("/")
def root() -> dict[str, Any]:
    return {"name": app.title, "docs": "/docs"}


@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        payload = decode_access_token(token, websocket.app.state.container.env_settings)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if not payload.get("sub"):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    container = websocket.app.state.container
    await container.websocket_manager.connect("dashboard", websocket)
    await websocket.send_json(jsonable_encoder(_build_dashboard_payload(container)))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        container.websocket_manager.disconnect("dashboard", websocket)
