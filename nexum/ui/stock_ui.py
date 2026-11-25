from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)
from sqlalchemy import select

from nexum.core import stock
from nexum.core.errores import NexumError
from nexum.db import models as m
from nexum.db import comercial as c
from nexum.db.base import get_session
from nexum.ui.buscador import BuscadorArticulos
from nexum.ui.formato import cant, money


def _tabla(cols):
    t = QTableWidget(0, len(cols)); t.setHorizontalHeaderLabels(cols)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers); t.verticalHeader().hide(); t.setAlternatingRowColors(True)
    return t


class PantallaConsultaStock(QWidget):
    """Stock de todos los artículos, una columna por sucursal."""
    def __init__(self, sesion):
        super().__init__()
        self.setWindowTitle("Consultas de Stock")
        with get_session() as db:
            self.sucursales = [(s.id, s.nombre) for s in db.scalars(select(m.Sucursal).order_by(m.Sucursal.codigo))]
        self.buscador = BuscadorArticulos(("codigo", "nombre", "stock"), limite=300)
        self.buscador.tabla.hide()
        self.entrada = self.buscador.entrada
        self.tabla = _tabla(["Código", "Nombre"] + [n for _, n in self.sucursales] + ["Total"])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.solo_con_stock = QPushButton("Solo con stock"); self.solo_con_stock.setCheckable(True)
        self.solo_con_stock.toggled.connect(self.refrescar)
        self.entrada.textChanged.connect(self.refrescar)
        top = QHBoxLayout(); top.addWidget(self.entrada, 1); top.addWidget(self.solo_con_stock)
        lay = QVBoxLayout(self); lay.addLayout(top); lay.addWidget(self.tabla)
        self.resize(900, 560)
        self.refrescar()

    def refrescar(self, *_):
        from nexum.core import busqueda
        with get_session() as db:
            arts = busqueda.buscar_articulos(db, self.entrada.text(), 300)
            sal = stock.saldos_por_sucursal(db, [a.id for a in arts])
            filas = []
            for a in arts:
                por_suc = [sal[a.id].get(sid, 0) for sid, _ in self.sucursales]
                total = sum(por_suc)
                if self.solo_con_stock.isChecked() and total <= 0:
                    continue
                filas.append((a, por_suc, total))
            self.tabla.setRowCount(len(filas))
            for r, (a, por_suc, total) in enumerate(filas):
                vals = [a.codigo, a.nombre] + [cant(v) for v in por_suc] + [cant(total)]
                for col, v in enumerate(vals):
                    it = QTableWidgetItem(v)
                    if col >= 2:
                        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        if total <= 0:
                            it.setForeground(Qt.red)
                    self.tabla.setItem(r, col, it)


class PantallaKardex(QWidget):
    """Consulta por artículo: movimientos con saldo acumulado."""
    def __init__(self, sesion):
        super().__init__()
        self.setWindowTitle("Consultas por Artículo")
        self.buscador = BuscadorArticulos(("codigo", "nombre", "stock"))
        self.buscador.elegido.connect(self._cargar)
        self.tabla = _tabla(["Fecha", "Sucursal", "Tipo", "Referencia", "Cantidad", "Saldo", "Obs."])
        self.tabla.horizontalHeader().setStretchLastSection(True)
        sp = QSplitter(); sp.addWidget(self.buscador); sp.addWidget(self.tabla); sp.setStretchFactor(1, 2)
        lay = QVBoxLayout(self); lay.addWidget(sp)
        self.resize(1050, 560)

    def _cargar(self, id_):
        with get_session() as db:
            sucs = {s.id: s.nombre for s in db.scalars(select(m.Sucursal))}
            movs = stock.kardex(db, id_)
        self.tabla.setRowCount(len(movs))
        for r, (mv, acum) in enumerate(reversed(movs)):
            vals = [mv.fecha.strftime("%d/%m/%Y %H:%M"), sucs.get(mv.sucursal_id, ""), mv.tipo, mv.referencia or "",
                    cant(mv.cantidad), cant(acum), mv.observacion or ""]
            for col, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if col in (4, 5):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tabla.setItem(r, col, it)
        self.tabla.resizeColumnsToContents()


class PantallaAjusteStock(QWidget):
    """Stock inicial (tipo INICIAL) o inventario/ajuste por conteo (tipo AJUSTE)."""
    def __init__(self, sesion, tipo="AJUSTE"):
        super().__init__()
        self.sesion, self.tipo, self.art_id = sesion, tipo, None
        self.setWindowTitle("Inicial de Stock" if tipo == "INICIAL" else "Inventario")
        self.buscador = BuscadorArticulos(("codigo", "nombre", "stock"))
        self.buscador.elegido.connect(self._elegir)
        self.lbl_art = QLabel("Elegí un artículo de la lista"); self.lbl_art.setStyleSheet("font-weight:600")
        self.suc = QComboBox()
        with get_session() as db:
            for s in db.scalars(select(m.Sucursal).order_by(m.Sucursal.codigo)):
                self.suc.addItem(s.nombre, s.id)
            if sesion.sucursal_id:
                self.suc.setCurrentIndex(max(self.suc.findData(sesion.sucursal_id), 0))
        self.suc.currentIndexChanged.connect(self._actualizar)
        self.lbl_actual = QLabel("—")
        self.real = QDoubleSpinBox(); self.real.setRange(0, 1e9); self.real.setDecimals(3); self.real.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.real.setAlignment(Qt.AlignRight)
        self.obs = QLineEdit()
        self.lbl_dif = QLabel("")
        self.real.valueChanged.connect(self._dif)
        self.btn = QPushButton("Aplicar"); self.btn.setObjectName("primario"); self.btn.clicked.connect(self._aplicar)
        self.btn.setEnabled(sesion.puede("stock.movimientos.inicial" if tipo == "INICIAL" else "stock.inventario", "modificar"))
        self.estado = QLabel("")
        f = QFormLayout()
        f.addRow("Artículo", self.lbl_art); f.addRow("Sucursal", self.suc); f.addRow("Stock actual", self.lbl_actual)
        f.addRow("Cantidad " + ("inicial" if tipo == "INICIAL" else "contada"), self.real); f.addRow("Diferencia", self.lbl_dif)
        f.addRow("Observación", self.obs)
        der = QWidget(); ld = QVBoxLayout(der); ld.addLayout(f); ld.addWidget(self.btn); ld.addWidget(self.estado); ld.addStretch(1)
        sp = QSplitter(); sp.addWidget(self.buscador); sp.addWidget(der); sp.setStretchFactor(0, 2); sp.setStretchFactor(1, 1)
        lay = QVBoxLayout(self); lay.addWidget(sp)
        self.resize(980, 520)

    def _elegir(self, id_):
        self.art_id = id_
        with get_session() as db:
            a = db.get(c.Articulo, id_)
            self.lbl_art.setText(f"{a.codigo} — {a.nombre}")
        self._actualizar()

    def _actualizar(self, *_):
        if not self.art_id:
            return
        with get_session() as db:
            actual = stock.saldo(db, self.art_id, self.suc.currentData())
        self.lbl_actual.setText(cant(actual)); self.real.setValue(float(actual)); self._dif()

    def _dif(self, *_):
        try:
            from decimal import Decimal
            d = Decimal(str(round(self.real.value(), 3))) - Decimal(self.lbl_actual.text().replace(",", ".") or "0")
            self.lbl_dif.setText(f"{d:+g}" if d else "sin cambios")
        except Exception:
            self.lbl_dif.setText("")

    def _aplicar(self):
        if not self.art_id:
            self.estado.setText("Elegí un artículo"); return
        try:
            with get_session() as db:
                mv = stock.ajustar_a(db, self.sesion, self.art_id, self.suc.currentData(), self.real.value(),
                                     self.tipo, self.obs.text().strip() or None)
        except NexumError as e:
            self.estado.setStyleSheet("color:#dc2626;font-weight:600"); self.estado.setText(str(e)); return
        self.estado.setStyleSheet("color:#16a34a;font-weight:600")
        self.estado.setText("✓ Stock actualizado" if mv else "Sin cambios")
        self.buscador.refrescar(); self._actualizar()
