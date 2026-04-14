from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder


class WebSocketManager:
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections[channel].add(websocket)

    def disconnect(self, channel: str, websocket: WebSocket) -> None:
        self.connections[channel].discard(websocket)

    async def broadcast(self, channel: str, payload: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        encoded_payload = jsonable_encoder(payload)
        for socket in list(self.connections[channel]):
            try:
                await socket.send_json(encoded_payload)
            except Exception:
                stale.append(socket)
        for socket in stale:
            self.disconnect(channel, socket)
