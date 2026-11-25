from nexum.core import auth, setup
from nexum.db import base


def sistema_nuevo(provincias=False):
    base.init_engine("sqlite:///:memory:")
    base.crear_tablas()
    with base.get_session() as db:
        setup.configurar_inicial(db, empresa="Comercio Demo", cuit="20-12345678-6", condicion_iva="RI",
                                 sucursal="Casa Central", usuario="admin", nombre="Admin", clave="secreto1",
                                 cargar_provincias=provincias)
        return auth.iniciar_sesion(db, "admin", "secreto1")
