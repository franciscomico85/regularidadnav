from pydantic import BaseModel, Field
from datetime import datetime


# --- Balizas ---
class Baliza(BaseModel):
    nombre: str
    lat: float
    lng: float
    orden: int


# --- Regata ---
class RegataCreate(BaseModel):
    nombre: str
    fecha: str
    club_organizador: str = ""
    velocidad_minima: int = Field(10, ge=10, le=20)
    velocidad_maxima: int = Field(20, ge=10, le=20)
    balizas: list[Baliza] = []


class RegataUpdate(BaseModel):
    nombre: str | None = None
    fecha: str | None = None
    club_organizador: str | None = None
    velocidad_minima: int | None = Field(None, ge=10, le=20)
    velocidad_maxima: int | None = Field(None, ge=10, le=20)
    balizas: list[Baliza] | None = None


class RegataOut(BaseModel):
    id: int
    nombre: str
    fecha: str
    club_organizador: str
    clave_acceso: str
    velocidad_minima: int
    velocidad_maxima: int
    estado: str
    balizas: list[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Barco ---
class BarcoCreate(BaseModel):
    nombre: str
    numero_vela: str = ""
    velocidad_declarada: int = Field(ge=10, le=20)


class BarcoUpdate(BaseModel):
    nombre: str | None = None
    numero_vela: str | None = None
    velocidad_declarada: int | None = Field(None, ge=10, le=20)


class BarcoOut(BaseModel):
    id: int
    nombre: str
    numero_vela: str
    velocidad_declarada: int
    estado: str
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


# --- Posicion ---
class PosicionIn(BaseModel):
    lat: float
    lng: float
    cog: float | None = None
    speed_kn: float | None = None
    timestamp: datetime | None = None


class PosicionBatchIn(BaseModel):
    posiciones: list[PosicionIn]


# --- Paso por baliza ---
class PasoIn(BaseModel):
    baliza_orden: int
    timestamp_real: float
    lat: float | None = None
    lng: float | None = None
    registrado_por: str = "manual"


class PasoOut(BaseModel):
    id: int
    baliza_orden: int
    timestamp_teorico: float
    timestamp_real: float
    penalizacion_segundos: int
    lat: float | None
    lng: float | None
    registrado_por: str

    model_config = {"from_attributes": True}


# --- Clasificacion ---
class ClasificacionItem(BaseModel):
    posicion: int
    barco_id: int
    nombre: str
    numero_vela: str
    velocidad_declarada: int
    estado: str
    penalizacion_total: int
    balizas_pasadas: int
    total_balizas: int


# --- Resultado ---
class ResultadoBarco(BaseModel):
    posicion: int
    barco_id: int
    nombre: str
    numero_vela: str
    velocidad_declarada: int
    estado: str
    penalizacion_total: int
    desglose: list[PasoOut]
