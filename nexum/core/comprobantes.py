"""Emisión y anulación de comprobantes de mostrador, con numeración y descuento de stock."""
import json
import re
from datetime import datetime

from sqlalchemy import select

from nexum.core import params, precios, stock
from nexum.core.errores import NexumError, exigir
from nexum.core.precios import D, dec, q2
from nexum.db import comercial as c, models as m

COD_MOSTRADOR = "ventas.facturacion.facturacion_mostrador"
COD_ANULAR = "administracion.anular_comprobantes"
TIPOS = {"FA": "Factura A", "FB": "Factura B", "FC": "Factura C", "FX": "Comprobante X"}
FORMAS_PAGO = {"EF": "Efectivo", "TA": "Tarjeta", "TR": "Transferencia"}
CONDICIONES_IVA = [("RI", "Responsable Inscripto"), ("MT", "Monotributo"), ("EX", "Exento"),
                   ("CF", "Consumidor Final"), ("NR", "No Responsable")]


def tipo_para(condicion_emisor: str, condicion_cliente: str) -> str:
    if condicion_emisor == "RI":
        return "FA" if condicion_cliente == "RI" else "FB"
    return "FC"


def calcular_linea(cantidad, precio_unit, desc_pct, alicuota):
    total = q2(dec(cantidad) * dec(precio_unit) * (1 - dec(desc_pct) / 100))
    neto = q2(total / (1 + dec(alicuota) / 100))
    return neto, total - neto, total


def emitir(db, sesion, lineas: list[dict], cliente_id=None, forma_pago="EF", tipo=None, observaciones=None):
    """lineas: [{articulo_id, cantidad, precio_unit (opcional), desc_pct (opcional)}]"""
    exigir(sesion, COD_MOSTRADOR, "crear")
    if not lineas:
        raise NexumError("El comprobante no tiene renglones")
    if forma_pago not in FORMAS_PAGO:
        raise NexumError("Forma de pago inválida")
    emp = db.scalars(select(m.Empresa)).first()
    suc_id = sesion.sucursal_id or db.scalars(select(m.Sucursal)).first().id
    cliente = db.get(c.Cliente, cliente_id) if cliente_id else None
    tipo = tipo or tipo_para(emp.condicion_iva, cliente.condicion_iva if cliente else "CF")
    if tipo == "FA" and (cliente is None or not cliente.cuit):
        raise NexumError("La Factura A requiere un cliente con CUIT")
    tal = db.scalar(select(c.Talonario).where(c.Talonario.sucursal_id == suc_id, c.Talonario.tipo == tipo)
                    .order_by(c.Talonario.punto_venta).with_for_update())
    if tal is None:
        raise NexumError(f"No hay talonario configurado para {TIPOS.get(tipo, tipo)} en esta sucursal")

    permite_negativo = params.obtener(db, "stock_negativo", "si") == "si"
    pedido: dict[int, D] = {}
    items = []
    for l in lineas:
        art = db.get(c.Articulo, l["articulo_id"])
        if art is None or not art.activo:
            raise NexumError("Hay un artículo inexistente o dado de baja")
        if art.perfil == "C":
            raise NexumError(f"«{art.nombre}» es solo de compra y no se puede vender")
        cant = D(str(l["cantidad"]))
        if cant <= 0:
            raise NexumError(f"Cantidad inválida en «{art.nombre}»")
        precio = D(str(l["precio_unit"])) if l.get("precio_unit") is not None else precios.precio_vigente(art)
        desc = D(str(l.get("desc_pct") or 0))
        if desc < 0 or desc > 100 or (art.desc_max is not None and desc > dec(art.desc_max)):
            raise NexumError(f"Descuento no permitido en «{art.nombre}» (máximo {dec(art.desc_max) if art.desc_max is not None else 100}%)")
        pedido[art.id] = pedido.get(art.id, D(0)) + cant
        neto, iva, total = calcular_linea(cant, precio, desc, art.alicuota_iva)
        items.append(c.ComprobanteItem(articulo_id=art.id, codigo=art.codigo, descripcion=art.nombre, cantidad=cant,
                                       precio_unit=precio, desc_pct=desc, alicuota_iva=art.alicuota_iva,
                                       neto=neto, iva=iva, total=total))
    if not permite_negativo:
        for aid, cant in pedido.items():
            disponible = stock.saldo(db, aid, suc_id)
            if disponible < cant:
                nombre = db.get(c.Articulo, aid).nombre
                raise NexumError(f"Stock insuficiente de «{nombre}»: hay {disponible:g} y se piden {cant:g}")

    tal.ultimo_numero += 1
    comp = c.Comprobante(
        fecha=datetime.now(), sucursal_id=suc_id, tipo=tipo, punto_venta=tal.punto_venta, numero=tal.ultimo_numero,
        cliente_id=cliente.id if cliente else None,
        cliente_nombre=cliente.razon_social if cliente else "Consumidor Final", cliente_cuit=cliente.cuit if cliente else None,
        neto=sum(i.neto for i in items), iva=sum(i.iva for i in items), total=sum(i.total for i in items),
        forma_pago=forma_pago, observaciones=observaciones, usuario_id=sesion.usuario_id, items=items)
    db.add(comp)
    db.flush()
    for it in items:
        stock.mover(db, sesion, it.articulo_id, suc_id, -it.cantidad, "VENTA", referencia=comp.numero_completo, commit=False)
    db.add(m.Auditoria(usuario_id=sesion.usuario_id, accion="emitir", entidad="comprobante",
                       detalle=json.dumps({"id": comp.id, "numero": comp.numero_completo, "total": float(comp.total)})))
    db.commit()
    return comp


def anular(db, sesion, comprobante_id: int, motivo: str):
    exigir(sesion, COD_ANULAR, "anular")
    if not (motivo or "").strip():
        raise NexumError("Indicá el motivo de la anulación")
    comp = db.get(c.Comprobante, comprobante_id)
    if comp is None:
        raise NexumError("El comprobante no existe")
    if comp.estado == "ANULADO":
        raise NexumError("El comprobante ya está anulado")
    if comp.cae:
        raise NexumError("El comprobante tiene CAE: corresponde emitir una nota de crédito")
    for it in comp.items:
        stock.mover(db, sesion, it.articulo_id, comp.sucursal_id, it.cantidad, "ANULACION",
                    referencia=comp.numero_completo, observacion=motivo.strip(), commit=False)
    comp.estado = "ANULADO"
    db.add(m.Auditoria(usuario_id=sesion.usuario_id, accion="anular", entidad="comprobante",
                       detalle=json.dumps({"id": comp.id, "numero": comp.numero_completo, "motivo": motivo.strip()},
                                          ensure_ascii=False)))
    db.commit()
    return comp


def parsear_cantidad_codigo(texto: str) -> tuple[D, str]:
    """'3*TORNILLO' → (3, 'TORNILLO'); sin '*' → (1, texto)."""
    mt = re.match(r"^\s*(\d+(?:[.,]\d+)?)\s*\*\s*(.+?)\s*$", texto or "")
    if mt:
        return D(mt.group(1).replace(",", ".")), mt.group(2)
    return D(1), (texto or "").strip()
