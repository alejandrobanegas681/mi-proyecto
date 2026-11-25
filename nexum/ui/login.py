from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from nexum import config
from nexum.core.auth import LoginError, iniciar_sesion
from nexum.db.base import get_session


class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{config.APP_NAME} - Ingreso")
        self.sesion = None
        self.usuario = QLineEdit()
        self.clave = QLineEdit()
        self.clave.setEchoMode(QLineEdit.Password)
        self.error = QLabel("")
        self.error.setStyleSheet("color: #b00020;")
        boton = QPushButton("Ingresar")
        boton.setDefault(True)
        boton.clicked.connect(self._ingresar)
        form = QFormLayout()
        form.addRow("Usuario", self.usuario)
        form.addRow("Clave", self.clave)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<h2>{config.APP_NAME}</h2>"))
        lay.addLayout(form)
        lay.addWidget(self.error)
        lay.addWidget(boton)

    def _ingresar(self):
        with get_session() as db:
            try:
                self.sesion = iniciar_sesion(db, self.usuario.text().strip(), self.clave.text())
            except LoginError as e:
                self.error.setText(str(e))
                self.clave.clear()
                return
        self.accept()
