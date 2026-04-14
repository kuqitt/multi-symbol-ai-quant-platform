from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from app.config import AppConfig
from app.database import get_session
from app.dependencies import require_roles
from app.exchange_client import create_exchange_adapter
from app.models import User
from app.schemas import (
    ConfigUpdateRequest,
    CredentialStatus,
    SystemConfigResponse,
    SystemConfigUpdateRequest,
)


router = APIRouter(prefix="/api", tags=["config"])


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"


def _credential_status(api_key: str, secret: str, passphrase: str = "") -> CredentialStatus:
    return CredentialStatus(
        api_key_configured=bool(api_key),
        api_key_masked=_mask_secret(api_key),
        secret_configured=bool(secret),
        secret_masked=_mask_secret(secret),
        passphrase_configured=bool(passphrase),
    )


async def _rebuild_adapter(container, session: Session, config: AppConfig) -> None:
    await container.market_data_service.stop()
    try:
        await container.adapter.close()
    except Exception:
        pass
    new_adapter = create_exchange_adapter(config, container.env_settings)
    container.adapter = new_adapter
    container.market_data_service.adapter = new_adapter
    container.metrics_service.adapter = new_adapter
    container.portfolio_service.adapter = new_adapter
    container.portfolio_service.bootstrap_adapter(session)
    container.state.set_paper_account(starting_balance=config.simulation.starting_balance)
    container.market_data_service.start()


@router.get("/config")
def get_business_config(request: Request, _: User = Depends(require_roles("admin", "trader", "viewer", "approver"))) -> dict:
    return request.app.state.container.config_service.get_config().to_business_config().model_dump(mode="json")


@router.put("/config")
async def update_business_config(
    payload: ConfigUpdateRequest,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin", "trader")),
) -> dict:
    container = request.app.state.container
    current_runtime = container.config_service.get_runtime_config()
    next_saved = container.config_service.get_config().apply_business_config(payload.config)
    updated = container.config_service.update_config(
        session,
        new_config=next_saved,
        apply_immediately=payload.apply_immediately,
        changed_by=user.username or payload.changed_by,
    )
    if payload.apply_immediately:
        requires_market_restart = (
            current_runtime.symbols != updated.symbols or current_runtime.timeframe != updated.timeframe
        )
        if requires_market_restart:
            await _rebuild_adapter(container, session, container.config_service.get_runtime_config())
        await container.bot_service.reload()
    return {
        "success": True,
        "config": updated.to_business_config().model_dump(mode="json"),
        "apply_immediately": payload.apply_immediately,
    }


@router.get("/system-config", response_model=SystemConfigResponse)
def get_system_config(
    request: Request,
    _: User = Depends(require_roles("admin", "trader", "viewer", "approver")),
) -> SystemConfigResponse:
    container = request.app.state.container
    env_settings = container.env_settings
    okx_api_key = env_settings.okx_api_key or env_settings.api_key
    okx_api_secret = env_settings.okx_api_secret or env_settings.api_secret
    okx_api_passphrase = env_settings.okx_api_passphrase or env_settings.api_passphrase
    binance_api_key = env_settings.binance_api_key or env_settings.api_key
    binance_api_secret = env_settings.binance_api_secret or env_settings.api_secret
    return SystemConfigResponse(
        config=container.config_service.get_config().to_system_config(),
        live_trading_enabled=bool(env_settings.enable_live_trading),
        okx_credentials=_credential_status(okx_api_key, okx_api_secret, okx_api_passphrase),
        binance_credentials=_credential_status(binance_api_key, binance_api_secret),
    )


@router.put("/system-config")
async def update_system_config(
    payload: SystemConfigUpdateRequest,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin", "trader")),
) -> dict:
    container = request.app.state.container
    current_runtime = container.config_service.get_runtime_config()
    next_saved = container.config_service.get_config().apply_system_config(payload.config)
    updated = container.config_service.update_config(
        session,
        new_config=next_saved,
        apply_immediately=payload.apply_immediately,
        changed_by=user.username or payload.changed_by,
    )
    if payload.apply_immediately:
        runtime_config = container.config_service.get_runtime_config()
        container.state.env = runtime_config.env
        container.state.exchange = runtime_config.exchange
        container.logger.setLevel(runtime_config.logging.level.upper())
        requires_adapter_restart = (
            current_runtime.exchange != runtime_config.exchange
            or current_runtime.env != runtime_config.env
            or current_runtime.market_type != runtime_config.market_type
            or current_runtime.simulation != runtime_config.simulation
            or current_runtime.connectors != runtime_config.connectors
            or current_runtime.symbols != runtime_config.symbols
            or current_runtime.timeframe != runtime_config.timeframe
        )
        if requires_adapter_restart:
            await _rebuild_adapter(container, session, runtime_config)
        await container.bot_service.reload()
    return {
        "success": True,
        "config": updated.to_system_config().model_dump(mode="json"),
        "apply_immediately": payload.apply_immediately,
    }
