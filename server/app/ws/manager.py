import asyncio

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self._broadcast_lock: asyncio.Lock | None = None
        self._broadcast_lock_loop: asyncio.AbstractEventLoop | None = None

    def _get_broadcast_lock(self) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        if self._broadcast_lock is None or self._broadcast_lock_loop is not loop:
            self._broadcast_lock = asyncio.Lock()
            self._broadcast_lock_loop = loop
        return self._broadcast_lock

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        async with self._get_broadcast_lock():
            disconnected: list[WebSocket] = []
            for connection in list(self.active_connections):
                try:
                    await asyncio.wait_for(connection.send_json(message), timeout=0.5)
                except Exception:
                    disconnected.append(connection)

            for connection in disconnected:
                self.disconnect(connection)


manager = ConnectionManager()
