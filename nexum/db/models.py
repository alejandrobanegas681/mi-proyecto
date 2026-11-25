"""Modelos base: empresa, sucursal, usuarios, permisos, módulos, parámetros y auditoría.
Multiempresa y multisucursal desde el día uno."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nexum.db.base import Base


class Empresa(Base):
    __tablename__ = "empresa"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    cuit: Mapped[str | None] = mapped_column(String(13))
    condicion_iva: Mapped[str] = mapped_column(String(2), default="RI")
    domicilio: Mapped[str | None] = mapped_column(String(160))
    telefono: Mapped[str | None] = mapped_column(String(40))


class Sucursal(Base):
    __tablename__ = "sucursal"
    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"))
    codigo: Mapped[str] = mapped_column(String(10))
    nombre: Mapped[str] = mapped_column(String(80))


class Rol(Base):
    __tablename__ = "rol"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60), unique=True)
    es_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    permisos: Mapped[list["Permiso"]] = relationship(back_populates="rol", cascade="all, delete-orphan")


class Permiso(Base):
    """Permiso por opción de menú (codigo_menu) y por acción. Un permiso sobre un
    nodo padre (ej. 'ventas') aplica a todos sus hijos."""
    __tablename__ = "permiso"
    id: Mapped[int] = mapped_column(primary_key=True)
    rol_id: Mapped[int] = mapped_column(ForeignKey("rol.id"))
    codigo_menu: Mapped[str] = mapped_column(String(200))
    ver: Mapped[bool] = mapped_column(Boolean, default=True)
    crear: Mapped[bool] = mapped_column(Boolean, default=False)
    modificar: Mapped[bool] = mapped_column(Boolean, default=False)
    anular: Mapped[bool] = mapped_column(Boolean, default=False)
    imprimir: Mapped[bool] = mapped_column(Boolean, default=False)
    rol: Mapped[Rol] = relationship(back_populates="permisos")


class Usuario(Base):
    __tablename__ = "usuario"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    clave_hash: Mapped[str] = mapped_column(String(200))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    rol_id: Mapped[int] = mapped_column(ForeignKey("rol.id"))
    sucursal_id: Mapped[int | None] = mapped_column(ForeignKey("sucursal.id"))
    rol: Mapped[Rol] = relationship()


class ModuloActivo(Base):
    """Permite activar/desactivar módulos completos (paquetes por cliente)."""
    __tablename__ = "modulo_activo"
    codigo: Mapped[str] = mapped_column(String(60), primary_key=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Parametro(Base):
    __tablename__ = "parametro"
    clave: Mapped[str] = mapped_column(String(80), primary_key=True)
    valor: Mapped[str | None] = mapped_column(Text)


class Auditoria(Base):
    """Quién hizo qué y cuándo (anulaciones, ajustes de stock, cambios de precios...)."""
    __tablename__ = "auditoria"
    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    accion: Mapped[str] = mapped_column(String(40))
    entidad: Mapped[str] = mapped_column(String(80))
    detalle: Mapped[str | None] = mapped_column(Text)
