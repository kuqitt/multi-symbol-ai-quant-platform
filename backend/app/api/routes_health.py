from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas import HealthResponse


router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    container = request.app.state.container
    runtime_config = container.config_service.get_runtime_config()
    return HealthResponse(
        ok=True,
        env=runtime_config.env,
        exchange=runtime_config.exchange,
        database=container.env_settings.database_url,
    )
