"""Tablas maestras simples (códigos y descripciones)."""
from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from nexum.db.base import Base


class _Simple:
    """Estructura común: código único, nombre y baja lógica."""
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(10), unique=True)
    nombre: Mapped[str] = mapped_column(String(80))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Familia(_Simple, Base):
    __tablename__ = "familia"


class Rubro(_Simple, Base):
    __tablename__ = "rubro"


class Clase(_Simple, Base):
    __tablename__ = "clase"


class Marca(_Simple, Base):
    __tablename__ = "marca"


class Zona(_Simple, Base):
    __tablename__ = "zona"


class Provincia(_Simple, Base):
    __tablename__ = "provincia"


class Localidad(Base):
    __tablename__ = "localidad"
    id: Mapped[int] = mapped_column(primary_key=True)
    provincia_id: Mapped[int] = mapped_column(ForeignKey("provincia.id"))
    nombre: Mapped[str] = mapped_column(String(80))
    codigo_postal: Mapped[str | None] = mapped_column(String(8))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class CondicionPago(_Simple, Base):
    __tablename__ = "condicion_pago"
    dias: Mapped[int] = mapped_column(Integer, default=0)
