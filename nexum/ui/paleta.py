"""Ctrl+K: escribís parte del nombre de cualquier pantalla y Enter la abre."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout


class PaletaComandos(QDialog):
    def __init__(self, hojas, parent=None):
        """hojas: [(etiqueta, ruta_legible, codigo)]"""
        super().__init__(parent, Qt.Dialog | Qt.FramelessWindowHint)
        self.hojas, self.codigo = hojas, None
        self.setMinimumWidth(520)
        self.entrada = QLineEdit(); self.entrada.setPlaceholderText("Ir a… (escribí parte del nombre)")
        self.entrada.setStyleSheet("font-size: 13pt; padding: 8px;")
        self.lista = QListWidget()
        lay = QVBoxLayout(self); lay.addWidget(self.entrada); lay.addWidget(self.lista)
        self.entrada.textChanged.connect(self._filtrar)
        self.entrada.returnPressed.connect(self._aceptar)
        self.lista.itemActivated.connect(lambda _i: self._aceptar())
        self._filtrar("")

    def _filtrar(self, texto):
        import unicodedata
        norm = lambda s: unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
        tokens = norm(texto).split()
        self.lista.clear()
        for etiqueta, ruta, codigo in self.hojas:
            if all(t in norm(ruta) for t in tokens):
                it = QListWidgetItem(f"{etiqueta}    —    {ruta}")
                it.setData(Qt.UserRole, codigo)
                self.lista.addItem(it)
                if self.lista.count() >= 12:
                    break
        self.lista.setCurrentRow(0)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Down, Qt.Key_Up):
            self.lista.keyPressEvent(e)
        else:
            super().keyPressEvent(e)

    def _aceptar(self):
        it = self.lista.currentItem()
        if it:
            self.codigo = it.data(Qt.UserRole)
            self.accept()
