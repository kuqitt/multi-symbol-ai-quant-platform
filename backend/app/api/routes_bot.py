from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session

from app.database import get_session
from app.dependencies import require_roles
from app.models import User


router = APIRouter(prefix="/api/bot", tags=["bot"])


class BotBindTelegramRequest(BaseModel):
    chat_id: str


class BotBindFeishuRequest(BaseModel):
    receive_id: str
    receive_id_type: Literal["open_id", "user_id", "union_id", "chat_id", "email"] = "chat_id"


class BotPreviewCommandRequest(BaseModel):
    platform: Literal["telegram", "feishu"]
    command: str
    source_id: str = ""


@router.get("/meta")
async def get_bot_meta(request: Request, _: User = Depends(require_roles("admin", "trader", "viewer", "approver"))) -> dict:
    return await request.app.state.container.bot_service.get_metadata()


@router.post("/command-preview")
async def preview_bot_command(
    payload: BotPreviewCommandRequest,
    request: Request,
    _: User = Depends(require_roles("admin", "trader", "viewer", "approver")),
) -> dict:
    return await request.app.state.container.bot_service.preview_command(payload.platform, payload.command, payload.source_id)


@router.post("/telegram/sync")
async def sync_telegram_updates(
    request: Request,
    _: User = Depends(require_roles("admin", "trader")),
) -> dict:
    return await request.app.state.container.bot_service.sync_telegram_updates(process_commands=True)


@router.post("/telegram/bind")
async def bind_telegram_chat(
    payload: BotBindTelegramRequest,
    request: Request,
    _: Session = Depends(get_session),
    user: User = Depends(require_roles("admin", "trader")),
) -> dict:
    updated = await request.app.state.container.bot_service.bind_telegram_chat(payload.chat_id, changed_by=user.username or "web-ui")
    await request.app.state.container.bot_service.reload()
    return {"success": True, "chat_id": updated.notifier.telegram_chat_id}


@router.post("/feishu/bind")
async def bind_feishu_chat(
    payload: BotBindFeishuRequest,
    request: Request,
    _: Session = Depends(get_session),
    user: User = Depends(require_roles("admin", "trader")),
) -> dict:
    updated = await request.app.state.container.bot_service.bind_feishu_receive(
        payload.receive_id,
        payload.receive_id_type,
        changed_by=user.username or "web-ui",
    )
    await request.app.state.container.bot_service.reload()
    return {
        "success": True,
        "receive_id": updated.notifier.feishu_receive_id,
        "receive_id_type": updated.notifier.feishu_receive_id_type,
    }


@router.post("/telegram/webhook/{bot_token}")
async def telegram_webhook(bot_token: str, request: Request) -> dict:
    container = request.app.state.container
    config = container.config_service.get_runtime_config()
    expected_token = config.notifier.telegram_bot_token or container.env_settings.telegram_bot_token
    if not expected_token or bot_token != expected_token:
        raise HTTPException(status_code=404, detail="invalid telegram bot token")

    payload = await request.json()
    container.bot_service._remember_telegram_target(payload)
    await container.bot_service.handle_telegram_update(payload, expected_token)
    return {"ok": True}


@router.post("/feishu/webhook")
async def feishu_webhook(request: Request) -> dict:
    payload = await request.json()
    return await request.app.state.container.bot_service.handle_feishu_event(payload)