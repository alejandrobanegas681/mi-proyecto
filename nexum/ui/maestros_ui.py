"""Registra todas las pantallas reales por código de menú."""
from nexum.maestros.definiciones import DEFINICIONES
from nexum.ui.abm_widget import PantallaABM
from nexum.ui.articulos_ui import PantallaArticulos
from nexum.ui.comprobantes_ui import PantallaComprobantes
from nexum.ui.mostrador_ui import PantallaMostrador
from nexum.ui.precios_ui import PantallaActualizacionGlobal, PantallaImportarLista
from nexum.ui.registry import registrar
from nexum.ui.stock_ui import PantallaAjusteStock, PantallaConsultaStock, PantallaKardex
from nexum.ui.usuarios_ui import PantallaUsuarios

for _d in DEFINICIONES:
    registrar(_d.codigo_menu)(lambda sesion, d=_d: PantallaABM(d, sesion))

registrar("stock.archivos.articulos")(PantallaArticulos)
registrar("ventas.facturacion.facturacion_mostrador")(PantallaMostrador)
registrar("ventas.movimientos.consulta_de_comprobantes")(PantallaComprobantes)
registrar("stock.consultas_de_stock")(PantallaConsultaStock)
registrar("stock.consultas_por_articulo")(PantallaKardex)
registrar("stock.movimientos.inicial")(lambda s: PantallaAjusteStock(s, "INICIAL"))
registrar("stock.inventario")(lambda s: PantallaAjusteStock(s, "AJUSTE"))
registrar("ventas.movimientos.precios.actualizacion_global")(PantallaActualizacionGlobal)
registrar("ventas.movimientos.precios.actualizacion_de_precios")(PantallaImportarLista)
registrar("administracion.usuarios")(PantallaUsuarios)
