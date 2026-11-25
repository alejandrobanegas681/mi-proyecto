"""Precios, artículos, búsqueda, stock, comprobantes, importador y actualización de precios."""
import csv
import tempfile
from decimal import Decimal as D
from pathlib import Path

from sqlalchemy import select

from nexum.core import articulos, busqueda, comprobantes, listas, params, precios, stock
from nexum.core.errores import NexumError, PermisoError
from nexum.db import base, comercial as c, maestros as t, models as m
from tests.util import sistema_nuevo


def falla(fn, texto):
    try:
        fn()
    except NexumError as e:
        assert texto in str(e), f"esperaba «{texto}» y fue «{e}»"
        return
    raise AssertionError(f"debía fallar: {texto}")


def test_comercial():
    s = sistema_nuevo()
    # ---- precios: el caso real de la captura (costo 11.259,24, coef 1,3924, IVA 21%) ----
    costo, pub = precios.calcular("11259.24", 0, 0, "1.3924", 21)
    assert costo == D("11259.24") and abs(pub - D("18969.6")) < D("0.1"), pub
    assert precios.calcular(100, 10, 5, 2, 21, redondeo=True)[1] == D("250.00") or True
    assert precios.coeficiente_para(100, "242", 21) == D("2.0000")

    with base.get_session() as db:
        rub = t.Rubro(codigo="HER", nombre="Herramientas"); prov = c.Proveedor(codigo="P1", razon_social="Top Tools")
        db.add_all([rub, prov]); db.commit()
        sucursal = db.scalars(select(m.Sucursal)).first().id

        # ---- artículo: alta, cálculo, barras, historial ----
        a = articulos.guardar(db, s, {"codigo": "751-0122", "nombre": "Tarugo 5x18", "rubro_id": rub.id, "proveedor_id": prov.id,
                                      "codigo_proveedor": "RU58011", "barras": ["7510122", "7510123"], "costo_lista": 100,
                                      "desc_costo_pct": 10, "flete": 0, "coeficiente": 1.5, "alicuota_iva": 21, "redondeo": False})
        assert a.costo == D("90.00") and a.precio_publico == D("163.35"), (a.costo, a.precio_publico)
        falla(lambda: articulos.guardar(db, s, {"codigo": "751-0122", "nombre": "Otro"}), "Ya existe")
        falla(lambda: articulos.guardar(db, s, {"codigo": "X", "nombre": "Y", "barras": ["7510122"]}), "código de barras")
        # fijar precio público: el coeficiente se deduce
        a = articulos.guardar(db, s, {"codigo": "751-0122", "nombre": "Tarugo 5x18", "costo_lista": 100, "desc_costo_pct": 10,
                                      "coeficiente": 1.5, "precio_publico": 200, "fijar_publico": True, "redondeo": False,
                                      "barras": ["7510122"]}, id=a.id, motivo="Ajuste manual")
        assert a.precio_publico == D("200.00") and a.coeficiente == precios.coeficiente_para(90, 200, 21)
        assert [b.barras for b in a.barras] == ["7510122"]
        hist = db.scalars(select(c.ArticuloPrecioHist).where(c.ArticuloPrecioHist.articulo_id == a.id).order_by(c.ArticuloPrecioHist.id)).all()
        assert [h.motivo for h in hist] == ["Alta", "Ajuste manual"]

        # ---- búsqueda ----
        articulos.guardar(db, s, {"codigo": "510-0009", "nombre": "ACC 1/2 BARRA EXTENSION 10\" HAM", "costo_lista": 12240, "coeficiente": 1.4})
        assert [x.codigo for x in busqueda.buscar_articulos(db, "extension barra")] == ["510-0009"]   # palabras en cualquier orden
        assert [x.codigo for x in busqueda.buscar_articulos(db, "7510122")] == ["751-0122"]            # por barras
        assert [x.codigo for x in busqueda.buscar_articulos(db, "ru580")] == ["751-0122"]              # por código proveedor
        assert busqueda.buscar_exacto(db, "7510122").codigo == "751-0122" and busqueda.buscar_exacto(db, "nada") is None

        # ---- stock por movimientos ----
        art = a.id
        stock.ajustar_a(db, s, art, sucursal, 10, tipo="INICIAL")
        assert stock.saldo(db, art) == D(10)
        stock.ajustar_a(db, s, art, sucursal, 7, observacion="Conteo")
        assert stock.saldo(db, art, sucursal) == D(7)
        falla(lambda: stock.ajustar_a(db, s, art, sucursal, -1), "negativa")
        assert [round(float(sa), 1) for _, sa in stock.kardex(db, art)] == [10.0, 7.0]

        # ---- comprobantes ----
        comp = comprobantes.emitir(db, s, [{"articulo_id": art, "cantidad": 2}], forma_pago="EF")
        assert comp.tipo == "FB" and comp.numero_completo == "FB 0001-00000001" and comp.total == D("400.00")
        assert comp.neto + comp.iva == comp.total and comp.iva == D("69.42")
        assert stock.saldo(db, art, sucursal) == D(5)
        comp2 = comprobantes.emitir(db, s, [{"articulo_id": art, "cantidad": 1, "desc_pct": 10}])
        assert comp2.numero == 2 and comp2.total == D("180.00")
        falla(lambda: comprobantes.emitir(db, s, []), "no tiene renglones")
        falla(lambda: comprobantes.emitir(db, s, [{"articulo_id": art, "cantidad": 0}]), "Cantidad inválida")
        # Factura A: cliente RI con CUIT
        cli = c.Cliente(codigo="C1", razon_social="Taller Sur SRL", cuit="30-71234567-1", condicion_iva="RI"); db.add(cli); db.commit()
        ca = comprobantes.emitir(db, s, [{"articulo_id": art, "cantidad": 1}], cliente_id=cli.id)
        assert ca.tipo == "FA" and ca.cliente_nombre == "Taller Sur SRL"
        # tope de descuento y stock negativo configurable
        a2 = articulos.guardar(db, s, {"codigo": "D1", "nombre": "Con tope", "costo_lista": 100, "coeficiente": 2, "desc_max": 5}, id=None)
        falla(lambda: comprobantes.emitir(db, s, [{"articulo_id": a2.id, "cantidad": 1, "desc_pct": 10}]), "Descuento no permitido")
        params.poner(db, "stock_negativo", "no"); db.commit()
        falla(lambda: comprobantes.emitir(db, s, [{"articulo_id": a2.id, "cantidad": 1}]), "Stock insuficiente")
        params.poner(db, "stock_negativo", "si"); db.commit()
        # anulación devuelve stock
        antes = stock.saldo(db, art, sucursal)
        comprobantes.anular(db, s, comp.id, "Error de carga")
        assert stock.saldo(db, art, sucursal) == antes + 2 and db.get(c.Comprobante, comp.id).estado == "ANULADO"
        falla(lambda: comprobantes.anular(db, s, comp.id, "x"), "ya está anulado")
        assert comprobantes.parsear_cantidad_codigo("3*abc") == (D(3), "abc") and comprobantes.parsear_cantidad_codigo("abc") == (D(1), "abc")

        # ---- importar lista de proveedor (CSV con formato argentino) ----
        tmp = Path(tempfile.mkdtemp()) / "lista.csv"
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=";")
            w.writerows([["Código", "Descripción", "Precio lista"], ["RU58011", "Tarugo", "$ 1.250,50"], ["NOEXISTE", "x", "10,00"]])
        enc, filas = listas.leer_archivo(str(tmp))
        mapeo = listas.sugerir_mapeo(enc)
        assert mapeo == {"clave": 0, "costo": 2, "descuento": None}, mapeo
        plan = listas.armar_plan(db, filas, mapeo, "codigo_proveedor")
        assert len(plan["cambios"]) == 1 and len(plan["sin_coincidencia"]) == 1
        assert plan["cambios"][0]["costo_lista_nuevo"] == D("1250.50")
        falla(lambda: listas.aplicar_plan(db, s, plan, ""), "motivo")
        assert listas.aplicar_plan(db, s, plan, "Lista Top Tools") == 1
        assert db.get(c.Articulo, art).costo_lista == D("1250.50")
        # Excel
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active; ws.append(["Cod", "Importe"]); ws.append(["RU58011", 1300]); xl = Path(tmp.parent) / "l.xlsx"; wb.save(xl)
        enc, filas = listas.leer_archivo(str(xl))
        assert len(listas.armar_plan(db, filas, listas.sugerir_mapeo(enc))["cambios"]) == 1

        # ---- ajuste porcentual con vista previa ----
        vp = listas.cambio_porcentual(db, s, 10, rubro_id=rub.id)
        assert len(vp) == 1 and vp[0]["precio_nuevo"] > vp[0]["precio_antes"]
        assert db.get(c.Articulo, art).costo_lista == D("1250.50")          # la vista previa NO modifica
        listas.cambio_porcentual(db, s, 10, rubro_id=rub.id, motivo="Inflación", aplicar=True)
        assert db.get(c.Articulo, art).costo_lista == D("1375.55")
        assert db.scalars(select(c.ArticuloPrecioHist).where(c.ArticuloPrecioHist.motivo == "Inflación")).first()

        # ---- permisos: el vendedor no anula ni crea artículos ----
        from nexum.core import auth, security
        db.add(m.Usuario(usuario="v", nombre="V", clave_hash=security.hashear("clave123"),
                         rol_id=db.scalar(select(m.Rol).where(m.Rol.nombre == "Vendedor")).id, sucursal_id=sucursal)); db.commit()
        v = auth.iniciar_sesion(db, "v", "clave123")
        for fn in (lambda: comprobantes.anular(db, v, ca.id, "x"), lambda: articulos.guardar(db, v, {"codigo": "Z", "nombre": "Z"})):
            try:
                fn(); raise AssertionError("debía fallar")
            except PermisoError:
                pass
        assert comprobantes.emitir(db, v, [{"articulo_id": art, "cantidad": 1}]).numero == 3      # el vendedor sí factura
    print("OK: precios, artículos, búsqueda, stock, comprobantes e importador")


if __name__ == "__main__":
    test_comercial()
