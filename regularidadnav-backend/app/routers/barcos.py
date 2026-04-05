from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Barco
from schemas import BarcoCreate, BarcoUpdate, BarcoOut
from routers.regatas import get_regata
from ws.manager import manager

router = APIRouter(prefix="/api/regatas/{clave}/barcos", tags=["barcos"])


@router.post("", response_model=BarcoOut)
async def inscribir_barco(clave: str, data: BarcoCreate, db: AsyncSession = Depends(get_db)):
    regata = await get_regata(clave, db)
    if data.velocidad_declarada < regata.velocidad_minima or data.velocidad_declarada > regata.velocidad_maxima:
        raise HTTPException(400, f"Velocidad debe estar entre {regata.velocidad_minima} y {regata.velocidad_maxima}")
    barco = Barco(
        regata_id=regata.id,
        nombre=data.nombre,
        numero_vela=data.numero_vela,
        velocidad_declarada=data.velocidad_declarada,
    )
    db.add(barco)
    await db.commit()
    await db.refresh(barco)
    await manager.broadcast(clave, {"tipo": "barco_nuevo", "barco": BarcoOut.model_validate(barco).model_dump(mode="json")})
    return barco


@router.get("", response_model=list[BarcoOut])
async def listar_barcos(clave: str, db: AsyncSession = Depends(get_db)):
    regata = await get_regata(clave, db)
    result = await db.execute(select(Barco).where(Barco.regata_id == regata.id))
    return result.scalars().all()


@router.patch("/{barco_id}", response_model=BarcoOut)
async def actualizar_barco(clave: str, barco_id: int, data: BarcoUpdate, db: AsyncSession = Depends(get_db)):
    regata = await get_regata(clave, db)
    result = await db.execute(select(Barco).where(Barco.id == barco_id, Barco.regata_id == regata.id))
    barco = result.scalar_one_or_none()
    if not barco:
        raise HTTPException(404, "Barco no encontrado")
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(barco, field, val)
    await db.commit()
    await db.refresh(barco)
    return barco


@router.post("/{barco_id}/salida", response_model=BarcoOut)
async def registrar_salida(clave: str, barco_id: int, db: AsyncSession = Depends(get_db)):
    regata = await get_regata(clave, db)
    if regata.estado != "activa":
        raise HTTPException(400, "La regata no está activa")
    result = await db.execute(select(Barco).where(Barco.id == barco_id, Barco.regata_id == regata.id))
    barco = result.scalar_one_or_none()
    if not barco:
        raise HTTPException(404, "Barco no encontrado")
    if barco.estado != "prestart":
        raise HTTPException(400, "El barco ya ha salido")
    barco.estado = "en_ruta"
    barco.started_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(barco)
    await manager.broadcast(clave, {"tipo": "salida", "barco_id": barco.id, "started_at": barco.started_at.isoformat()})
    return barco
