"""Stock por movimientos: el saldo siempre se calcula, nunca se edita."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select

from nexum.core.errores import NexumError, exigir
from nexum.core.precios import D, dec
from nexum.db import comercial as c, models as m


def mover(db, sesion, articulo_id, sucursal_id, cantidad, tipo, referencia=None, observacion=None, commit=True):
    cantidad = D(str(cantidad))
    if cantidad == 0:
        raise NexumError("La cantidad no puede ser cero")
    mov = c.StockMovimiento(articulo_id=articulo_id, sucursal_id=sucursal_id, cantidad=cantidad, tipo=tipo,
                            referencia=referencia, observacion=observacion, usuario_id=sesion.usuario_id,
                            fecha=datetime.now())
    db.add(mov)
    if commit:
        db.commit()
    return mov


def saldo(db, articulo_id, sucursal_id=None) -> Decimal:
    q = select(func.coalesce(func.sum(c.StockMovimiento.cantidad), 0)).where(c.StockMovimiento.articulo_id == articulo_id)
    if sucursal_id:
        q = q.where(c.StockMovimiento.sucursal_id == sucursal_id)
    return dec(db.scalar(q))


def saldos_por_sucursal(db, articulo_ids: list[int]) -> dict:
    """{articulo_id: {sucursal_id: saldo}} para una lista de artículos (una sola consulta)."""
    out = {a: {} for a in articulo_ids}
    if not articulo_ids:
        return out
    q = (select(c.StockMovimiento.articulo_id, c.StockMovimiento.sucursal_id, func.sum(c.StockMovimiento.cantidad))
         .where(c.StockMovimiento.articulo_id.in_(articulo_ids))
         .group_by(c.StockMovimiento.articulo_id, c.StockMovimiento.sucursal_id))
    for a, s, tot in db.execute(q):
        out[a][s] = dec(tot)
    return out


def ajustar_a(db, sesion, articulo_id, sucursal_id, cantidad_real, tipo="AJUSTE", observacion=None):
    """Lleva el stock de una sucursal a la cantidad contada, registrando la diferencia."""
    exigir(sesion, "stock.movimientos.inicial" if tipo == "INICIAL" else "stock.inventario", "modificar")
    real = D(str(cantidad_real))
    if real < 0:
        raise NexumError("La cantidad contada no puede ser negativa")
    diferencia = real - saldo(db, articulo_id, sucursal_id)
    if diferencia == 0:
        return None
    mov = mover(db, sesion, articulo_id, sucursal_id, diferencia, tipo, observacion=observacion, commit=False)
    db.add(m.Auditoria(usuario_id=sesion.usuario_id, accion="stock_" + tipo.lower(), entidad="articulo",
                       detalle=f"art={articulo_id} suc={sucursal_id} dif={diferencia}"))
    db.commit()
    return mov


def kardex(db, articulo_id, sucursal_id=None) -> list[tuple]:
    """[(movimiento, saldo_acumulado)] en orden cronológico."""
    q = select(c.StockMovimiento).where(c.StockMovimiento.articulo_id == articulo_id)
    if sucursal_id:
        q = q.where(c.StockMovimiento.sucursal_id == sucursal_id)
    acum, out = D(0), []
    for mv in db.scalars(q.order_by(c.StockMovimiento.fecha, c.StockMovimiento.id)):
        acum += dec(mv.cantidad)
        out.append((mv, acum))
    return out
