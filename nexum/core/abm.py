"""Motor genérico de ABM. Una tabla maestra se define con DefinicionABM y una lista de
Campo; el listado, el alta, la edición y la baja (con permisos y auditoría) salen solos."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from nexum.core.errores import NexumError, PermisoError  # noqa: F401
from nexum.db import models as m


class AbmError(NexumError):
    pass


@dataclass
class Campo:
    nombre: str
    etiqueta: str
    tipo: str = "texto"            # texto, entero, decimal, bool, fecha, opcion, fk
    requerido: bool = False
    largo: int | None = None
    opciones: list[tuple] | None = None   # para tipo "opcion": [(valor, etiqueta), ...]
    fk: tuple | None = None               # para tipo "fk": (Modelo, "atributo_a_mostrar")
    en_lista: bool = True
    por_defecto: object = None
    validador: object = None       # función(valor) -> mensaje de error o None


@dataclass
class DefinicionABM:
    modelo: type
    titulo: str
    codigo_menu: str
    campos: list[Campo]
    orden_por: str = "nombre"
    unicos: tuple = ()             # campos que no pueden repetirse


# ---------- utilidades ----------
def _exigir(sesion, d: DefinicionABM, accion: str):
    if not sesion.puede(d.codigo_menu, accion):
        raise PermisoError(f"No tenés permiso para {accion} en «{d.titulo}»")


def _limpiar(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def _ser(v):
    if isinstance(v, date):
        return v.isoformat()
    return float(v) if isinstance(v, Decimal) else v


def opciones_fk(db, campo: Campo) -> list[tuple]:
    modelo, attr = campo.fk
    return [(f.id, getattr(f, attr)) for f in db.scalars(select(modelo).order_by(getattr(modelo, attr)))]


def texto_celda(db, campo: Campo, obj) -> str:
    v = getattr(obj, campo.nombre)
    if v is None:
        return ""
    if campo.tipo == "fk":
        modelo, attr = campo.fk
        rel = db.get(modelo, v)
        return str(getattr(rel, attr)) if rel else ""
    if campo.tipo == "opcion":
        return str(dict(campo.opciones or []).get(v, v))
    if campo.tipo == "bool":
        return "Sí" if v else "No"
    if campo.tipo == "fecha":
        return v.strftime("%d/%m/%Y")
    return str(v)


def validar(d: DefinicionABM, datos: dict) -> dict:
    errores = {}
    for c in d.campos:
        v = datos.get(c.nombre)
        if c.requerido and c.tipo != "bool" and v is None:
            errores[c.nombre] = f"«{c.etiqueta}» es obligatorio"
        elif c.tipo == "texto" and c.largo and isinstance(v, str) and len(v) > c.largo:
            errores[c.nombre] = f"«{c.etiqueta}» admite hasta {c.largo} caracteres"
        elif c.validador and v is not None and (msg := c.validador(v)):
            errores[c.nombre] = msg
    return errores


# ---------- operaciones ----------
def listar(db, d: DefinicionABM, texto: str = "", inactivos: bool = False) -> list:
    q = select(d.modelo)
    if hasattr(d.modelo, "activo") and not inactivos:
        q = q.where(d.modelo.activo.is_(True))
    if texto:
        cols = [getattr(d.modelo, c.nombre) for c in d.campos if c.tipo == "texto"]
        if cols:
            q = q.where(or_(*[col.ilike(f"%{texto}%") for col in cols]))
    return list(db.scalars(q.order_by(getattr(d.modelo, d.orden_por))))


def guardar(db, sesion, d: DefinicionABM, datos: dict, id: int | None = None):
    _exigir(sesion, d, "modificar" if id else "crear")
    datos = {c.nombre: _limpiar(datos.get(c.nombre, c.por_defecto)) for c in d.campos}
    for c in d.campos:
        if c.tipo == "decimal" and datos[c.nombre] is not None:
            datos[c.nombre] = Decimal(str(round(datos[c.nombre], 4)))
    errores = validar(d, datos)
    if errores:
        raise AbmError("; ".join(errores.values()))
    for u in d.unicos:
        q = select(d.modelo).where(getattr(d.modelo, u) == datos[u])
        if id:
            q = q.where(d.modelo.id != id)
        if db.scalar(q.limit(1)):
            etiqueta = next(c.etiqueta for c in d.campos if c.nombre == u)
            raise AbmError(f"Ya existe un registro con {etiqueta} «{datos[u]}»")
    if id:
        obj = db.get(d.modelo, id)
        if obj is None:
            raise AbmError("El registro ya no existe")
        antes = {k: _ser(getattr(obj, k)) for k in datos}
        for k, v in datos.items():
            setattr(obj, k, v)
        detalle = {"id": id, "antes": antes, "despues": {k: _ser(v) for k, v in datos.items()}}
        accion = "modificar"
    else:
        obj = d.modelo(**datos)
        db.add(obj)
        db.flush()
        detalle = {"id": obj.id, "datos": {k: _ser(v) for k, v in datos.items()}}
        accion = "crear"
    db.add(m.Auditoria(usuario_id=sesion.usuario_id, accion=accion,
                       entidad=d.modelo.__tablename__, detalle=json.dumps(detalle, ensure_ascii=False)))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AbmError("No se pudo guardar: el código ya existe (puede estar dado de baja)")
    return obj


def eliminar(db, sesion, d: DefinicionABM, id: int):
    """Si la tabla tiene 'activo' hace baja lógica; si no, borra el registro."""
    _exigir(sesion, d, "anular")
    obj = db.get(d.modelo, id)
    if obj is None:
        raise AbmError("El registro ya no existe")
    if hasattr(obj, "activo"):
        obj.activo = False
        accion = "baja"
    else:
        db.delete(obj)
        accion = "eliminar"
    db.add(m.Auditoria(usuario_id=sesion.usuario_id, accion=accion, entidad=d.modelo.__tablename__,
                       detalle=json.dumps({"id": id})))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AbmError("No se puede eliminar: el registro está en uso")
