from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)
from sqlalchemy import select

from nexum.core import usuarios
from nexum.core.errores import NexumError
from nexum.db import models as m
from nexum.db.base import get_session


class UsuarioDialog(QDialog):
    def __init__(self, u=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Usuario - " + ("Editar" if u else "Nuevo"))
        self.usuario, self.nombre = QLineEdit(u.usuario if u else ""), QLineEdit(u.nombre if u else "")
        self.clave = QLineEdit(); self.clave.setEchoMode(QLineEdit.Password)
        self.clave.setPlaceholderText("Dejar vacía para no cambiarla" if u else "Mínimo 6 caracteres")
        self.rol, self.suc = QComboBox(), QComboBox()
        self.suc.addItem("—", None)
        with get_session() as db:
            for r in db.scalars(select(m.Rol).order_by(m.Rol.nombre)):
                self.rol.addItem(r.nombre, r.id)
            for s in db.scalars(select(m.Sucursal).order_by(m.Sucursal.codigo)):
                self.suc.addItem(s.nombre, s.id)
        if u:
            self.rol.setCurrentIndex(max(self.rol.findData(u.rol_id), 0)); self.suc.setCurrentIndex(max(self.suc.findData(u.sucursal_id), 0))
        self.activo = QCheckBox("Activo"); self.activo.setChecked(u.activo if u else True)
        f = QFormLayout()
        for lbl, w in (("Usuario *", self.usuario), ("Nombre", self.nombre), ("Clave", self.clave), ("Rol *", self.rol),
                       ("Sucursal", self.suc), ("", self.activo)):
            f.addRow(lbl, w)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self); lay.addLayout(f); lay.addWidget(bb)

    def valores(self):
        return {"usuario": self.usuario.text(), "nombre": self.nombre.text(), "clave": self.clave.text(),
                "rol_id": self.rol.currentData(), "sucursal_id": self.suc.currentData(), "activo": self.activo.isChecked()}


class PantallaUsuarios(QWidget):
    def __init__(self, sesion):
        super().__init__()
        self.sesion = sesion
        self.setWindowTitle("Usuarios")
        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(["Usuario", "Nombre", "Rol", "Sucursal", "Activo"])
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.verticalHeader().hide(); self.tabla.setAlternatingRowColors(True); self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.doubleClicked.connect(lambda _i: self._abrir(self._id()))
        b_nuevo = QPushButton("Nuevo"); b_nuevo.clicked.connect(lambda: self._abrir(None))
        b_edit = QPushButton("Editar"); b_edit.clicked.connect(lambda: self._abrir(self._id()))
        b_nuevo.setEnabled(sesion.puede(usuarios.COD, "crear")); b_edit.setEnabled(sesion.puede(usuarios.COD, "modificar"))
        b_clave = QPushButton("Cambiar mi clave"); b_clave.clicked.connect(self._mi_clave)
        top = QHBoxLayout(); top.addWidget(b_nuevo); top.addWidget(b_edit); top.addStretch(1); top.addWidget(b_clave)
        lay = QVBoxLayout(self); lay.addLayout(top); lay.addWidget(self.tabla)
        self.resize(720, 420)
        self.refrescar()

    def refrescar(self):
        with get_session() as db:
            roles = {r.id: r.nombre for r in db.scalars(select(m.Rol))}
            sucs = {s.id: s.nombre for s in db.scalars(select(m.Sucursal))}
            us = list(db.scalars(select(m.Usuario).order_by(m.Usuario.usuario)))
            self.tabla.setRowCount(len(us))
            for r, u in enumerate(us):
                for col, v in enumerate((u.usuario, u.nombre, roles.get(u.rol_id, ""), sucs.get(u.sucursal_id, ""), "Sí" if u.activo else "No")):
                    it = QTableWidgetItem(v)
                    if col == 0:
                        it.setData(Qt.UserRole, u.id)
                    self.tabla.setItem(r, col, it)

    def _id(self):
        f = self.tabla.currentRow()
        return self.tabla.item(f, 0).data(Qt.UserRole) if f >= 0 else None

    def _abrir(self, id_):
        with get_session() as db:
            u = db.get(m.Usuario, id_) if id_ else None
            dlg = UsuarioDialog(u, self)
        while dlg.exec() == QDialog.Accepted:
            try:
                with get_session() as db:
                    usuarios.guardar(db, self.sesion, dlg.valores(), id_)
            except NexumError as e:
                QMessageBox.warning(self, "Usuarios", str(e)); continue
            self.refrescar(); break

    def _mi_clave(self):
        actual, ok = QInputDialog.getText(self, "Cambiar mi clave", "Clave actual:", QLineEdit.Password)
        if not ok:
            return
        nueva, ok = QInputDialog.getText(self, "Cambiar mi clave", "Clave nueva (mínimo 6 caracteres):", QLineEdit.Password)
        if not ok:
            return
        try:
            with get_session() as db:
                usuarios.cambiar_mi_clave(db, self.sesion, actual, nueva)
            QMessageBox.information(self, "Clave", "Clave actualizada")
        except NexumError as e:
            QMessageBox.warning(self, "Clave", str(e))
