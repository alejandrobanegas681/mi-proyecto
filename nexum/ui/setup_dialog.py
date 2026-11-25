"""Se muestra solo la primera vez: pide lo mínimo para empezar. No carga datos de ejemplo."""
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout)

from nexum import config
from nexum.core import setup
from nexum.core.comprobantes import CONDICIONES_IVA
from nexum.core.errores import NexumError
from nexum.db.base import get_session


class SetupDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{config.APP_NAME} - Primera configuración")
        self.setMinimumWidth(440)
        self.empresa, self.cuit = QLineEdit(), QLineEdit()
        self.cuit.setPlaceholderText("opcional, ej. 30-12345678-9")
        self.iva = QComboBox()
        for k, v in CONDICIONES_IVA[:3]:
            self.iva.addItem(v, k)
        self.sucursal = QLineEdit("Casa Central")
        self.usuario, self.nombre = QLineEdit("admin"), QLineEdit()
        self.clave, self.clave2 = QLineEdit(), QLineEdit()
        for w in (self.clave, self.clave2):
            w.setEchoMode(QLineEdit.Password)
        self.provincias = QCheckBox("Cargar las 24 provincias argentinas (opcional)")
        self.error = QLabel(""); self.error.setStyleSheet("color:#dc2626;font-weight:600")
        btn = QPushButton("Crear y empezar"); btn.setObjectName("primario"); btn.setDefault(True); btn.clicked.connect(self._crear)
        f = QFormLayout()
        for lbl, w in (("Empresa *", self.empresa), ("CUIT", self.cuit), ("Condición frente al IVA", self.iva),
                       ("Primera sucursal *", self.sucursal), ("Usuario administrador *", self.usuario), ("Su nombre", self.nombre),
                       ("Clave * (mín. 6)", self.clave), ("Repetir clave *", self.clave2)):
            f.addRow(lbl, w)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<h2>Bienvenido a {config.APP_NAME}</h2><p>Completá estos datos para empezar. El sistema arranca vacío: todo lo demás lo cargás vos.</p>"))
        lay.addLayout(f); lay.addWidget(self.provincias); lay.addWidget(self.error); lay.addWidget(btn)
        self.datos = None

    def _crear(self):
        if self.clave.text() != self.clave2.text():
            self.error.setText("Las claves no coinciden"); return
        try:
            with get_session() as db:
                setup.configurar_inicial(db, empresa=self.empresa.text(), cuit=self.cuit.text() or None,
                                         condicion_iva=self.iva.currentData(), sucursal=self.sucursal.text(),
                                         usuario=self.usuario.text(), nombre=self.nombre.text(), clave=self.clave.text(),
                                         cargar_provincias=self.provincias.isChecked())
        except NexumError as e:
            self.error.setText(str(e)); return
        self.datos = (self.usuario.text().strip(), self.clave.text())
        self.accept()
