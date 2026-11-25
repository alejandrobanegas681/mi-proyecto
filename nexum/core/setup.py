"""Primera puesta en marcha. NEXUM arranca vacío: lo único que se crea es lo que el usuario indica."""
from sqlalchemy import select

from nexum.core import menu, params, security
from nexum.core.errores import NexumError
from nexum.core.validadores import validar_cuit
from nexum.db import comercial as c, maestros as t, models as m

PROVINCIAS = [
    ("A", "Salta"), ("B", "Buenos Aires"), ("C", "Ciudad Autónoma de Buenos Aires"), ("D", "San Luis"),
    ("E", "Entre Ríos"), ("F", "La Rioja"), ("G", "Santiago del Estero"), ("H", "Chaco"),
    ("J", "San Juan"), ("K", "Catamarca"), ("L", "La Pampa"), ("M", "Mendoza"), ("N", "Misiones"),
    ("P", "Formosa"), ("Q", "Neuquén"), ("R", "Río Negro"), ("S", "Santa Fe"), ("T", "Tucumán"),
    ("U", "Chubut"), ("V", "Tierra del Fuego"), ("W", "Corrientes"), ("X", "Córdoba"),
    ("Y", "Jujuy"), ("Z", "Santa Cruz"),
]

# Roles iniciales: {código de menú: acciones permitidas}
_ROLES = {
    "Vendedor": {
        "ventas.facturacion": ("ver", "crear", "imprimir"),
        "ventas.archivos.clientes": ("ver", "crear", "modificar"),
        "ventas.movimientos.consulta_de_comprobantes": ("ver", "imprimir"),
        "stock.archivos.articulos": ("ver",),
        "stock.consultas_de_stock": ("ver",),
        "stock.consultas_por_articulo": ("ver",),
    },
    "Depósito": {
        "stock": ("ver", "crear", "modificar", "imprimir"),
        "compras_y_bancos.archivos.proveedores": ("ver",),
    },
}


def necesita_configuracion(db) -> bool:
    return db.scalar(select(m.Usuario).limit(1)) is None


def configurar_inicial(db, *, empresa: str, cuit: str | None, condicion_iva: str, sucursal: str,
                       usuario: str, nombre: str, clave: str, cargar_provincias: bool = False):
    if not necesita_configuracion(db):
        raise NexumError("El sistema ya fue configurado")
    if not empresa.strip() or not sucursal.strip() or not usuario.strip():
        raise NexumError("Completá empresa, sucursal y usuario")
    if cuit and (err := validar_cuit(cuit)):
        raise NexumError(err)
    if len(clave) < 6:
        raise NexumError("La clave debe tener al menos 6 caracteres")

    emp = m.Empresa(nombre=empresa.strip(), cuit=(cuit or None), condicion_iva=condicion_iva)
    db.add(emp)
    db.flush()
    suc = m.Sucursal(empresa_id=emp.id, codigo="001", nombre=sucursal.strip())
    admin = m.Rol(nombre="Administrador", es_admin=True)
    db.add_all([suc, admin])
    for nombre_rol, permisos in _ROLES.items():
        rol = m.Rol(nombre=nombre_rol)
        for cod, acciones in permisos.items():
            rol.permisos.append(m.Permiso(codigo_menu=cod, **{a: True for a in acciones}))
        db.add(rol)
    db.flush()
    db.add(m.Usuario(usuario=usuario.strip(), nombre=nombre.strip() or usuario.strip(),
                     clave_hash=security.hashear(clave), rol_id=admin.id, sucursal_id=suc.id))
    for cod in menu.codigos_modulos(menu.parsear()):
        db.add(m.ModuloActivo(codigo=cod, activo=True))
    for tipo in ("FA", "FB", "FC", "FX"):
        db.add(c.Talonario(sucursal_id=suc.id, punto_venta=1, tipo=tipo))
    params.poner(db, "stock_negativo", "si")
    params.poner(db, "redondeo_paso", "1")
    if cargar_provincias:
        db.add_all([t.Provincia(codigo=cod, nombre=n) for cod, n in PROVINCIAS])
    db.commit()
    return emp
