"""
WebSocket connection manager.
Manages per-job subscriber sets and broadcasts messages.
"""
from __future__ import annotations
import json
from collections import defaultdict
from fastapi import WebSocket
from loguru import logger


class WSManager:
    def __init__(self) -> None:
        # job_id → set of connected WebSockets
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, job_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[job_id].add(ws)
        logger.debug(f"WS connected: job={job_id}")

    def disconnect(self, job_id: str, ws: WebSocket) -> None:
        self._connections[job_id].discard(ws)
        logger.debug(f"WS disconnected: job={job_id}")

    async def broadcast(self, job_id: str, data: dict) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._connections.get(job_id, [])):
            try:
                await ws.send_text(json.dumps(data, default=str))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections[job_id].discard(ws)


ws_manager = WSManager()
