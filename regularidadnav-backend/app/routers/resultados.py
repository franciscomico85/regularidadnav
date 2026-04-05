import csv
import io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models import Barco, RegistroPaso
from schemas import ResultadoBarco, PasoOut
from routers.regatas import get_regata

router = APIRouter(prefix="/api/regatas/{clave}/resultados", tags=["resultados"])


async def _build_resultados(clave: str, db: AsyncSession) -> list[dict]:
    regata = await get_regata(clave, db)
    result = await db.execute(
        select(Barco)
        .where(Barco.regata_id == regata.id)
        .options(selectinload(Barco.registros_paso))
    )
    barcos = result.scalars().all()

    items = []
    for barco in barcos:
        pasos = sorted(barco.registros_paso, key=lambda r: r.baliza_orden)
        pen_total = sum(r.penalizacion_segundos for r in pasos)
        items.append({
            "barco_id": barco.id,
            "nombre": barco.nombre,
            "numero_vela": barco.numero_vela,
            "velocidad_declarada": barco.velocidad_declarada,
            "estado": barco.estado,
            "penalizacion_total": pen_total,
            "desglose": [PasoOut.model_validate(p) for p in pasos],
        })

    ORDER = {"finalizado": 0, "en_ruta": 1, "prestart": 2}
    items.sort(key=lambda x: (ORDER.get(x["estado"], 9), x["penalizacion_total"]))
    for i, item in enumerate(items):
        item["posicion"] = i + 1

    return items


@router.get("", response_model=list[ResultadoBarco])
async def resultados(clave: str, db: AsyncSession = Depends(get_db)):
    return await _build_resultados(clave, db)


@router.get("/export")
async def exportar_csv(clave: str, db: AsyncSession = Depends(get_db)):
    items = await _build_resultados(clave, db)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Posicion", "Barco", "Vela", "Velocidad", "Estado", "Penalizacion Total"])
    for item in items:
        writer.writerow([
            item["posicion"],
            item["nombre"],
            item["numero_vela"],
            item["velocidad_declarada"],
            item["estado"],
            item["penalizacion_total"],
        ])

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=resultados.csv"},
    )
