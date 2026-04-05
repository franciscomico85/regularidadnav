import math
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Barco, Regata, RegistroPaso, PosicionGPS
from schemas import PosicionIn, PosicionBatchIn, PasoIn, PasoOut
from routers.regatas import get_regata, _hav, _distancias_balizas
from ws.manager import manager

router = APIRouter(prefix="/api/regatas/{clave}/barcos/{barco_id}", tags=["tracking"])


async def _get_barco(clave: str, barco_id: int, db: AsyncSession) -> tuple[Regata, Barco]:
    regata = await get_regata(clave, db)
    result = await db.execute(select(Barco).where(Barco.id == barco_id, Barco.regata_id == regata.id))
    barco = result.scalar_one_or_none()
    if not barco:
        raise HTTPException(404, "Barco no encontrado")
    return regata, barco


@router.post("/posicion")
async def enviar_posicion(clave: str, barco_id: int, data: PosicionIn | PosicionBatchIn, db: AsyncSession = Depends(get_db)):
    regata, barco = await _get_barco(clave, barco_id, db)

    posiciones = data.posiciones if isinstance(data, PosicionBatchIn) else [data]

    for pos in posiciones:
        gps = PosicionGPS(
            barco_id=barco.id,
            lat=pos.lat,
            lng=pos.lng,
            cog=pos.cog,
            speed_kn=pos.speed_kn,
            timestamp=pos.timestamp or datetime.now(timezone.utc),
        )
        db.add(gps)

    await db.commit()

    last = posiciones[-1]
    await manager.broadcast(clave, {
        "tipo": "posicion",
        "barco_id": barco.id,
        "nombre": barco.nombre,
        "lat": last.lat,
        "lng": last.lng,
        "cog": last.cog,
        "speed_kn": last.speed_kn,
    })

    return {"ok": True, "count": len(posiciones)}


@router.post("/paso", response_model=PasoOut)
async def registrar_paso(clave: str, barco_id: int, data: PasoIn, db: AsyncSession = Depends(get_db)):
    regata, barco = await _get_barco(clave, barco_id, db)

    if barco.estado != "en_ruta":
        raise HTTPException(400, "El barco no está en ruta")

    # Check not already registered
    existing = await db.execute(
        select(RegistroPaso).where(
            RegistroPaso.barco_id == barco.id,
            RegistroPaso.baliza_orden == data.baliza_orden,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Paso por esta baliza ya registrado")

    # Calculate theoretical time
    dist_map = _distancias_balizas(regata.balizas)
    dist_baliza = dist_map.get(data.baliza_orden, 0)
    timestamp_teorico = dist_baliza / barco.velocidad_declarada * 3600

    penalizacion = math.ceil(abs(data.timestamp_real - timestamp_teorico))

    registro = RegistroPaso(
        barco_id=barco.id,
        baliza_orden=data.baliza_orden,
        timestamp_teorico=timestamp_teorico,
        timestamp_real=data.timestamp_real,
        penalizacion_segundos=penalizacion,
        lat=data.lat,
        lng=data.lng,
        registrado_por=data.registrado_por,
    )
    db.add(registro)

    # Check if this was the last buoy
    total_balizas = len(regata.balizas)
    pasos_result = await db.execute(
        select(RegistroPaso).where(RegistroPaso.barco_id == barco.id)
    )
    pasos_count = len(pasos_result.scalars().all()) + 1  # +1 for current
    if pasos_count >= total_balizas - 1:  # -1 because first buoy is start
        barco.estado = "finalizado"
        barco.finished_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(registro)

    await manager.broadcast(clave, {
        "tipo": "paso",
        "barco_id": barco.id,
        "nombre": barco.nombre,
        "baliza_orden": data.baliza_orden,
        "penalizacion": penalizacion,
        "timestamp_real": data.timestamp_real,
        "timestamp_teorico": timestamp_teorico,
    })

    return registro
