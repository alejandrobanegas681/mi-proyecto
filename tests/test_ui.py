"""Interfaz sin pantalla (offscreen): asistente, ventana, paleta, artículos, mostrador, stock y precios."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from decimal import Decimal as D
from pathlib import Path
import csv, tempfile

from PySide6.QtWidgets import QApplication

from nexum.core import stock
from nexum.db import base, comercial as c
from sqlalchemy import select
from tests.util import sistema_nuevo


def test_ui():
    s = sistema_nuevo()
    app = QApplication.instance() or QApplication([])
    from nexum.ui import tema
    tema.aplicar(app, False); tema.aplicar(app, True)
    import nexum.ui.maestros_ui  # noqa
    from nexum.maestros.definiciones import DEFINICIONES
    from nexum.ui.main_window import MainWindow
    from nexum.ui.paleta import PaletaComandos
    from nexum.ui.registry import crear_pantalla
    from nexum.ui.setup_dialog import SetupDialog

    # asistente de primer uso
    d = SetupDialog(); d.empresa.setText("X"); assert d.windowTitle()

    # ventana principal, paleta y apertura de pantallas por código
    mw = MainWindow(s)
    assert mw.arbol.topLevelItemCount() == 6 and len(mw.hojas) > 150
    p = PaletaComandos(mw.hojas); p.entrada.setText("mostrador"); assert p.lista.count() >= 1
    mw.filtro.setText("articulos")
    for cod in ("ventas.facturacion.facturacion_mostrador", "stock.archivos.articulos", "stock.consultas_de_stock",
                "stock.consultas_por_articulo", "stock.movimientos.inicial", "stock.inventario", "administracion.usuarios",
                "ventas.movimientos.consulta_de_comprobantes", "ventas.movimientos.precios.actualizacion_global",
                "ventas.movimientos.precios.actualizacion_de_precios", "ventas.archivos.clientes", "stock.archivos.rubros"):
        assert mw.abrir(cod) is not None, cod
    assert mw.abrir("tesoreria.caja.caja_chica").windowTitle() == "Caja Chica"          # pantalla "en construcción"
    n = mw.tabs.count(); mw._cerrar(0); assert mw.tabs.count() == n - 1
    for d_ in DEFINICIONES:
        assert type(crear_pantalla(d_.codigo_menu, d_.titulo, s)).__name__ == "PantallaABM"

    # artículos: cargar la ficha por la interfaz, con el precio calculado en vivo
    from nexum.ui.articulos_ui import PantallaArticulos
    pa = PantallaArticulos(s)
    w = pa.w
    w["codigo"].setText("751-0122"); w["nombre"].setText("Tarugo 5x18"); w["barras"].setText("7510122, 7510123")
    w["costo_lista"].setValue(11259.24); w["coeficiente"].setValue(1.3924)
    assert abs(w["precio_publico"].value() - 18970) < 1 and pa.lbl_costo.text() == "11.259,24"   # redondeado al peso
    w["redondeo"].setChecked(False); assert abs(w["precio_publico"].value() - 18969.6) < 0.1
    w["precio_publico"].setValue(20000); w["precio_publico"].editingFinished.emit()               # tipeo el público: deduce coef
    assert w["coeficiente"].value() > 1.4 and pa._fijar
    assert pa._guardar(otro=True) and w["codigo"].text() == ""                                    # guardar y cargar otro
    with base.get_session() as db:
        a = db.scalar(select(c.Articulo))
        assert a.precio_publico == D("20000.00") and len(a.barras) == 2
    w["codigo"].setText("751-0122"); w["nombre"].setText("dup")
    assert not pa._guardar() and "Ya existe" in pa.estado.text()                                  # error visible, sin romper
    pa.buscador.entrada.setText("tarugo"); pa.buscador.refrescar(); assert pa.buscador.tabla.rowCount() == 1

    # stock inicial por la interfaz
    from nexum.ui.stock_ui import PantallaAjusteStock, PantallaConsultaStock, PantallaKardex
    aj = PantallaAjusteStock(s, "INICIAL"); aj.buscador.refrescar(); aj.buscador.tabla.selectRow(0)
    aj.real.setValue(25); aj._aplicar()
    with base.get_session() as db:
        assert stock.saldo(db, a.id) == D(25)
    cs = PantallaConsultaStock(s); assert cs.tabla.rowCount() == 1
    kx = PantallaKardex(s); kx.buscador.tabla.selectRow(0); assert kx.tabla.rowCount() == 1

    # mostrador: lector de barras, «2*código», cobro y numeración
    from nexum.ui.mostrador_ui import PantallaMostrador
    pm = PantallaMostrador(s)
    pm.entrada.setText("7510122"); pm._agregar_texto()
    pm.entrada.setText("2*751-0122"); pm._agregar_texto()
    assert len(pm.lineas) == 1 and pm.lineas[0]["cantidad"] == D(3) and pm.lbl_total.text() == "$ 60.000,00"
    pm.entrada.setText("zzzz"); pm._agregar_texto(); assert "No se encontró" in pm.estado.text()
    pm._cobrar()
    assert pm.ultimo[1] == "FB 0001-00000001" and not pm.lineas
    with base.get_session() as db:
        assert stock.saldo(db, a.id) == D(22)
    from nexum.ui.comprobantes_ui import PantallaComprobantes
    pc = PantallaComprobantes(s); assert pc.tabla.rowCount() == 1

    # importar lista por la interfaz
    from nexum.ui.precios_ui import PantallaImportarLista, PantallaActualizacionGlobal
    tmp = Path(tempfile.mkdtemp()) / "l.csv"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        csv.writer(f, delimiter=";").writerows([["Código", "Precio"], ["751-0122", "12.000,00"]])
    pi = PantallaImportarLista(s); pi.campo.setCurrentIndex(pi.campo.findData("codigo")); pi.cargar_archivo(str(tmp)); pi._previa()
    assert "1 cambian" in pi.estado.text(); pi.motivo.setText("Prueba"); pi._aplicar()
    with base.get_session() as db:
        assert db.scalar(select(c.Articulo)).costo_lista == D("12000.00")
    pg = PantallaActualizacionGlobal(s); pg._correr(False); assert pg.tabla.rowCount() == 1

    # usuarios
    from nexum.ui.usuarios_ui import PantallaUsuarios, UsuarioDialog
    pu = PantallaUsuarios(s); ud = UsuarioDialog()
    assert pu.tabla.rowCount() == 1 and ud.rol.count() == 3
    print("OK: interfaz completa funcionando")
    return app


if __name__ == "__main__":
    test_ui()
    # Qt sin pantalla a veces falla al destruir objetos al salir; el resultado ya se verificó arriba.
    os._exit(0)
