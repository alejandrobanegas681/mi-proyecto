"""Buscador de artículos reutilizable: escribís y filtra al instante (con pequeña espera)."""
from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QHeaderView, QLineEdit, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from nexum.core import busqueda, precios, stock
from nexum.db.base import get_session
from nexum.ui.formato import cant, money


class BuscadorArticulos(QWidget):
    elegido = Signal(int)          # id del artículo seleccionado
    activado = Signal(int)         # doble clic o Enter sobre un artículo

    def __init__(self, columnas=("codigo", "nombre", "precio", "stock"), limite=100):
        super().__init__()
        self.columnas, self.limite = columnas, limite
        self.entrada = QLineEdit()
        self.entrada.setPlaceholderText("Buscar: varias palabras, código o código de barras…")
        self.entrada.setClearButtonEnabled(True)
        self.tabla = QTableWidget(0, len(columnas))
        titulos = {"codigo": "Código", "nombre": "Nombre", "precio": "Precio", "stock": "Stock", "costo": "Costo"}
        self.tabla.setHorizontalHeaderLabels([titulos[c] for c in columnas])
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.verticalHeader().hide()
        h = self.tabla.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeToContents)
        h.setSectionResizeMode(columnas.index("nombre"), QHeaderView.Stretch)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.entrada)
        lay.addWidget(self.tabla)
        self._timer = QTimer(self, singleShot=True, interval=180)
        self._timer.timeout.connect(self.refrescar)
        self.entrada.textChanged.connect(lambda _t: self._timer.start())
        self.tabla.itemSelectionChanged.connect(self._seleccion)
        self.tabla.doubleClicked.connect(lambda _i: self._activar())
        self.entrada.returnPressed.connect(self._enter)
        self.refrescar()

    def refrescar(self):
        with get_session() as db:
            arts = busqueda.buscar_articulos(db, self.entrada.text(), self.limite)
            saldos = stock.saldos_por_sucursal(db, [a.id for a in arts]) if "stock" in self.columnas else {}
            self.tabla.setRowCount(len(arts))
            for r, a in enumerate(arts):
                valores = {"codigo": a.codigo, "nombre": a.nombre, "precio": money(precios.precio_vigente(a)),
                           "costo": money(a.costo), "stock": cant(sum(saldos.get(a.id, {}).values()) if saldos else 0)}
                for col, key in enumerate(self.columnas):
                    item = QTableWidgetItem(valores[key])
                    if key in ("precio", "costo", "stock"):
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    if col == 0:
                        item.setData(Qt.UserRole, a.id)
                    self.tabla.setItem(r, col, item)

    def id_actual(self):
        fila = self.tabla.currentRow()
        return self.tabla.item(fila, 0).data(Qt.UserRole) if fila >= 0 else None

    def seleccionar_id(self, id_):
        for r in range(self.tabla.rowCount()):
            if self.tabla.item(r, 0).data(Qt.UserRole) == id_:
                self.tabla.selectRow(r)
                return

    def _seleccion(self):
        i = self.id_actual()
        if i:
            self.elegido.emit(i)

    def _activar(self):
        i = self.id_actual()
        if i:
            self.activado.emit(i)

    def _enter(self):
        self._timer.stop()
        self.refrescar()
        if self.tabla.rowCount() and self.tabla.currentRow() < 0:
            self.tabla.selectRow(0)
        self._activar()
