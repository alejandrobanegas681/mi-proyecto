"""Definición de los maestros. Agregar uno nuevo = agregar una entrada acá."""
from nexum.core.abm import Campo, DefinicionABM
from nexum.core.comprobantes import CONDICIONES_IVA
from nexum.core.validadores import validar_cuit
from nexum.db import comercial as cm, maestros as t


def _simple(modelo, titulo, codigo_menu, extra=()):
    return DefinicionABM(
        modelo=modelo, titulo=titulo, codigo_menu=codigo_menu, orden_por="nombre", unicos=("codigo",),
        campos=[
            Campo("codigo", "Código", "texto", requerido=True, largo=10),
            Campo("nombre", "Nombre", "texto", requerido=True, largo=80),
            *extra,
            Campo("activo", "Activo", "bool", en_lista=False, por_defecto=True),
        ],
    )


def _persona(modelo, titulo, codigo_menu, cond_defecto, extra=()):
    return DefinicionABM(
        modelo=modelo, titulo=titulo, codigo_menu=codigo_menu, orden_por="razon_social", unicos=("codigo",),
        campos=[
            Campo("codigo", "Código", "texto", requerido=True, largo=10),
            Campo("razon_social", "Razón social", "texto", requerido=True, largo=120),
            Campo("cuit", "CUIT", "texto", largo=13, validador=validar_cuit),
            Campo("condicion_iva", "Condición IVA", "opcion", requerido=True, opciones=CONDICIONES_IVA,
                  por_defecto=cond_defecto, en_lista=False),
            Campo("telefono", "Teléfono", "texto", largo=40),
            Campo("email", "Email", "texto", largo=120, en_lista=False),
            Campo("domicilio", "Domicilio", "texto", largo=160, en_lista=False),
            Campo("localidad_id", "Localidad", "fk", fk=(t.Localidad, "nombre"), en_lista=False),
            *extra,
            Campo("activo", "Activo", "bool", en_lista=False, por_defecto=True),
        ],
    )


DEFINICIONES = [
    _simple(t.Familia, "Familias", "stock.archivos.familias"),
    _simple(t.Rubro, "Rubros", "stock.archivos.rubros"),
    _simple(t.Clase, "Clases", "stock.archivos.clases"),
    _simple(t.Marca, "Marcas", "stock.archivos.marcas"),
    _simple(t.Zona, "Zonas", "ventas.archivos.zonas"),
    _simple(t.Provincia, "Provincias", "ventas.archivos.provincias"),
    _simple(t.CondicionPago, "Condiciones de Pago", "ventas.archivos.condiciones_de_pago",
            extra=[Campo("dias", "Días", "entero", por_defecto=0)]),
    DefinicionABM(
        modelo=t.Localidad, titulo="Localidades", codigo_menu="ventas.archivos.localidades", orden_por="nombre",
        campos=[
            Campo("provincia_id", "Provincia", "fk", requerido=True, fk=(t.Provincia, "nombre")),
            Campo("nombre", "Nombre", "texto", requerido=True, largo=80),
            Campo("codigo_postal", "Cód. postal", "texto", largo=8),
            Campo("activo", "Activo", "bool", en_lista=False, por_defecto=True),
        ],
    ),
    _persona(cm.Cliente, "Clientes", "ventas.archivos.clientes", "CF", extra=[
        Campo("descuento_pct", "Descuento %", "decimal", en_lista=False, por_defecto=0),
        Campo("limite_credito", "Límite de crédito", "decimal", en_lista=False, por_defecto=0)]),
    _persona(cm.Proveedor, "Proveedores", "compras_y_bancos.archivos.proveedores", "RI"),
]
