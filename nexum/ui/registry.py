"""Registro de pantallas. Cada pantalla real se asocia al código de menú;
las que no están registradas abren un aviso 'En construcción'."""
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

_PANTALLAS: dict = {}


def registrar(codigo: str):
    def deco(fabrica):
        _PANTALLAS[codigo] = fabrica
        return fabrica
    return deco


def crear_pantalla(codigo: str, etiqueta: str, sesion) -> QWidget:
    if codigo in _PANTALLAS:
        return _PANTALLAS[codigo](sesion)
    w = QWidget()
    w.setWindowTitle(etiqueta)
    lay = QVBoxLayout(w)
    lay.addWidget(QLabel(f"<h3>{etiqueta}</h3><p>Pantalla en construcción.<br><small>{codigo}</small></p>"))
    return w
