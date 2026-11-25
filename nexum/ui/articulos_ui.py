"""Ficha de artículos: buscador a la izquierda, ficha a la derecha con precio calculado en vivo."""
from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget, QScrollArea, QAbstractItemView)
from sqlalchemy import select

from nexum.core import articulos, params, precios, stock
from nexum.core.errores import NexumError
from nexum.db import comercial as c, maestros as t, models as m
from nexum.db.base import get_session
from nexum.ui.buscador import BuscadorArticulos
from nexum.ui.formato import cant, money

PERFILES = [("CV", "Compra y venta"), ("C", "Solo compra"), ("V", "Solo venta")]
ALICUOTAS = [("21", "21 %"), ("10.5", "10,5 %"), ("27", "27 %"), ("0", "Exento / 0 %")]


def _spin(maximo=1e9, decimales=2, minimo=0.0, sufijo=""):
    s = QDoubleSpinBox()
    s.setRange(minimo, maximo)
    s.setDecimals(decimales)
    s.setGroupSeparatorShown(True)
    s.setButtonSymbols(QDoubleSpinBox.NoButtons)
    s.setAlignment(Qt.AlignRight)
    if sufijo:
        s.setSuffix(sufijo)
    return s


class PantallaArticulos(QWidget):
    def __init__(self, sesion):
        super().__init__()
        self.sesion, self.id_actual, self._bloq, self._fijar = sesion, None, False, False
        self.setWindowTitle("Artículos")
        self.buscador = BuscadorArticulos(("codigo", "nombre", "precio", "stock"))
        self.buscador.elegido.connect(self._cargar)
        self._armar_ficha()

        izq = QWidget(); li = QVBoxLayout(izq); li.setContentsMargins(0, 0, 6, 0); li.addWidget(self.buscador)
        der = QWidget(); ld = QVBoxLayout(der); ld.setContentsMargins(6, 0, 0, 0)
        ld.addLayout(self._barra())
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(self.ficha)
        ld.addWidget(scroll, 1)
        ld.addWidget(self.pestanas)
        sp = QSplitter(); sp.addWidget(izq); sp.addWidget(der); sp.setStretchFactor(0, 2); sp.setStretchFactor(1, 3)
        lay = QVBoxLayout(self); lay.addWidget(sp)
        for tecla, fn in (("Ctrl+N", self._nuevo), ("Ctrl+S", self._guardar)):
            QShortcut(QKeySequence(tecla), self, activated=fn)
        self.resize(1180, 760)
        self._nuevo()

    # ---------- construcción ----------
    def _barra(self):
        self.btn_nuevo = QPushButton("Nuevo  (Ctrl+N)"); self.btn_nuevo.clicked.connect(self._nuevo)
        self.btn_guardar = QPushButton("Guardar  (Ctrl+S)"); self.btn_guardar.setObjectName("primario")
        self.btn_guardar.clicked.connect(self._guardar)
        self.btn_otro = QPushButton("Guardar y cargar otro"); self.btn_otro.clicked.connect(lambda: self._guardar(otro=True))
        self.btn_baja = QPushButton("Dar de baja"); self.btn_baja.clicked.connect(self._baja)
        self.estado = QLabel(""); self.estado.setObjectName("suave")
        p = self.sesion.puede
        cod = articulos.CODIGO_MENU
        self.btn_nuevo.setEnabled(p(cod, "crear"))
        self.btn_guardar.setEnabled(p(cod, "crear") or p(cod, "modificar"))
        self.btn_otro.setEnabled(p(cod, "crear"))
        self.btn_baja.setEnabled(p(cod, "anular"))
        h = QHBoxLayout()
        for w in (self.btn_nuevo, self.btn_guardar, self.btn_otro, self.btn_baja):
            h.addWidget(w)
        h.addStretch(1); h.addWidget(self.estado)
        return h

    def _combo(self, modelo, attr="nombre", vacio="—"):
        cb = QComboBox()
        cb.addItem(vacio, None)
        with get_session() as db:
            for o in db.scalars(select(modelo).where(modelo.activo.is_(True)).order_by(getattr(modelo, attr))):
                cb.addItem(getattr(o, attr), o.id)
        return cb

    def _armar_ficha(self):
        w = self.w = {}
        w["codigo"] = QLineEdit(); w["codigo"].setMaxLength(20)
        w["nombre"] = QLineEdit(); w["nombre"].setMaxLength(80)
        w["descripcion"] = QPlainTextEdit(); w["descripcion"].setFixedHeight(48)
        w["rubro_id"] = self._combo(t.Rubro); w["familia_id"] = self._combo(t.Familia)
        w["clase_id"] = self._combo(t.Clase); w["marca_id"] = self._combo(t.Marca)
        w["perfil"] = QComboBox(); [w["perfil"].addItem(e, v) for v, e in PERFILES]
        w["proveedor_id"] = self._combo(c.Proveedor, "razon_social")
        w["codigo_proveedor"] = QLineEdit(); w["codigo_reemplazo"] = QLineEdit(); w["ubicacion"] = QLineEdit()
        w["barras"] = QLineEdit(); w["barras"].setPlaceholderText("uno o varios, separados por coma")
        w["unidad"] = QLineEdit(); w["unidad"].setMaximumWidth(70)
        w["kilos"] = _spin(1e6, 3)
        w["alicuota_iva"] = QComboBox(); [w["alicuota_iva"].addItem(e, v) for v, e in ALICUOTAS]
        w["desc_max"] = _spin(100, 2, -1, " %"); w["desc_max"].setSpecialValueText("Sin tope")
        w["recargo_pct"] = _spin(1000, 2, 0, " %")
        w["etiqueta"] = QCheckBox("Imprimir etiqueta")
        w["costo_lista"] = _spin(); w["desc_costo_pct"] = _spin(100, 2, 0, " %"); w["flete"] = _spin()
        self.lbl_costo = QLabel("0,00"); self.lbl_costo.setStyleSheet("font-weight:600")
        w["coeficiente"] = _spin(1e5, 4)
        w["precio_publico"] = _spin(); w["precio_publico"].setStyleSheet("font-weight:700; font-size:12pt")
        w["redondeo"] = QCheckBox("Redondear precio")
        self.oferta = QGroupBox("Precio oferta"); self.oferta.setCheckable(True); self.oferta.setChecked(False)
        w["oferta_precio"] = _spin()
        w["oferta_desde"] = QDateEdit(); w["oferta_hasta"] = QDateEdit()
        for d in (w["oferta_desde"], w["oferta_hasta"]):
            d.setCalendarPopup(True); d.setDisplayFormat("dd/MM/yyyy"); d.setDate(QDate.currentDate())
        w["observaciones"] = QLineEdit()
        w["activo"] = QCheckBox("Activo"); w["activo"].setChecked(True)

        ident = QGroupBox("Identificación"); f = QFormLayout(ident)
        f.addRow("Código *", w["codigo"]); f.addRow("Nombre *", w["nombre"]); f.addRow("Descripción", w["descripcion"])
        fila = QHBoxLayout(); fila.addWidget(w["rubro_id"]); fila.addWidget(QLabel("Familia")); fila.addWidget(w["familia_id"])
        f.addRow("Rubro", fila)
        fila = QHBoxLayout(); fila.addWidget(w["clase_id"]); fila.addWidget(QLabel("Marca")); fila.addWidget(w["marca_id"])
        f.addRow("Clase", fila)

        cods = QGroupBox("Códigos y proveedor"); f = QFormLayout(cods)
        f.addRow("Código de barras", w["barras"])
        fila = QHBoxLayout(); fila.addWidget(w["proveedor_id"], 2); fila.addWidget(QLabel("Cód. prov.")); fila.addWidget(w["codigo_proveedor"], 1)
        f.addRow("Proveedor", fila)
        fila = QHBoxLayout(); fila.addWidget(w["codigo_reemplazo"]); fila.addWidget(QLabel("Ubicación")); fila.addWidget(w["ubicacion"])
        f.addRow("Reemplaza a", fila)

        com = QGroupBox("Condiciones comerciales"); f = QFormLayout(com)
        fila = QHBoxLayout(); fila.addWidget(w["perfil"]); fila.addWidget(QLabel("IVA")); fila.addWidget(w["alicuota_iva"])
        fila.addWidget(QLabel("Unidad")); fila.addWidget(w["unidad"])
        f.addRow("Perfil", fila)
        fila = QHBoxLayout(); fila.addWidget(w["desc_max"]); fila.addWidget(QLabel("Recargo auto")); fila.addWidget(w["recargo_pct"])
        fila.addWidget(QLabel("Kilos")); fila.addWidget(w["kilos"])
        f.addRow("Descuento máx.", fila)
        f.addRow("Observaciones", w["observaciones"])
        fila = QHBoxLayout(); fila.addWidget(w["etiqueta"]); fila.addWidget(w["activo"]); fila.addStretch(1)
        f.addRow("", fila)

        pr = QGroupBox("Precio"); g = QFormLayout(pr)
        fila = QHBoxLayout()
        for lbl, wd in (("Costo de lista", w["costo_lista"]), ("Desc.", w["desc_costo_pct"]), ("Flete", w["flete"])):
            fila.addWidget(QLabel(lbl)); fila.addWidget(wd)
        g.addRow(fila)
        fila = QHBoxLayout()
        fila.addWidget(QLabel("Costo")); fila.addWidget(self.lbl_costo); fila.addSpacing(16)
        fila.addWidget(QLabel("Coeficiente")); fila.addWidget(w["coeficiente"]); fila.addSpacing(16)
        fila.addWidget(QLabel("PRECIO PÚBLICO")); fila.addWidget(w["precio_publico"]); fila.addWidget(w["redondeo"])
        g.addRow(fila)
        self.lbl_fechas = QLabel(""); self.lbl_fechas.setObjectName("suave"); g.addRow(self.lbl_fechas)
        of = QHBoxLayout(self.oferta)
        for lbl, wd in (("Precio", w["oferta_precio"]), ("Desde", w["oferta_desde"]), ("Hasta", w["oferta_hasta"])):
            of.addWidget(QLabel(lbl)); of.addWidget(wd)

        self.ficha = QWidget(); l = QVBoxLayout(self.ficha); l.setContentsMargins(0, 0, 4, 0)
        for g_ in (ident, cods, com, pr, self.oferta):
            l.addWidget(g_)
        l.addStretch(1)

        self.tab_hist = QTableWidget(0, 6)
        self.tab_hist.setHorizontalHeaderLabels(["Fecha", "Usuario", "Costo lista", "Coef.", "Precio", "Motivo"])
        self.tab_stock = QTableWidget(0, 2); self.tab_stock.setHorizontalHeaderLabels(["Sucursal", "Stock"])
        for tb in (self.tab_hist, self.tab_stock):
            tb.setEditTriggers(QAbstractItemView.NoEditTriggers); tb.verticalHeader().hide(); tb.setAlternatingRowColors(True)
            tb.horizontalHeader().setStretchLastSection(True)
        self.pestanas = QTabWidget(); self.pestanas.setMaximumHeight(170)
        self.pestanas.addTab(self.tab_stock, "Stock por sucursal"); self.pestanas.addTab(self.tab_hist, "Historial de precios")

        # recálculo en vivo
        for k in ("costo_lista", "desc_costo_pct", "flete", "coeficiente"):
            w[k].valueChanged.connect(self._desde_coeficiente)
        w["redondeo"].toggled.connect(self._desde_coeficiente)
        w["alicuota_iva"].currentIndexChanged.connect(self._desde_coeficiente)
        w["precio_publico"].editingFinished.connect(self._desde_publico)

    # ---------- cálculo en vivo ----------
    def _paso(self):
        with get_session() as db:
            return params.obtener(db, "redondeo_paso", "1")

    def _ali(self):
        return self.w["alicuota_iva"].currentData()

    def _desde_coeficiente(self, *_):
        if self._bloq:
            return
        w = self.w
        costo, pub = precios.calcular(w["costo_lista"].value(), w["desc_costo_pct"].value(), w["flete"].value(),
                                      w["coeficiente"].value(), self._ali(), w["redondeo"].isChecked(), self._paso())
        self._bloq = True
        self.lbl_costo.setText(money(costo)); w["precio_publico"].setValue(float(pub))
        self._bloq = False
        self._fijar = False

    def _desde_publico(self):
        if self._bloq:
            return
        w = self.w
        costo, _ = precios.calcular(w["costo_lista"].value(), w["desc_costo_pct"].value(), w["flete"].value(), 1, self._ali())
        self._bloq = True
        w["coeficiente"].setValue(float(precios.coeficiente_para(costo, w["precio_publico"].value(), self._ali())))
        self._bloq = False
        self._fijar = True

    # ---------- carga y guardado ----------
    def _nuevo(self):
        self.id_actual = None
        self._poner(None)
        self.estado.setText("Artículo nuevo")
        self.w["codigo"].setFocus()

    def _cargar(self, id_):
        with get_session() as db:
            art = db.get(c.Articulo, id_)
            if art:
                self.id_actual = id_
                self._poner(art, db)

    def _poner(self, art, db=None):
        w = self.w
        self._bloq = True
        def setc(cb, v):
            i = cb.findData(v); cb.setCurrentIndex(max(i, 0))
        w["codigo"].setText(art.codigo if art else ""); w["nombre"].setText(art.nombre if art else "")
        w["descripcion"].setPlainText((art.descripcion or "") if art else "")
        for k in ("rubro_id", "familia_id", "clase_id", "marca_id", "proveedor_id"):
            setc(w[k], getattr(art, k) if art else None)
        setc(w["perfil"], art.perfil if art else "CV")
        setc(w["alicuota_iva"], f"{float(art.alicuota_iva):g}" if art else "21")
        for k in ("codigo_proveedor", "codigo_reemplazo", "ubicacion", "observaciones"):
            w[k].setText((getattr(art, k) or "") if art else "")
        w["barras"].setText(", ".join(b.barras for b in art.barras) if art else "")
        w["unidad"].setText(art.unidad if art else "UN")
        w["kilos"].setValue(float(art.kilos or 0) if art else 0)
        w["desc_max"].setValue(float(art.desc_max) if art and art.desc_max is not None else -1)
        w["recargo_pct"].setValue(float(art.recargo_pct or 0) if art else 0)
        w["etiqueta"].setChecked(bool(art.etiqueta) if art else False)
        w["activo"].setChecked(bool(art.activo) if art else True)
        w["costo_lista"].setValue(float(art.costo_lista or 0) if art else 0)
        w["desc_costo_pct"].setValue(float(art.desc_costo_pct or 0) if art else 0)
        w["flete"].setValue(float(art.flete or 0) if art else 0)
        w["coeficiente"].setValue(float(art.coeficiente or 1) if art else 1)
        w["precio_publico"].setValue(float(art.precio_publico or 0) if art else 0)
        w["redondeo"].setChecked(bool(art.redondeo) if art else True)
        self.lbl_costo.setText(money(art.costo) if art else "0,00")
        hay_oferta = bool(art and art.oferta_precio)
        self.oferta.setChecked(hay_oferta)
        w["oferta_precio"].setValue(float(art.oferta_precio or 0) if art else 0)
        for k in ("oferta_desde", "oferta_hasta"):
            d = getattr(art, k) if art else None
            w[k].setDate(QDate(d.year, d.month, d.day) if d else QDate.currentDate())
        fc = art.fecha_costo.strftime("%d/%m/%Y") if art and art.fecha_costo else "—"
        fp = art.fecha_precio.strftime("%d/%m/%Y") if art and art.fecha_precio else "—"
        self.lbl_fechas.setText(f"Costo actualizado: {fc}    ·    Precio actualizado: {fp}")
        self._bloq = False
        self._fijar = False
        self._llenar_pestanas(art, db)

    def _llenar_pestanas(self, art, db):
        self.tab_hist.setRowCount(0); self.tab_stock.setRowCount(0)
        if not art:
            return
        db = db or get_session()
        sucs = list(db.scalars(select(m.Sucursal).order_by(m.Sucursal.codigo)))
        sal = stock.saldos_por_sucursal(db, [art.id])[art.id]
        self.tab_stock.setRowCount(len(sucs))
        for r, s in enumerate(sucs):
            self.tab_stock.setItem(r, 0, QTableWidgetItem(s.nombre))
            it = QTableWidgetItem(cant(sal.get(s.id, 0))); it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tab_stock.setItem(r, 1, it)
        hist = list(db.scalars(select(c.ArticuloPrecioHist).where(c.ArticuloPrecioHist.articulo_id == art.id)
                               .order_by(c.ArticuloPrecioHist.id.desc()).limit(50)))
        usuarios = {u.id: u.usuario for u in db.scalars(select(m.Usuario))}
        self.tab_hist.setRowCount(len(hist))
        for r, h in enumerate(hist):
            for col, v in enumerate((h.fecha.strftime("%d/%m/%Y %H:%M"), usuarios.get(h.usuario_id, ""), money(h.costo_lista),
                                     f"{float(h.coeficiente):.4f}", money(h.precio_publico), h.motivo or "")):
                self.tab_hist.setItem(r, col, QTableWidgetItem(v))
        self.tab_hist.resizeColumnsToContents()

    def _datos(self) -> dict:
        w = self.w
        d = {"codigo": w["codigo"].text(), "nombre": w["nombre"].text(), "descripcion": w["descripcion"].toPlainText(),
             "perfil": w["perfil"].currentData(), "alicuota_iva": w["alicuota_iva"].currentData(),
             "unidad": w["unidad"].text() or "UN", "kilos": w["kilos"].value() or None,
             "desc_max": None if w["desc_max"].value() < 0 else w["desc_max"].value(),
             "recargo_pct": w["recargo_pct"].value(), "etiqueta": w["etiqueta"].isChecked(), "activo": w["activo"].isChecked(),
             "costo_lista": w["costo_lista"].value(), "desc_costo_pct": w["desc_costo_pct"].value(), "flete": w["flete"].value(),
             "coeficiente": w["coeficiente"].value(), "precio_publico": w["precio_publico"].value(),
             "fijar_publico": self._fijar, "redondeo": w["redondeo"].isChecked(),
             "barras": [b for b in w["barras"].text().split(",")]}
        for k in ("rubro_id", "familia_id", "clase_id", "marca_id", "proveedor_id"):
            d[k] = w[k].currentData()
        for k in ("codigo_proveedor", "codigo_reemplazo", "ubicacion", "observaciones"):
            d[k] = w[k].text()
        if self.oferta.isChecked() and w["oferta_precio"].value() > 0:
            d["oferta_precio"] = w["oferta_precio"].value()
            d["oferta_desde"] = w["oferta_desde"].date().toPython(); d["oferta_hasta"] = w["oferta_hasta"].date().toPython()
        else:
            d["oferta_precio"] = d["oferta_desde"] = d["oferta_hasta"] = None
        return d

    def _guardar(self, otro=False):
        try:
            with get_session() as db:
                art = articulos.guardar(db, self.sesion, self._datos(), self.id_actual)
                guardado = (art.id, art.codigo)
        except NexumError as e:
            self.estado.setObjectName("error"); self.estado.setStyleSheet("color:#dc2626;font-weight:600")
            self.estado.setText(str(e))
            return False
        self.estado.setStyleSheet("color:#16a34a;font-weight:600")
        self.estado.setText(f"✓ Guardado: {guardado[1]}")
        self.buscador.refrescar()
        if otro:
            self.id_actual = None
            self._poner(None)
            self.estado.setText(f"✓ Guardado: {guardado[1]}   —   cargá el siguiente")
            self.w["codigo"].setFocus()
        else:
            self.id_actual = guardado[0]
            self._cargar(guardado[0])
            self.buscador.seleccionar_id(guardado[0])
        return True

    def _baja(self):
        if not self.id_actual:
            return
        if QMessageBox.question(self, "Artículos", "¿Dar de baja este artículo? Deja de aparecer en búsquedas y ventas.") != QMessageBox.Yes:
            return
        try:
            with get_session() as db:
                articulos.dar_de_baja(db, self.sesion, self.id_actual)
        except NexumError as e:
            QMessageBox.warning(self, "Artículos", str(e)); return
        self.buscador.refrescar(); self._nuevo()
