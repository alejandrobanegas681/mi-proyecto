"""Artículos, precios, stock, clientes, proveedores y comprobantes."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nexum.db.base import Base


def _num(p=14, s=2, default=0):
    return mapped_column(Numeric(p, s), default=Decimal(str(default)))


class Proveedor(Base):
    __tablename__ = "proveedor"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(10), unique=True)
    razon_social: Mapped[str] = mapped_column(String(120), index=True)
    cuit: Mapped[str | None] = mapped_column(String(13))
    condicion_iva: Mapped[str] = mapped_column(String(2), default="RI")
    telefono: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(120))
    domicilio: Mapped[str | None] = mapped_column(String(160))
    localidad_id: Mapped[int | None] = mapped_column(ForeignKey("localidad.id"))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Cliente(Base):
    __tablename__ = "cliente"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(10), unique=True)
    razon_social: Mapped[str] = mapped_column(String(120), index=True)
    cuit: Mapped[str | None] = mapped_column(String(13))
    condicion_iva: Mapped[str] = mapped_column(String(2), default="CF")
    telefono: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(120))
    domicilio: Mapped[str | None] = mapped_column(String(160))
    localidad_id: Mapped[int | None] = mapped_column(ForeignKey("localidad.id"))
    descuento_pct: Mapped[Decimal] = _num(5, 2)
    limite_credito: Mapped[Decimal] = _num(14, 2)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Articulo(Base):
    __tablename__ = "articulo"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(80), index=True)
    descripcion: Mapped[str | None] = mapped_column(Text)
    rubro_id: Mapped[int | None] = mapped_column(ForeignKey("rubro.id"))
    familia_id: Mapped[int | None] = mapped_column(ForeignKey("familia.id"))
    clase_id: Mapped[int | None] = mapped_column(ForeignKey("clase.id"))
    marca_id: Mapped[int | None] = mapped_column(ForeignKey("marca.id"))
    perfil: Mapped[str] = mapped_column(String(2), default="CV")  # CV compra/venta, C solo compra, V solo venta
    proveedor_id: Mapped[int | None] = mapped_column(ForeignKey("proveedor.id"))
    codigo_proveedor: Mapped[str | None] = mapped_column(String(40), index=True)
    codigo_reemplazo: Mapped[str | None] = mapped_column(String(20))
    ubicacion: Mapped[str | None] = mapped_column(String(30))
    unidad: Mapped[str] = mapped_column(String(10), default="UN")
    kilos: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    alicuota_iva: Mapped[Decimal] = _num(5, 2, 21)
    desc_max: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))      # vacío = sin tope
    recargo_pct: Mapped[Decimal] = _num(5, 2)
    etiqueta: Mapped[bool] = mapped_column(Boolean, default=False)
    moneda: Mapped[str] = mapped_column(String(3), default="ARS")
    # --- cadena de precio ---
    costo_lista: Mapped[Decimal] = _num()
    desc_costo_pct: Mapped[Decimal] = _num(5, 2)
    flete: Mapped[Decimal] = _num()
    costo: Mapped[Decimal] = _num()
    coeficiente: Mapped[Decimal] = _num(10, 4, 1)
    precio_publico: Mapped[Decimal] = _num()
    redondeo: Mapped[bool] = mapped_column(Boolean, default=True)
    fecha_costo: Mapped[date | None] = mapped_column(Date)
    fecha_precio: Mapped[date | None] = mapped_column(Date)
    oferta_precio: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    oferta_desde: Mapped[date | None] = mapped_column(Date)
    oferta_hasta: Mapped[date | None] = mapped_column(Date)
    observaciones: Mapped[str | None] = mapped_column(Text)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    barras: Mapped[list["ArticuloBarras"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class ArticuloBarras(Base):
    __tablename__ = "articulo_barras"
    id: Mapped[int] = mapped_column(primary_key=True)
    articulo_id: Mapped[int] = mapped_column(ForeignKey("articulo.id"), index=True)
    barras: Mapped[str] = mapped_column(String(40), unique=True, index=True)


class ArticuloPrecioHist(Base):
    """Cada cambio de costo o precio queda registrado: quién, cuándo y por qué."""
    __tablename__ = "articulo_precio_hist"
    id: Mapped[int] = mapped_column(primary_key=True)
    articulo_id: Mapped[int] = mapped_column(ForeignKey("articulo.id"), index=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    costo_lista: Mapped[Decimal] = _num()
    costo: Mapped[Decimal] = _num()
    coeficiente: Mapped[Decimal] = _num(10, 4, 1)
    precio_publico: Mapped[Decimal] = _num()
    motivo: Mapped[str | None] = mapped_column(String(120))


class StockMovimiento(Base):
    """El stock NO es un campo: es la suma de estos movimientos por artículo y sucursal."""
    __tablename__ = "stock_movimiento"
    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    sucursal_id: Mapped[int] = mapped_column(ForeignKey("sucursal.id"), index=True)
    articulo_id: Mapped[int] = mapped_column(ForeignKey("articulo.id"), index=True)
    cantidad: Mapped[Decimal] = _num(14, 3)   # con signo
    tipo: Mapped[str] = mapped_column(String(12))  # INICIAL, AJUSTE, VENTA, ANULACION, COMPRA, TRANSF
    referencia: Mapped[str | None] = mapped_column(String(40))
    observacion: Mapped[str | None] = mapped_column(String(160))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))


class Talonario(Base):
    __tablename__ = "talonario"
    __table_args__ = (UniqueConstraint("sucursal_id", "punto_venta", "tipo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    sucursal_id: Mapped[int] = mapped_column(ForeignKey("sucursal.id"))
    punto_venta: Mapped[int] = mapped_column(Integer, default=1)
    tipo: Mapped[str] = mapped_column(String(3))
    ultimo_numero: Mapped[int] = mapped_column(Integer, default=0)


class Comprobante(Base):
    __tablename__ = "comprobante"
    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    sucursal_id: Mapped[int] = mapped_column(ForeignKey("sucursal.id"))
    tipo: Mapped[str] = mapped_column(String(3))
    punto_venta: Mapped[int] = mapped_column(Integer)
    numero: Mapped[int] = mapped_column(Integer)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("cliente.id"))
    cliente_nombre: Mapped[str] = mapped_column(String(120), default="Consumidor Final")
    cliente_cuit: Mapped[str | None] = mapped_column(String(13))
    neto: Mapped[Decimal] = _num()
    iva: Mapped[Decimal] = _num()
    total: Mapped[Decimal] = _num()
    forma_pago: Mapped[str] = mapped_column(String(2), default="EF")
    estado: Mapped[str] = mapped_column(String(8), default="EMITIDO")
    cae: Mapped[str | None] = mapped_column(String(20))
    cae_vto: Mapped[date | None] = mapped_column(Date)
    observaciones: Mapped[str | None] = mapped_column(String(200))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    items: Mapped[list["ComprobanteItem"]] = relationship(cascade="all, delete-orphan", lazy="selectin")

    @property
    def numero_completo(self) -> str:
        return f"{self.tipo} {self.punto_venta:04d}-{self.numero:08d}"


class ComprobanteItem(Base):
    __tablename__ = "comprobante_item"
    id: Mapped[int] = mapped_column(primary_key=True)
    comprobante_id: Mapped[int] = mapped_column(ForeignKey("comprobante.id"), index=True)
    articulo_id: Mapped[int] = mapped_column(ForeignKey("articulo.id"))
    codigo: Mapped[str] = mapped_column(String(20))
    descripcion: Mapped[str] = mapped_column(String(80))
    cantidad: Mapped[Decimal] = _num(14, 3)
    precio_unit: Mapped[Decimal] = _num()      # con IVA incluido
    desc_pct: Mapped[Decimal] = _num(5, 2)
    alicuota_iva: Mapped[Decimal] = _num(5, 2, 21)
    neto: Mapped[Decimal] = _num()
    iva: Mapped[Decimal] = _num()
    total: Mapped[Decimal] = _num()
