from __future__ import annotations

import json
from importlib import import_module

from fastapi.testclient import TestClient

from app.main import app
from app.services.bot_service import BotService


def test_api_health_and_config() -> None:
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["ok"] is True

        login = client.post("/api/auth/login", json={"username": "admin", "password": "ChangeMe123!"})
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        config = client.get("/api/config", headers=headers)
        assert config.status_code == 200
        assert "symbols" in config.json()
        assert "regime" in config.json()
        assert "signal" in config.json()
        assert "allocation" in config.json()
        assert "cost_model" in config.json()

        system_config = client.get("/api/system-config", headers=headers)
        assert system_config.status_code == 200
        assert "config" in system_config.json()
        assert "okx_credentials" in system_config.json()

        bot_meta = client.get("/api/bot/meta", headers=headers)
        assert bot_meta.status_code == 200
        assert "commands" in bot_meta.json()
        assert "telegram" in bot_meta.json()
        assert "feishu" in bot_meta.json()
        assert bot_meta.json()["feishu"]["callback_path"] == "/api/bot/feishu/webhook"

        preview = client.post(
            "/api/bot/command-preview",
            headers=headers,
            json={"platform": "telegram", "command": "/symbol BTC/USDT"},
        )
        assert preview.status_code == 200
        assert preview.json()["recognized_command"] == "symbol"

        preview_decisions = client.post(
            "/api/bot/command-preview",
            headers=headers,
            json={"platform": "feishu", "command": "/decisions"},
        )
        assert preview_decisions.status_code == 200
        assert preview_decisions.json()["recognized_command"] == "decisions"

        status_response = client.get("/api/status", headers=headers)
        assert status_response.status_code == 200
        assert "status" in status_response.json()

        metrics = client.get("/api/metrics/summary", headers=headers)
        assert metrics.status_code == 200
        assert "equity" in metrics.json()

        attribution = client.get("/api/metrics/attribution", headers=headers)
        assert attribution.status_code == 200
        assert "overview" in attribution.json()
        assert "by_strategy" in attribution.json()

        reset = client.post("/api/strategy/paper-account/reset", headers=headers, json={"starting_balance": 1000})
        assert reset.status_code == 200
        assert reset.json()["starting_balance"] == 1000


def test_bot_command_helpers() -> None:
    menu_commands = BotService._telegram_menu_commands(BotService)  # type: ignore[misc]
    assert all(" " not in item["command"] for item in menu_commands)
    assert {item["command"] for item in menu_commands} >= {"status", "metrics", "symbol", "resetpaper"}

    extractor = BotService._extract_feishu_text  # type: ignore[assignment]
    assert extractor(BotService, {"content": '{"text":"/status"}'}) == "/status"
    assert (
        extractor(BotService, {"content": json.dumps({"text": '<at user_id="ou_xxx"></at> /metrics'})}) == "/metrics"
    )


def test_feishu_ws_event_conversion() -> None:
    event_module = import_module("lark_oapi.api.im.v1.model.p2_im_message_receive_v1")
    sdk_event = event_module.P2ImMessageReceiveV1(
        {
            "event": {
                "message": {
                    "message_id": "om_123",
                    "chat_id": "oc_456",
                    "chat_type": "group",
                    "message_type": "text",
                    "content": json.dumps({"text": "/status"}),
                },
                "sender": {
                    "sender_id": {
                        "open_id": "ou_1",
                        "user_id": "u_1",
                        "union_id": "on_1",
                    }
                },
            }
        }
    )

    bot = object.__new__(BotService)
    bot.config_service = type("ConfigServiceStub", (), {"get_runtime_config": lambda self: object()})()
    bot._feishu_app_id = lambda config: "cli_test"  # type: ignore[method-assign]

    payload = BotService._convert_feishu_ws_event_to_payload(bot, sdk_event)
    assert payload["header"]["event_type"] == "im.message.receive_v1"
    assert payload["event"]["message"]["message_id"] == "om_123"
    assert payload["event"]["message"]["chat_id"] == "oc_456"
    assert payload["event"]["sender"]["sender_id"]["open_id"] == "ou_1"
