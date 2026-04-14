from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import require_roles
from app.models import LogEntry, RiskEvent, User
from app.schemas import LogRead, RiskEventRead


router = APIRouter(prefix="/api", tags=["logs"])


@router.get("/logs")
def get_logs(
    request: Request,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("admin", "trader", "viewer", "approver")),
) -> dict:
    logs = session.exec(select(LogEntry).order_by(LogEntry.timestamp.desc()).limit(200)).all()
    risk_events = session.exec(select(RiskEvent).order_by(RiskEvent.created_at.desc()).limit(100)).all()
    return {
        "logs": [LogRead(**item.model_dump()) for item in logs],
        "risk_events": [RiskEventRead(**item.model_dump()) for item in risk_events],
        "alerts": request.app.state.container.state.to_dict()["latest_alerts"],
    }
