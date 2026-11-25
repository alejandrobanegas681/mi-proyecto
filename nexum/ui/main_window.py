from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QDockWidget, QLineEdit, QMainWindow, QTabWidget, QToolBar, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from nexum import config
from nexum.core import menu
from nexum.ui import tema
from nexum.ui.paleta import PaletaComandos
from nexum.ui.registry import crear_pantalla

ACCESOS = [("Mostrador", "F2", "ventas.facturacion.facturacion_mostrador"),
           ("Artículos", "F3", "stock.archivos.articulos"),
           ("Stock", "F4", "stock.consultas_de_stock"),
           ("Clientes", "F5", "ventas.archivos.clientes")]


class MainWindow(QMainWindow):
    def __init__(self, sesion):
        super().__init__()
        self.sesion, self.abiertas, self.hojas = sesion, {}, []
        self.setWindowTitle(f"{config.APP_NAME} v{config.APP_VERSION}")
        self.resize(1360, 820)

        self.tabs = QTabWidget(); self.tabs.setTabsClosable(True); self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self._cerrar)
        self.setCentralWidget(self.tabs)

        self.filtro = QLineEdit(); self.filtro.setPlaceholderText("Filtrar el menú…"); self.filtro.setClearButtonEnabled(True)
        self.filtro.textChanged.connect(self._filtrar_arbol)
        self.arbol = QTreeWidget(); self.arbol.setHeaderHidden(True); self.arbol.setIndentation(14)
        self.arbol.itemActivated.connect(self._abrir_item); self.arbol.itemDoubleClicked.connect(self._abrir_item)
        for nodo in menu.parsear():
            self._agregar(nodo, self.arbol.invisibleRootItem(), nodo.etiqueta)
        cont = QWidget(); l = QVBoxLayout(cont); l.setContentsMargins(4, 4, 4, 4); l.addWidget(self.filtro); l.addWidget(self.arbol)
        dock = QDockWidget("Menú", self); dock.setWidget(cont); dock.setFeatures(QDockWidget.DockWidgetMovable)
        dock.setMinimumWidth(230)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

        barra = QToolBar("Accesos"); barra.setMovable(False)
        self.addToolBar(barra)
        for nombre, tecla, codigo in ACCESOS:
            if sesion.puede(codigo, "ver"):
                a = QAction(f"{nombre}  ({tecla})", self); a.setShortcut(QKeySequence(tecla))
                a.triggered.connect(lambda _c=False, cod=codigo: self.abrir(cod)); barra.addAction(a)
        barra.addSeparator()
        a = QAction("Ir a…  (Ctrl+K)", self); a.setShortcut(QKeySequence("Ctrl+K")); a.triggered.connect(self.paleta); barra.addAction(a)
        a = QAction("Tema claro/oscuro", self); a.triggered.connect(self.alternar_tema); barra.addAction(a)
        cerrar = QAction(self); cerrar.setShortcut(QKeySequence("Ctrl+W")); cerrar.triggered.connect(lambda: self._cerrar(self.tabs.currentIndex()))
        self.addAction(cerrar)
        self.statusBar().showMessage(f"Usuario: {sesion.nombre}   ·   Ctrl+K para buscar cualquier pantalla")

    # ---------- menú ----------
    def _agregar(self, nodo, padre_item, ruta) -> bool:
        if nodo.es_hoja and not self.sesion.puede(nodo.codigo, "ver"):
            return False
        item = QTreeWidgetItem([nodo.etiqueta])
        item.setData(0, Qt.UserRole, nodo.codigo if nodo.es_hoja else None)
        item.setData(0, Qt.UserRole + 1, ruta)
        visible = nodo.es_hoja
        if nodo.es_hoja:
            self.hojas.append((nodo.etiqueta, ruta, nodo.codigo))
        for h in nodo.hijos:
            visible |= self._agregar(h, item, f"{ruta} › {h.etiqueta}")
        if visible:
            padre_item.addChild(item)
        return visible

    def _filtrar_arbol(self, texto):
        import unicodedata
        norm = lambda s: unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
        tokens = norm(texto).split()

        def visitar(it) -> bool:
            if it.childCount() == 0:
                ok = all(t in norm(it.data(0, Qt.UserRole + 1)) for t in tokens)
                it.setHidden(not ok); return ok
            alguno = any([visitar(it.child(i)) for i in range(it.childCount())])
            it.setHidden(not alguno); it.setExpanded(bool(tokens) and alguno); return alguno
        for i in range(self.arbol.topLevelItemCount()):
            visitar(self.arbol.topLevelItem(i))

    def _abrir_item(self, item, _col=0):
        codigo = item.data(0, Qt.UserRole)
        if codigo:
            self.abrir(codigo)

    # ---------- pestañas ----------
    def abrir(self, codigo):
        if codigo in self.abiertas:
            self.tabs.setCurrentWidget(self.abiertas[codigo]); return self.abiertas[codigo]
        etiqueta = next((h[0] for h in self.hojas if h[2] == codigo), codigo)
        w = crear_pantalla(codigo, etiqueta, self.sesion)
        self.abiertas[codigo] = w
        self.tabs.setCurrentIndex(self.tabs.addTab(w, etiqueta))
        return w

    def _cerrar(self, idx):
        if idx < 0:
            return
        w = self.tabs.widget(idx)
        for k, v in list(self.abiertas.items()):
            if v is w:
                del self.abiertas[k]
        self.tabs.removeTab(idx); w.deleteLater()

    def paleta(self):
        dlg = PaletaComandos(self.hojas, self)
        if dlg.exec() == PaletaComandos.Accepted and dlg.codigo:
            self.abrir(dlg.codigo)

    def alternar_tema(self):
        cfg = QSettings("NEXUM", "NEXUM")
        oscuro = not (cfg.value("oscuro", "false") == "true")
        cfg.setValue("oscuro", "true" if oscuro else "false")
        from PySide6.QtWidgets import QApplication
        tema.aplicar(QApplication.instance(), oscuro)
