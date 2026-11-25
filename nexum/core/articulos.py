"""Alta y modificación de artículos con cálculo de precios, códigos de barras e historial."""
import json
from datetime import date

from sqlalchemy import select

from nexum.core import params, precios
from nexum.core.errores import NexumError, exigir
from nexum.db import comercial as c, models as m

CODIGO_MENU = "stock.archivos.articulos"
D, dec = precios.D, precios.dec

_TEXTO = ["codigo", "nombre", "descripcion", "perfil", "codigo_proveedor", "codigo_reemplazo", "ubicacion",
          "unidad", "moneda", "observaciones"]
_ENTEROS_FK = ["rubro_id", "familia_id", "clase_id", "marca_id", "proveedor_id"]
_DECIMALES = ["kilos", "alicuota_iva", "desc_max", "recargo_pct", "costo_lista", "desc_costo_pct", "flete",
              "coeficiente", "oferta_precio"]
_OTROS = ["etiqueta", "redondeo", "oferta_desde", "oferta_hasta", "activo"]


def _vacio(v):
    return v is None or (isinstance(v, str) and not v.strip())


def guardar(db, sesion, datos: dict, id: int | None = None, motivo: str | None = None) -> c.Articulo:
    """datos puede incluir 'barras' (lista) y 'fijar_publico' (True si el usuario tipeó el precio
    público: entonces el coeficiente se deduce de ese precio)."""
    exigir(sesion, CODIGO_MENU, "modificar" if id else "crear")
    codigo = (datos.get("codigo") or "").strip()
    nombre = (datos.get("nombre") or "").strip()
    if not codigo:
        raise NexumError("El código es obligatorio")
    if not nombre:
        raise NexumError("El nombre es obligatorio")
    q = select(c.Articulo).where(c.Articulo.codigo == codigo)
    if id:
        q = q.where(c.Articulo.id != id)
    if db.scalar(q.limit(1)):
        raise NexumError(f"Ya existe un artículo con el código «{codigo}»")

    barras = list(dict.fromkeys(b.strip() for b in datos.get("barras", []) if b and b.strip()))
    for b in barras:
        otro = db.scalar(select(c.ArticuloBarras).where(c.ArticuloBarras.barras == b))
        if otro and otro.articulo_id != id:
            raise NexumError(f"El código de barras «{b}» ya pertenece a otro artículo")

    art = db.get(c.Articulo, id) if id else c.Articulo()
    if id and art is None:
        raise NexumError("El artículo ya no existe")
    nuevo = id is None
    antes = (dec(art.costo_lista), dec(art.coeficiente), dec(art.precio_publico)) if not nuevo else None

    for k in _TEXTO:
        if k in datos:
            setattr(art, k, None if _vacio(datos[k]) else str(datos[k]).strip())
    art.codigo, art.nombre = codigo, nombre
    art.perfil = art.perfil or "CV"
    art.unidad = art.unidad or "UN"
    art.moneda = art.moneda or "ARS"
    for k in _ENTEROS_FK:
        if k in datos:
            setattr(art, k, datos[k] or None)
    for k in _DECIMALES:
        if k in datos:
            v = datos[k]
            setattr(art, k, None if _vacio(v) else D(str(v)))
    for k in _OTROS:
        if k in datos:
            setattr(art, k, datos[k])
    for k in ("alicuota_iva", "recargo_pct", "costo_lista", "desc_costo_pct", "flete"):
        if getattr(art, k) is None:
            setattr(art, k, D(21) if k == "alicuota_iva" else D(0))
    if art.coeficiente is None or dec(art.coeficiente) <= 0:
        art.coeficiente = D(1)
    if art.redondeo is None:
        art.redondeo = True
    if art.activo is None:
        art.activo = True

    paso = D(params.obtener(db, "redondeo_paso", "1"))
    costo, publico = precios.calcular(art.costo_lista, art.desc_costo_pct, art.flete, art.coeficiente,
                                      art.alicuota_iva, art.redondeo, paso)
    if datos.get("fijar_publico") and not _vacio(datos.get("precio_publico")):
        publico = precios.q2(datos["precio_publico"])
        art.coeficiente = precios.coeficiente_para(costo, publico, art.alicuota_iva)
    hoy = date.today()
    if nuevo or dec(art.costo) != costo:
        art.fecha_costo = hoy
    if nuevo or dec(art.precio_publico) != publico:
        art.fecha_precio = hoy
    art.costo, art.precio_publico = costo, publico

    # códigos de barras: se conservan los existentes, se quitan los que sobran y se agregan los nuevos
    existentes = {b.barras: b for b in art.barras}
    for b, obj in existentes.items():
        if b not in barras:
            art.barras.remove(obj)
    for b in barras:
        if b not in existentes:
            art.barras.append(c.ArticuloBarras(barras=b))

    db.add(art)
    db.flush()
    if nuevo or antes != (dec(art.costo_lista), dec(art.coeficiente), dec(art.precio_publico)):
        registrar_historial(db, sesion, art, motivo or ("Alta" if nuevo else "Edición"))
    db.add(m.Auditoria(usuario_id=sesion.usuario_id, accion="crear" if nuevo else "modificar", entidad="articulo",
                       detalle=json.dumps({"id": art.id, "codigo": art.codigo}, ensure_ascii=False)))
    db.commit()
    return art


def registrar_historial(db, sesion, art, motivo):
    db.add(c.ArticuloPrecioHist(articulo_id=art.id, usuario_id=sesion.usuario_id, costo_lista=art.costo_lista,
                                costo=art.costo, coeficiente=art.coeficiente, precio_publico=art.precio_publico,
                                motivo=motivo))


def dar_de_baja(db, sesion, id: int):
    exigir(sesion, CODIGO_MENU, "anular")
    art = db.get(c.Articulo, id)
    if art is None:
        raise NexumError("El artículo ya no existe")
    art.activo = False
    db.add(m.Auditoria(usuario_id=sesion.usuario_id, accion="baja", entidad="articulo",
                       detalle=json.dumps({"id": id, "codigo": art.codigo})))
    db.commit()
