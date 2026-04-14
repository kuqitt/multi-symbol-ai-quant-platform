from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from collections import deque
from datetime import datetime
from typing import Any

import httpx
import lark_oapi as lark
import lark_oapi.ws.client as lark_ws_client
from sqlmodel import Session, select

from app.config import AppConfig
from app.models import OrderApproval, StrategyRun
from app.state import RiskStatus, StrategyRuntimeStatus


class BotService:
    TELEGRAM_POLL_INTERVAL_SECONDS = 5

    def __init__(
        self,
        *,
        session_factory: Any,
        config_service: Any,
        env_settings: Any,
        state: Any,
        metrics_service: Any,
        portfolio_service: Any,
        market_data_service: Any,
        approval_service: Any,
        websocket_manager: Any,
        logger: Any,
    ) -> None:
        self.session_factory = session_factory
        self.config_service = config_service
        self.env_settings = env_settings
        self.state = state
        self.metrics_service = metrics_service
        self.portfolio_service = portfolio_service
        self.market_data_service = market_data_service
        self.approval_service = approval_service
        self.websocket_manager = websocket_manager
        self.logger = logger
        self._telegram_task: asyncio.Task[None] | None = None
        self._telegram_running = False
        self._feishu_client: Any | None = None
        self._feishu_thread: threading.Thread | None = None
        self._feishu_loop: asyncio.AbstractEventLoop | None = None
        self._feishu_running = False
        self._telegram_offsets: dict[str, int] = {}
        self._telegram_recent_targets: dict[str, dict[str, Any]] = {}
        self._telegram_commands_registered: set[str] = set()
        self._feishu_message_ids: deque[str] = deque(maxlen=200)
        self._feishu_recent_targets: dict[str, dict[str, Any]] = {}
        self._testing = bool(os.getenv("PYTEST_CURRENT_TEST")) or "pytest" in sys.modules

    def get_command_catalog(self) -> list[dict[str, Any]]:
        return [
            {"command": "/start", "description": "显示欢迎信息与完整命令菜单", "requires_binding": False, "control": False},
            {"command": "/help", "description": "查看帮助与命令说明", "requires_binding": False, "control": False},
            {"command": "/menu", "description": "显示快捷命令菜单", "requires_binding": False, "control": False},
            {"command": "/chatid", "description": "返回当前会话 ID，便于完成绑定", "requires_binding": False, "control": False},
            {"command": "/bind", "description": "把当前会话绑定为默认控制与告警目标", "requires_binding": False, "control": False},
            {"command": "/status", "description": "查看当前运行状态、环境与风控状态", "requires_binding": False, "control": False},
            {"command": "/metrics", "description": "查看权益、收益、回撤与交易概览", "requires_binding": False, "control": False},
            {"command": "/positions", "description": "查看当前持仓摘要", "requires_binding": False, "control": False},
            {"command": "/symbol BTC/USDT", "description": "查看某个交易对的实时状态与最近决策", "requires_binding": False, "control": False},
            {"command": "/decisions", "description": "查看最近策略决策摘要", "requires_binding": False, "control": False},
            {"command": "/approvals", "description": "查看待审核订单列表", "requires_binding": False, "control": False},
            {"command": "/run", "description": "启动策略引擎", "requires_binding": True, "control": True},
            {"command": "/pause", "description": "暂停策略轮询", "requires_binding": True, "control": True},
            {"command": "/stop", "description": "停止策略引擎", "requires_binding": True, "control": True},
            {"command": "/protect", "description": "进入保护模式", "requires_binding": True, "control": True},
            {"command": "/resetpaper 1000", "description": "重置模拟账户余额，仅 paper 环境可用", "requires_binding": True, "control": True},
        ]

    async def start(self) -> None:
        if self._testing:
            return
        config = self.config_service.get_runtime_config()
        token = self._telegram_token(config)
        feishu_app_id = self._feishu_app_id(config)
        feishu_app_secret = self._feishu_app_secret(config)
        if config.notifier.telegram_enabled and token and (self._telegram_task is None or self._telegram_task.done()):
            self._telegram_running = True
            self._telegram_task = asyncio.create_task(self._run_telegram_poll_loop())
        if (
            config.notifier.feishu_enabled
            and feishu_app_id
            and feishu_app_secret
            and (self._feishu_thread is None or not self._feishu_thread.is_alive())
        ):
            self._start_feishu_long_connection(feishu_app_id, feishu_app_secret)

    async def stop(self) -> None:
        self._telegram_running = False
        if self._telegram_task:
            await asyncio.wait([self._telegram_task], timeout=2)
        await self._stop_feishu_long_connection()

    async def reload(self) -> None:
        await self.stop()
        await self.start()

    async def get_metadata(self) -> dict[str, Any]:
        config = self.config_service.get_runtime_config()
        telegram_token = self._telegram_token(config)
        feishu_app_id = self._feishu_app_id(config)
        return {
            "commands": self.get_command_catalog(),
            "telegram": {
                "enabled": bool(config.notifier.telegram_enabled and telegram_token),
                "transport": "polling",
                "worker_active": bool(self._telegram_task and not self._telegram_task.done()),
                "bound_target_id": self._telegram_chat_id(config),
                "supports_inbound": bool(telegram_token),
                "setup_hint": "默认使用轮询接收命令，不需要额外配置 Telegram webhook。先给机器人发消息，再执行 /chatid 或 /bind。",
                "recent_targets": list(self._telegram_recent_targets.values()),
                "callback_path": "/api/bot/telegram/webhook/<bot_token>",
            },
            "feishu": {
                "enabled": bool(config.notifier.feishu_enabled and feishu_app_id and self._feishu_app_secret(config)),
                "transport": "long-connection",
                "worker_active": bool(self._feishu_thread and self._feishu_thread.is_alive()),
                "bound_target_id": self._feishu_receive_id(config),
                "supports_inbound": bool(feishu_app_id and self._feishu_app_secret(config)),
                "setup_hint": "推荐在飞书开放平台把事件订阅切换为长连接并订阅 im.message.receive_v1。本地服务启动后即可直接收消息，不需要公网回调地址。收到消息后可用 /bind 绑定当前群。",
                "recent_targets": list(self._feishu_recent_targets.values()),
                "callback_path": "/api/bot/feishu/webhook",
            },
        }

    async def sync_telegram_updates(self, process_commands: bool = True) -> dict[str, Any]:
        config = self.config_service.get_runtime_config()
        token = self._telegram_token(config)
        if not token:
            return {"processed_updates": 0, "recent_targets": [], "worker_active": False}

        webhook_configured = await self._telegram_has_webhook(token)
        if webhook_configured:
            return {
                "processed_updates": 0,
                "recent_targets": list(self._telegram_recent_targets.values()),
                "worker_active": bool(self._telegram_task and not self._telegram_task.done()),
                "webhook_configured": True,
            }

        processed_updates = 0
        try:
            payload = await self._telegram_request(
                token,
                "getUpdates",
                method="GET",
                params={
                    "offset": self._telegram_offsets.get(token, 0),
                    "limit": 50,
                    "timeout": 0,
                    "allowed_updates": json.dumps(["message", "callback_query"]),
                },
            )
            for update in payload.get("result", []):
                update_id = int(update.get("update_id") or 0)
                if update_id:
                    self._telegram_offsets[token] = max(self._telegram_offsets.get(token, 0), update_id + 1)
                self._remember_telegram_target(update)
                if process_commands:
                    await self.handle_telegram_update(update, token)
                processed_updates += 1
        except Exception:
            self.logger.exception("Telegram 同步最近消息失败", extra={"category": "bot"})

        return {
            "processed_updates": processed_updates,
            "recent_targets": list(self._telegram_recent_targets.values()),
            "worker_active": bool(self._telegram_task and not self._telegram_task.done()),
            "webhook_configured": False,
        }

    async def preview_command(self, platform: str, command: str, source_id: str = "") -> dict[str, Any]:
        context = {
            "platform": platform,
            "source_id": source_id.strip(),
            "display_name": source_id.strip(),
            "message_id": "preview",
        }
        return await self.execute_command(command, context)

    async def bind_telegram_chat(self, chat_id: str, changed_by: str) -> AppConfig:
        return self._update_notifier_binding(
            changed_by=changed_by,
            telegram_chat_id=chat_id.strip(),
            feishu_receive_id=None,
            feishu_receive_id_type=None,
        )

    async def bind_feishu_receive(self, receive_id: str, receive_id_type: str, changed_by: str) -> AppConfig:
        return self._update_notifier_binding(
            changed_by=changed_by,
            telegram_chat_id=None,
            feishu_receive_id=receive_id.strip(),
            feishu_receive_id_type=receive_id_type.strip(),
        )

    async def handle_telegram_update(self, update: dict[str, Any], token: str) -> None:
        message = update.get("message") or {}
        callback_query = update.get("callback_query") or {}

        if callback_query:
            callback_data = str(callback_query.get("data") or "")
            callback_message = callback_query.get("message") or {}
            chat = callback_message.get("chat") or {}
            context = {
                "platform": "telegram",
                "source_id": str(chat.get("id") or ""),
                "display_name": self._telegram_display_name(chat),
                "message_id": str((callback_message.get("message_id") or "")),
            }
            result = await self.execute_command(callback_data, context)
            if callback_query.get("id"):
                await self._telegram_request(
                    token,
                    "answerCallbackQuery",
                    json_payload={"callback_query_id": callback_query["id"], "text": "已处理"},
                )
            await self._send_telegram_message(token, context["source_id"], result["message"], include_keyboard=True)
            return

        text = str(message.get("text") or "").strip()
        chat = message.get("chat") or {}
        if not text or not chat.get("id"):
            return

        context = {
            "platform": "telegram",
            "source_id": str(chat.get("id")),
            "display_name": self._telegram_display_name(chat),
            "message_id": str(message.get("message_id") or ""),
        }
        result = await self.execute_command(text, context)
        await self._send_telegram_message(token, context["source_id"], result["message"], include_keyboard=result["include_keyboard"])

    async def handle_feishu_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            if payload.get("challenge"):
                return {"challenge": payload.get("challenge")}

            action_payload = payload.get("action") or ((payload.get("event") or {}).get("action") or {})
            if action_payload:
                normalized_payload = dict(payload)
                normalized_payload["action"] = action_payload
                return await self._handle_feishu_card_action(normalized_payload)

            header = payload.get("header") or {}
            config = self.config_service.get_runtime_config()
            app_id = header.get("app_id") or ((payload.get("event") or {}).get("app_id"))
            if app_id and app_id != self._feishu_app_id(config):
                return {"code": 0, "msg": "ignored"}

            event_type = header.get("event_type") or str((payload.get("event") or {}).get("type") or "")
            if event_type and event_type != "im.message.receive_v1":
                return {"code": 0, "msg": "ignored"}

            event = payload.get("event") or {}
            message = event.get("message") or {}
            self._remember_feishu_target(event)
            message_id = str(message.get("message_id") or payload.get("open_message_id") or "")
            if message_id in self._feishu_message_ids:
                return {"code": 0, "msg": "duplicate"}
            if message_id:
                self._feishu_message_ids.append(message_id)

            message_type = str(message.get("message_type") or "text")
            if message_type != "text":
                await self._reply_feishu_text(message_id, "目前只支持文本命令，例如 /status、/metrics、/bind。")
                return {"code": 0, "msg": "ok"}

            text = self._extract_feishu_text(message)
            if not text:
                return {"code": 0, "msg": "ignored"}

            context = {
                "platform": "feishu",
                "source_id": str(message.get("chat_id") or payload.get("open_chat_id") or ""),
                "display_name": str(message.get("chat_id") or payload.get("open_chat_id") or ""),
                "message_id": message_id,
            }
            result = await self.execute_command(text, context)
            if result.get("reply_mode") == "card":
                await self._reply_feishu_card(context["message_id"], result["card"])
            else:
                await self._reply_feishu_text(context["message_id"], result["message"])
            return {"code": 0, "msg": "ok"}
        except Exception:
            self.logger.exception("飞书命令处理失败", extra={"category": "bot"})
            return {"code": 0, "msg": "error"}

    async def execute_command(self, raw_command: str, context: dict[str, Any]) -> dict[str, Any]:
        normalized, args = self._parse_command(raw_command)
        config = self.config_service.get_runtime_config()
        if not normalized:
            return self._build_help_response(config, context)

        if normalized in {"start", "help", "menu", "帮助", "菜单"}:
            return self._build_help_response(config, context, normalized)

        if normalized in {"chatid", "chat_id", "whereami", "会话", "会话id"}:
            return {
                "recognized_command": normalized,
                "message": self._build_identity_text(config, context),
                "authorized": False,
                "include_keyboard": True,
                "reply_mode": "text",
            }

        if normalized in {"bind", "绑定"}:
            bound_message = await self._bind_current_source(config, context)
            return {"recognized_command": normalized, "message": bound_message, "authorized": True, "include_keyboard": True, "reply_mode": "text"}

        if normalized in {"status", "状态"}:
            return {"recognized_command": normalized, "message": self._build_status_text(), "authorized": True, "include_keyboard": False, "reply_mode": "text"}

        if normalized in {"metrics", "summary", "指标"}:
            return {"recognized_command": normalized, "message": self._build_metrics_text(), "authorized": True, "include_keyboard": False, "reply_mode": "text"}

        if normalized in {"positions", "持仓"}:
            return {"recognized_command": normalized, "message": self._build_positions_text(), "authorized": True, "include_keyboard": False, "reply_mode": "text"}

        if normalized in {"symbol", "币种", "交易对"}:
            return {
                "recognized_command": normalized,
                "message": self._build_symbol_text(args),
                "authorized": True,
                "include_keyboard": False,
                "reply_mode": "text",
            }

        if normalized in {"decisions", "decision", "决策"}:
            return {
                "recognized_command": normalized,
                "message": self._build_decisions_text(),
                "authorized": True,
                "include_keyboard": False,
                "reply_mode": "text",
            }

        if normalized in {"approvals", "approval", "审核"}:
            return {"recognized_command": normalized, "message": self._build_approvals_text(), "authorized": True, "include_keyboard": False, "reply_mode": "text"}

        if normalized in {"run", "运行", "启动"}:
            if not self._is_bound_controller(config, context):
                return {"recognized_command": normalized, "message": self._build_not_bound_text(config, context), "authorized": False, "include_keyboard": True, "reply_mode": "text"}
            return {"recognized_command": normalized, "message": await self._run_strategy(), "authorized": True, "include_keyboard": False, "reply_mode": "text"}

        if normalized in {"pause", "暂停"}:
            if not self._is_bound_controller(config, context):
                return {"recognized_command": normalized, "message": self._build_not_bound_text(config, context), "authorized": False, "include_keyboard": True, "reply_mode": "text"}
            return {"recognized_command": normalized, "message": await self._pause_strategy(), "authorized": True, "include_keyboard": False, "reply_mode": "text"}

        if normalized in {"stop", "停止"}:
            if not self._is_bound_controller(config, context):
                return {"recognized_command": normalized, "message": self._build_not_bound_text(config, context), "authorized": False, "include_keyboard": True, "reply_mode": "text"}
            return {"recognized_command": normalized, "message": await self._stop_strategy(), "authorized": True, "include_keyboard": False, "reply_mode": "text"}

        if normalized in {"protect", "保护"}:
            if not self._is_bound_controller(config, context):
                return {"recognized_command": normalized, "message": self._build_not_bound_text(config, context), "authorized": False, "include_keyboard": True, "reply_mode": "text"}
            return {"recognized_command": normalized, "message": await self._protect_strategy(), "authorized": True, "include_keyboard": False, "reply_mode": "text"}

        if normalized in {"resetpaper", "reset", "重置模拟盘"}:
            if not self._is_bound_controller(config, context):
                return {"recognized_command": normalized, "message": self._build_not_bound_text(config, context), "authorized": False, "include_keyboard": True, "reply_mode": "text"}
            return {
                "recognized_command": normalized,
                "message": await self._reset_paper_account(args),
                "authorized": True,
                "include_keyboard": False,
                "reply_mode": "text",
            }

        return {
            "recognized_command": "help",
            "message": f"未识别命令：{raw_command}\n\n{self._build_help_text(config, context)}",
            "authorized": False,
            "include_keyboard": True,
            "reply_mode": "text",
        }

    async def _handle_feishu_card_action(self, payload: dict[str, Any]) -> dict[str, Any]:
        action = payload.get("action") or {}
        value = action.get("value") or {}
        command = str(value.get("command") or "").strip()
        source_id = str(value.get("source_id") or "").strip()
        message_id = str(payload.get("open_message_id") or payload.get("open_chat_id") or "")
        context = {
            "platform": "feishu",
            "source_id": source_id,
            "display_name": source_id,
            "message_id": message_id,
        }
        result = await self.execute_command(command, context)
        return {
            "toast": {
                "type": "info",
                "content": result["message"][:160],
            }
        }

    def _start_feishu_long_connection(self, app_id: str, app_secret: str) -> None:
        self._feishu_running = True
        self._feishu_client = self._create_feishu_ws_client(app_id, app_secret)
        self._feishu_thread = threading.Thread(target=self._run_feishu_ws_client, name="feishu-bot-ws", daemon=True)
        self._feishu_thread.start()

    def _create_feishu_ws_client(self, app_id: str, app_secret: str) -> Any:
        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self._handle_feishu_ws_message)
            .build()
        )
        return lark.ws.Client(
            app_id,
            app_secret,
            log_level=lark.LogLevel.INFO,
            event_handler=event_handler,
        )

    def _run_feishu_ws_client(self) -> None:
        thread_loop = asyncio.new_event_loop()
        self._feishu_loop = thread_loop
        asyncio.set_event_loop(thread_loop)
        lark_ws_client.loop = thread_loop
        try:
            if self._feishu_client is not None:
                self._feishu_client.start()
        except Exception:
            self.logger.exception("飞书长连接启动失败", extra={"category": "bot"})
        finally:
            try:
                pending = asyncio.all_tasks(thread_loop)
                for task in pending:
                    task.cancel()
                if not thread_loop.is_closed():
                    thread_loop.stop()
                    thread_loop.close()
            except Exception:
                pass
            self._feishu_loop = None
            self._feishu_running = False

    async def _stop_feishu_long_connection(self) -> None:
        self._feishu_running = False
        client = self._feishu_client
        thread = self._feishu_thread
        loop = self._feishu_loop
        self._feishu_client = None
        self._feishu_thread = None
        self._feishu_loop = None
        if client is None:
            return
        try:
            disconnect = getattr(client, "_disconnect", None)
            if disconnect is not None and loop is not None and not loop.is_closed():
                future = asyncio.run_coroutine_threadsafe(disconnect(), loop)
                future.result(timeout=3)
        except Exception:
            self.logger.exception("飞书长连接断开失败", extra={"category": "bot"})
        if thread and thread.is_alive():
            thread.join(timeout=1)

    def _handle_feishu_ws_message(self, data: Any) -> None:
        try:
            payload = self._convert_feishu_ws_event_to_payload(data)
            loop = asyncio.get_running_loop()
            task = loop.create_task(self.handle_feishu_event(payload))
            task.add_done_callback(self._handle_feishu_ws_task_done)
        except Exception:
            self.logger.exception("飞书长连接消息处理失败", extra={"category": "bot"})

    def _handle_feishu_ws_task_done(self, task: asyncio.Task[Any]) -> None:
        try:
            task.result()
        except Exception:
            self.logger.exception("飞书长连接异步任务失败", extra={"category": "bot"})

    def _convert_feishu_ws_event_to_payload(self, data: Any) -> dict[str, Any]:
        event = getattr(data, "event", None)
        message = getattr(event, "message", None)
        sender = getattr(event, "sender", None)
        sender_id = getattr(sender, "sender_id", None)
        return {
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": self._feishu_app_id(self.config_service.get_runtime_config()),
            },
            "event": {
                "message": {
                    "message_id": str(getattr(message, "message_id", "") or ""),
                    "chat_id": str(getattr(message, "chat_id", "") or ""),
                    "chat_type": str(getattr(message, "chat_type", "") or ""),
                    "message_type": str(getattr(message, "message_type", "text") or "text"),
                    "content": getattr(message, "content", "{}") or "{}",
                },
                "sender": {
                    "sender_id": {
                        "open_id": str(getattr(sender_id, "open_id", "") or ""),
                        "user_id": str(getattr(sender_id, "user_id", "") or ""),
                        "union_id": str(getattr(sender_id, "union_id", "") or ""),
                    }
                },
            },
        }

    async def _run_telegram_poll_loop(self) -> None:
        while self._telegram_running:
            try:
                config = self.config_service.get_runtime_config()
                token = self._telegram_token(config)
                if config.notifier.telegram_enabled and token:
                    if token not in self._telegram_commands_registered:
                        await self._register_telegram_commands(token)
                    await self.sync_telegram_updates(process_commands=True)
            except Exception:
                self.logger.exception("Telegram 轮询命令失败", extra={"category": "bot"})
            await asyncio.sleep(self.TELEGRAM_POLL_INTERVAL_SECONDS)

    async def _register_telegram_commands(self, token: str) -> None:
        try:
            await self._telegram_request(
                token,
                "setMyCommands",
                json_payload={
                    "commands": self._telegram_menu_commands()
                },
            )
            self._telegram_commands_registered.add(token)
        except Exception:
            self.logger.exception("注册 Telegram 命令菜单失败", extra={"category": "bot"})

    async def _telegram_has_webhook(self, token: str) -> bool:
        try:
            payload = await self._telegram_request(token, "getWebhookInfo", method="GET")
            return bool((payload.get("result") or {}).get("url"))
        except Exception:
            return False

    async def _telegram_request(
        self,
        token: str,
        method_name: str,
        *,
        method: str = "POST",
        params: dict[str, Any] | None = None,
        json_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"https://api.telegram.org/bot{token}/{method_name}"
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.request(method, url, params=params, json=json_payload)
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(str(payload.get("description") or f"Telegram API 调用失败: {method_name}"))
        return payload

    async def _send_telegram_message(self, token: str, chat_id: str, text: str, *, include_keyboard: bool) -> None:
        body: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text[:4096],
        }
        if include_keyboard:
            body["reply_markup"] = {
                "keyboard": [
                    [{"text": "/status"}, {"text": "/metrics"}],
                    [{"text": "/positions"}, {"text": "/decisions"}],
                    [{"text": "/symbol BTC/USDT"}, {"text": "/approvals"}],
                    [{"text": "/bind"}, {"text": "/run"}, {"text": "/resetpaper 1000"}],
                    [{"text": "/pause"}, {"text": "/stop"}, {"text": "/protect"}],
                ],
                "resize_keyboard": True,
                "is_persistent": True,
            }
        await self._telegram_request(token, "sendMessage", json_payload=body)

    async def _reply_feishu_text(self, message_id: str, text: str) -> None:
        config = self.config_service.get_runtime_config()
        app_id = self._feishu_app_id(config)
        app_secret = self._feishu_app_secret(config)
        if not (app_id and app_secret and message_id):
            return

        access_token = await self._get_feishu_tenant_access_token(app_id, app_secret)
        if not access_token:
            return

        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(
                f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                json={
                    "content": json.dumps({"text": text}, ensure_ascii=False),
                    "msg_type": "text",
                },
            )
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(
                f"飞书回复失败: code={payload.get('code')} msg={payload.get('msg')} payload={json.dumps(payload, ensure_ascii=False)}"
            )

    async def _reply_feishu_card(self, message_id: str, card: dict[str, Any]) -> None:
        config = self.config_service.get_runtime_config()
        app_id = self._feishu_app_id(config)
        app_secret = self._feishu_app_secret(config)
        if not (app_id and app_secret and message_id):
            return

        access_token = await self._get_feishu_tenant_access_token(app_id, app_secret)
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(
                f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                json={
                    "content": json.dumps(card, ensure_ascii=False),
                    "msg_type": "interactive",
                },
            )
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(
                f"飞书卡片回复失败: code={payload.get('code')} msg={payload.get('msg')} payload={json.dumps(payload, ensure_ascii=False)}"
            )

    async def _get_feishu_tenant_access_token(self, app_id: str, app_secret: str) -> str:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                headers={"Content-Type": "application/json; charset=utf-8"},
                json={"app_id": app_id, "app_secret": app_secret},
            )
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(str(payload.get("msg") or "飞书 tenant_access_token 获取失败"))
        return str(payload.get("tenant_access_token") or "")

    def _telegram_menu_commands(self) -> list[dict[str, str]]:
        return [
            {"command": "start", "description": "显示帮助菜单"},
            {"command": "help", "description": "查看命令说明"},
            {"command": "chatid", "description": "查看当前会话 ID"},
            {"command": "bind", "description": "绑定当前会话"},
            {"command": "status", "description": "查看运行状态"},
            {"command": "metrics", "description": "查看账户指标"},
            {"command": "positions", "description": "查看持仓摘要"},
            {"command": "symbol", "description": "查看单币状态"},
            {"command": "decisions", "description": "查看最近决策"},
            {"command": "approvals", "description": "查看待审核订单"},
            {"command": "run", "description": "启动策略"},
            {"command": "pause", "description": "暂停策略"},
            {"command": "stop", "description": "停止策略"},
            {"command": "protect", "description": "进入保护模式"},
            {"command": "resetpaper", "description": "重置模拟账户"},
        ]

    def _extract_feishu_text(self, message: dict[str, Any]) -> str:
        content_raw = message.get("content") or "{}"
        if isinstance(content_raw, dict):
            content_payload = content_raw
        else:
            try:
                content_payload = json.loads(content_raw)
            except json.JSONDecodeError:
                content_payload = {"text": str(content_raw)}
        text = str(content_payload.get("text") or "").strip()
        if not text:
            return ""
        if "</at>" in text:
            text = text.split("</at>", 1)[1].strip()
        return text

    def _parse_command(self, raw_command: str) -> tuple[str, str]:
        text = raw_command.strip()
        if not text:
            return "", ""
        if text.startswith("/"):
            without_slash = text[1:]
            command_token, _, remainder = without_slash.partition(" ")
            if "@" in command_token:
                command_token = command_token.split("@", 1)[0]
            return command_token.lower(), remainder.strip()
        command_token, _, remainder = text.partition(" ")
        return command_token.lower(), remainder.strip()

    def _build_help_response(self, config: AppConfig, context: dict[str, Any], recognized_command: str = "help") -> dict[str, Any]:
        if context.get("platform") == "feishu":
            return {
                "recognized_command": recognized_command,
                "message": self._build_help_text(config, context),
                "authorized": False,
                "include_keyboard": False,
                "reply_mode": "card",
                "card": self._build_feishu_menu_card(config, context),
            }
        return {
            "recognized_command": recognized_command,
            "message": self._build_help_text(config, context),
            "authorized": False,
            "include_keyboard": True,
            "reply_mode": "text",
        }

    def _build_help_text(self, config: AppConfig, context: dict[str, Any]) -> str:
        bound = self._bound_target_for_platform(config, context.get("platform") or "")
        lines = [
            "机器人控制菜单",
            f"当前来源: {context.get('display_name') or context.get('source_id') or 'unknown'}",
            f"当前绑定: {bound or '未绑定'}",
            "",
            "/chatid 查看当前会话 ID",
            "/bind 绑定当前会话为默认控制目标",
            "/status 查看运行状态",
            "/metrics 查看账户指标",
            "/positions 查看持仓",
            "/symbol BTC/USDT 查看单币状态",
            "/decisions 查看最近决策",
            "/approvals 查看待审核订单",
            "/run 启动策略",
            "/pause 暂停策略",
            "/stop 停止策略",
            "/protect 进入保护模式",
            "/resetpaper 1000 重置模拟账户",
            "",
            "说明: 控制命令仅对已绑定会话开放。",
        ]
        return "\n".join(lines)

    def _build_identity_text(self, config: AppConfig, context: dict[str, Any]) -> str:
        platform = context.get("platform") or "unknown"
        current_id = context.get("source_id") or ""
        bound_id = self._bound_target_for_platform(config, platform)
        return "\n".join(
            [
                f"平台: {platform}",
                f"当前会话 ID: {current_id or '未知'}",
                f"当前绑定: {bound_id or '未绑定'}",
                "如果这是你要接收告警和控制项目的会话，发送 /bind 即可完成绑定。",
            ]
        )

    def _build_status_text(self) -> str:
        status = self.state.to_dict()
        return "\n".join(
            [
                "运行状态",
                f"策略状态: {status['status']}",
                f"风控状态: {status['risk_status']}",
                f"环境: {status['env']}",
                f"交易所: {status['exchange']}",
                f"实盘开关: {'开启' if status['live_enabled'] else '关闭'}",
                f"最近心跳: {status['last_heartbeat'] or '暂无'}",
            ]
        )

    def _build_metrics_text(self) -> str:
        summary = self.metrics_service.get_summary()
        return "\n".join(
            [
                "账户指标",
                f"权益: {summary['equity']:.2f}",
                f"可用余额: {summary['available_balance']:.2f}",
                f"总收益: {summary['total_pnl']:.2f}",
                f"日收益: {summary['daily_pnl']:.2f}",
                f"最大回撤: {summary['max_drawdown']:.2%}",
                f"胜率: {summary['win_rate']:.2%}",
                f"总交易数: {summary['total_trades']}",
                f"当前持仓数: {summary['position_count']}",
            ]
        )

    def _build_positions_text(self) -> str:
        positions = [item for item in self.metrics_service.list_positions() if item.quantity > 0]
        if not positions:
            return "当前没有持仓。"
        lines = ["当前持仓"]
        for position in positions[:8]:
            lines.append(
                f"{position.symbol} {position.quantity:.6f} @ {position.avg_price:.4f} 未实现 {position.unrealized_pnl:.2f}"
            )
        return "\n".join(lines)

    def _build_symbol_text(self, args: str) -> str:
        symbol_query = args.strip().upper()
        if not symbol_query:
            return "请提供交易对，例如 /symbol BTC/USDT"

        matched_symbol = None
        config = self.config_service.get_runtime_config()
        for symbol in config.symbols:
            normalized = symbol.upper()
            if symbol_query == normalized or symbol_query.replace("/", "") == normalized.replace("/", ""):
                matched_symbol = symbol
                break
        if matched_symbol is None:
            return f"未找到交易对 {symbol_query}。当前监控列表：{', '.join(config.symbols)}"

        ticker = self.state.latest_tickers.get(matched_symbol) or {}
        symbol_state = self.state.symbol_states.get(matched_symbol) or {}
        latest_decision = None
        for decision in self.metrics_service.list_decisions(limit=30):
            if decision.symbol == matched_symbol:
                latest_decision = decision
                break

        lines = [f"交易对状态 {matched_symbol}"]
        if ticker:
            lines.append(f"最新价: {float(ticker.get('price') or ticker.get('last') or 0):.6f}")
            if ticker.get("change_percent") is not None:
                lines.append(f"24h 涨跌: {float(ticker.get('change_percent')):.2f}%")
        if symbol_state:
            lines.append(f"当前阶段: {symbol_state.get('phase') or 'unknown'}")
            lines.append(f"最后动作: {symbol_state.get('last_action') or 'unknown'}")
            lines.append(f"最后原因: {symbol_state.get('last_reason') or 'unknown'}")
        if latest_decision:
            lines.append(
                f"最近决策: {latest_decision.final_action} 分数 {latest_decision.signal_score:.3f} 原因 {latest_decision.reason}"
            )
        return "\n".join(lines)

    def _build_decisions_text(self) -> str:
        decisions = self.metrics_service.list_decisions(limit=6)
        if not decisions:
            return "当前没有最近决策记录。"
        lines = ["最近策略决策"]
        for decision in decisions:
            lines.append(
                f"{decision.symbol} {decision.final_action} 分数 {decision.signal_score:.3f} 置信度 {decision.confidence:.2f} 原因 {decision.reason}"
            )
        return "\n".join(lines)

    def _build_approvals_text(self) -> str:
        with self.session_factory() as session:
            approvals = session.exec(
                select(OrderApproval)
                .where(OrderApproval.status == "PENDING")
                .order_by(OrderApproval.requested_at.desc())
            ).all()
        if not approvals:
            return "当前没有待审核订单。"
        lines = ["待审核订单"]
        for approval in approvals[:10]:
            lines.append(f"#{approval.id} {approval.symbol} {approval.side} 名义价值 {approval.notional:.2f}")
        return "\n".join(lines)

    def _build_not_bound_text(self, config: AppConfig, context: dict[str, Any]) -> str:
        return "\n".join(
            [
                "当前会话还没有控制权限。",
                self._build_identity_text(config, context),
            ]
        )

    async def _bind_current_source(self, config: AppConfig, context: dict[str, Any]) -> str:
        source_id = str(context.get("source_id") or "").strip()
        platform = context.get("platform") or ""
        if not source_id:
            return "无法识别当前会话 ID，绑定失败。"

        if platform == "telegram":
            current_bound = self._telegram_chat_id(config)
            if current_bound and current_bound != source_id:
                return f"Telegram 已绑定到 {current_bound}，如需切换请先在系统配置页重新绑定。"
            await self.bind_telegram_chat(source_id, changed_by="telegram-bot")
            return f"已把 Telegram 会话 {source_id} 绑定为默认控制与告警目标。"

        if platform == "feishu":
            current_bound = self._feishu_receive_id(config)
            if current_bound and current_bound != source_id:
                return f"飞书已绑定到 {current_bound}，如需切换请先在系统配置页重新绑定。"
            await self.bind_feishu_receive(source_id, "chat_id", changed_by="feishu-bot")
            return f"已把飞书会话 {source_id} 绑定为默认控制与告警目标。"

        return "当前平台不支持自动绑定。"

    def _remember_feishu_target(self, event: dict[str, Any]) -> None:
        message = event.get("message") or {}
        sender = event.get("sender") or {}
        chat_id = str(message.get("chat_id") or "")
        if not chat_id:
            return
        sender_id = ((sender.get("sender_id") or {}).get("open_id")) or ""
        self._feishu_recent_targets[chat_id] = {
            "id": chat_id,
            "title": str((sender.get("sender_id") or {}).get("union_id") or sender_id or chat_id),
            "platform": "feishu",
            "chat_type": str(message.get("chat_type") or "unknown"),
            "username": str(sender_id),
        }

    def _is_bound_controller(self, config: AppConfig, context: dict[str, Any]) -> bool:
        source_id = str(context.get("source_id") or "")
        bound = self._bound_target_for_platform(config, str(context.get("platform") or ""))
        return bool(source_id and bound and source_id == bound)

    def _bound_target_for_platform(self, config: AppConfig, platform: str) -> str:
        if platform == "telegram":
            return self._telegram_chat_id(config)
        if platform == "feishu":
            return self._feishu_receive_id(config)
        return ""

    def _telegram_token(self, config: AppConfig) -> str:
        return config.notifier.telegram_bot_token or self.env_settings.telegram_bot_token

    def _telegram_chat_id(self, config: AppConfig) -> str:
        return config.notifier.telegram_chat_id or self.env_settings.telegram_chat_id

    def _feishu_app_id(self, config: AppConfig) -> str:
        return config.notifier.feishu_app_id or self.env_settings.feishu_app_id

    def _feishu_app_secret(self, config: AppConfig) -> str:
        return config.notifier.feishu_app_secret or self.env_settings.feishu_app_secret

    def _feishu_receive_id(self, config: AppConfig) -> str:
        return config.notifier.feishu_receive_id or self.env_settings.feishu_receive_id

    def _remember_telegram_target(self, update: dict[str, Any]) -> None:
        message = update.get("message") or (update.get("callback_query") or {}).get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            return
        entry = {
            "id": str(chat_id),
            "title": self._telegram_display_name(chat),
            "platform": "telegram",
            "chat_type": str(chat.get("type") or "unknown"),
            "username": str(chat.get("username") or ""),
        }
        self._telegram_recent_targets[str(chat_id)] = entry

    def _telegram_display_name(self, chat: dict[str, Any]) -> str:
        if chat.get("title"):
            return str(chat.get("title"))
        first_name = str(chat.get("first_name") or "")
        last_name = str(chat.get("last_name") or "")
        username = str(chat.get("username") or "")
        combined = " ".join(part for part in [first_name, last_name] if part).strip()
        return combined or username or str(chat.get("id") or "unknown")

    def _update_notifier_binding(
        self,
        *,
        changed_by: str,
        telegram_chat_id: str | None,
        feishu_receive_id: str | None,
        feishu_receive_id_type: str | None,
    ) -> AppConfig:
        current = self.config_service.get_config().model_copy(deep=True)
        if telegram_chat_id is not None:
            current.notifier.telegram_chat_id = telegram_chat_id
        if feishu_receive_id is not None:
            current.notifier.feishu_receive_id = feishu_receive_id
        if feishu_receive_id_type is not None:
            current.notifier.feishu_receive_id_type = feishu_receive_id_type
        with self.session_factory() as session:
            return self.config_service.update_config(
                session,
                new_config=current,
                apply_immediately=True,
                changed_by=changed_by,
            )

    def _close_run_if_open(self, session: Session, new_status: str) -> None:
        if self.state.run_id is None:
            return
        run = session.get(StrategyRun, self.state.run_id)
        if run:
            run.status = new_status
            run.ended_at = datetime.utcnow()
            session.add(run)
            session.commit()

    async def _broadcast_runtime(self) -> None:
        await self.websocket_manager.broadcast("dashboard", {"type": "status", "status": self.state.to_dict()})

    async def _run_strategy(self) -> str:
        with self.session_factory() as session:
            config = self.config_service.get_runtime_config()
            if self.state.status == StrategyRuntimeStatus.RUNNING:
                return "策略已经在运行中。"
            if config.env == "paper" and config.simulation.reset_account_on_start:
                self.portfolio_service.reset_paper_account(session, config.simulation.starting_balance)
                await self.market_data_service.refresh_once()
            run = StrategyRun(
                status=StrategyRuntimeStatus.RUNNING.value,
                mode=config.env,
                env=config.env,
                total_symbols=len(config.symbols),
                note="由机器人命令启动",
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            self.state.run_id = run.id
            self.state.started_at = run.started_at
            self.state.set_status(StrategyRuntimeStatus.RUNNING)
            if self.state.risk_status == RiskStatus.PROTECT_MODE:
                self.state.set_risk_status(RiskStatus.NORMAL, "")
        await self._broadcast_runtime()
        return "策略已启动。"

    async def _pause_strategy(self) -> str:
        if self.state.status == StrategyRuntimeStatus.PAUSED:
            return "策略已经处于暂停状态。"
        self.state.set_status(StrategyRuntimeStatus.PAUSED)
        await self._broadcast_runtime()
        return "策略已暂停。"

    async def _stop_strategy(self) -> str:
        with self.session_factory() as session:
            self._close_run_if_open(session, StrategyRuntimeStatus.STOPPED.value)
            self.state.run_id = None
            self.state.set_status(StrategyRuntimeStatus.STOPPED)
        await self._broadcast_runtime()
        return "策略已停止。"

    async def _protect_strategy(self) -> str:
        with self.session_factory() as session:
            self._close_run_if_open(session, StrategyRuntimeStatus.PROTECT_MODE.value)
            self.state.set_status(StrategyRuntimeStatus.PROTECT_MODE)
            self.state.set_risk_status(RiskStatus.PROTECT_MODE, "机器人命令触发保护模式")
        await self._broadcast_runtime()
        return "系统已进入保护模式。"

    async def _reset_paper_account(self, args: str) -> str:
        config = self.config_service.get_runtime_config()
        if config.env != "paper":
            return "只有在 paper 环境下才允许重置模拟账户。"

        starting_balance = config.simulation.starting_balance
        if args:
            try:
                starting_balance = float(args)
            except ValueError:
                return "重置金额格式错误，例如 /resetpaper 1000"
        if starting_balance <= 0:
            return "重置金额必须大于 0。"

        with self.session_factory() as session:
            self._close_run_if_open(session, StrategyRuntimeStatus.STOPPED.value)
            self.state.run_id = None
            self.state.set_status(StrategyRuntimeStatus.STOPPED)
            self.state.set_risk_status(RiskStatus.NORMAL, "")
            applied_balance = self.portfolio_service.reset_paper_account(session, starting_balance)
        await self.market_data_service.refresh_once()
        summary = self.metrics_service.get_summary()
        await self._broadcast_runtime()
        await self.websocket_manager.broadcast("dashboard", {"type": "metrics", "summary": summary})
        return f"模拟账户已重置为 {applied_balance:.2f}，当前权益 {summary['equity']:.2f}。"

    def _build_feishu_menu_card(self, config: AppConfig, context: dict[str, Any]) -> dict[str, Any]:
        source_id = str(context.get("source_id") or "")
        bound = self._bound_target_for_platform(config, "feishu") or "未绑定"
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "量化机器人控制台"},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"当前会话: {source_id or 'unknown'}\n"
                            f"当前绑定: {bound}\n"
                            "当前飞书卡片快捷按钮暂时关闭，请直接发送下面的文本命令。"
                        ),
                    },
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "可用命令:\n/status\n/metrics\n/positions\n/decisions\n/approvals\n/bind\n/run\n/pause\n/stop\n/protect\n/resetpaper 1000\n/symbol BTC/USDT",
                    },
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": "如需控制当前群，请先发送 /bind。",
                        }
                    ],
                },
            ],
        }

    def _feishu_card_button(self, text: str, command: str, source_id: str, button_type: str) -> dict[str, Any]:
        return {
            "tag": "button",
            "text": {"tag": "plain_text", "content": text},
            "type": button_type,
            "value": {"command": command, "source_id": source_id},
        }