from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QInputDialog, QLineEdit, QMessageBox,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
from sqlalchemy import or_, select

from nexum.core import comprobantes
from nexum.core.errores import NexumError
from nexum.db import comercial as c
from nexum.db.base import get_session
from nexum.ui.formato import cant, money


class PantallaComprobantes(QWidget):
    def __init__(self, sesion):
        super().__init__()
        self.sesion = sesion
        self.setWindowTitle("Consulta de Comprobantes")
        self.buscar = QLineEdit(); self.buscar.setPlaceholderText("Número, cliente o CUIT…")
        self.buscar.textChanged.connect(self.refrescar)
        self.btn_detalle = QPushButton("Ver detalle"); self.btn_detalle.clicked.connect(self._detalle)
        self.btn_anular = QPushButton("Anular"); self.btn_anular.clicked.connect(self._anular)
        self.btn_anular.setEnabled(sesion.puede(comprobantes.COD_ANULAR, "anular"))
        self.tabla = QTableWidget(0, 7)
        self.tabla.setHorizontalHeaderLabels(["Fecha", "Comprobante", "Cliente", "Pago", "Total", "Estado", "Usuario"])
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.verticalHeader().hide(); self.tabla.setAlternatingRowColors(True)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tabla.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tabla.doubleClicked.connect(lambda _i: self._detalle())
        top = QHBoxLayout(); top.addWidget(self.buscar, 1); top.addWidget(self.btn_detalle); top.addWidget(self.btn_anular)
        lay = QVBoxLayout(self); lay.addLayout(top); lay.addWidget(self.tabla)
        self.resize(960, 560)
        self.refrescar()

    def refrescar(self, *_):
        t = self.buscar.text().strip()
        with get_session() as db:
            q = select(c.Comprobante)
            if t:
                like = f"%{t}%"
                q = q.where(or_(c.Comprobante.cliente_nombre.ilike(like), c.Comprobante.cliente_cuit.ilike(like),
                                c.Comprobante.numero == (int(t) if t.isdigit() else -1)))
            filas = list(db.scalars(q.order_by(c.Comprobante.id.desc()).limit(300)))
            from nexum.db import models as m
            usuarios = {u.id: u.usuario for u in db.scalars(select(m.Usuario))}
            self.tabla.setRowCount(len(filas))
            for r, cp in enumerate(filas):
                vals = [cp.fecha.strftime("%d/%m/%Y %H:%M"), cp.numero_completo, cp.cliente_nombre,
                        comprobantes.FORMAS_PAGO.get(cp.forma_pago, cp.forma_pago), money(cp.total), cp.estado,
                        usuarios.get(cp.usuario_id, "")]
                for col, v in enumerate(vals):
                    it = QTableWidgetItem(v)
                    if col == 4:
                        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    if cp.estado == "ANULADO":
                        it.setForeground(Qt.gray)
                    if col == 0:
                        it.setData(Qt.UserRole, cp.id)
                    self.tabla.setItem(r, col, it)

    def _id(self):
        f = self.tabla.currentRow()
        return self.tabla.item(f, 0).data(Qt.UserRole) if f >= 0 else None

    def _detalle(self):
        i = self._id()
        if not i:
            return
        with get_session() as db:
            cp = db.get(c.Comprobante, i)
            lineas = "\n".join(f"{cant(it.cantidad):>6} x {it.descripcion[:38]:<38} $ {money(it.total):>12}" for it in cp.items)
            txt = f"{cp.numero_completo}  —  {cp.cliente_nombre}\n\n{lineas}\n\nNeto $ {money(cp.neto)}   IVA $ {money(cp.iva)}   TOTAL $ {money(cp.total)}"
        QMessageBox.information(self, "Detalle", txt)

    def _anular(self):
        i = self._id()
        if not i:
            return
        motivo, ok = QInputDialog.getText(self, "Anular comprobante", "Motivo de la anulación:")
        if not ok:
            return
        try:
            with get_session() as db:
                comprobantes.anular(db, self.sesion, i, motivo)
        except NexumError as e:
            QMessageBox.warning(self, "Anular", str(e))
        self.refrescar()
