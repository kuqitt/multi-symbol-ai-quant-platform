from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse

from app.dependencies import require_roles
from app.models import User
from app.schemas import AttributionResponse, SummaryMetricsResponse


router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/summary", response_model=SummaryMetricsResponse)
def get_summary(
    request: Request,
    _: User = Depends(require_roles("admin", "trader", "viewer", "approver")),
) -> SummaryMetricsResponse:
    summary = request.app.state.container.metrics_service.get_summary()
    return SummaryMetricsResponse(**summary)


@router.get("/attribution", response_model=AttributionResponse)
def get_attribution(
    request: Request,
    _: User = Depends(require_roles("admin", "trader", "viewer", "approver")),
) -> AttributionResponse:
    payload = request.app.state.container.metrics_service.get_attribution_summary()
    return AttributionResponse(**payload)


@router.get("/equity-curve")
def get_equity_curve(
    request: Request,
    _: User = Depends(require_roles("admin", "trader", "viewer", "approver")),
) -> dict:
    return {"points": request.app.state.container.metrics_service.get_equity_curve()}


@router.get("/drawdown")
def get_drawdown(
    request: Request,
    _: User = Depends(require_roles("admin", "trader", "viewer", "approver")),
) -> dict:
    return {"points": request.app.state.container.metrics_service.get_drawdown_curve()}


@router.get("/daily-pnl")
def get_daily_pnl(
    request: Request,
    _: User = Depends(require_roles("admin", "trader", "viewer", "approver")),
) -> dict:
    return {"points": request.app.state.container.metrics_service.get_daily_pnl()}


@router.get("/export")
def export_metrics(
    request: Request,
    _: User = Depends(require_roles("admin", "trader", "viewer", "approver")),
) -> FileResponse:
    backend_dir = Path(__file__).resolve().parents[2]
    output = backend_dir / "results" / f"metrics_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    path = request.app.state.container.metrics_service.export_report_csv(output)
    return FileResponse(path, filename=path.name)
