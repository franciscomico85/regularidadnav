import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Regata(Base):
    __tablename__ = "regatas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    fecha: Mapped[str] = mapped_column(String(20))
    club_organizador: Mapped[str] = mapped_column(String(200), default="")
    clave_acceso: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    velocidad_minima: Mapped[int] = mapped_column(Integer, default=10)
    velocidad_maxima: Mapped[int] = mapped_column(Integer, default=20)
    estado: Mapped[str] = mapped_column(String(20), default="configuracion")
    balizas: Mapped[dict | list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    barcos: Mapped[list["Barco"]] = relationship(back_populates="regata", cascade="all, delete-orphan")


class Barco(Base):
    __tablename__ = "barcos"

    id: Mapped[int] = mapped_column(primary_key=True)
    regata_id: Mapped[int] = mapped_column(ForeignKey("regatas.id", ondelete="CASCADE"))
    nombre: Mapped[str] = mapped_column(String(200))
    numero_vela: Mapped[str] = mapped_column(String(50), default="")
    velocidad_declarada: Mapped[int] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(String(20), default="prestart")
    started_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    regata: Mapped["Regata"] = relationship(back_populates="barcos")
    registros_paso: Mapped[list["RegistroPaso"]] = relationship(back_populates="barco", cascade="all, delete-orphan")
    posiciones: Mapped[list["PosicionGPS"]] = relationship(back_populates="barco", cascade="all, delete-orphan")


class RegistroPaso(Base):
    __tablename__ = "registros_paso"

    id: Mapped[int] = mapped_column(primary_key=True)
    barco_id: Mapped[int] = mapped_column(ForeignKey("barcos.id", ondelete="CASCADE"))
    baliza_orden: Mapped[int] = mapped_column(Integer)
    timestamp_teorico: Mapped[float] = mapped_column(Float)
    timestamp_real: Mapped[float] = mapped_column(Float)
    penalizacion_segundos: Mapped[int] = mapped_column(Integer)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    registrado_por: Mapped[str] = mapped_column(String(20), default="manual")

    barco: Mapped["Barco"] = relationship(back_populates="registros_paso")


class PosicionGPS(Base):
    __tablename__ = "posiciones_gps"

    id: Mapped[int] = mapped_column(primary_key=True)
    barco_id: Mapped[int] = mapped_column(ForeignKey("barcos.id", ondelete="CASCADE"))
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    cog: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed_kn: Mapped[float | None] = mapped_column(Float, nullable=True)

    barco: Mapped["Barco"] = relationship(back_populates="posiciones")
