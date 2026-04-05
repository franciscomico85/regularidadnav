import math
import string
import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models import Regata, Barco, RegistroPaso
from schemas import RegataCreate, RegataUpdate, RegataOut, ClasificacionItem

router = APIRouter(prefix="/api/regatas", tags=["regatas"])

CHARS = string.ascii_uppercase + string.digits


def gen_clave() -> str:
    return "".join(secrets.choice(CHARS) for _ in range(8))


async def get_regata(clave: str, db: AsyncSession) -> Regata:
    result = await db.execute(select(Regata).where(Regata.clave_acceso == clave))
    regata = result.scalar_one_or_none()
    if not regata:
        raise HTTPException(404, "Regata no encontrada")
    return regata


def _hav(lat1, lng1, lat2, lng2) -> float:
    R = 3440.065
    r = math.pi / 180
    dlat = (lat2 - lat1) * r
    dlng = (lng2 - lng1) * r
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1 * r) * math.cos(lat2 * r) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _distancias_balizas(balizas: list[dict]) -> dict[int, float]:
    """Returns {orden: distancia_acumulada_nm}"""
    dist = {}
    acum = 0.0
    sorted_b = sorted(balizas, key=lambda b: b["orden"])
    for i, b in enumerate(sorted_b):
        if i > 0:
            prev = sorted_b[i - 1]
            acum += _hav(prev["lat"], prev["lng"], b["lat"], b["lng"])
        dist[b["orden"]] = acum
    return dist


@router.post("", response_model=RegataOut)
async def crear_regata(data: RegataCreate, db: AsyncSession = Depends(get_db)):
    regata = Regata(
        nombre=data.nombre,
        fecha=data.fecha,
        club_organizador=data.club_organizador,
        velocidad_minima=data.velocidad_minima,
        velocidad_maxima=data.velocidad_maxima,
        balizas=[b.model_dump() for b in data.balizas],
        clave_acceso=gen_clave(),
    )
    db.add(regata)
    await db.commit()
    await db.refresh(regata)
    return regata


@router.get("/{clave}", response_model=RegataOut)
async def obtener_regata(clave: str, db: AsyncSession = Depends(get_db)):
    return await get_regata(clave, db)


@router.patch("/{clave}", response_model=RegataOut)
async def actualizar_regata(clave: str, data: RegataUpdate, db: AsyncSession = Depends(get_db)):
    regata = await get_regata(clave, db)
    if regata.estado != "configuracion":
        raise HTTPException(400, "Solo se puede editar en estado configuracion")
    for field, val in data.model_dump(exclude_unset=True).items():
        if field == "balizas" and val is not None:
            val = [b if isinstance(b, dict) else b.model_dump() for b in val]
        setattr(regata, field, val)
    await db.commit()
    await db.refresh(regata)
    return regata


@router.post("/{clave}/activar", response_model=RegataOut)
async def activar_regata(clave: str, db: AsyncSession = Depends(get_db)):
    regata = await get_regata(clave, db)
    if regata.estado != "configuracion":
        raise HTTPException(400, "La regata ya está activa o finalizada")
    if len(regata.balizas) < 2:
        raise HTTPException(400, "Mínimo 2 balizas para activar")
    regata.estado = "activa"
    await db.commit()
    await db.refresh(regata)
    return regata


@router.get("/{clave}/clasificacion", response_model=list[ClasificacionItem])
async def clasificacion(clave: str, db: AsyncSession = Depends(get_db)):
    regata = await get_regata(clave, db)
    result = await db.execute(
        select(Barco)
        .where(Barco.regata_id == regata.id)
        .options(selectinload(Barco.registros_paso))
    )
    barcos = result.scalars().all()

    items = []
    for barco in barcos:
        pen_total = sum(r.penalizacion_segundos for r in barco.registros_paso)
        items.append({
            "barco_id": barco.id,
            "nombre": barco.nombre,
            "numero_vela": barco.numero_vela,
            "velocidad_declarada": barco.velocidad_declarada,
            "estado": barco.estado,
            "penalizacion_total": pen_total,
            "balizas_pasadas": len(barco.registros_paso),
            "total_balizas": len(regata.balizas),
        })

    # Finalizados primero (por pen ASC), luego en_ruta, luego prestart
    ORDER = {"finalizado": 0, "en_ruta": 1, "prestart": 2}
    items.sort(key=lambda x: (ORDER.get(x["estado"], 9), x["penalizacion_total"]))
    for i, item in enumerate(items):
        item["posicion"] = i + 1

    return items
