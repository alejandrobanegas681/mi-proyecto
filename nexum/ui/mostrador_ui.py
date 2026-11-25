"""Facturación de mostrador pensada para teclado y lector de barras.
Escribís o escaneás y Enter. «3*codigo» agrega 3 unidades. F12 cobra."""
from decimal import Decimal as D

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)
from sqlalchemy import select

from nexum.core import busqueda, comprobantes, precios, stock
from nexum.core.errores import NexumError
from nexum.db import comercial as c, models as m
from nexum.db.base import get_session
from nexum.ui.formato import cant, money


class SelectorArticulo(QDialog):
    """Cuando la búsqueda devuelve varios, se elige con las flechas y Enter."""
    def __init__(self, filas, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Elegí el artículo")
        self.setMinimumWidth(560)
        self.lista = QListWidget()
        for id_, codigo, nombre, precio in filas:
            it = QListWidgetItem(f"{codigo}   {nombre}   —   $ {money(precio)}")
            it.setData(Qt.UserRole, id_)
            self.lista.addItem(it)
        self.lista.setCurrentRow(0)
        self.lista.itemActivated.connect(lambda _i: self.accept())
        lay = QVBoxLayout(self); lay.addWidget(self.lista)

    def elegido(self):
        it = self.lista.currentItem()
        return it.data(Qt.UserRole) if it else None


COLS = ["Código", "Descripción", "Cant.", "Precio", "Desc. %", "Total"]


class PantallaMostrador(QWidget):
    def __init__(self, sesion):
        super().__init__()
        self.sesion, self.lineas, self._bloq, self.ultimo = sesion, [], False, None
        self.setWindowTitle("Facturación Mostrador")
        self.entrada = QLineEdit()
        self.entrada.setPlaceholderText("Código, código de barras o nombre…  (Enter)    ·    3*código para varias unidades")
        self.entrada.setStyleSheet("font-size: 13pt; padding: 7px 10px;")
        self.entrada.returnPressed.connect(self._agregar_texto)

        self.cliente = QComboBox(); self.cliente.setEditable(False); self.cliente.setMinimumWidth(260)
        self.cliente.addItem("Consumidor Final", None)
        with get_session() as db:
            for cl in db.scalars(select(c.Cliente).where(c.Cliente.activo.is_(True)).order_by(c.Cliente.razon_social).limit(500)):
                self.cliente.addItem(f"{cl.razon_social}" + (f"  ({cl.cuit})" if cl.cuit else ""), cl.id)
        self.cliente.currentIndexChanged.connect(self._actualizar_tipo)
        self.pago = QComboBox()
        for k, v in comprobantes.FORMAS_PAGO.items():
            self.pago.addItem(v, k)
        self.lbl_tipo = QLabel(""); self.lbl_tipo.setObjectName("suave")

        self.tabla = QTableWidget(0, len(COLS))
        self.tabla.setHorizontalHeaderLabels(COLS)
        self.tabla.verticalHeader().hide(); self.tabla.setAlternatingRowColors(True)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        h = self.tabla.horizontalHeader(); h.setSectionResizeMode(QHeaderView.ResizeToContents); h.setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabla.itemChanged.connect(self._editado)

        self.lbl_total = QLabel("$ 0,00"); self.lbl_total.setObjectName("total"); self.lbl_total.setAlignment(Qt.AlignRight)
        self.lbl_info = QLabel(""); self.lbl_info.setObjectName("suave")
        self.estado = QLabel("")
        self.btn_cobrar = QPushButton("Cobrar  (F12)"); self.btn_cobrar.setObjectName("primario")
        self.btn_cobrar.setMinimumHeight(44); self.btn_cobrar.clicked.connect(self._cobrar)
        self.btn_limpiar = QPushButton("Limpiar  (F9)"); self.btn_limpiar.clicked.connect(self._limpiar)
        self.btn_quitar = QPushButton("Quitar renglón  (Supr)"); self.btn_quitar.clicked.connect(self._quitar)
        self.btn_cobrar.setEnabled(sesion.puede(comprobantes.COD_MOSTRADOR, "crear"))

        top = QHBoxLayout()
        top.addWidget(QLabel("Cliente")); top.addWidget(self.cliente); top.addWidget(QLabel("Pago")); top.addWidget(self.pago)
        top.addWidget(self.lbl_tipo); top.addStretch(1)
        pie = QHBoxLayout()
        izq = QVBoxLayout(); izq.addWidget(self.lbl_info); izq.addWidget(self.estado)
        pie.addLayout(izq, 1)
        der = QVBoxLayout(); der.addWidget(self.lbl_total)
        bt = QHBoxLayout(); bt.addWidget(self.btn_quitar); bt.addWidget(self.btn_limpiar); bt.addWidget(self.btn_cobrar, 1)
        der.addLayout(bt)
        pie.addLayout(der, 2)
        lay = QVBoxLayout(self)
        lay.addLayout(top); lay.addWidget(self.entrada); lay.addWidget(self.tabla, 1); lay.addLayout(pie)
        for tecla, fn in (("F12", self._cobrar), ("F9", self._limpiar), ("Ctrl+Return", self._cobrar)):
            QShortcut(QKeySequence(tecla), self, activated=fn)
        QShortcut(QKeySequence(Qt.Key_Delete), self.tabla, activated=self._quitar)
        self.resize(980, 640)
        self._actualizar_tipo()
        self.entrada.setFocus()

    # ---------- lógica de pantalla ----------
    def _actualizar_tipo(self, *_):
        with get_session() as db:
            emp = db.scalars(select(m.Empresa)).first()
            cid = self.cliente.currentData()
            cl = db.get(c.Cliente, cid) if cid else None
            tipo = comprobantes.tipo_para(emp.condicion_iva, cl.condicion_iva if cl else "CF")
        self.lbl_tipo.setText(f"Se emite: {comprobantes.TIPOS[tipo]}")

    def _agregar_texto(self):
        cantidad, texto = comprobantes.parsear_cantidad_codigo(self.entrada.text())
        if not texto:
            return
        with get_session() as db:
            art = busqueda.buscar_exacto(db, texto)
            if art is None:
                res = busqueda.buscar_articulos(db, texto, 30)
                if not res:
                    self._msg(f"No se encontró «{texto}»", error=True); self.entrada.selectAll(); return
                if len(res) == 1:
                    art = res[0]
                else:
                    dlg = SelectorArticulo([(a.id, a.codigo, a.nombre, precios.precio_vigente(a)) for a in res], self)
                    if dlg.exec() != QDialog.Accepted or not dlg.elegido():
                        return
                    art = db.get(c.Articulo, dlg.elegido())
            if art.perfil == "C":
                self._msg(f"«{art.nombre}» es solo de compra", error=True); return
            sucursal = self.sesion.sucursal_id or db.scalars(select(m.Sucursal)).first().id
            disponible = stock.saldo(db, art.id, sucursal)
            datos = dict(articulo_id=art.id, codigo=art.codigo, nombre=art.nombre, precio=precios.precio_vigente(art),
                         alicuota=art.alicuota_iva, disponible=disponible, en_oferta=precios.en_oferta(art))
        self._sumar(datos, cantidad)
        self.entrada.clear()

    def _sumar(self, datos, cantidad):
        for ln in self.lineas:
            if ln["articulo_id"] == datos["articulo_id"] and ln["desc"] == 0:
                ln["cantidad"] += cantidad
                self._redibujar(); self._avisar_stock(ln); return
        ln = dict(datos, cantidad=cantidad, desc=D(0))
        self.lineas.append(ln)
        self._redibujar(); self._avisar_stock(ln)
        self.tabla.selectRow(len(self.lineas) - 1)

    def _avisar_stock(self, ln):
        if ln["cantidad"] > ln["disponible"]:
            self._msg(f"Atención: stock {cant(ln['disponible'])} de «{ln['nombre']}» (se piden {cant(ln['cantidad'])})", error=True)
        else:
            self._msg(f"{ln['nombre']}" + ("  — EN OFERTA" if ln["en_oferta"] else ""))

    def _redibujar(self):
        self._bloq = True
        self.tabla.setRowCount(len(self.lineas))
        total = D(0)
        for r, ln in enumerate(self.lineas):
            _, _, tot = comprobantes.calcular_linea(ln["cantidad"], ln["precio"], ln["desc"], ln["alicuota"])
            total += tot
            vals = [ln["codigo"], ln["nombre"], cant(ln["cantidad"]), money(ln["precio"]), cant(ln["desc"]), money(tot)]
            for col, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if col >= 2:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if col not in (2, 4):
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.tabla.setItem(r, col, it)
        self.lbl_total.setText(f"$ {money(total)}")
        self.lbl_info.setText(f"{len(self.lineas)} renglón(es)")
        self._bloq = False

    def _editado(self, item):
        if self._bloq or item.column() not in (2, 4):
            return
        ln = self.lineas[item.row()]
        try:
            v = D(item.text().replace(",", "."))
            if item.column() == 2:
                if v <= 0:
                    raise ValueError
                ln["cantidad"] = v
            else:
                if v < 0 or v > 100:
                    raise ValueError
                ln["desc"] = v
        except Exception:
            self._msg("Valor inválido", error=True)
        self._redibujar()
        if item.column() == 2:
            self._avisar_stock(ln)

    def _quitar(self):
        fila = self.tabla.currentRow()
        if 0 <= fila < len(self.lineas):
            del self.lineas[fila]
            self._redibujar()
        self.entrada.setFocus()

    def _limpiar(self):
        self.lineas.clear(); self._redibujar(); self.entrada.clear(); self.entrada.setFocus()

    def _msg(self, texto, error=False):
        self.estado.setStyleSheet("color:#dc2626;font-weight:600" if error else "color:#6b7280")
        self.estado.setText(texto)

    def _cobrar(self):
        if not self.lineas:
            self._msg("Agregá al menos un artículo", error=True); return
        payload = [{"articulo_id": l["articulo_id"], "cantidad": l["cantidad"], "precio_unit": l["precio"],
                    "desc_pct": l["desc"]} for l in self.lineas]
        try:
            with get_session() as db:
                comp = comprobantes.emitir(db, self.sesion, payload, cliente_id=self.cliente.currentData(),
                                           forma_pago=self.pago.currentData())
                self.ultimo = (comp.id, comp.numero_completo, comp.total)
        except NexumError as e:
            self._msg(str(e), error=True); return
        self.lineas.clear(); self._redibujar()
        self.estado.setStyleSheet("color:#16a34a;font-weight:700;font-size:12pt")
        self.estado.setText(f"✓ {self.ultimo[1]}  —  $ {money(self.ultimo[2])}")
        self.entrada.setFocus()
