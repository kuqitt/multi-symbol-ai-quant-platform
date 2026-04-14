from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import AppConfig, EnvironmentSettings


class NotificationManager:
    def __init__(self, env_settings: EnvironmentSettings, logger: Any) -> None:
        self.env_settings = env_settings
        self.logger = logger
        self._telegram_chat_cache: dict[str, str] = {}

    async def _discover_telegram_chat_id(self, token: str) -> str:
        cached_chat_id = self._telegram_chat_cache.get(token)
        if cached_chat_id:
            return cached_chat_id

        async with httpx.AsyncClient(timeout=10.0) as client:
            webhook_info = await client.get(f"https://api.telegram.org/bot{token}/getWebhookInfo")
            webhook_payload = webhook_info.json()
            if webhook_payload.get("ok") and webhook_payload.get("result", {}).get("url"):
                self.logger.warning("Telegram 已配置 webhook，无法通过 getUpdates 自动发现 chat_id", extra={"category": "notifier"})
                return ""

            response = await client.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"limit": 100, "timeout": 0},
            )
        payload = response.json()
        if not payload.get("ok"):
            return ""

        for update in reversed(payload.get("result", [])):
            chat_id = self._extract_telegram_chat_id(update)
            if chat_id:
                self._telegram_chat_cache[token] = chat_id
                return chat_id
        return ""

    def _extract_telegram_chat_id(self, update: dict[str, Any]) -> str:
        candidates = [
            update.get("message"),
            update.get("edited_message"),
            update.get("channel_post"),
            update.get("edited_channel_post"),
            update.get("business_message"),
            update.get("edited_business_message"),
            update.get("my_chat_member"),
            update.get("chat_member"),
        ]

        callback_query = update.get("callback_query") or {}
        if callback_query.get("message"):
            candidates.append(callback_query["message"])

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            chat = candidate.get("chat") or {}
            chat_id = chat.get("id")
            if chat_id is not None:
                return str(chat_id)
        return ""

    async def _send_telegram(self, message: str, token: str, chat_id: str) -> None:
        if not token:
            return
        target_chat_id = chat_id or await self._discover_telegram_chat_id(token)
        if not target_chat_id:
            self.logger.warning(
                "Telegram 未找到可用 chat_id，请先给机器人发一条消息，或在环境变量中显式配置 TELEGRAM_CHAT_ID",
                extra={"category": "notifier"},
            )
            return
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                url,
                json={"chat_id": target_chat_id, "text": message},
            )

    async def _get_feishu_tenant_access_token(self, app_id: str, app_secret: str) -> str:
        if not (app_id and app_secret):
            return ""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": app_id, "app_secret": app_secret},
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
        payload = response.json()
        if payload.get("code") != 0:
            self.logger.warning(
                "飞书 tenant_access_token 获取失败",
                extra={"category": "notifier", "payload": payload},
            )
            return ""
        return str(payload.get("tenant_access_token") or "")

    async def _send_feishu(self, message: str, webhook_url: str) -> None:
        if not webhook_url:
            return
        payload = {
            "msg_type": "text",
            "content": {
                "text": message,
            },
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(webhook_url, json=payload)

    async def _send_feishu_app(
        self,
        message: str,
        app_id: str,
        app_secret: str,
        receive_id: str,
        receive_id_type: str,
    ) -> None:
        if not (app_id and app_secret):
            return
        if not receive_id:
            self.logger.warning(
                "飞书已配置 App ID / App Secret，但缺少消息接收者 ID，无法主动推送",
                extra={"category": "notifier"},
            )
            return

        access_token = await self._get_feishu_tenant_access_token(app_id, app_secret)
        if not access_token:
            return

        body = {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": message}, ensure_ascii=False),
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}",
                json=body,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
            )

    async def send_alert(self, config: AppConfig, message: str) -> None:
        try:
            telegram_token = config.notifier.telegram_bot_token or self.env_settings.telegram_bot_token
            telegram_chat_id = config.notifier.telegram_chat_id or self.env_settings.telegram_chat_id
            feishu_app_id = config.notifier.feishu_app_id or self.env_settings.feishu_app_id
            feishu_receive_id = config.notifier.feishu_receive_id or self.env_settings.feishu_receive_id
            feishu_receive_id_type = config.notifier.feishu_receive_id_type or self.env_settings.feishu_receive_id_type
            feishu_webhook_url = config.notifier.feishu_webhook_url or self.env_settings.feishu_webhook_url
            feishu_app_secret = config.notifier.feishu_app_secret or self.env_settings.feishu_app_secret
            if config.notifier.telegram_enabled:
                await self._send_telegram(message, telegram_token, telegram_chat_id)
            if config.notifier.feishu_enabled:
                if feishu_app_id and feishu_app_secret:
                    await self._send_feishu_app(
                        message,
                        feishu_app_id,
                        feishu_app_secret,
                        feishu_receive_id,
                        feishu_receive_id_type,
                    )
                else:
                    await self._send_feishu(message, feishu_webhook_url)
        except Exception:
            self.logger.exception("通知发送失败", extra={"category": "notifier"})

    async def send_approval_request(self, config: AppConfig, approval_payload: dict[str, Any]) -> None:
        symbol = approval_payload.get("symbol", "UNKNOWN")
        side = approval_payload.get("side", "N/A")
        notional = approval_payload.get("notional", 0.0)
        message = f"[审批请求] {symbol} {side} 需人工审核，名义价值 {notional:.2f}"
        await self.send_alert(config, message)
