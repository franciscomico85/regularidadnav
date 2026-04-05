import json
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete

from database import init_db, SessionLocal
from models import PosicionGPS
from ws.manager import manager
from routers import regatas, barcos, posiciones, resultados


async def purge_old_positions():
    """Delete GPS positions older than 24h every hour."""
    while True:
        await asyncio.sleep(3600)
        try:
            async with SessionLocal() as db:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                await db.execute(delete(PosicionGPS).where(PosicionGPS.timestamp < cutoff))
                await db.commit()
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(purge_old_positions())
    yield
    task.cancel()


app = FastAPI(title="RegularidadNav API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(regatas.router)
app.include_router(barcos.router)
app.include_router(posiciones.router)
app.include_router(resultados.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/{clave_regata}")
async def websocket_endpoint(websocket: WebSocket, clave_regata: str):
    await manager.connect(clave_regata, websocket)
    try:
        while True:
            text = await websocket.receive_text()
            try:
                data = json.loads(text)
                # Relay client messages to all others
                await manager.broadcast(clave_regata, data)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(clave_regata, websocket)
