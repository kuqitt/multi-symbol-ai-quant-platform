from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session

from app.database import get_session
from app.dependencies import require_roles
from app.models import StrategyRun
from app.models import User
from app.schemas import ActionResponse, PaperAccountResetRequest, PaperAccountResetResponse
from app.state import RiskStatus, StrategyRuntimeStatus


router = APIRouter(prefix="/api/strategy", tags=["strategy"])


def _close_run_if_open(container, session: Session, new_status: str) -> None:
    if container.state.run_id is None:
        return
    run = session.get(StrategyRun, container.state.run_id)
    if run:
        run.status = new_status
        run.ended_at = datetime.utcnow()
        session.add(run)
        session.commit()


async def _broadcast_runtime(container) -> None:
    await container.websocket_manager.broadcast("dashboard", {"type": "status", "status": container.state.to_dict()})


@router.post("/start", response_model=ActionResponse)
async def start_strategy(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin", "trader")),
) -> ActionResponse:
    container = request.app.state.container
    config = container.config_service.get_runtime_config()
    if config.env == "paper" and config.simulation.reset_account_on_start:
        container.portfolio_service.reset_paper_account(session, config.simulation.starting_balance)
        await container.market_data_service.refresh_once()
    run = StrategyRun(
        status=StrategyRuntimeStatus.RUNNING.value,
        mode=config.env,
        env=config.env,
        total_symbols=len(config.symbols),
        note=f"由 {user.username} 通过接口启动",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    container.state.run_id = run.id
    container.state.started_at = run.started_at
    container.state.set_status(StrategyRuntimeStatus.RUNNING)
    if container.state.risk_status == RiskStatus.PROTECT_MODE:
        container.state.set_risk_status(RiskStatus.NORMAL, "")
    await _broadcast_runtime(container)
    return ActionResponse(success=True, status=container.state.status.value, message="策略已启动")


@router.post("/pause", response_model=ActionResponse)
async def pause_strategy(request: Request, _: User = Depends(require_roles("admin", "trader"))) -> ActionResponse:
    container = request.app.state.container
    container.state.set_status(StrategyRuntimeStatus.PAUSED)
    await _broadcast_runtime(container)
    return ActionResponse(success=True, status=container.state.status.value, message="策略已暂停")


@router.post("/stop", response_model=ActionResponse)
async def stop_strategy(
    request: Request,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("admin", "trader")),
) -> ActionResponse:
    container = request.app.state.container
    _close_run_if_open(container, session, StrategyRuntimeStatus.STOPPED.value)
    container.state.run_id = None
    container.state.set_status(StrategyRuntimeStatus.STOPPED)
    await _broadcast_runtime(container)
    return ActionResponse(success=True, status=container.state.status.value, message="策略已停止")


@router.post("/protect", response_model=ActionResponse)
async def protect_strategy(
    request: Request,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("admin", "trader", "approver")),
) -> ActionResponse:
    container = request.app.state.container
    _close_run_if_open(container, session, StrategyRuntimeStatus.PROTECT_MODE.value)
    container.state.set_status(StrategyRuntimeStatus.PROTECT_MODE)
    container.state.set_risk_status(RiskStatus.PROTECT_MODE, "手动进入保护模式")
    await _broadcast_runtime(container)
    return ActionResponse(success=True, status=container.state.status.value, message="已进入保护模式")


@router.post("/paper-account/reset", response_model=PaperAccountResetResponse)
async def reset_paper_account(
    payload: PaperAccountResetRequest,
    request: Request,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("admin", "trader")),
) -> PaperAccountResetResponse:
    container = request.app.state.container
    config = container.config_service.get_runtime_config()
    if config.env != "paper":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只有在模拟盘模式下才允许重置模拟账户")

    starting_balance = payload.starting_balance or config.simulation.starting_balance
    if starting_balance <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="模拟账户初始资金必须大于 0")

    _close_run_if_open(container, session, StrategyRuntimeStatus.STOPPED.value)
    container.state.run_id = None
    container.state.set_status(StrategyRuntimeStatus.STOPPED)
    container.state.set_risk_status(RiskStatus.NORMAL, "")
    applied_balance = container.portfolio_service.reset_paper_account(session, starting_balance)
    await container.market_data_service.refresh_once()
    summary = container.metrics_service.get_summary()
    await _broadcast_runtime(container)
    await container.websocket_manager.broadcast("dashboard", {"type": "metrics", "summary": summary})
    return PaperAccountResetResponse(
        success=True,
        status=container.state.status.value,
        message=f"模拟账户已重置为 {applied_balance:.2f} USDT",
        starting_balance=applied_balance,
        equity=summary["equity"],
        available_balance=summary["available_balance"],
    )
