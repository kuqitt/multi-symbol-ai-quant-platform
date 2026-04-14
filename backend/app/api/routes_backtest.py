from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import require_roles
from app.models import BacktestResult, OptimizationResult, User
from app.schemas import (
    BacktestResultRead,
    BacktestRunRequest,
    OptimizationResultRead,
    OptimizationRunRequest,
)


router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.post("/run")
def run_backtest(
    payload: BacktestRunRequest,
    request: Request,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("admin", "trader")),
) -> dict:
    container = request.app.state.container
    config = container.config_service.get_config()
    result = container.backtest_engine.run(name=payload.name, csv_paths=payload.csv_paths, config=config)
    row = BacktestResult(
        name=payload.name,
        symbols_csv=",".join(payload.symbols or config.symbols),
        total_return=result.summary["total_return"],
        win_rate=result.summary["win_rate"],
        max_drawdown=result.summary["max_drawdown"],
        sharpe=result.summary["sharpe"],
        summary_json=result.summary,
        trades_csv_path=str(result.trades_csv_path),
        report_json_path=str(result.report_json_path),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"success": True, "result": BacktestResultRead(**row.model_dump())}


@router.post("/optimize")
def run_optimization(
    payload: OptimizationRunRequest,
    request: Request,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("admin", "trader")),
) -> dict:
    container = request.app.state.container
    config = container.config_service.get_config()
    symbol = payload.symbol or config.symbols[0]
    csv_path = Path(payload.csv_path) if payload.csv_path else Path(__file__).resolve().parents[2] / "data" / f"{symbol.replace('/', '').lower()}.csv"
    result = container.research_service.optimize(csv_path=csv_path, config=config, strategy_name=payload.strategy_name)
    row = OptimizationResult(
        name=payload.name,
        symbol=symbol,
        strategy_name=payload.strategy_name,
        score=result.score,
        parameters_json=result.parameters,
        walk_forward_json=result.walk_forward,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"success": True, "result": OptimizationResultRead(**row.model_dump())}


@router.get("/results", response_model=list[BacktestResultRead])
def list_backtest_results(
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("admin", "trader", "viewer", "approver")),
) -> list[BacktestResultRead]:
    rows = session.exec(select(BacktestResult).order_by(BacktestResult.created_at.desc())).all()
    return [BacktestResultRead(**row.model_dump()) for row in rows]


@router.get("/optimizations", response_model=list[OptimizationResultRead])
def list_optimization_results(
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("admin", "trader", "viewer", "approver")),
) -> list[OptimizationResultRead]:
    rows = session.exec(select(OptimizationResult).order_by(OptimizationResult.created_at.desc())).all()
    return [OptimizationResultRead(**row.model_dump()) for row in rows]
