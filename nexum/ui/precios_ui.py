from decimal import Decimal as D

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
from sqlalchemy import select

from nexum.core import listas
from nexum.core.errores import NexumError
from nexum.db import comercial as c, maestros as t
from nexum.db.base import get_session
from nexum.ui.formato import money


def _tabla(cols):
    tb = QTableWidget(0, len(cols)); tb.setHorizontalHeaderLabels(cols)
    tb.setEditTriggers(QAbstractItemView.NoEditTriggers); tb.verticalHeader().hide(); tb.setAlternatingRowColors(True)
    tb.horizontalHeader().setStretchLastSection(True)
    return tb


def _combo(modelo, attr="nombre", vacio="Todos"):
    cb = QComboBox(); cb.addItem(vacio, None)
    with get_session() as db:
        for o in db.scalars(select(modelo).where(modelo.activo.is_(True)).order_by(getattr(modelo, attr))):
            cb.addItem(getattr(o, attr), o.id)
    return cb


class PantallaActualizacionGlobal(QWidget):
    """Sube o baja precios por porcentaje, con vista previa y motivo obligatorio."""
    def __init__(self, sesion):
        super().__init__()
        self.sesion = sesion
        self.setWindowTitle("Actualización Global de Precios")
        self.rubro, self.marca = _combo(t.Rubro), _combo(t.Marca)
        self.prov = _combo(c.Proveedor, "razon_social")
        self.pct = QDoubleSpinBox(); self.pct.setRange(-90, 500); self.pct.setDecimals(2); self.pct.setSuffix(" %"); self.pct.setValue(10)
        self.sobre = QComboBox(); self.sobre.addItem("Costo de lista", "costo_lista"); self.sobre.addItem("Coeficiente (margen)", "coeficiente")
        self.motivo = QLineEdit(); self.motivo.setPlaceholderText("Ej.: Aumento general noviembre")
        self.btn_prev = QPushButton("Vista previa"); self.btn_prev.clicked.connect(lambda: self._correr(False))
        self.btn_aplicar = QPushButton("Aplicar cambios"); self.btn_aplicar.setObjectName("primario")
        self.btn_aplicar.clicked.connect(lambda: self._correr(True)); self.btn_aplicar.setEnabled(False)
        self.btn_aplicar.setEnabled(False)
        self.estado = QLabel("")
        self.tabla = _tabla(["Código", "Nombre", "Precio actual", "Precio nuevo"])
        f = QFormLayout()
        f.addRow("Rubro", self.rubro); f.addRow("Marca", self.marca); f.addRow("Proveedor", self.prov)
        f.addRow("Variación", self.pct); f.addRow("Aplicar sobre", self.sobre); f.addRow("Motivo", self.motivo)
        bt = QHBoxLayout(); bt.addWidget(self.btn_prev); bt.addWidget(self.btn_aplicar); bt.addWidget(self.estado, 1)
        lay = QVBoxLayout(self); lay.addLayout(f); lay.addLayout(bt); lay.addWidget(self.tabla)
        self.resize(760, 560)

    def _correr(self, aplicar):
        if aplicar and QMessageBox.question(self, "Precios", "¿Aplicar el cambio a todos los artículos de la vista previa?") != QMessageBox.Yes:
            return
        try:
            with get_session() as db:
                filas = listas.cambio_porcentual(db, self.sesion, self.pct.value(), self.sobre.currentData(), self.rubro.currentData(),
                                                 self.marca.currentData(), self.prov.currentData(), self.motivo.text(), aplicar)
        except NexumError as e:
            self.estado.setStyleSheet("color:#dc2626;font-weight:600"); self.estado.setText(str(e)); return
        self.tabla.setRowCount(len(filas))
        for r, f in enumerate(filas):
            for col, v in enumerate((f["codigo"], f["nombre"], money(f["precio_antes"]), money(f["precio_nuevo"]))):
                it = QTableWidgetItem(v)
                if col >= 2:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tabla.setItem(r, col, it)
        self.tabla.resizeColumnsToContents()
        self.estado.setStyleSheet("color:#16a34a;font-weight:600")
        self.estado.setText(f"✓ {len(filas)} artículos actualizados" if aplicar else f"{len(filas)} artículos afectados")
        self.btn_aplicar.setEnabled(not aplicar and bool(filas))


class PantallaImportarLista(QWidget):
    """Lista de precios del proveedor (Excel/CSV): elegís columnas, ves las diferencias y aplicás."""
    def __init__(self, sesion):
        super().__init__()
        self.sesion, self.filas, self.plan = sesion, [], None
        self.setWindowTitle("Actualización de Precios — importar lista")
        self.btn_arch = QPushButton("Elegir archivo…"); self.btn_arch.clicked.connect(self._elegir)
        self.lbl_arch = QLabel("Ningún archivo"); self.lbl_arch.setObjectName("suave")
        self.prov = _combo(c.Proveedor, "razon_social", "Cualquier proveedor")
        self.campo = QComboBox()
        for k, v in listas.CAMPOS_CLAVE.items():
            self.campo.addItem(v, k)
        self.col_clave, self.col_costo, self.col_desc = QComboBox(), QComboBox(), QComboBox()
        self.motivo = QLineEdit(); self.motivo.setPlaceholderText("Ej.: Lista Top Tools noviembre")
        self.btn_prev = QPushButton("Vista previa"); self.btn_prev.clicked.connect(self._previa)
        self.btn_aplicar = QPushButton("Aplicar"); self.btn_aplicar.setObjectName("primario"); self.btn_aplicar.setEnabled(False)
        self.btn_aplicar.clicked.connect(self._aplicar)
        self.estado = QLabel("")
        self.tabla = _tabla(["Código", "Nombre", "Costo anterior", "Costo nuevo", "Var. %", "Precio nuevo"])
        f = QFormLayout()
        h = QHBoxLayout(); h.addWidget(self.btn_arch); h.addWidget(self.lbl_arch, 1); f.addRow("Archivo", h)
        f.addRow("Proveedor", self.prov); f.addRow("Identificar artículos por", self.campo)
        f.addRow("Columna del código", self.col_clave); f.addRow("Columna del costo", self.col_costo)
        f.addRow("Columna del descuento", self.col_desc); f.addRow("Motivo", self.motivo)
        bt = QHBoxLayout(); bt.addWidget(self.btn_prev); bt.addWidget(self.btn_aplicar); bt.addWidget(self.estado, 1)
        lay = QVBoxLayout(self); lay.addLayout(f); lay.addLayout(bt); lay.addWidget(self.tabla)
        self.resize(860, 640)

    def _elegir(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Lista de precios", "", "Listas (*.xlsx *.xlsm *.csv *.txt)")
        if ruta:
            self.cargar_archivo(ruta)

    def cargar_archivo(self, ruta):
        try:
            enc, self.filas = listas.leer_archivo(ruta)
        except NexumError as e:
            self.estado.setText(str(e)); return
        self.lbl_arch.setText(f"{ruta.split('/')[-1].split(chr(92))[-1]}  ({len(self.filas)} filas)")
        sug = listas.sugerir_mapeo(enc)
        for cb, key, opcional in ((self.col_clave, "clave", False), (self.col_costo, "costo", False), (self.col_desc, "descuento", True)):
            cb.clear()
            if opcional:
                cb.addItem("— ninguna —", None)
            for i, h in enumerate(enc):
                cb.addItem(h or f"(columna {i + 1})", i)
            if sug[key] is not None:
                cb.setCurrentIndex(cb.findData(sug[key]))
        self.plan = None; self.btn_aplicar.setEnabled(False)

    def _previa(self):
        if not self.filas:
            self.estado.setText("Elegí un archivo"); return
        mapeo = {"clave": self.col_clave.currentData(), "costo": self.col_costo.currentData(), "descuento": self.col_desc.currentData()}
        with get_session() as db:
            self.plan = listas.armar_plan(db, self.filas, mapeo, self.campo.currentData(), self.prov.currentData())
        ch = self.plan["cambios"]
        self.tabla.setRowCount(len(ch))
        for r, x in enumerate(ch):
            vals = (x["codigo"], x["nombre"], money(x["costo_lista_antes"]), money(x["costo_lista_nuevo"]),
                    "" if x["variacion_pct"] is None else f"{x['variacion_pct']:+}", money(x["precio_nuevo"]))
            for col, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if col >= 2:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tabla.setItem(r, col, it)
        self.tabla.resizeColumnsToContents()
        self.estado.setStyleSheet("color:#6b7280")
        self.estado.setText(f"{len(ch)} cambian · {self.plan['sin_cambio']} sin cambio · {len(self.plan['sin_coincidencia'])} sin coincidencia")
        self.btn_aplicar.setEnabled(bool(ch))

    def _aplicar(self):
        if not self.plan:
            return
        try:
            with get_session() as db:
                n = listas.aplicar_plan(db, self.sesion, self.plan, self.motivo.text())
        except NexumError as e:
            self.estado.setStyleSheet("color:#dc2626;font-weight:600"); self.estado.setText(str(e)); return
        self.estado.setStyleSheet("color:#16a34a;font-weight:600"); self.estado.setText(f"✓ {n} artículos actualizados")
        self.plan = None; self.btn_aplicar.setEnabled(False)
