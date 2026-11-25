"""Árbol de menú de NEXUM. Se define como texto indentado (2 espacios por nivel)
y cada nodo recibe un código único (ej. 'stock.archivos.articulos') que se usa
para permisos, módulos activables y para registrar pantallas."""
import re
import unicodedata
from dataclasses import dataclass, field

MENU_TEXT = """
Ventas
  Archivos
    Clientes
    Sucursales
    Vendedores
    Gravámenes
    Impuestos
    Listas de Precios
    Retenciones y Percepciones
    Condiciones de Pago
    Estados de Cuenta Corriente
    Condiciones de IVA
    Tarjetas
    Controladores Fiscales
    Zonas
    Tablas de Descuentos
    Provincias
    Localidades
    Clases de Clientes
    Grupos de Clientes
  Facturación
    Facturación Mostrador
  Movimientos
    Consulta de Comprobantes
    Tickets
    Control de Zetas
    Consultas de Presupuestos
    Vales al Personal
    Precios Especiales por Cliente
    Pedidos a Casa Central
    Cuentas Corrientes
      Saldo Inicial
      Consultas de Cuentas Corrientes
      Recibos
      Recibos por Grupos
      Pagos Anticipados
      Informes
        Ficha
        Saldos Generales
        Detalle de Saldos
        Remitos sin Facturar
        Control de Remitos
    Tarjetas de Crédito
      Saldo Inicial
      Consultas de Tarjetas
      Liquidación de Tarjetas
      Informe de Saldos
      Control de Ventas con Tarjeta
    Precios
      Actualización de Precios
      Actualización Global
      Consultas de Precios
      Informe de Listas de Precios
      Etiquetas de Precios
  Informes
    Por Artículo
      Ventas Totales
      Rentabilidad
      Ventas y Compras
      Estadística
      Totales por Proveedor
      Totales por Vendedor
    Por Cliente
      Comprobantes Emitidos
      Estadísticas
      Por Provincia
      Reparticiones Gobierno
      Ventas por Artículo
      Facturas Vencidas
    IVA Ventas
    Comprobantes por Tasa
    Retenciones y Percepciones
    Control de Tickets
    Resumen General
    Cierres
    Ventas por Vendedor
    Informe de Presupuestos
    Informe de Pedidos
    Comprobantes por Forma de Pago
    Resultados de Caja
    Movimiento Interno Valorizado
    Informe Parte Diario
    Informe de Cobranzas
    Informe de Recibos de Cuenta Corriente
Tesorería
  Archivos
    Cajas Chicas
  Caja
    Inicial de Caja
    Consultas de Caja
    Cierre de Caja Sucursal
    Sueldos y Anticipos
    Transferencias de Caja
    Caja Chica
    Movimientos de Caja
    Cierre de Caja General
    Parte Diario de P.V.
Stock
  Archivos
    Artículos
    Familias
    Rubros
    Clases
    Marcas
    Combos de Artículos
    Ofertas de Artículos
  Movimientos
    Inicial
    Fraccionamiento
    Remitos a Sucursales
    Recalcular Stock
    Recepción de Stock
  Inventario
  Consultas por Artículo
  Consultas de Stock
  Control de Reposición
  Control de Reposición por Rubro
  Informes
    Existencias
    Ficha de Stock
    Movimiento Diario
    Valorización de Stock
    Valorización de Inventario
    Reposición de Stock
    Resumen
    Movimiento Interno
    Reposición por Venta
    Etiquetas de Código de Barras
  Informe de Márgenes y Rentabilidad
Compras y Bancos
  Archivos
    Proveedores
    Imputaciones
    Retenciones y Percepciones
    Cuentas Bancarias
    Tipos de Compra
  Movimientos
    Inicial de Proveedores
    Consulta de Compras
    Consultas de Proveedores
    Cheques en Cartera
    Histórico de Cheques
    Órdenes de Compra
    Consulta de Órdenes de Compra
    Órdenes de Pago
    Consulta de Órdenes de Pago
    Compras y Gastos
    Gastos Caja Chica
    Depósitos Bancarios
    Débitos Bancarios
    Consultas de Movimientos Bancarios
    Transferencias Bancarias
  Informes
    Proveedores Cuenta Corriente
    Por Artículo
    Compras por Imputación
    IVA Compras
    Libro Bancos
    Vencimientos de Cheques
    Informe de Cheques
    Informe de Órdenes de Compra
    Informe de Gastos Internos
Administración
  Personal
    ABM Personal
    Informe de Horas Trabajadas
    Carga de Inasistencias
    Feriados Laborales
    Informe de Anticipos de Sueldo
  Usuarios
  Parámetros
  Anular Comprobantes
  Talonarios
  Cambio de Claves de Vendedor
  Recalcular Cuentas de Clientes
  Recalcular Cuentas de Proveedores
  Módulos
Contabilidad
  Archivos
    Plan de Cuentas
    Ejercicios Contables
    Centros de Costo
    Coeficientes por Inflación
  Movimientos
    Asientos General
    Subdiario de Compras
    Subdiario Compras a General
    Subdiario de Ventas
    Generar Asientos de Venta
    Subdiario Ventas a General
    Subdiario de Tesorería
    Subdiario Tesorería a General
    Ajuste por Inflación
    Refundición de Resultados
  Informes
    Plan de Cuentas
    Libro Subdiario de Compras
    Libro Mayor de Compras
    Libro Mayor
    Libro Diario
    Balance de Sumas y Saldos
    Informe de Asientos
"""


@dataclass
class NodoMenu:
    etiqueta: str
    codigo: str
    hijos: list["NodoMenu"] = field(default_factory=list)

    @property
    def es_hoja(self) -> bool:
        return not self.hijos

    @property
    def modulo(self) -> str:
        return self.codigo.split(".")[0]


def _slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")


def parsear(texto: str = MENU_TEXT) -> list[NodoMenu]:
    raiz: list[NodoMenu] = []
    pila: list[NodoMenu] = []
    for linea in texto.splitlines():
        if not linea.strip():
            continue
        nivel = (len(linea) - len(linea.lstrip(" "))) // 2
        etiqueta = linea.strip()
        pila = pila[:nivel]
        padre = pila[-1] if pila else None
        codigo = f"{padre.codigo}.{_slug(etiqueta)}" if padre else _slug(etiqueta)
        nodo = NodoMenu(etiqueta, codigo)
        (padre.hijos if padre else raiz).append(nodo)
        pila.append(nodo)
    return raiz


def codigos_modulos(arbol: list[NodoMenu]) -> list[str]:
    return [n.codigo for n in arbol]
