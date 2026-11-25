import json

from sqlalchemy import select

from nexum.core import security
from nexum.core.errores import NexumError, exigir
from nexum.db import models as m

COD = "administracion.usuarios"


def guardar(db, sesion, datos: dict, id: int | None = None) -> m.Usuario:
    exigir(sesion, COD, "modificar" if id else "crear")
    usuario = (datos.get("usuario") or "").strip()
    clave = datos.get("clave") or ""
    if not usuario:
        raise NexumError("El usuario es obligatorio")
    if not datos.get("rol_id"):
        raise NexumError("Elegí un rol")
    if (id is None or clave) and len(clave) < 6:
        raise NexumError("La clave debe tener al menos 6 caracteres")
    q = select(m.Usuario).where(m.Usuario.usuario == usuario)
    if id:
        q = q.where(m.Usuario.id != id)
    if db.scalar(q.limit(1)):
        raise NexumError(f"Ya existe el usuario «{usuario}»")
    activo = bool(datos.get("activo", True))
    if id and id == sesion.usuario_id and not activo:
        raise NexumError("No podés desactivar tu propio usuario")
    u = db.get(m.Usuario, id) if id else m.Usuario()
    u.usuario, u.nombre = usuario, (datos.get("nombre") or usuario).strip()
    u.rol_id, u.sucursal_id, u.activo = datos["rol_id"], datos.get("sucursal_id") or None, activo
    if clave:
        u.clave_hash = security.hashear(clave)
    db.add(u)
    db.add(m.Auditoria(usuario_id=sesion.usuario_id, accion="modificar" if id else "crear", entidad="usuario",
                       detalle=json.dumps({"usuario": usuario, "clave_cambiada": bool(clave)})))
    db.commit()
    return u


def cambiar_mi_clave(db, sesion, actual: str, nueva: str):
    u = db.get(m.Usuario, sesion.usuario_id)
    if not security.verificar(actual, u.clave_hash):
        raise NexumError("La clave actual no es correcta")
    if len(nueva) < 6:
        raise NexumError("La clave nueva debe tener al menos 6 caracteres")
    u.clave_hash = security.hashear(nueva)
    db.add(m.Auditoria(usuario_id=u.id, accion="cambiar_clave", entidad="usuario", detalle=u.usuario))
    db.commit()
