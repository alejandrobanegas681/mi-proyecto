"""Pantalla genérica de ABM: listado + búsqueda + formulario, a partir de una DefinicionABM."""
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
                               QDoubleSpinBox, QFormLayout, QHBoxLayout, QLineEdit, QMessageBox, QPushButton,
                               QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from nexum.core import abm
from nexum.core.errores import NexumError
from nexum.db.base import get_session


class FormularioDialog(QDialog):
    def __init__(self, db, d, obj=None, parent=None):
        super().__init__(parent)
        self.d = d
        self.setWindowTitle(f"{d.titulo} - {'Editar' if obj else 'Nuevo'}")
        self.setMinimumWidth(380)
        self.widgets = {}
        form = QFormLayout()
        for c in d.campos:
            w = self._crear_widget(db, c)
            valor = getattr(obj, c.nombre) if obj else c.por_defecto
            self._poner(w, c, valor)
            self.widgets[c.nombre] = w
            form.addRow(c.etiqueta + (" *" if c.requerido else ""), w)
        botones = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(botones)

    def _crear_widget(self, db, c):
        if c.tipo == "texto":
            w = QLineEdit()
            if c.largo:
                w.setMaxLength(c.largo)
            return w
        if c.tipo == "entero":
            w = QSpinBox(); w.setRange(-2_000_000_000, 2_000_000_000); return w
        if c.tipo == "decimal":
            w = QDoubleSpinBox(); w.setRange(-1e12, 1e12); w.setDecimals(2); return w
        if c.tipo == "bool":
            return QCheckBox()
        if c.tipo == "fecha":
            w = QDateEdit(); w.setCalendarPopup(True); w.setDisplayFormat("dd/MM/yyyy"); return w
        w = QComboBox()
        if not c.requerido:
            w.addItem("", None)
        for valor, etiqueta in (abm.opciones_fk(db, c) if c.tipo == "fk" else c.opciones or []):
            w.addItem(str(etiqueta), valor)
        return w

    @staticmethod
    def _poner(w, c, v):
        if c.tipo == "texto":
            w.setText(v or "")
        elif c.tipo in ("entero", "decimal"):
            w.setValue(v or 0)
        elif c.tipo == "bool":
            w.setChecked(bool(v))
        elif c.tipo == "fecha":
            w.setDate(QDate(v.year, v.month, v.day) if v else QDate.currentDate())
        else:
            i = w.findData(v)
            w.setCurrentIndex(max(i, 0))

    def valores(self) -> dict:
        out = {}
        for c in self.d.campos:
            w = self.widgets[c.nombre]
            if c.tipo == "texto":
                out[c.nombre] = w.text()
            elif c.tipo in ("entero", "decimal"):
                out[c.nombre] = w.value()
            elif c.tipo == "bool":
                out[c.nombre] = w.isChecked()
            elif c.tipo == "fecha":
                out[c.nombre] = w.date().toPython()
            else:
                out[c.nombre] = w.currentData()
        return out


class PantallaABM(QWidget):
    def __init__(self, definicion, sesion):
        super().__init__()
        self.d, self.sesion = definicion, sesion
        self.setWindowTitle(definicion.titulo)
        self.columnas = [c for c in definicion.campos if c.en_lista]

        self.buscar = QLineEdit(); self.buscar.setPlaceholderText("Buscar...")
        self.buscar.textChanged.connect(self.refrescar)
        self.inactivos = QCheckBox("Mostrar inactivos")
        self.inactivos.toggled.connect(self.refrescar)
        self.btn_nuevo = QPushButton("Nuevo"); self.btn_nuevo.clicked.connect(self._nuevo)
        self.btn_editar = QPushButton("Editar"); self.btn_editar.clicked.connect(self._editar)
        self.btn_borrar = QPushButton("Eliminar"); self.btn_borrar.clicked.connect(self._eliminar)
        self.btn_nuevo.setEnabled(sesion.puede(definicion.codigo_menu, "crear"))
        self.btn_editar.setEnabled(sesion.puede(definicion.codigo_menu, "modificar"))
        self.btn_borrar.setEnabled(sesion.puede(definicion.codigo_menu, "anular"))

        self.tabla = QTableWidget(0, len(self.columnas))
        self.tabla.setHorizontalHeaderLabels([c.etiqueta for c in self.columnas])
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.doubleClicked.connect(lambda _i: self._editar())

        arriba = QHBoxLayout()
        for w in (self.buscar, self.inactivos, self.btn_nuevo, self.btn_editar, self.btn_borrar):
            arriba.addWidget(w)
        lay = QVBoxLayout(self)
        lay.addLayout(arriba)
        lay.addWidget(self.tabla)
        self.resize(720, 460)
        self.refrescar()

    def refrescar(self, *_):
        with get_session() as db:
            filas = abm.listar(db, self.d, self.buscar.text().strip(), self.inactivos.isChecked())
            self.tabla.setRowCount(len(filas))
            for r, obj in enumerate(filas):
                for col, c in enumerate(self.columnas):
                    item = QTableWidgetItem(abm.texto_celda(db, c, obj))
                    if col == 0:
                        item.setData(Qt.UserRole, obj.id)
                    self.tabla.setItem(r, col, item)
        self.tabla.resizeColumnsToContents()

    def _id_seleccionado(self):
        fila = self.tabla.currentRow()
        return self.tabla.item(fila, 0).data(Qt.UserRole) if fila >= 0 else None

    def _formulario(self, id=None):
        with get_session() as db:
            obj = db.get(self.d.modelo, id) if id else None
            dlg = FormularioDialog(db, self.d, obj, self)
        while dlg.exec() == QDialog.Accepted:
            with get_session() as db:
                try:
                    abm.guardar(db, self.sesion, self.d, dlg.valores(), id)
                except NexumError as e:
                    QMessageBox.warning(self, self.d.titulo, str(e))
                    continue
            self.refrescar()
            break

    def _nuevo(self):
        self._formulario()

    def _editar(self):
        id = self._id_seleccionado()
        if id and self.btn_editar.isEnabled():
            self._formulario(id)

    def _eliminar(self):
        id = self._id_seleccionado()
        if not id:
            return
        if QMessageBox.question(self, self.d.titulo, "¿Eliminar el registro seleccionado?") != QMessageBox.Yes:
            return
        with get_session() as db:
            try:
                abm.eliminar(db, self.sesion, self.d, id)
            except NexumError as e:
                QMessageBox.warning(self, self.d.titulo, str(e))
        self.refrescar()
