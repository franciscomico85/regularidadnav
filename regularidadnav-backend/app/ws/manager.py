import json
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, clave: str, ws: WebSocket):
        await ws.accept()
        self._rooms.setdefault(clave, []).append(ws)

    def disconnect(self, clave: str, ws: WebSocket):
        conns = self._rooms.get(clave, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self._rooms.pop(clave, None)

    async def broadcast(self, clave: str, data: dict):
        msg = json.dumps(data)
        dead = []
        for ws in self._rooms.get(clave, []):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(clave, ws)


manager = ConnectionManager()
