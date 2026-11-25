"""Login, sesión y chequeo de permisos."""
from dataclasses import dataclass, field

from sqlalchemy import select

from nexum.core import security
from nexum.db import models as m

ACCIONES = ("ver", "crear", "modificar", "anular", "imprimir")


@dataclass
class Sesion:
    usuario_id: int
    usuario: str
    nombre: str
    sucursal_id: int | None
    es_admin: bool
    permisos: dict[str, dict[str, bool]] = field(default_factory=dict)
    modulos_activos: set[str] = field(default_factory=set)

    def puede(self, codigo: str, accion: str = "ver") -> bool:
        """Un módulo desactivado bloquea todo. Un permiso en un nodo padre aplica a sus hijos."""
        if codigo.split(".")[0] not in self.modulos_activos:
            return False
        if self.es_admin:
            return True
        partes = codigo.split(".")
        for i in range(len(partes), 0, -1):
            p = self.permisos.get(".".join(partes[:i]))
            if p is not None:
                return bool(p.get(accion, False))
        return False


class LoginError(Exception):
    pass


def iniciar_sesion(db, usuario: str, clave: str) -> Sesion:
    u = db.scalar(select(m.Usuario).where(m.Usuario.usuario == usuario))
    if u is None or not u.activo or not security.verificar(clave, u.clave_hash):
        raise LoginError("Usuario o clave incorrectos")
    permisos = {
        p.codigo_menu: {a: getattr(p, a) for a in ACCIONES} for p in u.rol.permisos
    }
    activos = {mo.codigo for mo in db.scalars(select(m.ModuloActivo)) if mo.activo}
    db.add(m.Auditoria(usuario_id=u.id, accion="login", entidad="usuario", detalle=u.usuario))
    db.commit()
    return Sesion(u.id, u.usuario, u.nombre, u.sucursal_id, u.rol.es_admin, permisos, activos)
