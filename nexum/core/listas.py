"""Actualización de precios: importación de listas de proveedor (CSV/Excel) y ajuste porcentual.
Siempre hay vista previa antes de aplicar, y cada cambio queda en el historial del artículo."""
import csv
import json
import re
from pathlib import Path

from sqlalchemy import select

from nexum.core import params, precios
from nexum.core.articulos import registrar_historial
from nexum.core.errores import NexumError, exigir
from nexum.core.precios import D, dec
from nexum.db import comercial as c, models as m

COD_IMPORTAR = "ventas.movimientos.precios.actualizacion_de_precios"
COD_GLOBAL = "ventas.movimientos.precios.actualizacion_global"
CAMPOS_CLAVE = {"codigo_proveedor": "Código del proveedor", "codigo": "Código propio", "barras": "Código de barras"}


def numero(valor):
    """Interpreta '1.234,56', '1234.56', '$ 1.234,56' o números ya numéricos."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, (int, float)):
        return D(str(valor))
    s = re.sub(r"[^\d,.\-]", "", str(valor))
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return D(s)
    except Exception:
        return None


def leer_archivo(ruta: str, hoja: int = 0) -> tuple[list[str], list[list]]:
    """Devuelve (encabezados, filas) de un .csv, .xlsx o .xlsm."""
    p = Path(ruta)
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        wb = load_workbook(p, read_only=True, data_only=True)
        filas = [list(r) for r in wb.worksheets[hoja].iter_rows(values_only=True)]
    elif p.suffix.lower() in (".csv", ".txt"):
        texto = p.read_text(encoding="utf-8-sig", errors="replace")
        dialecto = csv.Sniffer().sniff(texto[:2000], delimiters=";,\t|") if texto.strip() else csv.excel
        filas = list(csv.reader(texto.splitlines(), dialecto))
    else:
        raise NexumError("Formato no soportado: usá .csv o .xlsx")
    filas = [f for f in filas if any(x not in (None, "") for x in f)]
    if not filas:
        raise NexumError("El archivo está vacío")
    return [str(x or "").strip() for x in filas[0]], filas[1:]


def sugerir_mapeo(encabezados: list[str]) -> dict:
    """Adivina qué columna es la clave, el costo y el descuento según el nombre del encabezado."""
    import unicodedata
    norm = [unicodedata.normalize("NFKD", h).encode("ascii", "ignore").decode().lower() for h in encabezados]
    usadas: set[int] = set()

    def buscar(*palabras):
        for i, h in enumerate(norm):
            if i not in usadas and any(p in h for p in palabras):
                usadas.add(i)
                return i
        return None
    clave = buscar("cod", "ref", "sku", "articulo")
    costo = buscar("precio", "costo", "lista", "importe")
    return {"clave": clave, "costo": costo, "descuento": buscar("descuento", "bonif", "dto")}


def armar_plan(db, filas, mapeo: dict, campo_clave="codigo_proveedor", proveedor_id=None) -> dict:
    """mapeo = {'clave': idx, 'costo': idx, 'descuento': idx|None}.
    Devuelve {'cambios': [...], 'sin_coincidencia': [...], 'sin_cambio': n}."""
    if campo_clave not in CAMPOS_CLAVE:
        raise NexumError("Campo clave inválido")
    cambios, sin, igual, vistos = [], [], 0, set()
    for n, fila in enumerate(filas, start=2):
        try:
            clave = str(fila[mapeo["clave"]] or "").strip()
            nuevo = numero(fila[mapeo["costo"]])
        except (IndexError, TypeError):
            continue
        if not clave or nuevo is None:
            continue
        q = select(c.Articulo).where(c.Articulo.activo.is_(True))
        if campo_clave == "barras":
            q = q.where(c.Articulo.id.in_(select(c.ArticuloBarras.articulo_id).where(c.ArticuloBarras.barras == clave)))
        else:
            q = q.where(getattr(c.Articulo, campo_clave) == clave)
        if proveedor_id:
            q = q.where(c.Articulo.proveedor_id == proveedor_id)
        art = db.scalars(q).first()
        if art is None:
            sin.append((n, clave))
            continue
        if art.id in vistos:
            continue
        vistos.add(art.id)
        desc = None
        if mapeo.get("descuento") is not None:
            desc = numero(fila[mapeo["descuento"]])
        desc = desc if desc is not None else dec(art.desc_costo_pct)
        costo_n, publico_n = precios.calcular(nuevo, desc, art.flete, art.coeficiente, art.alicuota_iva, art.redondeo,
                                              D(params.obtener(db, "redondeo_paso", "1")))
        if dec(art.costo_lista) == nuevo and dec(art.desc_costo_pct) == desc:
            igual += 1
            continue
        cambios.append({"articulo_id": art.id, "codigo": art.codigo, "nombre": art.nombre,
                        "costo_lista_antes": dec(art.costo_lista), "costo_lista_nuevo": nuevo, "desc_nuevo": desc,
                        "precio_antes": dec(art.precio_publico), "precio_nuevo": publico_n,
                        "variacion_pct": ((nuevo / dec(art.costo_lista) - 1) * 100).quantize(D("0.01"))
                        if dec(art.costo_lista) > 0 else None})
    return {"cambios": cambios, "sin_coincidencia": sin, "sin_cambio": igual}


def aplicar_plan(db, sesion, plan: dict, motivo: str):
    exigir(sesion, COD_IMPORTAR, "modificar")
    if not (motivo or "").strip():
        raise NexumError("Indicá un motivo (por ejemplo: «Lista proveedor X, noviembre»)")
    paso = D(params.obtener(db, "redondeo_paso", "1"))
    from datetime import date
    for ch in plan["cambios"]:
        art = db.get(c.Articulo, ch["articulo_id"])
        art.costo_lista, art.desc_costo_pct = ch["costo_lista_nuevo"], ch["desc_nuevo"]
        art.costo, art.precio_publico = precios.calcular(art.costo_lista, art.desc_costo_pct, art.flete,
                                                         art.coeficiente, art.alicuota_iva, art.redondeo, paso)
        art.fecha_costo = art.fecha_precio = date.today()
        registrar_historial(db, sesion, art, motivo.strip())
    db.add(m.Auditoria(usuario_id=sesion.usuario_id, accion="actualizar_precios", entidad="articulo",
                       detalle=json.dumps({"cantidad": len(plan["cambios"]), "motivo": motivo.strip()},
                                          ensure_ascii=False)))
    db.commit()
    return len(plan["cambios"])


def cambio_porcentual(db, sesion, porcentaje, sobre="costo_lista", rubro_id=None, marca_id=None, proveedor_id=None,
                      motivo="", aplicar=False) -> list[dict]:
    """Sube o baja un porcentaje el costo de lista (o el coeficiente) de los artículos filtrados."""
    exigir(sesion, COD_GLOBAL, "modificar")
    if sobre not in ("costo_lista", "coeficiente"):
        raise NexumError("Elegí si el cambio es sobre el costo de lista o el coeficiente")
    pct = D(str(porcentaje))
    if pct == 0:
        raise NexumError("El porcentaje no puede ser cero")
    if aplicar and not (motivo or "").strip():
        raise NexumError("Indicá el motivo del cambio")
    q = select(c.Articulo).where(c.Articulo.activo.is_(True))
    for col, val in ((c.Articulo.rubro_id, rubro_id), (c.Articulo.marca_id, marca_id), (c.Articulo.proveedor_id, proveedor_id)):
        if val:
            q = q.where(col == val)
    paso = D(params.obtener(db, "redondeo_paso", "1"))
    factor = 1 + pct / 100
    salida = []
    from datetime import date
    for art in db.scalars(q.order_by(c.Articulo.nombre)):
        cl = dec(art.costo_lista) * factor if sobre == "costo_lista" else dec(art.costo_lista)
        co = (dec(art.coeficiente) * factor).quantize(D("0.0001")) if sobre == "coeficiente" else dec(art.coeficiente)
        costo_n, publico_n = precios.calcular(cl, art.desc_costo_pct, art.flete, co, art.alicuota_iva, art.redondeo, paso)
        salida.append({"articulo_id": art.id, "codigo": art.codigo, "nombre": art.nombre,
                       "precio_antes": dec(art.precio_publico), "precio_nuevo": publico_n})
        if aplicar:
            art.costo_lista, art.coeficiente = precios.q2(cl), co
            art.costo, art.precio_publico = costo_n, publico_n
            art.fecha_costo = art.fecha_precio = date.today()
            registrar_historial(db, sesion, art, motivo.strip())
    if aplicar:
        db.add(m.Auditoria(usuario_id=sesion.usuario_id, accion="actualizar_precios", entidad="articulo",
                           detalle=json.dumps({"cantidad": len(salida), "pct": float(pct), "sobre": sobre,
                                               "motivo": motivo.strip()}, ensure_ascii=False)))
        db.commit()
    return salida
